# Formulación del CMDP (copia literal de la tesis)

Fuente: `Tesis/Tesis_Doctoral_Giraldo_Herrera.tex`, capítulos *Problem Description* (líneas 405–445),
*Formal Mathematical Framework* (446–618), la extensión de costo con pago del Gap 3 (676–684) y la
proxy de emisiones de la sección *Environmental Sustainability and Adoption* (230–243).
Copiado el 2026-10-20 sin cambios de contenido; solo se quitaron los comandos LaTeX de entorno
(`\begin{description}`, `\label`, `\ref`) y se mantienen las ecuaciones tal cual. Las referencias a
secciones de la tesis se dejan entre corchetes. Lo que el paper cambie respecto a esto se decide en la
Etapa 1 (`modelo-vs-evidencia.md`), no aquí.

---

## 1. Problem Description

The MDRP addressed in this study is grounded in the operational challenges of digital delivery platforms in Latin America. These platforms connect couriers $C$, users $U$, and restaurants/stores $R$. Information about stores and couriers is known in advance; information about users and orders becomes available only at order-placement time, creating the stochastic and dynamic character of the problem.

### 1.1 Sets and Parameters

- **$U$** Set of users, each $u \in U$ with drop-off location $\ell_u$.
- **$R$** Set of restaurants/stores, each $r \in R$ with pick-up location $\ell_r$.
- **$O$** Set of orders; each $o \in O$ is linked to restaurant $r_o \in R$, user $u_o \in U$, placement time $a_o$, ready time $e_o$, pick-up service time $s_r$, drop-off service time $s_u$, and target drop-off time $d_o$.
- **$C$** Set of couriers; each $c \in C$ has on-time $e_c$, off-time $l_c > e_c$, initial location $\ell_c$, and vehicle type $v_c \in \{\text{walking, bicycle, motorcycle, car}\}$.
- **$S$** Set of routes; each route $s \in S$ contains orders from a single restaurant ($|\{r_o : o \in s\}| = 1$) and is assigned to a single courier.

### 1.2 Structural Assumptions

1. **Route capacity.** Each route has a maximum number of orders $Q$.
2. **Static travel times.** Travel time $\tau(\ell,\ell')$ between any pair of locations is deterministic and time-invariant (computed from real road networks via OSRM).
3. **Notification constraints.** Couriers may only receive assignment notifications while idling or during pick-up; moving or dropping-off couriers are not notified for safety reasons.
4. **Single-order-per-user.** Each user places at most one order per operation day.
5. **Cancellation finality.** Once an order is canceled---either by the user or the platform---it cannot re-enter the system, and it counts negatively in service metrics.

### 1.3 Performance Metrics

The primary platform metric is the *coverage rate* (fraction of orders successfully delivered). Secondary metrics include click-to-door time, ready-to-door time, courier utilization, and ---critically for this thesis--- *fairness metrics* formally defined in [sec:fairness] and [sec:validation], together with the environmental diagnostic of Eq. (emissions).

---

## 2. Formal Mathematical Framework

This chapter formalizes the MDRP as a *Constrained Markov Decision Process* (CMDP) with a fairness component. This formalism is necessary to (i) precisely state the optimization problem, (ii) embed the fairness concept developed in [ch:concept] as a mathematical object, and (iii) provide a rigorous basis for the algorithmic contributions of the thesis.

### 2.1 System State

At each decision epoch $t$ (triggered at every rolling-horizon window boundary), the system state $s_t$ is a tuple

$$
s_t = \bigl(\mathcal{L}_t,\; \mathcal{O}_t,\; \mathcal{P}_t,\; \mathcal{H}_t\bigr),
$$

where:

- **$\mathcal{L}_t$ — Location state.** For each courier $c \in C$, the current position $\ell_c(t)$, status $\sigma_c(t) \in \{\text{idle, picking-up, in-transit, dropping-off, offline}\}$, and estimated time until next availability $\eta_c(t)$.
- **$\mathcal{O}_t$ — Order state.** The set of unassigned orders available for assignment at time $t$, including their attributes $(r_o, u_o, a_o, e_o, d_o)$.
- **$\mathcal{P}_t$ — Preparation state.** For each unassigned order $o \in \mathcal{O}_t$, the estimated remaining preparation time $\hat{p}_o(t)$.
- **$\mathcal{H}_t$ — Accumulated equity history.** For each courier $c$, a vector of accumulated performance indicators up to time $t$:

$$
h_c(t) = \bigl(\text{earn}_c(t),\; \text{orders}_c(t),\; \text{active}_c(t)\bigr),
$$

  where $\text{earn}_c(t)$ is total earnings, $\text{orders}_c(t)$ is total orders delivered, and $\text{active}_c(t)$ is total active time. This component tracks the *intertemporal equity state* and is absent from all existing MDRP formulations.

**Definition (Equity history).** $\mathcal{H}_t$ is the component of the state that enables *dynamic fairness control*: an assignment policy can use accumulated history to avoid compounding of inequities across rolling-horizon windows ([sec:concept-dimensions], temporal dimension).

### 2.2 Exogenous Information

Between decision epochs $t$ and $t+1$, exogenous information $\xi_{t+1}$ is revealed:

$$
\xi_{t+1} = \bigl(\Delta\mathcal{O}_{t+1},\; \Delta\mathcal{P}_{t+1},\; \Delta\mathcal{A}_{t+1}\bigr),
$$

where $\Delta\mathcal{O}_{t+1}$ is the set of new orders placed in $(t, t+1]$, $\Delta\mathcal{P}_{t+1}$ is the realization of preparation times, and $\Delta\mathcal{A}_{t+1}$ contains courier availability events (log-ins and log-outs).

### 2.3 Action Space

At epoch $t$, the platform chooses an assignment-and-routing action:

$$
a_t = \{(c, s) : c \in C_t^{\text{avail}},\; s \in S_t\},
$$

where $C_t^{\text{avail}} \subseteq C$ is the set of available couriers and $S_t$ is the set of feasible routes constructed from $\mathcal{O}_t$. Each courier is assigned at most one route; each order appears in at most one route. The action also includes a *pay offer* $\pi_{c,s}$ for each pair (courier, route), which determines the probability of acceptance the courier (see [sec:acceptance]).

### 2.4 Operational Cost Function

The per-epoch operational cost is

$$
c(s_t, a_t, \xi_{t+1}) = \sum_{o \in \mathcal{O}_t} w_1 \cdot \mathbf{1}[o \text{ not delivered}] + w_2 \cdot \sum_{o \text{ delivered}} \max(0,\; \tau_{\text{drop}}(o) - d_o),
\tag{eq:cost}
$$

where $w_1$ penalizes undelivered orders and $w_2$ penalizes lateness relative to the target drop-off time $d_o$.

**Justification and calibration of $w_1$, $w_2$ (observación 8 del Comité).** The weight $w_1$ is not an arbitrary penalty: it is designed to be anchored to the platform's actual opportunity cost of a non-delivered order, namely the commission revenue and store-side goodwill forfeited when an order is cancelled --- both directly observable in the Phase 2 historical data. The weight $w_2$ is designed to be anchored to the platform's contractual service-level treatment of late deliveries (e.g., a customer credit, refund, or discount policy triggered past a lateness threshold), where such a policy exists in the data; where it does not, $w_2$ is calibrated so that the model's revealed lateness tolerance reproduces the lateness distribution actually observed under the historical (corporate baseline) policy, using the Stage 1 historical-replay validation protocol. In both cases, $w_1$ and $w_2$ are treated as *estimated parameters*, not free hyperparameters: their calibration is an explicit deliverable of Phase 2, and [ch:results] will report the fitted values together with a sensitivity analysis showing how the resulting policies change as $w_1/w_2$ is varied.

### 2.5 Fairness Function

**Definition (Fairness metric $F$).** Let $\text{earn}_c(T)$ denote the total earnings of courier $c$ at the end of operation day $T$, and $\text{active}_c(T)$ the total active time. The *hourly earnings inequality* metric is

$$
F_{\text{Gini}}(\mathbf{w}) = \frac{\sum_{c} \sum_{c'} |w_c - w_{c'}|}{2|C|\sum_{c} w_c},
\qquad w_c = \frac{\text{earn}_c(T)}{\text{active}_c(T)},
\tag{eq:gini}
$$

where $\mathbf{w} = (w_1, \ldots, w_{|C|})$ is the vector of hourly earnings across couriers. $F_{\text{Gini}} \in [0,1]$, with 0 indicating perfect equality. Normalizing by $\text{active}_c(T)$ makes $F_{\text{Gini}}$ an equity-theoretic (input-adjusted), not merely descriptive, statistic.

Additional fairness metrics considered:

- **$F_{\text{MaxMin}}$** Max–min fairness: maximize the minimum hourly earnings across all couriers, $\max_{\pi} \min_c w_c$.
- **$F_{\text{Orders}}$** Order-count fairness: Gini coefficient applied to the number of orders delivered per courier per active hour --- a *balance* statistic, retained as a secondary diagnostic.
- **$F_{\text{Deficit}}$** Minimum-wage deficit: fraction of couriers whose hourly earnings fall below the statutory minimum wage $w^*$, $F_{\text{Deficit}} = |\{c : w_c < w^*\}| / |C|$.

The thesis will evaluate all four metrics, and additionally the zone- and vehicle-conditioned variants $F_{\text{Gini}}(\mathbf{w} \mid z)$ and $F_{\text{Gini}}(\mathbf{w} \mid v)$ (computed within each operating zone $z$ / within vehicle-type strata before being aggregated; secondary diagnostics, [sec:concept-dimensions]), but will use the pooled $F_{\text{Gini}}$ as the primary fairness criterion, given its interpretability, its prevalence in economic inequality literature, and the existence of closed-form sensitivity expressions that facilitate algorithm design.

#### 2.5.1 On the Choice of $\alpha$: A Formal Calibration Criterion (observación 6)

Three complementary, non-exclusive criteria:

- **Criterion A — Historical-baseline anchor.** Set $\alpha = F_{\text{Gini}}^{\text{hist}}$, the Gini coefficient of hourly earnings actually observed under the platform's current (corporate baseline) assignment policy on the historical data. The fairness constraint requires only that the proposed policy be *no less equal than the status quo*.
- **Criterion B — Inequality-severity bands.** Anchor $\alpha$ to conventional income-inequality severity bands (Gini below approximately $0.30$ read as "low", above approximately $0.40$ as "high" for a working population); set $\alpha$ to the upper bound of the band judged acceptable (e.g., $\alpha = 0.30$).
- **Criterion C — Pareto-knee selection.** Sweep $\alpha \in [0,1]$ to trace the full efficiency–fairness Pareto frontier and select the "knee" of the curve (point of maximum curvature) as the recommended operating point. Computable only *after* the Phase 5 experiments are run.

Criterion A gives a defensible lower bound on ambition, Criterion B an externally auditable target, Criterion C an empirically efficient operating point once data are available. [ch:results] reports $\alpha$ under all three.

### 2.6 Endogenous Acceptance Model

Let $p_{c,s}(\pi_{c,s}, s_t)$ denote the probability that the courier $c$ accepts the route $s$ when offered pay $\pi_{c,s}$ in state $s_t$. The acceptance probability is modeled as

$$
p_{c,s} = \sigma\!\bigl(\beta_0 + \beta_1 \pi_{c,s} + \beta_2 \,\text{dist}(s) + \beta_3 \,\text{active}_c(t) + \boldsymbol{\beta}_4^\top \mathbf{x}_{c,t}\bigr),
\tag{eq:acceptance}
$$

where $\sigma(\cdot)$ is the logistic function, $\text{dist}(s)$ is total route distance, $\text{active}_c(t)$ is cumulative active time (a fatigue proxy), and $\mathbf{x}_{c,t}$ captures other state features (vehicle type, time of day, etc.). Parameters $\boldsymbol{\beta}$ are estimated from historical data using maximum-likelihood logistic regression. Including the offered pay $\pi_{c,s}$ as an explanatory variable ($\beta_1$) is what distinguishes Eq. (eq:acceptance) from the closest existing precedent, the distance-and-courier-parameter acceptance function of Quintero (2020): here the courier's acceptance decision responds directly to the price the platform offers.

**Transition.** The transition from $s_t$ to $s_{t+1}$ is then

$$
s_{t+1} = f\!\bigl(s_t,\; a_t,\; \xi_{t+1},\; \mathbf{b}_t\bigr),
$$

where $\mathbf{b}_t \in \{0,1\}^{|C_t^{\text{avail}}|}$ is the vector of acceptance realizations, drawn from the Bernoulli distribution parameterized by (eq:acceptance).

#### 2.6.1 Route Balancing and Tariff Treatment (observación 7)

**Tariff treatment.** The pay offer $\pi_{c,s}$ in Eq. (eq:acceptance) is not a free decision variable chosen independently of the platform's real payment practice: it is constrained to follow the platform's actual tariff schedule, modeled as an affine function of route distance and a base fee,

$$
\pi_{c,s} = \pi_0 + \pi_1 \cdot \text{dist}(s),
\tag{eq:tariff}
$$

where $\pi_0$ (base fee) and $\pi_1$ (per-kilometer rate) are estimated from the historical payment records in Phase 2, consistent with real per-kilometer and per-order commission structures reported for Latin American platforms. Fairness-aware policies (BRKGA-Fair, Pay-BRKGA) are permitted to adjust $\pi_1$ within a bounded range around this baseline --- rather than to set pay arbitrarily --- so that the tariff structure explored remains operationally realistic and comparable to the platform's current practice.

**Route balancing.** Balancing routes by *count* alone (as in $F_{\text{Orders}}$) is insufficient, because routes differ systematically in distance and, through Eq. (eq:tariff), in pay. This dissertation therefore introduces an explicit route-balancing constraint, bounding the share of high-value routes any single courier may receive within a rolling-horizon window relative to their peers:

$$
\bigl|\{s \in a_t : c(s) = c,\ \text{dist}(s) > \bar{d}_t\}\bigr| \;\leq\; \kappa \cdot |\{s \in a_t : c(s) = c\}|,
\qquad \forall c \in C_t^{\text{avail}},
\tag{eq:routebalance}
$$

where $\bar{d}_t$ is the mean route distance among routes dispatched at epoch $t$, and $\kappa \in (0,1]$ is a concentration threshold ($\kappa = 1$ recovers the unconstrained case). Tariffs determine what a route is worth, and route balancing determines that no courier is structurally denied access to high-value routes.

### 2.7 Constrained Optimization Objective

The platform seeks a policy $\pi^*$ that minimizes the expected cumulative operational cost subject to a fairness constraint:

$$
\begin{aligned}
\min_{\pi}\; & \mathbb{E}_{\xi}\!\left[\sum_{t=0}^{T} \gamma^t c(s_t, a_t, \xi_{t+1})\right] & \text{(eq:obj)} \\
\text{s.t.}\; & F_{\text{Gini}}(\mathbf{w}^\pi) \leq \alpha, & \text{(eq:fair\_const)} \\
& \mathbb{E}[w_c^\pi] \geq w^* \quad \forall c \in C, & \text{(eq:minwage)} \\
& \text{Eq. (eq:routebalance)} \quad \forall t, & \text{(eq:routebalance\_ref)} \\
& a_t \in \mathcal{A}(s_t) \quad \forall t, & \text{(eq:feasibility)}
\end{aligned}
$$

where $\gamma \in (0,1]$ is a discount factor, $\alpha \in [0,1]$ is the maximum tolerated Gini inequality (calibrated per §2.5.1), and $w^*$ is the statutory minimum hourly wage. The constraint (eq:fair_const) bounds income inequality; constraint (eq:minwage) guarantees a minimum expected hourly wage for every courier; constraint (eq:routebalance_ref) enforces route balancing; constraint (eq:feasibility) ensures route feasibility and assignment validity.

This formulation subsumes the three existing approaches in the literature as special cases: (i) setting $\alpha = 1$ and removing (eq:minwage) and (eq:routebalance_ref) recovers the corporate (efficiency-only) model; (ii) incorporating $F_{\text{Orders}}$ as the fairness criterion recovers workload-balance models; (iii) using $F_{\text{Deficit}}$ recovers minimum-wage guarantee models.

### 2.8 Extensión del costo con pago (Gap 3, [ch:gaps])

The CMDP cost function (eq:cost) will be extended to include a payment term:

$$
c^+(s_t, a_t, \xi_{t+1}) = c(s_t, a_t, \xi_{t+1}) + \sum_{(c,s)\in a_t} \lambda \cdot \text{pay}(c, s, \pi_{c,s}),
\tag{eq:cost\_plus}
$$

where $\text{pay}(c,s,\pi_{c,s})$ is the actual payment to courier $c$ for route $s$ under the tariff schedule (eq:tariff), and $\lambda > 0$ is a weight traded off against coverage. Sensitivity analysis will sweep $\lambda$ to trace the cost-of-fairness curve.

### 2.9 Emissions proxy ([sec:concept-sustainability], observación 9)

Because vehicle type $v_c$ is already recorded for every courier, an *emissions proxy*

$$
E(a_t) = \sum_{(c,s) \in a_t} \epsilon(v_c) \cdot \text{dist}(s),
\tag{eq:emissions}
$$

where $\epsilon(v_c)$ is a per-kilometer emission factor for vehicle type $v_c$ (near zero for walking and bicycle couriers, positive for motorcycle and car), can be computed at no additional data cost and reported alongside the efficiency–fairness Pareto curves.

---

## 3. Métricas registradas por la plataforma de simulación ([sec:validation], Tabla tab:metrics)

| Metric | Definition | Addresses |
|---|---|---|
| Coverage rate | Fraction of orders delivered / total orders placed | Efficiency (G1–G4) |
| Click-to-door time | Mean time from order placement to drop-off (delivered orders) | Service quality |
| Ready-to-door time | Mean time from order ready to drop-off | Last-mile efficiency |
| Courier utilization | Active time / logged-in time per courier (mean across $C$) | Labor efficiency |
| $F_{\text{Gini}}$ | Gini coefficient of hourly earnings (eq:gini) | Fairness (G1, G2) |
| $F_{\text{Gini}}(\cdot\mid z)$, $F_{\text{Gini}}(\cdot\mid v)$ | Zone- and vehicle-conditioned Gini | Fairness dimensions (obs. 1) |
| $F_{\text{MaxMin}}$ | Minimum hourly earnings across couriers | Fairness (G2) |
| $F_{\text{Orders}}$ | Gini coefficient of orders/active-hour | Balance (G1) |
| $F_{\text{Deficit}}$ | Fraction of couriers below minimum wage $w^*$ | Fairness (G3) |
| Acceptance rate | Fraction of assigned routes accepted | Behavioral (G4) |
| Pay per order | Mean pay per delivered order | Economic (G3) |
| Emissions proxy $E$ | Vehicle-weighted route distance (eq:emissions) | Sustainability (obs. 9) |

All metrics are defined at the instance level (aggregated over the full operation day) and at the replication level (averaged over 10 replications per policy per instance).

---

## 4. Notas de lectura (no están en la tesis; para la Etapa 1)

- La tesis no define una *recompensa*; el CMDP se escribe en términos de costo (eq:cost) a minimizar. Si el paper necesita recompensa, es $r_t = -c(\cdot)$.
- $\gamma$ aparece en (eq:obj) pero no se fija ni se justifica; en un día de operación finito lo natural es $\gamma = 1$.
- (eq:fair_const) y (eq:minwage) están escritas sobre cantidades de fin de día ($T$), no por época; la tesis lo declara explícitamente en el Gap 2. La restricción (eq:routebalance) sí es por época.
- La aceptación (eq:acceptance) es lineal en pago y distancia; la evidencia de la encuesta (plan.md, Etapa 1) apunta a $\sigma(a + b\ln(\text{pago/km}))$. La decisión se toma en la Etapa 1.
- La tesis asume tiempos de viaje por OSRM; las instancias de Bogotá traen lat/lng, así que el loader (Etapa 2) tendrá que elegir haversine/Manhattan u OSRM.
- $\epsilon(v_c)$ no se calibra en la tesis; hay que tomar factores externos y declararlo.
