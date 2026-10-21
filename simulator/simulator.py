"""
MDRP Discrete-Event Simulation Engine (SimPy) -- adapted specifically to
grubhub/mdrplib instances: planar meters coordinates, a minute-based clock,
a single instance-wide travel speed (meters_per_minute), and the two
click-to-door SLAs each order carries (target = soft, maximum = hard).

Architecture: each entity (User, Courier, Dispatcher) is an autonomous
actor owning its own SimPy process, following the actor/DES pattern of the
thesis simulator this package is adapted from. Behavioural extensions
beyond the official MDRP benchmark (cancellation hazard model, stochastic
acceptance, repositioning) are preserved but OFF by default -- see
config.py -- so a default run matches mdrplib's own assumptions: every
order is eventually routed, and an assigned route is always executed.

Events:
  OrderArrival          -> order enters the pending pool at placement_time
  RollingHorizonTrigger -> policy.assign() is called every rolling_horizon minutes
  AcceptanceRealisation -> Bernoulli draw per (courier, route) pair
  PickUp / Delivery     -> courier collects / drops off a bundle's orders,
                           with the instance's own pickup/dropoff service time
  Cancellation          -> optional two-threshold hazard (off by default)
  CourierLogin/Logout   -> courier availability changes, H_t updated
  Repositioning         -> optional idle-courier repositioning (off by default)
"""
from __future__ import annotations

import math
import random
import logging
import time
from typing import Dict, List, Any, Optional

import simpy

from config import Config
from models import Order, Courier, Location
from distance import travel_time_min, dist_km, speed_of
from policies import Policy

logger = logging.getLogger(__name__)


# -- Actor base ------------------------------------------------------------------

class Actor:
    def __init__(self, env: simpy.Environment):
        self.env = env

    def _log(self, msg: str):
        logger.debug(f't={self.env.now:.1f}min: [{self.__class__.__name__}] {msg}')


# -- User actor (one per order) --------------------------------------------------

class UserActor(Actor):
    """
    OrderArrival -> (optional) two-threshold hazard cancellation.

    Cancellation is OFF by default (cfg.enable_cancellation = False),
    matching mdrplib's own assumption that every order is eventually
    routed -- the official evaluator has no notion of a dropped order.
    Enable it to study the thesis's own stochastic-customer extension.
    """

    def __init__(self, env: simpy.Environment, order: Order,
                dispatcher: 'Dispatcher', cfg: Config):
        super().__init__(env)
        self.order = order
        self.dispatcher = dispatcher
        self.cfg = cfg

    def start(self):
        self.env.process(self._run())

    def _run(self):
        yield self.env.timeout(self.order.placement_time)
        self.dispatcher.order_submitted_event(self.order)
        self._log(f'Order {self.order.order_id} placed')

        if not self.cfg.enable_cancellation:
            return

        cfg = self.cfg
        t1_abs = self.order.placement_time + cfg.cancel_t1_min
        wait_to_t1 = max(0.0, t1_abs - self.env.now)
        if wait_to_t1 > 0:
            yield self.env.timeout(wait_to_t1)

        if not self.dispatcher.is_pending(self.order.order_id):
            return  # assigned before T1

        t2_abs = self.order.placement_time + cfg.cancel_t2_min
        patience = -math.log(random.random()) / cfg.cancel_lambda_per_min
        cancel_at = min(t1_abs + patience, t2_abs)

        yield self.env.timeout(max(0.0, cancel_at - self.env.now))

        if self.dispatcher.is_pending(self.order.order_id):
            reason = 'customer' if cancel_at < t2_abs else 'platform'
            self.dispatcher.cancel_order_event(self.order, reason)


# -- Courier actor (one per courier) --------------------------------------------

class CourierActor(Actor):
    """
    Owns the courier's own state machine as an independent process:
    idle -> moving -> picking_up -> delivering -> idle
    (+ repositioning, notified).
    """

    def __init__(self, env: simpy.Environment, courier: Courier,
                dispatcher: 'Dispatcher', cfg: Config):
        super().__init__(env)
        self.courier = courier
        self.dispatcher = dispatcher
        self.cfg = cfg
        self._idle_proc: Optional[simpy.Process] = None

    def start(self):
        self.env.process(self._login())

    def _login(self):
        yield self.env.timeout(self.courier.on_time)
        self.courier.condition = 'idle'
        self._schedule_log_off_event()
        self.dispatcher.courier_idle_event(self)
        self._log(f'Courier {self.courier.courier_id} logged on')
        self._enter_idle()

    # -- Idle / autonomous repositioning -----------------------------------------

    def _enter_idle(self):
        self._idle_proc = self.env.process(self._idle_loop())

    def _idle_loop(self):
        try:
            if self.cfg.enable_repositioning:
                while True:
                    yield self.env.timeout(self.cfg.reposition_check_interval_min)
                    yield self.env.process(self._evaluate_movement_event())
            else:
                yield self.env.event()
        except simpy.Interrupt:
            pass  # notified, or logged off -- caller takes over

    def _evaluate_movement_event(self):
        target = self.dispatcher.reposition_target()
        if target is None:
            return
        d_km = dist_km(self.courier.location, target)
        if d_km < 0.3:
            return

        self.courier.condition = 'repositioning'
        self.dispatcher.courier_repositioning_event(self)
        tt = travel_time_min(self.courier.location, target, speed_of(self.courier, self.cfg)) \
             / self.cfg.reposition_speed_factor
        t0 = self.env.now
        yield self.env.timeout(tt)

        self.courier.history.active_time += (self.env.now - t0)
        self.courier.history.dist_traveled += d_km
        self.courier.location = target.copy()
        self.courier.condition = 'idle'
        self.dispatcher.courier_idle_event(self)
        self._log(f'Courier {self.courier.courier_id} repositioned ({d_km:.1f} km)')

    # -- Notification -> accept/reject decision ----------------------------------

    def notification_event(self, order_ids: List[int], pay_offer: float):
        if self.courier.condition in ('idle', 'repositioning'):
            if self._idle_proc is not None and self._idle_proc.is_alive:
                self._idle_proc.interrupt()

        self.courier.condition = 'notified'
        self.dispatcher.courier_notified_event(self)
        self.env.process(self._decide(order_ids, pay_offer))

    def _decide(self, order_ids: List[int], pay_offer: float):
        delay = max(0.05, random.gauss(self.cfg.decision_mean_min, self.cfg.decision_std_min))
        yield self.env.timeout(delay)

        if self.courier.condition != 'notified':
            return  # logged off during the delay

        orders = self.dispatcher.resolve_pending(order_ids, self.courier.courier_id)
        if not orders:
            self.courier.condition = 'idle'
            self.dispatcher.courier_idle_event(self)
            self._after_decision()
            return

        mini_state = {
            'L_t':  {self.courier.courier_id: self.courier},
            'O_t':  {o.order_id: o for o in orders},
            'H_t':  {self.courier.courier_id: self.courier.history},
            'time': self.env.now,
        }
        p = self.dispatcher.policy.acceptance_prob(self.courier, orders, pay_offer, mini_state)

        if random.random() < p:
            self.dispatcher.accept_event(self, orders, pay_offer)
            self.env.process(self._execute_route(orders))
        else:
            self.dispatcher.reject_event(self.courier, orders, pay_offer, p, delay)
            self.courier.condition = 'idle'
            self.dispatcher.courier_idle_event(self)
            self._after_decision()

    def _after_decision(self):
        if self.courier.log_off_scheduled:
            self._do_log_off()
        else:
            self._enter_idle()

    # -- Route execution ------------------------------------------------------------

    def _execute_route(self, orders: List[Order]):
        """
        PickUp + Delivery. Single-restaurant route: travel to the store once,
        wait until every order in the bundle is ready, spend
        cfg.pickup_service_min handling the pickup (once per stop at the
        restaurant, matching the official evaluator's own bookkeeping), then
        deliver each order in sequence with cfg.dropoff_service_min at each
        stop.
        """
        store_loc = orders[0].store_loc
        km_to_store = dist_km(self.courier.location, store_loc)

        yield self.env.process(self._move(store_loc))

        self.courier.condition = 'picking_up'
        self.dispatcher.courier_picking_up_event(self)

        ready_ok = max(o.ready_time for o in orders)
        wait = max(0.0, ready_ok - self.env.now)
        if wait > 0:
            yield self.env.timeout(wait)

        yield self.env.timeout(self.cfg.pickup_service_min)
        pickup_t = self.env.now
        for o in orders:
            o.picked_up_at = pickup_t

        for o in orders:
            km_to_user = dist_km(self.courier.location, o.user_loc)
            yield self.env.process(self._move(o.user_loc))

            self.courier.condition = 'delivering'
            yield self.env.timeout(self.cfg.dropoff_service_min)

            delivery_t = self.env.now
            o.delivered_at = delivery_t
            self.courier.history.orders_delivered += 1
            self.dispatcher.deliver_order_event(o)

            c2d = delivery_t - o.placement_time
            self.dispatcher.delivery_log.append({
                'courier_id':          self.courier.courier_id,
                'order_id':            o.order_id,
                'bundle_size':         len(orders),
                'assignment_time_min': round(o.assigned_at, 2),
                'pickup_time_min':     round(pickup_t, 2),
                'delivery_time_min':   round(delivery_t, 2),
                'pay':                 round(o.pay_received, 2),
                'km_to_store':         round(km_to_store, 3),
                'km_to_user':          round(km_to_user, 3),
                'total_km':            round(km_to_store + km_to_user, 3),
                'route_time_min':      round(delivery_t - o.assigned_at, 2),
                'c2d_min':             round(c2d, 2),
                'ready_to_door_min':   round(o.ready_to_door, 2) if o.ready_to_door is not None else None,
                'ready_to_pickup_min': round(o.ready_to_pickup, 2) if o.ready_to_pickup is not None else None,
                'overage_min':         round(max(0.0, c2d - o.target_click_to_door), 2),
                'store_x': o.store_loc.x, 'store_y': o.store_loc.y,
                'user_x':  o.user_loc.x,  'user_y':  o.user_loc.y,
            })
            self._log(
                f'Order {o.order_id} delivered by courier {self.courier.courier_id} '
                f'({km_to_store+km_to_user:.1f} km, c2d={c2d:.0f}min)'
            )

        self.courier.condition = 'idle'
        self.dispatcher.courier_idle_event(self)
        self._after_decision()

    def _move(self, dest: Location):
        d = dist_km(self.courier.location, dest)
        tt = travel_time_min(self.courier.location, dest, speed_of(self.courier, self.cfg))

        self.courier.condition = 'moving'
        t0 = self.env.now
        yield self.env.timeout(tt)

        self.courier.history.active_time += (self.env.now - t0)
        self.courier.history.dist_traveled += d
        self.courier.location = dest.copy()

    # -- Log off ---------------------------------------------------------------------

    def _schedule_log_off_event(self):
        self.env.process(self._log_off_timer())

    def _log_off_timer(self):
        yield self.env.timeout(self.courier.off_time - self.courier.on_time)
        self.log_off_event()

    def log_off_event(self):
        if self.courier.condition == 'idle':
            if self._idle_proc is not None and self._idle_proc.is_alive:
                self._idle_proc.interrupt()
            self._do_log_off()
        else:
            self.courier.log_off_scheduled = True
            self._log(f'Courier {self.courier.courier_id} log-off deferred')

    def _do_log_off(self):
        self.courier.condition = 'logged_off'
        self.dispatcher.courier_log_off_event(self)
        self._log(f'Courier {self.courier.courier_id} logged off')


# -- Dispatcher (singleton) ------------------------------------------------------

class Dispatcher(Actor):
    def __init__(self, env: simpy.Environment, policy: Policy, cfg: Config):
        super().__init__(env)
        self.policy = policy
        self.cfg = cfg

        self.pending_orders:   Dict[int, Order] = {}
        self.assigned_orders:  Dict[int, Order] = {}
        self.delivered_orders: Dict[int, Order] = {}
        self.canceled_orders:  Dict[int, Order] = {}

        self.all_couriers:  Dict[int, CourierActor] = {}
        self.idle_couriers: Dict[int, CourierActor] = {}

        self.delivery_log:     List[Dict[str, Any]] = []
        self.cancellation_log: List[Dict[str, Any]] = []
        self.rejection_log:    List[Dict[str, Any]] = []
        self.state_snapshots:  List[Dict[str, Any]] = []
        # One entry per accepted assignment (bundle or singleton) -- matches
        # the official evaluator's own "orders_per_bundle" list exactly.
        self.bundle_sizes: List[int] = []
        # Wall-clock (real) seconds spent inside policy.assign() per dispatch
        # round -- one entry per round that actually had something to decide.
        # The simulated clock (cfg.rolling_horizon, 2 min by default) and this
        # real-world duration are otherwise completely decoupled: SimPy's
        # virtual clock advances regardless of how long assign() actually
        # takes to run, so nothing here is "charged" against the 2-minute
        # window on its own. Comparing solve_max (metrics.py) against that
        # window in real seconds is how you check whether a given policy
        # could plausibly be re-run that often in an actual live dispatch
        # system, not something the simulation enforces by construction.
        self.dispatch_times: List[float] = []

    def start(self):
        self.env.process(self._rolling_horizon_loop())
        self.env.process(self._snapshot_loop())

    # -- Rolling horizon / matching ----------------------------------------------

    def _rolling_horizon_loop(self):
        while True:
            yield self.env.timeout(self.cfg.rolling_horizon)
            self._dispatch_event()

    def _dispatch_event(self):
        available = {
            cid: ca.courier
            for cid, ca in self.all_couriers.items()
            if cid in self.idle_couriers
        }
        if not available or not self.pending_orders:
            return

        state = {
            'L_t':  available,
            'O_t':  dict(self.pending_orders),
            'H_t':  {cid: c.history for cid, c in available.items()},
            # every courier currently logged on (idle or busy): fairness policies that
            # evaluate the Gini over the whole fleet (MIP-Fair, mipfair_scope=all) read this
            'H_all': {cid: ca.courier.history for cid, ca in self.all_couriers.items()
                      if ca.courier.condition not in ('offline', 'logged_off')},
            # the courier objects behind H_all (on_time / off_time for the exposure basis and the
            # eligible population of the second-generation policies, fair_history.py)
            'C_all': {cid: ca.courier for cid, ca in self.all_couriers.items()
                      if ca.courier.condition not in ('offline', 'logged_off')},
            'time': self.env.now,
        }

        t0 = time.perf_counter()
        assignments = self.policy.assign(state)
        self.dispatch_times.append(time.perf_counter() - t0)

        for courier_id, order_ids, pay_offer in assignments:
            courier_actor = self.idle_couriers.get(courier_id)
            if courier_actor is None:
                continue

            valid_ids = [
                oid for oid in order_ids
                if oid in self.pending_orders
                and courier_id not in self.pending_orders[oid].rejected_by
            ]
            if not valid_ids:
                continue

            courier_actor.notification_event(valid_ids, pay_offer)

    def resolve_pending(self, order_ids: List[int], courier_id: int) -> List[Order]:
        return [self.pending_orders[oid] for oid in order_ids if oid in self.pending_orders]

    def accept_event(self, courier_actor: CourierActor, orders: List[Order], pay_offer: float):
        for o in orders:
            o.assigned_at = self.env.now
            o.assigned_courier = courier_actor.courier.courier_id
            o.pay_received = pay_offer / max(1, len(orders))
            self.assigned_orders[o.order_id] = o
            self.pending_orders.pop(o.order_id, None)

        self.bundle_sizes.append(len(orders))
        courier_actor.courier.condition = 'busy'
        courier_actor.courier.history.earnings += pay_offer

    def reject_event(self, courier: Courier, orders: List[Order], pay_offer: float,
                     p: float, delay: float):
        for o in orders:
            o.rejected_by.add(courier.courier_id)
            total_dist = (dist_km(courier.location, o.store_loc)
                         + dist_km(o.store_loc, o.user_loc))
            self.rejection_log.append({
                'time_min':          round(self.env.now, 2),
                'courier_id':        courier.courier_id,
                'order_id':          o.order_id,
                'pay_offer':         round(pay_offer / max(1, len(orders)), 2),
                'dist_km':           round(total_dist, 3),
                'courier_active_h':  round(courier.history.active_time / 60.0, 3),
                'acceptance_prob':   round(p, 4),
                'n_prev_rejections': len(o.rejected_by) - 1,
            })

    def deliver_order_event(self, order: Order):
        self.delivered_orders[order.order_id] = order
        self.assigned_orders.pop(order.order_id, None)

    # -- Order lifecycle (called by UserActor) -----------------------------------

    def is_pending(self, order_id: int) -> bool:
        return order_id in self.pending_orders

    def order_submitted_event(self, order: Order):
        self.pending_orders[order.order_id] = order

    def cancel_order_event(self, order: Order, reason: str):
        order.canceled_at = self.env.now
        self.canceled_orders[order.order_id] = order
        self.pending_orders.pop(order.order_id, None)

        self.cancellation_log.append({
            'order_id':      order.order_id,
            'placement_min': round(order.placement_time, 2),
            'canceled_min':  round(self.env.now, 2),
            'wait_min':      round(self.env.now - order.placement_time, 2),
            'reason':        reason,
            'n_rejections':  len(order.rejected_by),
        })

    # -- Courier pool transitions (called by CourierActor) -----------------------

    def courier_idle_event(self, courier_actor: CourierActor):
        self.all_couriers[courier_actor.courier.courier_id] = courier_actor
        self.idle_couriers[courier_actor.courier.courier_id] = courier_actor

    def courier_repositioning_event(self, courier_actor: CourierActor):
        self.idle_couriers.pop(courier_actor.courier.courier_id, None)

    def courier_notified_event(self, courier_actor: CourierActor):
        self.idle_couriers.pop(courier_actor.courier.courier_id, None)

    def courier_picking_up_event(self, courier_actor: CourierActor):
        self.idle_couriers.pop(courier_actor.courier.courier_id, None)

    def courier_log_off_event(self, courier_actor: CourierActor):
        self.idle_couriers.pop(courier_actor.courier.courier_id, None)

    # -- Repositioning target -----------------------------------------------------

    def reposition_target(self) -> Optional[Location]:
        """Centroid of up to 20 pending orders' store locations."""
        pending = list(self.pending_orders.values())
        if not pending:
            return None
        sample = pending[:20]
        x = sum(o.store_loc.x for o in sample) / len(sample)
        y = sum(o.store_loc.y for o in sample) / len(sample)
        return Location(x=x, y=y)

    # -- State snapshots ------------------------------------------------------------

    def _snapshot_loop(self):
        while True:
            yield self.env.timeout(self.cfg.snapshot_interval_min)
            counts: Dict[str, int] = {}
            online = [ca for ca in self.all_couriers.values()
                     if ca.courier.condition != 'logged_off']
            for ca in online:
                counts[ca.courier.condition] = counts.get(ca.courier.condition, 0) + 1
            self.state_snapshots.append({
                'time_min':        round(self.env.now, 1),
                'online':          len(online),
                'idle':            counts.get('idle',          0),
                'notified':        counts.get('notified',      0),
                'moving':          counts.get('moving',        0),
                'picking_up':      counts.get('picking_up',    0),
                'delivering':      counts.get('delivering',    0),
                'repositioning':   counts.get('repositioning', 0),
                'pending_orders':  len(self.pending_orders),
                'assigned_orders': len(self.assigned_orders),
            })

    # -- Results assembly -------------------------------------------------------------

    def get_results(self) -> Dict[str, Any]:
        all_orders = {
            **self.delivered_orders,
            **self.canceled_orders,
            **self.pending_orders,
            **self.assigned_orders,
        }
        all_couriers = {
            cid: ca.courier
            for cid, ca in self.all_couriers.items()
            if ca.courier.condition != 'offline'
        }
        return {
            'orders':           all_orders,
            'couriers':         all_couriers,
            'delivery_log':     self.delivery_log,
            'cancellation_log': self.cancellation_log,
            'rejection_log':    self.rejection_log,
            'state_snapshots':  self.state_snapshots,
            'bundle_sizes':     self.bundle_sizes,
            'dispatch_times':   self.dispatch_times,
            'sim_time':         self.env.now,
        }


# -- World (thin orchestrator) ---------------------------------------------------

class World:
    def __init__(self, env: simpy.Environment, instance: Dict[str, Any],
                policy: Policy, cfg: Config):
        self.env = env
        self.instance = instance
        self.cfg = cfg
        self.dispatcher = Dispatcher(env, policy, cfg)

    def start(self):
        # Seed the GLOBAL random module here, once, before any actor runs.
        # UserActor's cancellation hazard and CourierActor's decision delay
        # (below) both draw from the global `random` module rather than a
        # per-instance Random(cfg.seed) -- without this, two runs of the
        # exact same instance/policy/cfg.seed could still produce different
        # decision-delay timing from process to process, since the global
        # module is otherwise seeded from OS entropy at interpreter start.
        # That non-determinism is not just a reproducibility concern: it can
        # shift exactly which dispatch round ends up with a large backlog of
        # pending orders/couriers, which for the ILP controls how big that
        # round's candidate-route set is -- i.e. it affects not only WHAT a
        # run decides but HOW LONG a given round takes to solve.
        random.seed(self.cfg.seed)
        self.dispatcher.start()
        for order in self.instance['orders']:
            UserActor(self.env, order, self.dispatcher, self.cfg).start()
        for courier in self.instance['couriers']:
            CourierActor(self.env, courier, self.dispatcher, self.cfg).start()

    def get_results(self) -> Dict[str, Any]:
        return self.dispatcher.get_results()


# -- Backward-compatible facade ---------------------------------------------------

class MDRPSimulator:
    """
        sim = MDRPSimulator(env, instance, policy, cfg)
        sim.start()
        env.run(until=cfg.sim_end)
        results = sim.get_results()
    """

    def __init__(self, env: simpy.Environment, instance: Dict[str, Any],
                policy: Policy, cfg: Config):
        self.world = World(env, instance, policy, cfg)

    def start(self):
        self.world.start()

    def get_results(self) -> Dict[str, Any]:
        return self.world.get_results()
