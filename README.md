# Simulador MDRP adaptado a mdrplib

Este repositorio tiene dos partes: los datos de instancias del *Meal
Delivery Routing Problem* (MDRP) y el simulador propio que corre sobre
ellas para comparar 11 modelos de asignación domiciliario-pedido. Todo lo
que necesitas para entender de qué trata el repo y qué hace cada cosa está
en este archivo.

## Estructura del repositorio

- **[`simulator/`](simulator)** — el simulador de eventos discretos (DES) y
  todo el análisis de sensibilidad: código, resultados y el dashboard
  interactivo del proyecto. Documentado en detalle más abajo.
- **[`public_instances/`](public_instances)** — las 240 instancias
  oficiales de [`grubhub/mdrplib`](https://github.com/grubhub/mdrplib),
  datos anonimizados de operación real de Grubhub, provistos junto con la
  [H. Milton Stewart School of Industrial & Systems Engineering de Georgia
  Tech](https://www.isye.gatech.edu/) para avanzar la investigación sobre
  este problema. Se derivan de 10 instancias semilla reduciendo su tamaño
  (`o100`: sin reducción, `o50`: 50% menos pedidos muestreando pedidos
  directamente, `r50`: 50% menos pedidos muestreando restaurantes),
  cambiando el horario de domiciliarios (`s1`: histórico, `s2`: turnos
  "optimizados"), aumentando la velocidad de viaje (`t100`: original,
  `t75`: tiempos ×0.75) y aumentando el tiempo de preparación (`p100`:
  original, `p125`: ×1.25). La descripción completa del problema y del
  procedimiento de construcción de cada instancia está en
  [`MDRPInstances.pdf`](MDRPInstances.pdf?raw=true) ("Meal Delivery
  Routing: The Grubhub Instances", el documento oficial de mdrplib).
- **[`MDRP_code/`](MDRP_code)** — el evaluador de referencia oficial de
  mdrplib (`compute_performance_summary.py`), cuya contabilidad el
  simulador replica en varios puntos (ver "Qué cambia respecto al
  simulador original" más abajo).
- **[`real_instancies/`](real_instancies)** — las 24 instancias originales
  (datos reales, coordenadas lat/lng) del simulador de la tesis previo a esta
  adaptación a mdrplib (`mdrp-sim-master`, ver la comparación detallada más
  abajo), una carpeta `Instancia_0`..`Instancia_23` por instancia con
  `couriers.csv` (domiciliario, vehículo, turno), `orders.csv` (pedido,
  tienda, recogida/entrega) y `stores.csv` (ubicación de cada tienda).
  Aunque el material de la tesis las llama "Bogotá", cubren seis ciudades
  (Bogotá, Medellín, Barranquilla, Cali, Bucaramanga, Pereira; tabla en
  `docs/paper-cmdp/instancias_reales.csv`). Las lee
  [`simulator/loader_real.py`](simulator/loader_real.py): `run.py` las detecta
  solo al pasar `--instances-dir real_instancies --instance Instancia_k`
  (proyección plana por instancia, velocidad por vehículo, SLA por pedido,
  pago en COP; aceptación calibrada con `--acceptance-mode logit_ppk
  --regime manual|autoaccept`). Tests: `simulator/tests/test_loader_real.py`,
  `simulator/tests/test_acceptance_ppk.py`.

## El simulador (`simulator/`)

Copia del simulador de eventos discretos (DES) de la tesis, reescrita para
trabajar **nativamente** con las 240 instancias de `public_instances/`.

### Qué es y cómo funciona

#### El problema

El *Meal Delivery Routing Problem* (MDRP): a lo largo de un día operativo hay
restaurantes, domiciliarios con turnos fijos (hora de entrada/salida) y
pedidos que van llegando (cada uno con su restaurante, su cliente, la hora en
que se hizo y la hora en que la comida está lista). El simulador decide, cada
cierto tiempo, qué domiciliario recoge y entrega cuál(es) pedido(s), y mide
qué tan bien queda el servicio: cuántos pedidos se entregan, qué tan rápido,
a qué costo y qué tan parejo queda el reparto de trabajo/pago entre
domiciliarios.

#### Arquitectura: simulación de eventos discretos por actores

El motor es [SimPy](https://simpy.readthedocs.io/) con el reloj en
**minutos** (la unidad nativa de mdrplib, no segundos). Una corrida empieza
en `cfg.sim_start_clock_min` y avanza `cfg.sim_end` minutos (por defecto el
día completo, 1,440 min). Todo vive en `simulator/simulator.py`, organizado
en 4 tipos de actor:

- **`World`** — arma la instancia (pedidos, domiciliarios, restaurantes) y
  arranca a todos los demás actores en el tiempo 0.
- **`UserActor`** (uno por pedido) — "duerme" hasta el `placement_time` del
  pedido y entonces avisa al `Dispatcher` que ya está pendiente. Si
  `cfg.enable_cancellation` está activo (apagado por defecto, porque mdrplib
  no modela cancelaciones) también puede cancelarlo por impaciencia del
  cliente o por un plazo límite de la plataforma — una extensión propia de
  la tesis, no parte del benchmark oficial.
- **`CourierActor`** (uno por domiciliario) — está disponible solo dentro de
  su turno (`on_time`/`off_time`). Cuando el `Dispatcher` le notifica una
  ruta, decide aceptarla o rechazarla (`acceptance.py`) y, si acepta, la
  ejecuta parada por parada: viaja al restaurante, espera si el pedido aún
  no está listo, lo recoge (`pickup_service_min`), viaja a cada cliente en
  el orden de la ruta y entrega (`dropoff_service_min`).
- **`Dispatcher`** — el cerebro. Corre la *ventana rodante* de despacho (ver
  abajo) y lleva los registros de pedidos pendientes/asignados y el log de
  entregas que alimenta las métricas.

#### El ciclo de despacho (ventana rodante de 2 minutos)

Cada `cfg.rolling_horizon` minutos (2 min por defecto, el mismo intervalo
que usa el panel de "costo computacional" del dashboard) el `Dispatcher`
corre una *ronda de despacho* (`_dispatch_event` en `simulator.py`):

1. Reúne los domiciliarios libres en ese instante y los pedidos aún sin
   asignar.
2. Le pasa ambos conjuntos a la política de asignación activa:
   `policy.assign(state) -> [(courier_id, [order_ids], pay_offer), ...]`.
3. Notifica a cada domiciliario asignado, que entonces decide aceptar o
   rechazar la ruta ofrecida.

Este ciclo se repite hasta que termina la ventana simulada. El tiempo real
(wall-clock) que tarda cada llamada a `assign()` se mide aparte
(`solve_mean/p90/max`) y se compara contra el presupuesto real de 120 s por
ronda — independiente del reloj simulado, que avanza sin importar cuánto
tarde Python en decidir.

#### Las 11 políticas de asignación

Todas implementan la misma interfaz (`Policy.assign`), así que cualquiera
puede correr sobre las mismas 240 instancias y compararse en igualdad de
condiciones. Nuestras 7 propias comparten de hecho el mismo objetivo real
—maximizar cobertura— y solo difieren en *cómo* llegan ahí; las 4 portadas
de `mdrp-sim-master` persiguen un objetivo distinto (ver más abajo).

| Política | De dónde | Qué hace |
|---|---|---|
| `greedy` | propia | Por domiciliario (prioridad: el que menos pedidos lleva hoy), toma el bundle factible más urgente en la tienda más cercana (`routing.py`). |
| `fair_greedy` | propia | Igual que `greedy`, pero prioriza domiciliarios con menor ganancia por hora y les suma un bono por ruta. |
| `ilp_max_coverage` | propia (PuLP/CBC) | MIP sobre (domiciliario, ruta candidata): maximiza pedidos cubiertos. |
| `ilp_max_equity` | propia | Mismo MIP, criterio de desempate: minimizar dispersión de ganancia entre domiciliarios. |
| `ilp_max_throughput` | propia | Mismo MIP, desempate: maximizar rutas por minuto de viaje. |
| `ilp_min_cost` | propia | Mismo MIP, desempate: minimizar pago total. |
| `ilp_min_lateness` | propia | Mismo MIP, desempate: minimizar atraso total sobre el SLA blando. |
| `mdrpsim_greedy` | portada de `mdrp-sim-master` | Por pedido (no por domiciliario): a cada uno le busca, entre todos los domiciliarios libres, el de menor tiempo total de viaje. Sin bundling; cada domiciliario recibe máximo un pedido por ronda. |
| `mdrpsim_mip` | portada | MIP exacto sobre bundles agrupados por restaurante: maximiza densidad de throughput menos una penalización por atraso (no cobertura). |
| `mdrpsim_graph` | portada | Relajación LP continua del mismo `mdrpsim_mip` — matemáticamente idéntica porque el poliedro de asignación es íntegro. |
| `mdrpsim_graph_prospects` | portada | Igual que `mdrpsim_graph`, pero solo considera candidatos dentro de 3&nbsp;km (filtro de "prospectos" de mdrp-sim-master). |

Más detalle de cada una en [`simulator/policies.py`](simulator/policies.py),
[`simulator/ilp_policy.py`](simulator/ilp_policy.py) y
[`simulator/mdrpsim_policies.py`](simulator/mdrpsim_policies.py) (el
docstring de este último documenta además qué se adaptó y qué NO se portó
de mdrp-sim-master, y por qué).

#### Parámetros clave de cada instancia y de la corrida

De `instance_parameters.txt` (uno por instancia, ver `simulator/loader.py`):

- `meters_per_minute` — velocidad del domiciliario (varía con el factor `t100`/`t75`).
- `target click-to-door` / `maximum click-to-door` — SLA blanda (mide atraso) y dura (corte de factibilidad); ver `simulator/routing.py::route_feasibility`.
- `pay per order`, `guaranteed pay per hour` — pago base y piso garantizado (con *true-up*, ver punto 7 más abajo).

De `simulator/config.py` (transversales a las 11 políticas):

- `max_bundle_size` (3 por defecto) — cuántos pedidos del mismo restaurante puede llevar un domiciliario en un solo viaje.
- `acceptance_mode` (`auto`/`fixed`/`logistic`) — si el domiciliario notificado siempre acepta la ruta, o puede rechazarla.
- `ilp_time_limit_sec` (`None` por defecto) — el solver nunca se corta por tiempo; corre hasta la solución óptima real (ver punto 14 más abajo).
- `enable_cancellation`, `enable_repositioning` — extensiones propias de la tesis, apagadas por defecto para igualar el supuesto del benchmark oficial.

#### Qué produce una corrida

`metrics.compute_metrics()` (ver [`simulator/metrics.py`](simulator/metrics.py))
resume el log de entregas en:

- **Servicio**: `coverage_rate` (% de pedidos entregados), percentiles de
  click-to-door/ready-to-door/ready-to-pickup, `overage` (minutos de atraso
  sobre el SLA blando), tamaño de bundle.
- **Económico**: `total_payment`, `proportion_trueup` (qué fracción de
  domiciliarios necesitó el piso garantizado).
- **Equidad**: `F_Gini` (desigualdad de ganancia por hora), `F_MaxMin`,
  `F_Orders`, `F_Deficit`, `F_Dist`.
- **Cómputo**: `solve_mean/p90/max` (segundos reales por ronda de
  despacho) y `wall_clock_sec` (duración total de la corrida).

Con esto, `batch_sensitivity.py`/`batch_mdrpsim.py`/`batch_greedy_fair.py`
corren las 11 políticas sobre las 240 instancias y producen un CSV con una
fila por corrida, listo para el análisis de sensibilidad (ver más abajo) o
para el dashboard interactivo del proyecto.

### Qué cambia respecto al simulador original ("simulador plataforma")

El simulador original fue construido primero para otro dataset (24 instancias
CSV estilo `mdrp-sim-master`, coordenadas lat/lon de Bogotá — ver
`real_instancies/`) y luego se le agregó un *loader* para leer mdrplib
proyectando su grilla sintética de metros a lat/lon. Esa proyección
escondía tres problemas que esta copia corrige, además de reorganizar el
código para que viva de forma autónoma junto a `public_instances/`:

1. **La velocidad de la instancia (`t100`/`t75`) se ignoraba.**
   `distance.py` original calculaba el tiempo de viaje con una tabla fija de
   velocidades por "tipo de vehículo" (concepto que mdrplib ni siquiera
   tiene), totalmente desconectada del `meters_per_minute` propio de cada
   instancia. Dos instancias idénticas salvo por el factor de velocidad
   producían el mismo tiempo de viaje. Aquí, [`simulator/distance.py`](simulator/distance.py)
   reproduce exactamente la fórmula del evaluador oficial:
   `tt = ceil(dist_metros / meters_per_minute)`, usando el `meters_per_minute`
   real de cada instancia (ver `simulator/loader.py`).

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
   hace [`MDRP_code/compute_performance_summary.py`](MDRP_code/compute_performance_summary.py).

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
   ([`simulator/routing.py`](simulator/routing.py)), que ahora usan por
   igual `GreedyPolicy`, `FairGreedyPolicy` (`best_route_for_courier`:
   "pedido factible más cercano" generalizado a bundles) y las 5 variantes
   del ILP (`generate_store_routes` + `route_feasibility`, incluyendo
   `max_equity`, que pasó de relajación LP continua y singleton-only a
   programación entera binaria sobre rutas — pierde la garantía de
   integralidad automática por unimodularidad total que tenía el caso
   singleton puro, pero CBC resuelve el MIP resultante en milisegundos
   igual que los otros 4 objetivos, así que no hay costo práctico). El
   valor por defecto de `max_bundle_size` se fijó en **3** (antes 1 = sin
   bundling).

10. **El criterio de aceptación del repartidor es transversal a las 7
    políticas, no una variante acoplada a una sola de ellas.** Antes de
    este cambio, Greedy/FairGreedy/las 5 del ILP solo podían usar una tasa
    de aceptación fija por repartidor, y la fórmula logística solo existía
    dentro de `LogisticAcceptancePolicy`, que a su vez solo funcionaba
    envolviendo la asignación de `GreedyPolicy` — no había forma de correr,
    por ejemplo, el ILP con `max_equity` combinado con aceptación
    logística. Se extrajeron las 3 reglas de aceptación a un módulo nuevo
    ([`simulator/acceptance.py`](simulator/acceptance.py)):
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

#### Qué NO se trajo de la copia original (y por qué)

- `instance_generator.py` (generador sintético de Bogotá) y
  `instance_loader.py` (el otro formato CSV, `mdrp-sim-master`): no son
  "las instancias y características que plantean en este repositorio" —
  pertenecen a otro dataset (ver `real_instancies/`).
- `osrm_service.py`: nunca estaba conectado al motor de simulación (se
  referenciaba solo en un comentario); enrutar sobre calles reales de
  Bogotá no tiene sentido para una grilla sintética de metros.
- `db_export.py`: la exportación a SQLite/Postgres no es necesaria para un
  análisis de sensibilidad tabular; `batch_sensitivity.py` ya produce un CSV
  consolidado, que es más directo para análisis estadístico (R, pandas, etc).

### Estructura del código (`simulator/`)

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
  mdrpsim_policies.py      Las 4 políticas portadas de mdrp-sim-master
  simulator.py             Motor DES (SimPy), arquitectura por actores
  metrics.py               Métricas de servicio, económicas y de equidad
  run.py                   CLI para una corrida individual
  batch_sensitivity.py     CLI para barrer el diseño factorial (240 instancias)
  requirements.txt
```

### Uso rápido

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

### Análisis de sensibilidad

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

### Supuestos a documentar en la tesis

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

## Política jerárquica con Gurobi (`simulator/hier/`, `--policy hier`)

Modelo multiobjetivo **lexicográfico** por ronda (paquete `simulator/hier/`, adaptador
`simulator/hier_policy.py`), montado según el marco de `Epicas/mdrp-marco-de-optimizacion.md`: una pasada por
objetivo con `setObjectiveN`, candado entre pasadas, parámetros por pasada, callback con progreso = 100 − GAP,
`end_reason` por pasada y artefactos por ronda. Orden decidido el 2026-10-20 (épica §14): cobertura › atraso ›
equidad › costo; atraso en minutos; equidad como déficit sobre la ganancia acumulada del día; candado 0 en
cobertura y 1e-4 en el resto; ningún objetivo protegido. Requiere `gurobipy` con licencia; sin él cae a `greedy`.

```bash
cd simulator
python run.py --instance 0o100t100s1p100 --policy hier --save
python run.py --instance 0o100t100s1p100 --policy hier --hier-order coverage equity lateness cost
python diag_hier_case.py --toy --brute-force          # una ronda didáctica, verificada por fuerza bruta
python diag_hier_case.py --instance 0o100t100s1p100 --time 720 --window 10
python diag_hier_day.py --instance 0o100t100s1p100    # resumen de las rondas de un día
python batch_hier_clusters.py --policies greedy hier  # 240 instancias, un proceso por corrida, resumen por cluster
python -m pytest tests/test_hier.py -q
```

Para lotes largos usar `batch_hier_clusters.py` (una corrida por proceso): gurobipy 11.0.3 mostró violaciones de
acceso esporádicas en procesos que encadenan muchos días simulados. Resultados sobre las 240 instancias
(hier gana en atraso y equidad, pierde 1,7 puntos de cobertura del día) en `docs/mdrp-jerarquia-objetivos.md` §9.

Documento de decisión (orden de objetivos, modelo, ejemplo interactivo, dudas y decisiones):
`docs/mdrp-jerarquia-objetivos.html` (fuente `.src.html`; construir con `python docs/build_deck.py`; rellenar la
tabla por cluster con `python docs/fill_clusters.py simulator/output/<csv>`; copia revisable en `.md`).

Las 24 instancias reales de Bogotá (`real_instancies/`) son los mismos datos de `sebastian-quintero/mdrp-sim`
(`instances/0..23`), normalizados con `stores.csv`; el simulador aún no las lee (formato lat/lon, horas del día,
cuatro vehículos y un solo SLA).
