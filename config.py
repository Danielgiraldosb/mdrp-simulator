"""
Simulation configuration for the mdrplib-adapted MDRP simulator.

All time fields are in MINUTES and all distance/coordinate fields are in
METERS -- the native units of the grubhub/mdrplib instance files
(orders.txt, couriers.txt, restaurants.txt, instance_parameters.txt).
There is no unit conversion anywhere in this package; the defaults below
are only placeholders and get overwritten per-instance by
loader.load_instance().
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    # -- Timing window (minutes from the instance clock) ----------------------
    sim_start_clock_min: float = 0.0     # window start, set via --from
    sim_end: float = 1_440.0             # window length in minutes (default: full day)
    rolling_horizon: float = 2.0         # minutes between dispatch rounds

    # -- Order cancellation -- two-threshold hazard model ----------------------
    # This is a modeling EXTENSION on top of the official MDRP benchmark:
    # mdrplib's own solution evaluator (MDRP_code/compute_performance_summary.py)
    # has no notion of cancellation -- every order is assumed to be routed
    # eventually. Off by default so a run matches that baseline assumption;
    # switch on with --cancellation to study the richer, stochastic variant.
    enable_cancellation: bool = False
    cancel_t1_min: float = 15.0          # customer patience starts
    cancel_t2_min: float = 30.0          # platform forced cancellation
    cancel_lambda_per_min: float = 0.10  # hazard rate after T1

    # -- Instance-derived parameters --------------------------------------------
    # Overwritten by loader.load_instance() from instance_parameters.txt.
    meters_per_minute: float = 320.0
    pickup_service_min: float = 4.0
    dropoff_service_min: float = 4.0
    target_click_to_door: float = 40.0   # soft SLA -> used for lateness/overage
    max_click_to_door: float = 90.0      # hard SLA -> used as feasibility cutoff
    pay_per_order: float = 10.0
    guaranteed_pay_per_hour: float = 15.0

    # External policy benchmark for the F_Deficit fairness metric -- independent
    # of the platform's own guaranteed_pay_per_hour. None means "use
    # guaranteed_pay_per_hour" (resolved in metrics.compute_metrics);
    # override with --min-wage to study a different statutory threshold.
    min_wage_hourly: Optional[float] = None

    # -- Courier acceptance (thesis extension) ----------------------------------
    # Transversal to every policy (Greedy, FairGreedy, all 5 ILP objectives --
    # see acceptance.py): changing acceptance_mode never changes how orders
    # get matched, only whether a notified courier takes the route.
    #   'auto'     -- always accepts (mdrplib's own baseline assumption)
    #   'fixed'    -- each courier's own fixed rate, drawn once from
    #                 [min_acceptance_rate, max_acceptance_rate] (loader.py);
    #                 set both equal for a single global probability
    #   'logistic' -- sigmoid of pay / distance / accumulated fatigue
    acceptance_mode: str = 'auto'        # 'auto' | 'fixed' | 'logistic'
    min_acceptance_rate: float = 1.0     # used by 'fixed'
    max_acceptance_rate: float = 1.0     # used by 'fixed'
    # Logistic coefficients -- illustrative placeholders rescaled to
    # mdrplib's own pay units and minute-based clock; replace with MLE
    # estimates from real acceptance data when available. Used by 'logistic'.
    accept_beta0: float = 0.8
    accept_beta1: float = 0.075          # per pay unit (pay_per_order=10 -> +0.75)
    accept_beta2: float = -0.23          # per km        (2 km -> -0.46, 5 km -> -1.15)
    accept_beta3: float = -0.0003        # per minute of active time (fatigue, minor)
    decision_mean_min: float = 0.33      # ~20s: time to accept/reject an offer
    decision_std_min: float = 0.17       # ~10s

    # -- Dispatch / ILP ----------------------------------------------------------
    # ILP tie-break rule: the real objective -- maximize coverage -- is the
    # SAME for all 5 (and, informally, for Greedy/FairGreedy's own greedy
    # rule too); this only picks the secondary criterion used among
    # coverage-maximal solutions. See ilp_policy.py's module docstring.
    objective: str = 'max_coverage'      # max_coverage | max_throughput | min_lateness | max_equity | min_cost
    ilp_solver: str = 'CBC'              # CBC (free) | GUROBI | CPLEX
    # None = no time limit: the solver runs each dispatch round to proven
    # optimality (or exhausts its own search) rather than returning a value
    # capped by a clock -- every reported ILP solution is a genuine optimum.
    # Set a float (seconds) only if you deliberately want a bounded-time,
    # possibly-suboptimal solver for a real-time feasibility study.
    ilp_time_limit_sec: Optional[float] = None
    # Transversal across every policy (Greedy, FairGreedy, and all 5 ILP
    # objectives -- see routing.py): 1 = no bundling, >1 = up to that many
    # same-restaurant orders can be grouped into a single route.
    max_bundle_size: int = 3
    # -- mdrp-sim-master ported policies (mdrpsim_policies.py) -------------------
    # Only read by mdrpsim_mip / mdrpsim_graph / mdrpsim_graph_prospects --
    # mirrors mdrp-sim-master's settings.DISPATCHER_DELAY_PENALTY (0.4) and
    # settings.DISPATCHER_PROSPECTS_MAX_DISTANCE (3 km).
    mdrpsim_delay_penalty: float = 0.4
    mdrpsim_prospects_max_distance_km: float = 3.0

    # Extra grace beyond the instance's own "maximum click-to-door" hard SLA.
    # 0 = use the instance's hard window exactly as published.
    late_tolerance_min: float = 0.0

    # -- Repositioning (thesis extension, off by default) -----------------------
    enable_repositioning: bool = False
    reposition_speed_factor: float = 1.0
    reposition_check_interval_min: float = 5.0

    # -- Snapshots ----------------------------------------------------------------
    snapshot_interval_min: float = 5.0

    seed: int = 42
