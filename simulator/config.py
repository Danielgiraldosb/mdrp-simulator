"""
Simulation configuration for the mdrplib-adapted MDRP simulator.

All time fields are in MINUTES and all distance/coordinate fields are in
METERS -- the native units of the grubhub/mdrplib instance files
(orders.txt, couriers.txt, restaurants.txt, instance_parameters.txt).
There is no unit conversion anywhere in this package; the defaults below
are only placeholders and get overwritten per-instance by
loader.load_instance().
"""
from dataclasses import dataclass, field
from typing import Dict, Optional


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
    #   'logit_ppk' -- sigmoid of ln(pay per km) calibrated on the Bogota
    #                 interviews (Comportamiento_domiciliarios_cuantitativo.xlsx,
    #                 sheet Parametros_modelo): threshold 903 COP/km, slope 2.89
    acceptance_mode: str = 'auto'        # 'auto' | 'fixed' | 'logistic' | 'logit_ppk'
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
    # logit_ppk: p = sigma(b * (ln(pay/km) - ln(theta))). theta is the pay per
    # km at which P(accept)=0.5 and b the slope on ln(pay/km). Point estimates
    # from 32 declared decisions of 11 couriers (2020, manual regime); 95% CI
    # theta [615, 1242] COP/km, b [2.02, 5.23] -- grade C, run sensitivity.
    accept_ppk_threshold: float = 903.0  # COP/km
    accept_ppk_slope: float = 2.89
    accept_ppk_min_km: float = 0.1       # guard against pay/0 on degenerate routes
    # Decision regime of the courier (interviews 2020 vs 2021, grade A):
    #   'manual'     -- each offer is accepted with the logit_ppk probability
    #   'autoaccept' -- the app accepts for the courier; the decision is about
    #                   being online, not about each order -> p = 1 per offer
    accept_regime: str = 'manual'        # 'manual' | 'autoaccept'

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

    # -- Hierarchical Gurobi policy (hier/, hier_policy.py) -----------------------
    # Lexicographic pass order, highest priority first (names from
    # hier.objectives.CATALOGUE). None = DEFAULT_ORDER:
    # coverage > lateness > equity > cost.
    hier_order: Optional[list] = None
    hier_top_k: int = 25                 # K nearest couriers per route (annotated prefilter)
    hier_write_artifacts: bool = False   # <id>_input/_sol/_partial json per round (épica §6)
    hier_out_dir: str = 'output/hier'

    # -- BRKGA policy (brkga_policy.py): port of the MIC 2026 BRKGA-Coverage / -----
    # BRKGA-Travel rolling-horizon dispatcher. Population and generations are
    # the originals per-window defaults; see docs/paper-cmdp/porte-brkga.md.
    brkga_fitness: str = 'coverage'        # coverage | travel
    brkga_population: int = 10
    brkga_generations: int = 10
    brkga_elite_frac: float = 0.2          # original: elite = max(2, pop // 5)
    brkga_mutant_frac: float = 0.2         # original: mutants = max(2, pop // 5)
    brkga_elite_bias: float = 0.7
    brkga_top_k_couriers: int = 3          # couriers tried per batch inside the decoder (original K = 3)
    brkga_cand_top_k: int = 25             # nearest couriers per route in the candidate prefilter (as ILP/Hier)
    # Decoder score of a (route, courier) pair, lower wins. 'finish' = route finish
    # time (original rule; a bundle never beats a singleton of the same courier,
    # so the original never bundled). 'finish_per_order' = travel time per order
    # in the route, which lets bundles compete. Author decision pending.
    brkga_score: str = 'finish_per_order'   # decision 2026-10-20: bundles compete (see porte-brkga.md)
    # -- BRKGA-Fair (brkga_fair.py): deficit-biased decoder on H_t ------------------
    # score -= brkga_fair_weight (minutes) * relative deficit of the courier,
    # deficit = max(0, mean_w - w_c) / mean_w over the idle couriers of the round.
    # 0 reproduces BRKGAPolicy exactly.
    brkga_fair_weight: float = 10.0
    brkga_fair_basis: str = 'hourly'      # hourly (as F_Gini) | total (as HierContext)
    # -- MIP-Fair (mip_fair.py): per-window MIP with the elastic Gini constraint ------
    # eq:fair_const on projected H_t. alpha = tolerated Gini (criterion B: 0.30).
    mipfair_alpha: float = 0.30
    mipfair_priority: str = 'coverage'      # fairness (Gini excess > coverage) | coverage (coverage > Gini excess)  # Etapa 4 pilot: fairness-first assigns nothing from a cold start
    mipfair_basis: str = 'hourly'         # hourly (as F_Gini) | total
    mipfair_cand_top_k: int = 25           # nearest couriers per route in the candidate prefilter (as ILP/Hier)
    # Whose earnings enter the Gini: 'all' = every logged-on courier (idle ones move,
    # busy ones fixed; thesis eq:fair_const is over C), 'idle' = only this round's idle couriers.
    mipfair_scope: str = 'all'
    # -- Pay-BRKGA (pay_brkga.py): bi-objective coverage + F_Deficit, decides pay ------
    # offers within +-paybrkga_pay_range of the tariff (thesis eq:cost_plus, lambda).
    paybrkga_pay_range: float = 0.30
    paybrkga_lambda_deficit: float = 0.5    # weight of projected F_Deficit (coverage-fraction units)
    paybrkga_lambda_pay: float = 0.2        # weight of relative pay excess (eq:cost_plus lambda)

    # Extra grace beyond the instance's own "maximum click-to-door" hard SLA.
    # 0 = use the instance's hard window exactly as published.
    late_tolerance_min: float = 0.0

    # -- Repositioning (thesis extension, off by default) -----------------------
    enable_repositioning: bool = False
    reposition_speed_factor: float = 1.0
    reposition_check_interval_min: float = 5.0

    # -- Real Colombian instances (loader_real.py) -------------------------------
    # Only read when the instance folder holds couriers/orders/stores.csv.
    # The 24 folders are labelled Bogota in the thesis material but span
    # several cities (Bogota, Pereira, Bucaramanga, Barranquilla, ...).
    # lat/lng are projected to planar meters around the instance's own
    # centre (median store) so that
    # distance.py's Euclidean formula applies unchanged; real_circuity
    # rescales those meters (1.0 = great-circle/haversine-equivalent,
    # ~1.3 = Manhattan-like street network approximation).
    real_circuity: float = 1.0
    # Per-vehicle speed (km/h). The CSV vehicle column holds bicycle /
    # motorcycle / walking / car. External urban-Bogota assumptions, not from
    # the survey (declare in the paper); override with --speeds.
    real_speeds_kmh: Dict[str, float] = field(default_factory=lambda: {
        'bicycle': 15.0, 'motorcycle': 25.0, 'walking': 5.0, 'car': 20.0})
    # Hard SLA = per-order expected_drop_off_time (soft SLA) + this slack.
    real_max_ctd_extra_min: float = 30.0
    # Couriers/stores/drop-offs farther than this from the instance centre
    # are dropped (the raw CSVs contain a few points in other cities).
    real_max_radius_km: float = 40.0
    # Flat pay per order in COP: survey V116 median without 'racha' (n=132).
    real_pay_per_order_cop: float = 2200.0
    # Statutory reference for F_Deficit: SMMLV 2021 per hour at 48 h/week.
    real_min_wage_cop_per_hour: float = 4367.91
    # Service times (Bogota survey; a transfer assumption for other cities):
    # V88 median wait at the store with the order bought
    # (20 min, IQR 15-30); interviews report 60 min for stress episodes.
    real_pickup_service_min: float = 20.0
    real_dropoff_service_min: float = 4.0   # no survey item; mdrplib default
    # Decision window: interviews median 16 s (IQR 9-28 s); the app shows 20 s.
    real_decision_mean_min: float = 16.0 / 60.0
    real_decision_std_min: float = 8.0 / 60.0

    # -- Snapshots ----------------------------------------------------------------
    snapshot_interval_min: float = 5.0

    seed: int = 42
