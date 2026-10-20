# Porte del BRKGA-Coverage / BRKGA-Travel a `Policy.assign` (Etapa 3, pieza 1)

Fecha: 2026-10-20. Origen: `articulo MDRP/MDVRPTW_BRKGA/brkga_rolling_horizon.py` (clase
`BRKGARollingHorizon`, métodos `_optimize_window` y `_decode_window_chromosome`), `decoder.py`
(funciones de fitness) y `operators.py` (élite, cruce sesgado, mutantes). Destino:
`simulator/brkga_policy.py` (`BRKGAPolicy`), registrado como `--policy brkga` en `run.py`;
tests en `simulator/tests/test_brkga.py` (12, todos verdes junto con los 42 anteriores).

## Qué se conserva del original

| Elemento | Original (MIC 2026) | Porte |
|---|---|---|
| Un BRKGA por ventana | ventana fija de 2 min, bucle propio | un BRKGA por ronda de despacho del simulador (`cfg.rolling_horizon`, 2 min por defecto) |
| Cromosoma | una clave por pedido listo + una por repartidor disponible | igual |
| Decodificador | tiendas en orden de su pedido más prioritario; en cada tiendas toma el pedido cabeza, prueba lotes de tamaño 1..3 contra los K=3 repartidores de mayor clave, se queda con el menor `finish_min`; un repartidor por ventana | igual, con dos cambios documentados abajo |
| Fitness | `fitness_coverage` (penalización por tramos a la cobertura, luego viaje medio/20) y `fitness_travel` | copiadas literalmente |
| Evolución | élite = `max(2, pop//5)`, mutantes = `max(2, pop//5)`, sesgo 0,7, sin parada temprana | igual (`brkga_elite_frac`, `brkga_mutant_frac`, `brkga_elite_bias`) |
| Tamaños por defecto | `pop_size=10`, `generations=10` por ventana | `brkga_population=10`, `brkga_generations=10` |

## Qué cambia y por qué

1. **Candidatos de ruta compartidos.** El original construía los lotes como prefijos de la lista de pedidos
   de la tienda ordenada por clave (cualquier subconjunto de 1 a 3). El porte solo usa los candidatos de
   `routing.generate_store_routes` (todos los singletons y UN lote por tienda con los `max_bundle_size`
   pedidos más urgentes) filtrados por `routing.route_feasibility` y por el prefiltro de los
   `brkga_cand_top_k = 25` repartidores más cercanos por ruta. Es exactamente el conjunto que usan el ILP
   (`_precompute_routes`) y el jerárquico (`HierContext._generate_candidates`); en el toy de 3 repartidores
   y 4 pedidos da los mismos 18 pares (test `test_candidates_match_hier_prefilter`). Motivo: el plan exige
   "los mismos candidatos de ruta" para que la comparación entre métodos sea justa.
2. **Factibilidad y tiempos del simulador.** El original medía tiempos con haversine y `SPEED_MAP` y exigía
   terminar el turno incluyendo el regreso a casa. El porte usa `route_feasibility` (SLA duro por pedido,
   tiempos de servicio, velocidad por repartidor de `loader_real.py`) y no hay tramo de regreso porque el
   simulador deja al repartidor en su última entrega. El puntaje `finish` pasa a ser `t + total_tt`
   (llegada a la última entrega).
3. **Pedido sin candidato factible.** El original abandonaba la tienda entera (`break`) cuando el pedido
   cabeza no tenía asignación factible; el porte lo salta y sigue con el siguiente pedido de la tienda.
   Mejora menor de cobertura; se declara para no atribuírsela al método.
4. **Aleatoriedad reproducible.** El original usaba `np.random` global; el porte usa un
   `numpy.random.default_rng(cfg.seed)` por política.
5. **Aceptación y pago.** El original no tenía ni aceptación ni pago. En el porte ambos son transversales:
   la aceptación la decide `cfg.acceptance_mode` (incluido `logit_ppk`) y el pago es
   `cfg.pay_per_order × pedidos`, como en greedy, fair_greedy e ILP.

6. **K repartidores entre los candidatos de la ruta (pieza 1b, 2026-10-20).** El porte tomaba los K = 3 repartidores de
   mayor clave entre *todos* los libres y luego buscaba si alguno estaba en el prefiltro de 25 de la ruta; con
   2.266 repartidores en la zona de Bogotá casi nunca lo estaba y el pedido se saltaba (cobertura 0,155 frente a
   0,437 del greedy en 12:00–14:00; Pay-BRKGA 0,555 en Pereira por lo mismo). Ahora toma los K de mayor clave
   entre los repartidores que pueden servir la ruta (`_Round.couriers_of`). En el original no había prefiltro,
   así que ambas lecturas coinciden; en el toy de 3 repartidores son idénticas (tests sin cambio). Tras el
   arreglo: Bogotá 12:00–14:00 cobertura 0,446 en 30 s (greedy 0,437 en 116 s); Pereira Pay-BRKGA 0,731.

## Hallazgo que requiere decisión del autor: el BRKGA original nunca agrupaba

El decodificador original puntúa cada par (lote, repartidor) por hora de fin del lote y se queda con el
menor. Para un mismo repartidor, un lote de 2 o 3 pedidos siempre termina después que el lote de 1 que
contiene al mismo pedido cabeza, así que el tamaño 1 gana siempre que sea factible (y si el singleton no
es factible, el lote tampoco). En consecuencia el `max_batch_size=3` del MIC 2026 era inoperante y el
BRKGA-Coverage/Travel reportado era, de hecho, un despachador de un pedido por repartidor y ventana.
(Verificable en los xlsx de resultados del MIC: el tamaño medio de lote debería ser 1; no lo comprobé en
esta sesión por el estado de la máquina.)

El porte ofrece las dos variantes con `cfg.brkga_score` / `--brkga-score`:

- `finish` (por defecto): regla original. En el toy cubre 3 de 4 pedidos (óptimo alcanzable sin lotes,
  verificado por fuerza bruta en `test_original_score_reaches_singleton_optimum`).
- `finish_per_order`: tiempo de viaje por pedido de la ruta. Los lotes compiten y en el toy cubre los 4
  pedidos, alcanzando el óptimo exhaustivo de su fitness (`test_per_order_score_reaches_full_optimum`).

**Decisión pendiente:** en el paper, ¿el baseline BRKGA es la regla original fiel (`finish`, comparable con
los resultados MIC 2026 pero sin lotes) o la variante con lotes (`finish_per_order`, más fuerte y más
comparable con el ILP y el jerárquico, que sí agrupan)? Recomendación: reportar `finish_per_order` como
BRKGA-Coverage y mencionar la variante original en una nota al pie o en el suplemento.

## Puntos de extensión para la Etapa 3

- `BRKGAPolicy._score(cand, courier_id, t)`: único lugar que decide qué ruta toma un repartidor dentro del
  decodificador. **BRKGA-Fair** = subclase que penaliza o premia según el déficit de equidad de `H_t`
  (`state['H_t'][cid]`), sin tocar nada más.
- `BRKGAPolicy._fitness(covered, n_orders, total_tt, assignments)`: ranking de la población. **Pay-BRKGA**
  (biobjetivo cobertura + F_Deficit con λ) entra aquí; el pago variable requerirá además devolver un
  `pay_offer` distinto de la tarifa plana en `assign`.
- `build_candidates(...)` es importable: MIP-Fair puede reusarlo y añadir la restricción Gini sobre esos
  mismos pares.

## Uso

```
python run.py --instance Instancia_22 --policy brkga --brkga-pop 10 --brkga-gens 10 --brkga-score finish_per_order
python -m pytest tests/test_brkga.py -q
```

Costo por ronda: `pop × gens` decodificaciones, cada una O(pedidos × K); con los valores por defecto son
100 decodificaciones por ronda, comparable al original. No se ha corrido un día completo en esta máquina
(bloqueo de hardware, ver `plan.md`).

## BRKGA-Fair (Etapa 3, pieza 2) — 2026-10-20

Archivo `simulator/brkga_fair.py`, clase `BRKGAFairPolicy(BRKGAPolicy)`, política `--policy brkga_fair`;
tests `tests/test_brkga_fair.py` (6). Definición de la tesis (l. 890): BRKGA-Coverage con un
decodificador que usa el estado de déficit $\mathcal{H}_t$ para sesgar la asignación hacia los repartidores
menos atendidos, sin salirse de la restricción de cobertura. Variante "dynamic-fair" de la brecha G2.

Implementación: una sola sobreescritura, `_score`:

    score(ruta, c) = score_base(ruta, c) − w · déficit_c,   déficit_c = max(0, w̄ − w_c) / w̄ ∈ [0, 1]

- `score_base` es la regla del BRKGA porteado (`brkga_score`: `finish` o `finish_per_order`, en minutos).
- `w_c` se toma de `state['H_t']`: ingresos por hora activa (`brkga_fair_basis=hourly`, la misma base que
  $F_{\text{Gini}}$, eq:gini; 0 si el repartidor aún no tiene tiempo activo) o ingresos totales (`total`,
  la base que usa el jerárquico). La media $\bar w$ es sobre los repartidores libres de la ronda.
- `w` = `brkga_fair_weight`, en minutos: un repartidor con déficit pleno se trata como si cada ruta suya
  terminara `w` minutos antes. Por defecto 10. Con `w = 0` la salida es idéntica a `brkga` con la misma
  semilla (test).
- La cobertura se protege igual que en el padre: el fitness que ordena la población no cambia, así que el
  déficit solo redirige rutas entre decodificaciones y la población conserva las de cobertura máxima. En el
  toy con `finish_per_order` y `w` grande, el repartidor 2 (el más rico) se queda sin ruta y la cobertura
  sigue en 4 de 4; con `finish` los tres repartidores son necesarios y la cobertura se mantiene en 3.

Control "myopic-fair" (equilibrio solo dentro de la ventana): en este simulador un repartidor toma a lo
sumo una ruta por ronda, de modo que el equilibrio intra-ventana ya está impuesto y no queda señal
adicional; el control myopic-fair es el `brkga` liso. Si el autor quiere otra definición (p. ej. déficit
sobre una ventana deslizante de 30 o 60 min), hay que añadir a `EquityHistory` una serie temporal de
ingresos; no existe hoy.

Decisiones del autor pendientes de esta pieza: base del déficit (`hourly` recomendado por coherencia con
el Gini), valor o barrido de `w` (propuesta: barrido {0, 5, 10, 20, 40} min en la Etapa 4), y si el
desempate por semilla debe reportarse.

## MIP-Fair (Etapa 3, pieza 3) — 2026-10-20

Archivo `simulator/mip_fair.py`, clase `MIPFairPolicy(Policy)`, política `--policy mip_fair`; tests
`tests/test_mip_fair.py` (7, con CBC). Definición de la tesis (l. 891): MIP por ventana con la restricción
Gini (eq:fair_const) sobre $\mathcal{H}_t$.

Modelo por ronda, sobre los mismos candidatos que ILP, jerárquico y BRKGA (`brkga_policy.build_candidates`)
y las mismas restricciones de asignación del ILP (pedido ≤ 1 ruta, repartidor ≤ 1 ruta):

- **Ingresos proyectados lineales.** Como un repartidor toma a lo sumo una ruta por ronda,
  $w_c = w_c^0(1-\sum_r x_{cr}) + \sum_r x_{cr}\,w_c(r)$ es lineal en las binarias. Base `hourly`
  ($w_c(r) = (\text{earn}_c + \text{pago}_r)/((\text{active}_c + tt_r)/60)$, la base del Gini de la tesis) o
  `total`. Pago plano `pay_per_order × |r|` (la tarifa eq:tariff sigue pendiente).
- **Gini linealizado.** $G(w)\le\alpha \iff \sum_{i<j} d_{ij} - \alpha\, n \sum_c w_c \le 0$ con
  $d_{ij} \ge \pm(w_i - w_j)$. Exacto para esta dirección de la desigualdad.
- **Elástica.** Una holgura $v \ge 0$ escalada por $n\,W_{ref}$ (adimensional, "exceso de Gini"): ninguna
  ronda es infactible y $v^* > 0$ dice cuánto no pudo cumplirse $\alpha$ en esa ventana.
- **Lexicográfico en tres solves** (cada etapa fija la anterior en su óptimo):
  `mipfair_priority=fairness` → min $v$ › max cobertura › min (λ·tt + μ·tardanza);
  `coverage` → max cobertura › min $v$ › desempate. `fairness` es la lectura fiel de eq:fair_const como
  restricción dura; `coverage` es la lectura "dentro de la restricción de cobertura" que usa BRKGA-Fair.
- Verificado por fuerza bruta en el toy: con $\alpha=0$ el resultado coincide con el óptimo lexicográfico
  exhaustivo en ambas prioridades y ambas bases; con $\alpha=1$ cubre 4 de 4 como el ILP.

Parámetros: `mipfair_alpha` (0,30 por defecto, criterio B), `mipfair_priority`, `mipfair_basis`,
`mipfair_cand_top_k`; reusa `ilp_solver` e `ilp_time_limit_sec` (CBC por defecto, Gurobi disponible).
Registro por ronda en `policy.rounds`: cobertura, $v^*$, Gini antes y después, tiempo de solve.

Alcance declarado (decisiones del autor):
1. El Gini se evalúa sobre los repartidores **libres** de la ronda, que es lo que lleva `state['H_t']`. Para
   evaluarlo sobre todos los conectados (incluidos los ocupados, con $w$ fijo) hay que ampliar el estado en
   `simulator._dispatch_event` con las historias de todos; cambio pequeño, no hecho.
2. eq:minwage (salario mínimo esperado) y eq:routebalance (κ) no están. Ambas entran como holguras
   elásticas adicionales en el mismo modelo si el autor las quiere en el paper.
3. Para el barrido de α de la Etapa 4, la prioridad `fairness` produce la curva Pareto esperada
   (cobertura cae al apretar α); con `coverage` la cobertura no cambia y solo se mueve el exceso.

## Pay-BRKGA (Etapa 3, pieza 4) — 2026-10-20

Archivo `simulator/pay_brkga.py`, clase `PayBRKGAPolicy(BRKGAPolicy)`, política `--policy pay_brkga`; tests
`tests/test_pay_brkga.py` (8). Definición de la tesis (l. 892 y eq:cost_plus): BRKGA biobjetivo cobertura +
$F_{\text{Deficit}}$ que además decide el pago de cada ruta dentro de un rango acotado alrededor de la tarifa.

- **Cromosoma:** claves de pedidos | claves de repartidores | un gen de pago por repartidor libre. El gen se
  mapea a un multiplicador $m_c \in [1-\delta, 1+\delta]$ (`paybrkga_pay_range`, 0,30 por defecto) y la
  oferta es `pay_per_order × |r| × m_c`. Con la tarifa plana actual el multiplicador escala todo el pago;
  cuando entre eq:tariff ($\pi_0 + \pi_1 d$) debe aplicarse solo a $\pi_1$, como pide la tesis.
- **Decodificador:** el del padre (`brkga_score`). Pay-BRKGA cambia a quién se paga cuánto, no cómo se
  construyen las rutas.
- **Fitness escalarizado** (menor es mejor, términos en unidades de fracción de cobertura):
  $(1 - E[\text{cubiertos}]/n) + \lambda_{def}\,F_{\text{Deficit}}^{proj} + \lambda_{pay}\,(\sum \text{pago}/\sum \text{tarifa} - 1) + 10^{-3}\,\overline{tt}/20$.
  $E[\text{cubiertos}]$ usa el **mismo modelo de aceptación** del simulador (`cfg.acceptance_mode`, p. ej.
  `logit_ppk`): subir el pago compra cobertura solo si el modelo lo dice; con aceptación `auto` el pago solo
  mueve $F_{\text{Deficit}}$ y el costo. $F_{\text{Deficit}}^{proj}$ = fracción de repartidores libres cuyo
  ingreso por hora, tras la ronda y suponiendo aceptación, queda bajo `min_wage_hourly` (o
  `guaranteed_pay_per_hour`, como en `metrics.py`).
- Verificado en el toy: con solo $\lambda_{pay}$ todas las ofertas quedan bajo la tarifa; con solo
  $\lambda_{def}$ el repartidor a 8/h (mínimo 15) recibe oferta por encima de la tarifa y sale del déficit;
  cobertura esperada = cobertura × tasa de aceptación bajo `fixed`.
- Registro por ronda: `pay_ratio`, `multipliers`, `expected_covered`, `f_deficit_proj`.

Parámetros: `paybrkga_pay_range`, `paybrkga_lambda_deficit` (0,5), `paybrkga_lambda_pay` (0,2); CLI
`--pay-range`, `--lambda-deficit`, `--lambda-pay`. El barrido de $\lambda_{pay}$ (y de $\lambda_{def}$)
traza la curva costo-de-la-equidad de la Etapa 4.

Decisiones del autor: (1) la escalarización es una suma ponderada, no un frente Pareto explícito (NSGA
style); basta para el barrido de λ que pide la tesis, y se declara. (2) Pay-BRKGA no usa el déficit en el
decodificador (eso es BRKGA-Fair); combinar ambos es una subclase trivial si se quiere. (3) Los pesos por
defecto son provisionales hasta la Etapa 4.

## Cierre de la Etapa 3 (2026-10-20)

Las cuatro piezas (porte BRKGA, BRKGA-Fair, MIP-Fair, Pay-BRKGA) corren bajo `Policy.assign` con los
mismos candidatos de `routing.py`, la misma ventana, la misma aceptación y el mismo pago base que greedy,
fair_greedy, ILP y jerárquico. 75 tests unitarios verdes (por archivo). Lo que falta de la Etapa 3 según
el plan: verificación en una instancia real (bloqueada por hardware) y las decisiones del autor listadas en
cada sección.

## Decisiones tomadas (2026-10-20, por encargo del autor: "toma la decisión tú")

| # | Decisión | Tomada | Justificación | Dónde |
|---|---|---|---|---|
| E1 | Puntaje del decodificador BRKGA | `finish_per_order` (default); regla `finish` al suplemento | Con `finish` ningún lote gana a un singleton del mismo repartidor: el MIC 2026 nunca agrupó. ILP y jerárquico sí agrupan; la comparación debe ser con lotes. | `config.brkga_score` |
| E2 | Base del déficit (BRKGA-Fair) | `hourly` | Misma base que F_Gini (eq:gini) y eq:fair_const; `total` castiga conectarse tarde, no estar mal servido. | `config.brkga_fair_basis` |
| E3 | Peso del déficit (BRKGA-Fair) | 10 min default; barrido {0, 5, 10, 20, 40} en la Etapa 4; myopic-fair = `brkga` liso | 10 min ≈ media ruta típica; la tesis pide la curva, no un valor. | `config.brkga_fair_weight` |
| E4 | Alcance del Gini (MIP-Fair) | todos los conectados (`mipfair_scope=all`), ocupados con ingresos fijos | eq:fair_const es sobre C; los libres de una ronda son un subconjunto sesgado. Requirió `H_all` en `simulator._dispatch_event`. | `config.mipfair_scope`, `simulator.py` |
| E5 | Prioridad y restricciones extra (MIP-Fair) | equidad › cobertura; sin eq:minwage ni eq:routebalance en el paper | Lectura dura de eq:fair_const; única que traza Pareto al barrer α. Salario mínimo → Pay-BRKGA y F_Deficit; balance de rutas → tesis. | `config.mipfair_priority` |
| E6 | Pay-BRKGA: forma y pesos | suma ponderada; rango ±30 % provisional; λ_def 0,5; barrido λ_pay {0,1; 0,2; 0,5; 1} | Una acción por ronda: un frente no es accionable; eq:cost_plus pide barrer λ. Rango a ajustar con V116 en la Etapa 4. | `config.paybrkga_*` |

Registradas también en la slide 13 del deck `docs/mdrp-jerarquia-objetivos.html` (sección 11 de su copia `.md`).

### E5 revisada (2026-10-20, noche, piloto de la Etapa 4)

| # | Decisión | Tomada | Justificación | Dónde |
|---|---|---|---|---|
| E5' | Prioridad lexicográfica de MIP-Fair | **cobertura › exceso de Gini › desempate** (`mipfair_priority=coverage`, nuevo default); la variante equidad › cobertura pasa al suplemento como ablación `mipfair_a030_fairfirst` | En el piloto (Pereira, 12:00–14:00, α = 0,30, alcance `all`) la variante equidad-primero entregó **cobertura 0,000**: con todos los repartidores en 0 COP cualquier asignación sube el Gini, así que "no asignar" minimiza v en cada ronda y el sistema nunca arranca. Con cobertura primero, el exceso de Gini decide *quién* recibe cada ruta entre las asignaciones de cobertura máxima, que es la palanca de equidad; α = 1 recupera al ILP corporativo y α → 0 minimiza el Gini proyectado en cada ronda. | `config.mipfair_priority`, `run.py --mipfair-priority`, `batch_paper.py` |
| E4' | Linealización del Gini en MIP-Fair | Misma restricción, construida por bloques: pares fijo–fijo como constante, pares libre–fijo como términos lineales en x (el ingreso de un repartidor libre toma uno entre finitos valores), pares libre–libre con variables d_ij | La versión de todos los pares es O(n²) por ronda: con 188 conectados (Pereira) no terminó dos horas en 4 min; en Bogotá (2.650) serían 3,5 millones de pares por ronda. La reformulación es exacta (los 8 tests contra fuerza bruta siguen verdes) y baja la ronda a 0,2 s en Pereira. Además `get_solver` prefiere `pulp.GUROBI` (API en memoria) sobre `GUROBI_CMD` (archivos LP). | `mip_fair.py::_solve`, `ilp_policy.get_solver` |
