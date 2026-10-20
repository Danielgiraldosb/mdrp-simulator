# Código de los métodos: dónde está y qué lo corre (Etapa 0, entregable 2)

Fecha: 2026-10-20. Inventario hecho sobre `C:/MDRP` (repo `mdrp-simulator`, rama master) y la carpeta
`articulo MDRP/` (materiales MIC 2026, commit 7ee5ac2).

## Resumen en una línea

Lo que la tesis llama **BRKGA-Fair, Pay-BRKGA y MIP-Fair no existe como código en ningún lado de este equipo**:
son entregables planeados (tesis, hitos P4a/P4b, líneas 1147–1149). Lo que sí existe son los *baselines*:
BRKGA-Coverage/Travel con horizonte rodante y los heurísticos corporativos (MIC 2026), más greedy, fair_greedy,
cinco ILP y el jerárquico en `simulator/`. El GRASP es de un artículo anterior (LNCS 14754, 2024) y su código
tampoco está en el repo.

## Inventario por método

| Método (nombre en la tesis) | ¿Existe? | Dónde | Qué lo corre | Objetivo / qué le falta |
|---|---|---|---|---|
| Corporate baseline (greedy del más cercano) | sí | `articulo MDRP/MDRPcorporativo_lookahead.py` (552 l), `Corporate lookahead/corporativo_lookahead.py` (852 l), `Corporate maxcover/corporativo_maxcover.py` (837 l) | scripts autónomos (bucle propio de tiempo, ventanas de 2 min, sin SimPy) | cobertura; `maxcover` selecciona candidatos por score de cobertura, `lookahead` mira demanda futura. Sin pago, sin aceptación, sin equidad. |
| BRKGA-Coverage | sí | `articulo MDRP/MDVRPTW_BRKGA/brkga_coverage.py` (274 l) + `decoder.py`, `operators.py`, `utils.py` | `python brkga_coverage.py --instance Instancia_k` (estático, un solo BRKGA sobre el día completo) | fitness = cobertura |
| BRKGA-Travel | sí | `MDVRPTW_BRKGA/brkga_travel.py` | ídem | fitness = tiempo de viaje medio por pedido |
| BRKGA + horizonte rodante | sí | `MDVRPTW_BRKGA/brkga_rolling_horizon.py` (523 l), clase `BRKGARollingHorizon(orders, couriers, stores, instance_info, params, fitness_type='coverage'|'travel')` | `run_all_instances_rolling_horizon.py` (24 instancias) | ventanas de 2 min "matching MDRPcorporativo"; un BRKGA por ventana |
| GRASP | no en el repo | artículo `giraldo2024grasp`, LNCS 14754 | — | pedir al autor dónde está el código (¿repo PyLO?) |
| BRKGA-Fair | **no** | definido solo en la tesis (l. 890): BRKGA-Coverage + decodificador que usa el déficit de $\mathcal{H}_t$ | — | por construir en Etapa 3 |
| MIP-Fair | **no** | tesis l. 891: MIP por ventana con la restricción Gini (eq:fair_const) | — | por construir; lo más cercano es `simulator/ilp_policy.py` (ver abajo) |
| Pay-BRKGA | **no** | tesis l. 892: BRKGA biobjetivo cobertura + $F_{\text{Deficit}}$ (λ) | — | por construir |
| greedy, fair_greedy | sí | `simulator/policies.py` | `simulator/run.py`, `batch_*.py` | fair_greedy prioriza por déficit acumulado (cercano a la idea de BRKGA-Fair pero greedy) |
| 5 ILP (PuLP; Gurobi opcional) | sí | `simulator/ilp_policy.py` | ídem | cobertura como objetivo primario; `cfg.objective` solo desempata (max_throughput, min_lateness, min_cost, …). **No tiene restricción Gini ni salario mínimo**: para MIP-Fair hay que añadir (eq:fair_const)/(eq:minwage) sobre $\mathcal{H}_t$, no solo un desempate. |
| 4 políticas de mdrp-sim (Quintero) | sí | `simulator/mdrpsim_policies.py` | ídem | portadas fielmente; objetivo throughput vs lateness |
| Jerárquico cov › lat › eq › cost | sí | `simulator/hier/`, `hier_policy.py` | `batch_hier_clusters.py` | candado por objetivo; 240 instancias Grubhub |

Conteo de confirmación: `grep -i 'gini|fair|pay|accept'` sobre los 9 archivos de `MDVRPTW_BRKGA/` y los 3
corporativos da 0 coincidencias relevantes (solo `dlambda` del haversine y `key=lambda`). Ninguno modela
pago, aceptación ni equidad.

## Interfaz de los scripts MIC 2026 (lo que habría que reproducir en `simulator/`)

- **Entrada:** `load_instance('Instancia_k')` lee `Instancias/Instancia_k/{couriers,orders,stores}.csv`.
  Columnas: `orders`: `order_id, store_id, drop_off_lat, drop_off_lng, placement_time, preparation_time,
  ready_time, expected_drop_off_time` (horas `H:MM:SS` desde el inicio del día); `couriers`: `courier_id, vehicle,
  on_lat, on_lng, on_time, off_time`; `stores`: id + lat/lng.
- **Las 24 instancias de `articulo MDRP/Instancias/` son byte a byte las mismas de `real_instancies/`**
  (verificado `cmp` en Instancia_0 e Instancia_23, los tres CSV). Hay una sola fuente de datos de Bogotá.
- **Distancias:** haversine (km). **Velocidades** (`SPEED_MAP`, km/h): motorcycle 25, bicycle 20, car 15,
  walking 5; desconocido → 15. Es la fuente para la decisión "velocidad por vehículo" de la Etapa 2.
- **Ventana:** 2 minutos fijos. SLA = `expected_drop_off_time` (60 min después de `placement_time` en los
  datos que vi). Sin aceptación: toda asignación se ejecuta.
- **Salida:** un `resultados_Instancia_k_*.xlsx` por instancia en `outputs_*/` y `MDVRPTW_BRKGA/results/`.
  Los consolidados están en `Resultados consolidados.xlsx` y `Resultados finales MIC 2026.xlsx`.

## Consecuencias para las decisiones de la Etapa 0

1. **Decisión 1 (¿un simulador o dos?)**: no hay "simulador anterior" que mantener para los métodos fair,
   porque esos métodos no existen. El BRKGA sí tiene su propio bucle (no SimPy); portarlo a `Policy.assign`
   sobre los candidatos de `routing.py` es trabajo de la Etapa 3, y es la única forma de que comparta ventana,
   aceptación y métricas con greedy/ILP/jerárquico. Recomendación firme: **un solo simulador**.
2. **Decisión 2 (unidades de pago)**: ningún script MIC maneja pago; la tarifa (eq:tariff) entra por primera
   vez con el loader de Bogotá. COP en Bogotá, mdrplib en Grubhub, aceptación en pago/km normalizado.
3. **Decisión 3 (Grubhub)**: el jerárquico ya corrió las 240; el BRKGA solo las 24 de Bogotá. Si Grubhub entra,
   es solo con las políticas que ya viven en `simulator/`.

## Resuelto por el autor (2026-10-20)

- No hay más código que el del repo. El GRASP se cita como trabajo previo y no se reimplementa.
- BRKGA-Fair, Pay-BRKGA y MIP-Fair se construyen desde cero en la Etapa 3, junto con el porte del
  BRKGA-Coverage (decoder + rolling horizon) a `Policy.assign`. Un solo simulador: `simulator/`.
- Consecuencia: la Etapa 3 son cuatro piezas nuevas, no un porte; ver el calendario revisado en `plan.md`.
