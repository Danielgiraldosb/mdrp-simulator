# Simulador MDRP adaptado a mdrplib

Copia del simulador de eventos discretos (DES) de la tesis, reescrita para
trabajar **nativamente** con las 240 instancias de
[`grubhub/mdrplib`](https://github.com/grubhub/mdrplib), incluidas en este
repo en [`../public_instances/`](../public_instances) para que el clon quede
autocontenido. Cómo está construida cada instancia (el procedimiento de
reducción de tamaño `o100`/`o50`/`r50`, los horarios `s1`/`s2`, los factores
de velocidad `t100`/`t75` y de preparación `p100`/`p125`, y la definición
completa del problema) está documentado en detalle en
[`../MDRPInstances.pdf`](../MDRPInstances.pdf?raw=true) ("Meal Delivery
Routing: The Grubhub Instances", el documento oficial de mdrplib) y en
[`../README.md`](../README.md); el evaluador de referencia está en
[`../MDRP_code/`](../MDRP_code).

También se incluye [`../real_instancies/`](../real_instancies): las 24
instancias originales (datos reales de Bogotá, formato CSV) del simulador
de la tesis previo a esta adaptación a mdrplib
(`mdrp-sim-master`, ver la comparación detallada más abajo) — no las usa
ningún script de este repo todavía, se dejan aquí para trabajo futuro.

## Qué cambia respecto al simulador original ("simulador plataforma")

El simulador original fue construido primero para otro dataset (24 instancias
CSV estilo `mdrp-sim-master`, coordenadas lat/lon de Bogotá) y luego se le
agregó un *loader* para leer mdrplib proyectando su grilla sintética de
metros a lat/lon. Esa proyección escondía tres problemas que esta copia
corrige, además de reorganizar el código para que viva de forma autónoma
junto a `public_instances/`:

1. **La velocidad de la instancia (`t100`/`t75`) se ignoraba.**
   `distance.py` original calculaba el tiempo de viaje con una tabla fija de
   velocidades por "tipo de vehículo" (concepto que mdrplib ni siquiera
   tiene), totalmente desconectada del `meters_per_minute` propio de cada
   instancia. Dos instancias idénticas salvo por el factor de velocidad
   producían el mismo tiempo de viaje. Aquí, [`distance.py`](distance.py)
   reproduce exactamente la fórmula del evaluador oficial:
   `tt = ceil(dist_metros / meters_per_minute)`, usando el `meters_per_minute`
   real de cada instancia (ver [`loader.py`](loader.py)).

2. **Las coordenadas se mantienen en su sistema nativo (metros, planas).**
   No hay proyección a lat/lon ni Haversine: `Location` es simplemente
   `(x, y)` en metros, igual que `orders.txt`/`restaurants.txt`/`couriers.txt`.
   Esto evita una fuente de distorsión y mantiene el reloj en **minutos**
   (la unidad nativa de mdrplib) en vez de convertir todo a segundos.

3. **Las dos SLA de la instancia se usan para lo que son.**
   `instance_parameters.txt` trae `target click-to-door` (meta blanda, usada
   para calcular *lateness*/*overage*) y `maximum click-to-door` (límite
   duro). El simulador original solo usaba la meta blanda más una tolerancia
   inventada (`late_tolerance_sec`). Aquí las políticas (`policies.py`,
   `ilp_policy.py`) usan `maximum click-to-door` como corte duro de
   factibilidad y `target click-to-door` solo para medir atraso — tal como
   hace [`MDRP_code/compute_performance_summary.py`](../MDRP_code/compute_performance_summary.py).

4. **Se modela el tiempo de servicio de recogida (`pickup service minutes`).**
   El simulador original esperaba a que el pedido estuviera listo pero no
   cobraba el tiempo de manejo en el restaurante. Aquí
   (`simulator.py::CourierActor._execute_route`) se cobra una vez por parada
   en el restaurante, igual que la contabilidad del evaluador oficial
   (`time_picking[d] += pickup_service_minutes`, una vez por asignación).

5. **`ready_time` ya no se sobrescribe.** En el original, el campo
   `ready_time` del pedido (dato de entrada: minuto en que la comida está
   lista) se reutilizaba en tiempo de ejecución para guardar el momento real
   de recogida, lo que distorsionaba `ready-to-door`. Aquí `ready_time` es
   inmutable y se añadió `picked_up_at` aparte, así que `ready_to_door` y
   `ready_to_pickup` coinciden exactamente con las columnas que reporta el
   evaluador oficial.

6. **La cancelación y la aceptación estocástica (extensiones propias de la
   tesis) quedan apagadas por defecto.** mdrplib no tiene noción de pedidos
   cancelados ni de repartidores que rechazan una ruta ya asignada — el
   evaluador oficial asume que toda ruta se ejecuta tal cual. Por defecto
   `enable_cancellation=False` y `acceptance_mode='auto'` (siempre acepta),
   para que una corrida "de fábrica" reproduzca esa suposición. Ambas
   extensiones siguen disponibles (`--cancellation`, `--acceptance-mode
   fixed|logistic`) para estudiar la variante estocástica de la tesis sobre
   los mismos datos — ver el punto 10 sobre cómo se independizó la
   aceptación de la política de asignación.

7. **Pago garantizado por hora, con *true-up*.** Cada instancia trae
   `guaranteed pay per hour`. Antes se usaba solo como umbral informativo
   (`F_Deficit`); ahora `metrics.py` replica el mecanismo real del evaluador
   oficial: si `earnings` de un repartidor por sus pedidos no alcanza
   `shift_hours * guaranteed_pay_per_hour`, se le paga ese mínimo
   (`proportion_trueup`, `total_payment`). `F_Deficit` se dejó como una
   comparación aparte contra un umbral externo configurable (`--min-wage`),
   independiente de la garantía propia de la plataforma.

8. **Ruta de instancias relativa, no hardcodeada.** Como este simulador vive
   dentro de `mdrplib-master/`, junto a `public_instances/`, ya no hace falta
   apuntar a una ruta absoluta de OneDrive que podía quedar desactualizada.

9. **`max_bundle_size` es transversal a las 7 políticas, no solo a 4 de
   ellas.** Hasta la primera versión de esta copia, `GreedyPolicy` y
   `FairGreedyPolicy` ignoraban por completo `cfg.max_bundle_size` (siempre
   asignaban un pedido a la vez), y el objetivo ILP `max_equity` tenía su
   propio camino de resolución (relajación LP) codificado como
   singleton-only sin importar ese parámetro — es decir, de 7
   políticas/variantes, solo 4 (los otros 4 objetivos del ILP) realmente
   agrupaban pedidos. Se extrajo la construcción de rutas/bundles y el
   chequeo de factibilidad acumulada a un módulo compartido
   ([`routing.py`](routing.py)), que ahora usan por igual `GreedyPolicy`,
   `FairGreedyPolicy` (`best_route_for_courier`: "pedido factible más
   cercano" generalizado a bundles) y las 5 variantes del ILP
   (`generate_store_routes` + `route_feasibility`, incluyendo `max_equity`,
   que pasó de relajación LP continua y singleton-only a programación
   entera binaria sobre rutas — pierde la garantía de integralidad
   automática por unimodularidad total que tenía el caso singleton puro,
   pero CBC resuelve el MIP resultante en milisegundos igual que los otros
   4 objetivos, así que no hay costo práctico). El valor por defecto de
   `max_bundle_size` se fijó en **3** (antes 1 = sin bundling).

10. **El criterio de aceptación del repartidor es transversal a las 7
    políticas, no una variante acoplada a una sola de ellas.** Antes de
    este cambio, Greedy/FairGreedy/las 5 del ILP solo podían usar una tasa
    de aceptación fija por repartidor, y la fórmula logística solo existía
    dentro de `LogisticAcceptancePolicy`, que a su vez solo funcionaba
    envolviendo la asignación de `GreedyPolicy` — no había forma de correr,
    por ejemplo, el ILP con `max_equity` combinado con aceptación
    logística. Se extrajeron las 3 reglas de aceptación a un módulo nuevo
    ([`acceptance.py`](acceptance.py)):
    - `auto` — siempre acepta (el supuesto de mdrplib, y el nuevo default).
    - `fixed` — la tasa propia de cada repartidor, sorteada una vez al
      cargar la instancia entre `[min_acceptance_rate, max_acceptance_rate]`
      (`loader.py`); con ambos extremos iguales equivale a una probabilidad
      única para todos.
    - `logistic` — la sigmoide de pago/distancia/fatiga acumulada
      (coeficientes ahora en `Config`, antes hardcodeados en
      `LogisticAcceptancePolicy`).

    `Policy.acceptance_prob()` quedó implementado una sola vez, en la clase
    base (`policies.py`), delegando al modelo que indique
    `cfg.acceptance_mode` — así las 7 políticas de asignación (Greedy,
    FairGreedy, los 5 objetivos del ILP) heredan cualquiera de los 3 modos
    sin tocar su propia lógica de asignación. `LogisticAcceptancePolicy`
    desapareció como política separada; `--policy` ahora solo elige
    asignación (`greedy | fair_greedy | ilp`) y `--acceptance-mode` elige
    aceptación por separado, con `batch_sensitivity.py --acceptance-modes`
    para barrerlas como una dimensión más del diseño.

11. **Las 7 políticas de asignación comparten ahora un único objetivo
    verdadero: maximizar cobertura.** Antes, `max_throughput` era la
    excepción entre los 5 objetivos del ILP — sin un término dominante,
    podía dejar un pedido sin cubrir si ninguna ruta factible resultaba
    "rentable" bajo sus pesos λ/μ, mientras que `min_lateness`, `min_cost`
    y `max_equity` ya maximizaban cobertura primero (gracias al peso
    M=τ<sup>max</sup>) y solo usaban atraso/costo/equidad para desempatar.
    Se le agregó a `max_throughput` el mismo término M·|r| dominante, así
    que ahora los 5 objetivos del ILP comparten exactamente la misma
    cobertura óptima — `cfg.objective` deja de ser "qué optimizar" y pasa a
    ser, con propiedad, "qué criterio de desempate usar entre las
    soluciones de cobertura máxima". `GreedyPolicy`/`FairGreedyPolicy` se
    documentaron explícitamente como heurísticas voraces clásicas para ese
    mismo objetivo de cobertura (sin garantía de alcanzarlo, a diferencia
    del ILP) — ninguna de las dos tenía ni tiene una función objetivo
    propia, solo una regla de prioridad distinta. El valor de cobertura de
    cualquier corrida (ILP o heurística) siempre está disponible en
    `n_delivered`/`coverage_rate` (`metrics.py`), calculado igual para las
    7 políticas — así que un estudio de sensibilidad puede compararlas
    sobre esa base común y leer costo, atraso y equidad como resultados,
    no como lo que cada una perseguía.

12. **Se instrumentó el tiempo real (wall-clock) de cómputo de cada
    política, separado del reloj simulado.** `cfg.rolling_horizon` (2 min
    por defecto) es tiempo *simulado*: SimPy avanza su reloj virtual sin
    importar cuántos segundos reales tarde Python en resolver
    `policy.assign()` — nada en el simulador "cobraba" ese cómputo contra
    la ventana de 2 minutos, así que no había forma de verificar si una
    política sería viable en un sistema de despacho real que de verdad
    tuviera que decidir cada 2 minutos reales. Ahora `Dispatcher` mide con
    `time.perf_counter()` cada llamada a `assign()`
    (`results['dispatch_times']`, `simulator.py`), y `compute_metrics()`
    reporta `solve_mean/std/min/p10/median/p90/max` (segundos reales por
    ronda) y `solve_calls`; `run.py`/`batch_sensitivity.py` además miden
    `wall_clock_sec` (duración total de `env.run()`) y lo pasan a
    `compute_metrics(..., wall_clock_sec=...)`. `run.py` imprime una
    comparación explícita de `solve_max` contra el presupuesto real en
    segundos (`rolling_horizon * 60`). En la instancia de prueba, Greedy
    resuelve cada ronda en ~0.0001s y el ILP en ~0.02-0.03s en promedio
    (con picos puntuales de hasta ~0.47s en `max_coverage`) — órdenes de
    magnitud por debajo del presupuesto de 120s, pero ahora es un dato
    medido por cada corrida, no un supuesto.

13. **Corregido: la simulación no era reproducible, ni siquiera con el mismo
    `seed`.** `simulator.py` usaba el módulo global `random` (no una
    instancia sembrada con `cfg.seed`) para el retraso de decisión de cada
    repartidor (`CourierActor._decide`) y para el umbral de cancelación
    opcional — ambos dependían de la entropía del sistema operativo al
    iniciar el proceso de Python, así que dos corridas "idénticas" (misma
    instancia, misma política, mismo `seed`) podían dar resultados
    ligeramente distintos cada vez. `World.start()` ahora llama
    `random.seed(cfg.seed)` una sola vez, antes de arrancar cualquier actor,
    dejando determinista toda la secuencia de sorteos posterior. Esto se
    descubrió investigando una corrida que no se podía reproducir al
    intentar depurarla (ver punto 14).

14. **Se quitó el límite de tiempo del solver ILP — cada ronda corre hasta
    la solución óptima real, no una aproximada por corte de reloj.**
    `ilp_time_limit_sec` pasó de `30.0` a `None` por defecto
    (`config.py`); `ilp_policy.py::_get_solver()` ya no le pasa ningún
    `timeLimit` a CBC/GUROBI/CPLEX cuando es `None`, así que el solver
    busca hasta probar optimalidad (o agotar su propia búsqueda), en vez de
    devolver lo que tuviera a mano cuando se acabara un cupo arbitrario de
    segundos. Esto se decidió tras encontrar, en el primer intento del lote
    de 1,200 corridas, un puñado de rondas (3 de ~276,000) que tardaron
    minutos reales pese al límite de 30s configurado — investigando la
    causa (ver punto 13 sobre el bug de reproducibilidad, corregido en el
    camino) se confirmó que NO era un problema de tamaño del modelo
    (los conteos de pares repartidor-ruta en esas rondas eran pequeños,
    &lt;150) sino variabilidad interna conocida del propio solver CBC
    (ramificación y acotamiento puede tardar drásticamente distinto entre
    corridas de la misma entrada, un fenómeno documentado en la literatura
    de programación entera) — y que, sin límite de tiempo, la misma ronda
    que antes tardó 2,953s resolvió el día completo en 4.76s. Se consideró
    y descartó una salvaguarda de tiempo real con reemplazo silencioso por
    Greedy: contaminaría los resultados del ILP con soluciones que no son
    del ILP, exactamente lo que un análisis de sensibilidad no puede
    permitirse. El costo de este cambio es que, en teoría, una ronda
    genuinamente difícil podría tardar un tiempo no acotado — en la
    práctica, la evidencia hasta ahora es que esto es raro y los tiempos de
    cómputo típicos siguen siendo de milisegundos a segundos.

### Qué NO se trajo de la copia original (y por qué)

- `instance_generator.py` (generador sintético de Bogotá) y
  `instance_loader.py` (el otro formato CSV, `mdrp-sim-master`): no son
  "las instancias y características que plantean en este repositorio" —
  pertenecen a otro dataset.
- `osrm_service.py`: nunca estaba conectado al motor de simulación (se
  referenciaba solo en un comentario); enrutar sobre calles reales de
  Bogotá no tiene sentido para una grilla sintética de metros.
- `db_export.py`: la exportación a SQLite/Postgres no es necesaria para un
  análisis de sensibilidad tabular; `batch_sensitivity.py` ya produce un CSV
  consolidado, que es más directo para análisis estadístico (R, pandas, etc).

## Estructura

```
simulator/
  config.py            Parámetros de simulación (minutos, metros)
  models.py             Location, Order, Courier, EquityHistory
  distance.py            Distancia euclidiana + tiempo de viaje (fórmula oficial)
  loader.py               Lee una instancia mdrplib + helpers del diseño factorial
  routing.py               Rutas/bundles + factibilidad acumulada (compartido por todas las políticas)
  acceptance.py            Criterios de aceptación (auto/fixed/logistic), transversal a todas las políticas
  policies.py             GreedyPolicy, FairGreedyPolicy
  ilp_policy.py            ILPPolicy (PuLP): 5 objetivos, bundling transversal (routing.py)
  simulator.py             Motor DES (SimPy), arquitectura por actores
  metrics.py               Métricas de servicio, económicas y de equidad
  run.py                   CLI para una corrida individual
  batch_sensitivity.py     CLI para barrer el diseño factorial (240 instancias)
  requirements.txt
```

## Uso rápido

```bash
cd simulator
pip install -r requirements.txt

python run.py --list                                   # ver las 240 instancias
python run.py --instance 0o100t100s1p100                # corrida base (política greedy)
python run.py --instance 0o100t100s1p100 --ilp --objective max_equity
python run.py --instance 0o100t100s1p100 --compare       # greedy vs fair_greedy
python run.py --instance 0o100t100s1p100 --bundle 3 --save
python run.py --instance 0o100t100s1p100 --ilp --objective max_equity --acceptance-mode logistic
```

## Análisis de sensibilidad

Los nombres de instancia codifican 5 factores: semilla, tamaño (`o100`/`o50`/`r50`),
velocidad (`t100`/`t75`), horario (`s1`/`s2`) y preparación (`p100`/`p125`).
`loader.parse_instance_name()` los descompone automáticamente, y
`batch_sensitivity.py` los usa para filtrar y para etiquetar cada fila de
resultados — así puedes aislar el efecto de un solo factor dejando los demás
fijos, o correr todo el diseño cruzado con una o varias políticas:

```bash
# Aislar el efecto de la velocidad (t100 vs t75), todo lo demás fijo:
python batch_sensitivity.py --seeds 0 --sizes o100 --schedules s1 --preps p100 \
       --speeds t100 t75 --policies greedy --out speed_only.csv

# Barrido completo (240 instancias) con dos políticas:
python batch_sensitivity.py --policies greedy fair_greedy --out sensitivity_results.csv

# Los 5 objetivos ILP, factor de tamaño únicamente, 3 semillas:
python batch_sensitivity.py --seeds 0 1 2 --policies ilp \
       --objectives max_coverage max_throughput min_lateness max_equity min_cost \
       --out ilp_objectives.csv
```

El CSV resultante trae una fila por corrida, con columnas de factor
(`seed`, `size`, `speed`, `schedule`, `prep`), la política/objetivo usados, y
todas las métricas de `metrics.compute_metrics` (cobertura, click-to-door,
ready-to-door, ready-to-pickup, tamaño de bundle, pago total, *true-up*,
F_Gini, F_MaxMin, F_Orders, F_Deficit, F_Dist) — listo para abrir en pandas/R
y correr ANOVA, regresión o un diseño factorial formal.

## Supuestos a documentar en la tesis

- El retraso de decisión del repartidor (`decision_mean_min`/`decision_std_min`,
  ~20s ± 10s) y los coeficientes `accept_beta0..3` de `acceptance_mode='logistic'`
  son ilustrativos — reemplázalos por estimaciones MLE si se dispone de datos
  reales de aceptación.
- `late_tolerance_min` (0 por defecto) es la única holgura que se permite
  por encima del `maximum click-to-door` publicado en la instancia; subirlo
  es una forma válida de estudiar sensibilidad a la dureza de la SLA.
- El reposicionamiento proactivo de repartidores ociosos
  (`--reposition`) es una extensión propia de la tesis, no parte de mdrplib.
- `_LAMBDA_COST`/`_MU_DELAY` en `ilp_policy.py` (penalización por minuto de
  viaje y de atraso en `max_throughput`) se recalibraron a `0.01`/`0.02`
  tras detectar que el valor heredado del simulador original (`0.06`/`0.12`
  — una constante por SEGUNDO de la tesis, simplemente multiplicada por 60 al
  pasar a minutos) hacía que casi cualquier pedido individual tuviera
  beneficio neto negativo frente a la recompensa de "+1 por pedido cubierto",
  colapsando la cobertura a ~20% independientemente de la instancia. Con la
  nueva calibración, una ruta típica (según la escala de distancias/velocidad
  de mdrplib) sigue siendo rentable, y solo las rutas con viaje o atraso muy
  por encima de lo típico se descartan — preservando el propósito de
  `max_throughput` (una función objetivo genuinamente sensible al costo, a
  diferencia de `min_lateness`/`min_cost`, que priorizan cobertura primero).
