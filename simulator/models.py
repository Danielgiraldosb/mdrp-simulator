"""
Core data classes, adapted to mdrplib's native planar (meters) coordinate
system and minute-based clock. See config.py for the unit conventions.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


# -- Location ------------------------------------------------------------------

@dataclass
class Location:
    x: float  # meters, per-instance planar origin
    y: float  # meters

    def copy(self) -> Location:
        return Location(self.x, self.y)


# -- Order -----------------------------------------------------------------------

@dataclass
class Order:
    """
    One order from orders.txt. ready_time is given directly by the instance
    (the minute the food becomes ready at the restaurant) and is immutable
    input data -- it is never overwritten at runtime. picked_up_at tracks
    the actual pickup time separately, so ready_to_door / ready_to_pickup
    match the official evaluator's own definitions exactly.
    """
    order_id: int
    placement_time: float        # min, from sim start
    store_loc: Location
    user_loc: Location
    ready_time: float            # min, from sim start (instance data)
    target_click_to_door: float  # min -- soft SLA ("target click-to-door")
    max_click_to_door: float     # min -- hard SLA ("maximum click-to-door")

    # -- Runtime state (updated during simulation) ---------------------------
    assigned_at: Optional[float] = None
    picked_up_at: Optional[float] = None
    delivered_at: Optional[float] = None
    canceled_at: Optional[float] = None
    assigned_courier: Optional[int] = None
    pay_received: float = 0.0
    # Couriers that already rejected this order -- never offered again to them
    rejected_by: set = field(default_factory=set)

    @property
    def is_pending(self) -> bool:
        return (self.assigned_courier is None
                and self.canceled_at is None
                and self.delivered_at is None)

    @property
    def is_delivered(self) -> bool:
        return self.delivered_at is not None

    @property
    def is_canceled(self) -> bool:
        return self.canceled_at is not None

    @property
    def click_to_door(self) -> Optional[float]:
        if self.delivered_at is None:
            return None
        return self.delivered_at - self.placement_time

    @property
    def ready_to_door(self) -> Optional[float]:
        if self.delivered_at is None:
            return None
        return self.delivered_at - self.ready_time

    @property
    def ready_to_pickup(self) -> Optional[float]:
        if self.picked_up_at is None:
            return None
        return self.picked_up_at - self.ready_time

    @property
    def click_to_door_overage(self) -> Optional[float]:
        """max(0, click-to-door - target click-to-door) -- official evaluator's metric."""
        if self.click_to_door is None:
            return None
        return max(0.0, self.click_to_door - self.target_click_to_door)


# -- Equity history h_c(t) -------------------------------------------------------

@dataclass
class EquityHistory:
    """Accumulated per-courier state -- equivalent to h_c(t) in the thesis."""
    earnings: float = 0.0           # total pay received (instance pay units)
    orders_delivered: int = 0       # total orders completed
    active_time: float = 0.0        # minutes in motion or serving
    dist_traveled: float = 0.0      # km traveled

    @property
    def hourly_earnings(self) -> float:
        if self.active_time > 0:
            return self.earnings / (self.active_time / 60.0)
        return 0.0

    @property
    def orders_per_hour(self) -> float:
        if self.active_time > 0:
            return self.orders_delivered / (self.active_time / 60.0)
        return 0.0

    @property
    def dist_per_hour(self) -> float:
        if self.active_time > 0:
            return self.dist_traveled / (self.active_time / 60.0)
        return 0.0


# -- Courier -----------------------------------------------------------------------

@dataclass
class Courier:
    """
    mdrplib has no vehicle-type distinction -- a single instance-wide
    meters_per_minute speed applies to every courier (see distance.py).
    """
    courier_id: int
    on_time: float    # min, from sim start when courier logs on
    off_time: float   # min, from sim start when courier logs off
    home_loc: Location
    acceptance_rate: float = 0.8    # used by the uniform acceptance policy
    # Real Colombian instances only (loader_real.py): vehicle type and its own
    # travel speed. None = use the instance-wide cfg.meters_per_minute
    # (mdrplib behaviour, unchanged). See distance.speed_of().
    vehicle: Optional[str] = None
    speed_m_per_min: Optional[float] = None

    # -- Runtime state --------------------------------------------------------
    location: Optional[Location] = None
    condition: str = 'offline'
    # conditions: offline | idle | notified | moving | picking_up | delivering
    #             | repositioning | busy | logged_off
    log_off_scheduled: bool = False
    history: EquityHistory = field(default_factory=EquityHistory)

    def __post_init__(self):
        self.location = self.home_loc.copy()

    @property
    def is_available(self) -> bool:
        return self.condition == 'idle'

    @property
    def shift_duration(self) -> float:
        return self.off_time - self.on_time
