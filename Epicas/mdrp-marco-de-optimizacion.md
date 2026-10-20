# Épica: marco de optimización jerárquico para el Meal-Delivery Routing Problem (MDRP), portado de XO Scheduler

Arranque: 2026-10-19 · Estado: **brief v1, por validar antes del S0**. Dueño: David.
Origen del marco: `solver-smartbp` (paquete `gurobi_xo`, el solver de XO Scheduler). Destino: el repo del MDRP.

> **Qué es este documento.** La descripción, a grandes rasgos, del *marco* de optimización que usamos en XO para
> montar el mismo en el MDRP: cómo se construye el MIP, cómo se encadenan varios objetivos en jerarquía, cómo se
> mide y publica el progreso, cómo se interrumpe una corrida, qué queda en disco, cómo se reprocesa, cómo se
> explica el resultado y qué disciplina de ingeniería lo sostiene. **No contiene** los objetivos ni las
> restricciones del MDRP: ya los tiene el equipo. Donde el marco los necesita aparecen como huecos `⟨MDRP: …⟩`.
> Cada sección cierra con «qué decidir para el MDRP» cuando hay una decisión que tomar.

---

## 0. Alcance: qué se porta y qué no

| Se porta (el marco) | No se porta (es del dominio de XO) |
|---|---|
| Pipeline request → repositorio → contexto → MIP → callback → resultado parcial/final | Sesiones, topics, plazas, currículos, continuidades, joins, viajes, workrules |
| Jerarquía lexicográfica de objetivos con una pasada por objetivo y candados entre pasadas | Las cuatro familias de objetivos de XO (Profit, Balanced, Less Fragmented, Pref Continuities) |
| Progreso por objetivo = 100 − GAP, `pct` global ponderado, historia de progreso, parciales con el mejor incumbente | El reparto 80/20 concreto y los contadores de plazas |
| Acciones en caliente: stop, skip de pasada, next de fase, `time_limit` y `mip_gap` por pasada, `stop_after` | — |
| Artefactos en disco por corrida y reproceso con solución previa fija | El formato de `scheduled_events` |
| Reporte de explicaciones aparte del resultado (por qué sí / por qué no / contrafactual / agregados) | Los códigos concretos de XO |
| Disciplina: gates `DISABLE_*`, bisección por variable de entorno, herramientas `diag_*`, fixtures desde corridas reales, baseline, docs | Los fixtures y tools de XO |

---

## 1. Principios del marco (lo que hay que conservar aunque cambie todo lo demás)

1. **Un MIP exacto por corrida, con Gurobi, construido entero en memoria.** Nada de heurísticas sueltas fuera del
   modelo: las tácticas de rendimiento (cotas externas, ruptura de simetría, ejecuciones aparte) viven *dentro* del
   marco y se inyectan al MIP por el callback. Así el resultado siempre tiene certificado (cota dual).
2. **Objetivos en jerarquía, no suma ponderada.** El negocio sabe decir «primero X, después Y, después Z»; no sabe
   decir «X pesa 0,7». Cada objetivo es una *pasada* (un MIP completo) con los anteriores «con candado». Ventajas que
   en XO han resultado decisivas: progreso por objetivo, skip de una pasada sin perder las anteriores, parámetros por
   pasada y explicación de «por qué tarda» pasada a pasada.
3. **Siempre hay algo que entregar.** Cada incumbente aceptado se publica como resultado parcial; el usuario puede
   parar en cualquier momento y quedarse con lo mejor visto. Una corrida parada no es una corrida fallida.
4. **El progreso es un certificado, no una sensación.** Progreso de un objetivo = 100 − GAP (incumbente contra cota).
   «Estancado» significa que la cota no cierra, no que la solución no mejora.
5. **Interrumpible en caliente** por API: parar, saltar la pasada activa, pasar a la fase siguiente, tope de tiempo y
   de calidad por pasada, tope global por tiempo y porcentaje.
6. **Reproducible sin servidor.** El request se guarda tal cual llega; cualquier corrida se repite offline con el
   mismo código, se inspecciona el modelo (LP, coeficientes por objetivo, IIS) y se convierte en fixture de test.
7. **Cada cambio de comportamiento detrás de un gate** (`DISABLE_<FEATURE>`) y con un test sobre una corrida real.
   Con el gate puesto, el modelo es *idéntico* al anterior (se comprueba con una huella del modelo).
8. **Reproceso = lo decidido es fijo, lo imposible es cero, el resto se decide.** La solución previa entra como
   restricciones de igualdad, no como MIP start.
9. **Explicar fuera del camino crítico.** El reporte de explicaciones se construye después de publicar el resultado
   final, con presupuesto, y viaja por su propio canal.

---

## 2. Arquitectura: capas y flujo de una corrida

```
HTTP (FastAPI + uvicorn, pydantic)                          api/model.py (contrato), solver_grb.py (endpoints)
  POST /process                 → arranca una corrida en un hilo, responde en seguida
  GET  /process/{id}            → estado + último resultado
  POST /process/action/{id}     → {action: next | stop | skip_objective, argument}
  DELETE /process/{id}, POST /clean
         │
         ▼
Process (api/process.py)                                     ciclo de vida de UNA corrida
  ├─ escribe <id>_input.json (request tal cual) y <id>_pending.json (para reintentar si el proceso muere)
  ├─ construye Repository ← Repository.fill(configuration, datos)   (parseo + alias cortos + mapping.json)
  ├─ por cada FASE: Context(process_id, repository, contexto_previo, consumidor_de_parciales)
  │     ├─ context.configure()    construye el MIP entero                     (§3)
  │     ├─ context.optimize()     Gurobi + callback; publica parciales         (§4)
  │     └─ emite el resultado de la fase (parcial si quedan fases)
  ├─ publica por PATCH reply_url (hilo publicador con coalescing; STOPPING y acks nunca se pierden)
  ├─ watchdog de memoria (OOM) que para la corrida con motivo
  └─ al final: PATCH FINISHED/STOPPED/FAULTED → después, reporte de explicaciones por POST aparte   (§7)
         │
         ▼
Context (core/context.py)  +  build_model/add_<familia>.py  +  configure_objectives.py
Callback (core/callbacks_model/optimize_callback.py)
Salida: output/<id>/<id>_sol.json, <id>_partialN.json, <id>_ph<fase>.sol, <id>_explanations.json
```

Correspondencia de piezas (nombres de XO → qué construir en el MDRP):

| Pieza en XO | Responsabilidad | En el MDRP |
|---|---|---|
| `api/model.py` | Contrato pydantic: request (configuración + datos), resultado, acciones, `objective_settings`, `stop_after` | `⟨MDRP: request = pedidos, repartidores/vehículos, restaurantes, horizonte, parámetros⟩` |
| `api/process.py` | Ciclo de vida, disco, publicación, acciones, watchdog | copiar casi tal cual |
| `core/repo.py` (`Repository`) | Parseo a modelo interno, alias cortos (`J1`, `R02`), fases, settings | `⟨MDRP: Order, Courier, Restaurant, Zone…⟩` |
| `core/context.py` (`Context`) | Generación de candidatos, variables, restricciones, objetivos, callback, solución, indicadores | el corazón; se porta la *estructura*, no el contenido |
| `core/build_model/add_*.py` | Una familia de restricciones por módulo, filas con nombre estable | `⟨MDRP: una familia por módulo⟩` |
| `core/build_model/configure_objectives.py` | `setObjectiveN` por objetivo + parámetros por pasada | `⟨MDRP: sus objetivos⟩` |
| `core/callbacks_model/optimize_callback.py` | Pasadas, progreso, parciales, skip, stop, `stop_after`, cotas externas | copiar y renombrar indicadores |
| `core/explanations.py` | Reporte de explicaciones | sprint aparte (§7) |
| `core/configuring_progress.py` / `configuring_profile.py` | Progreso y ETA de la construcción | copiar |
| `tools/diag_*.py`, `tests/fixtures/manifest.json` | Reproducción offline, catálogo de escenarios | copiar el patrón |

---

## 3. El modelo: cómo se monta (sin los objetivos ni las restricciones del MDRP)

### 3.1 Entrada → repositorio

- El request llega con **identificadores externos** (ObjectId de 24 caracteres en XO). El repositorio los mapea a
  **alias cortos** (`J1`, `R02`) para que los nombres de variables y filas sean legibles en un LP y en un IIS, y
  guarda `<id>_mapping.json` para revertirlos. Todo lo que sale (resultado, explicaciones) va con ids externos.
- El repositorio también fija: horizonte, fases, `objective_settings` por pasada, flags de escritura
  (`write_model`, `compute_iis`), y aplica transformaciones previas al modelo (en XO, la compactación de plazas
  contiguas: decidir una sola vez lo que el negocio obliga a decidir junto; vale la pena buscar el equivalente en el MDRP,
  p. ej. `⟨pedidos del mismo restaurante y misma franja que SIEMPRE van juntos⟩`).

### 3.2 `Context.configure()`: el orden de construcción

1. **Solución previa** (reproceso): lo que ya está decidido se registra como fijo antes de generar nada.
2. **Generación de candidatos** («opciones»): por cada unidad de decisión se enumeran las combinaciones admisibles
   aplicando **prefiltros anotados** (cada descarte guarda un código y un motivo: alimenta las explicaciones). En XO
   una combinación es `(clase, sesión, topic, plaza, periodo, recurso)`; en el MDRP sería
   `⟨pedido, repartidor, franja/posición, …⟩`. Aquí se gana o se pierde el tamaño del modelo: el prefiltro es exacto
   (nunca descarta algo factible) y mide cuántos candidatos deja por unidad.
3. **Variables**: binarias `x` por combinación (`Rx[...]` en XO) y variables agregadas (`z` por unidad decidida, `y` por
   grupo) acopladas con filas «enable» (`Σ x ≤ M·z`). Las variables se nombran con los alias (`x[J1,R02,...]`).
4. **Restricciones por familia, un módulo por familia**, con **nombres de fila estables** (`Familia_<ids>`): el IIS
   es legible, la taxonomía de filas (`rows_by_family`) sale gratis y cada familia se puede desactivar por gate.
   Familias típicas que el MDRP también tendrá: estructura (cada unidad decidida a lo sumo / exactamente una vez),
   capacidad del recurso (no dos cosas a la vez; `Once[recurso, periodo]`), reglas de trabajo del recurso (ventanas de
   duty, descansos; en XO son las más caras), orden y precedencia temporal, mismo día / contigüidad, `⟨MDRP: ventanas
   de entrega, capacidad del vehículo, tiempos de preparación, precedencia recogida→entrega…⟩`.
5. **Fijos y ceros**: `PrevSolution_* : x = 1` para lo decidido; `IMPOSSIBLE: Σ x = 0` para lo que se detectó
   imposible tras generar (con guardas para no fijar a 1 y a 0 la misma variable: en XO eso produjo infactibles de
   dos filas).
6. **Objetivos** (§3.3) y parámetros por pasada (§3.5).

Detalles de construcción que ahorraron mucho tiempo en XO y que conviene llevar de serie:

- **Registro Python de variables por nombre** en vez de `getVarByName` (que exige `update()` y es lento): en XO
  −16/−31 % del tiempo de construcción.
- **Progreso de la construcción** (`configuring_progress`): ticks por sub-fase, publicados ≤ 1 vez/1,5 s con ETA a
  partir de un perfil EMA por cliente; en modelos grandes la construcción tarda decenas de segundos y el front
  necesita ver algo.
- **Restricciones generales de Gurobi** (`addGenConstrMin/Max/Or`) para min/máx/usado: legibles y Gurobi las
  linealiza bien.
- `WRITE_LP=1` + `write_model` escribe el `.lp` para inspección; nunca por defecto (gigabytes en modelos grandes).

### 3.3 Objetivos: una pasada por objetivo

Cada objetivo es una expresión lineal sobre las variables del modelo, registrada con
`model.setObjectiveN(expr, index, priority=p, name="…")`. Gurobi resuelve en **orden de prioridad descendente**:
maximiza el primero, fija su valor (con tolerancia), maximiza el segundo bajo ese candado, y así. Convenciones de XO
que conviene mantener:

- **Todos en el mismo sentido** (MAX). Un objetivo «cuanto menos mejor» entra con signo negativo. Mezclar sentidos
  con `ObjNWeight = −1` funciona, pero complica la lectura del GAP y del progreso.
- **El índice técnico no es la prioridad.** Los objetivos opcionales pueden no existir en una corrida; se guarda un
  mapa nombre → índice → nº de pasada y toda la lógica (skip, settings, progreso) va por **nombre**.
- **Monobjetivo es un caso especial**: Gurobi no emite eventos de multiobjetivo; el callback anuncia la pasada única
  en el primer evento.
- **Estructuras de objetivo que ya sabemos que cuestan**: los objetivos de «conteo» (p. ej. *usar menos recursos*)
  tienen cota lineal floja («medio recurso») y Gurobi encuentra pronto pero **demuestra tarde**; los objetivos con
  óptimo **degenerado** (muchas soluciones con el mismo valor) hacen que el óptimo que se encuentre primero decida
  si las pasadas siguientes son fáciles o difíciles (varianza real: 8 s a 222 s con la misma entrada). Ver el
  catálogo de tácticas en §8.5.

Tabla a rellenar por el equipo del MDRP (la prioridad más alta corre primero):

| Prioridad | Nombre | Qué maximiza (expresión lineal) | Sentido original | ¿Protegido? (no admite `mip_gap`) | ¿Cuándo existe? |
|---|---|---|---|---|---|
| `⟨n⟩` | `⟨MDRP: objetivo 1⟩` | `⟨…⟩` | MAX / MIN→−MAX | sí / no | siempre / si hay … |
| `⟨n−1⟩` | `⟨MDRP: objetivo 2⟩` | `⟨…⟩` | | | |
| … | | | | | |

### 3.4 Candados entre pasadas

- Gurobi permite que la pasada *k* degrade los objetivos anteriores hasta la tolerancia (`ObjNAbsTol` /
  `ObjNRelTol`, ≈ 1e-4 relativa por defecto). Consecuencia medida en XO: dos corridas con el mismo valor del primer
  objetivo pueden dar valores distintos en el segundo (el candado deja un «hueco» de 1e-4·|valor|).
- Si una pasada terminó por `MIPGap` o `time_limit` (sin óptimo demostrado), el candado efectivo es **flojo**: ≈ cota
  dual − gap·|cota|, no el incumbente. Cualquier cota externa o ejecución aparte debe usar ese candado flojo, o la
  jerarquía rechazará su solución.
- **Gotcha**: no poner `NumObj = 0` sobre un modelo ya monobjetivo (se pierde el `setObjective` siguiente y el MIP
  corre con objetivo vacío: «óptimo 0» en 1 s).

### 3.5 Parámetros por pasada (`objective_settings`)

El request trae, por nombre de objetivo, `mip_gap` (el front lo manda como **calidad 0–100**; `MIPGap =
(100 − calidad)/100`) y `time_limit` (**minutos**; se pasa a segundos). Se aplican sobre el *multiobjective
environment* de cada pasada (`model.getMultiobjEnv(i)`): primero los defaults por nombre, luego los overrides del
request. Los objetivos **protegidos** (`PROTECTED_OBJECTIVE_NAMES`) rechazan `mip_gap` pero admiten `time_limit`.
Sin configuración: `MIPGap` 1e-4 y sin tope.

### 3.6 Qué decidir para el MDRP antes de escribir el modelo

| # | Decisión | Lo que hace XO | Recomendación |
|---|---|---|---|
| D1 | **Modelo del tiempo** | Discretizado en periodos (franjas del recurso); nada de tiempos continuos con big-M | Discretizar si el negocio ya piensa en franjas (`⟨p. ej. buckets de 5–15 min⟩`); el continuo con big-M da cotas malísimas |
| D2 | **Unidad de decisión** | Una binaria por `(unidad, recurso, periodo)` | `⟨MDRP: x[pedido, repartidor, franja] + variables de secuencia o de ruta?⟩`; si hay rutas, decidir si se enumeran (columnas) o se construyen (flujo) |
| D3 | **Qué es «cubierto»** | plaza con recurso asignado; `required: false` permite dejar sin cubrir sin infactibilidad | `⟨MDRP: pedido asignado y entregado dentro de ventana?⟩`; dejar SIEMPRE salida al modelo (no cubrir con coste) para que nunca sea infactible por demanda |
| D4 | **Orden de los objetivos** y sentido | PC > Profit > Balanced > LF > WL > FJA | `⟨MDRP: …⟩`; el primero debe ser el que el negocio no negocia |
| D5 | **Horizonte y reproceso** | horizonte deslizante; lo pasado es historia fija que afecta a reglas (descansos) | `⟨MDRP: pedidos ya en curso fijos; repartidores ya en ruta con posición inicial⟩` |

---

## 4. Ejecución: callback, progreso, parciales, estados

### 4.1 Lo que hace el callback en cada evento de Gurobi

| Evento | Qué hace XO |
|---|---|
| `MULTIOBJ` | Cierra la pasada anterior (toma la solución final con `cbGetSolution`), anuncia la siguiente (nombre, prioridad, nº de pasada); lanza, si toca, la ejecución aparte de esa pasada |
| `MESSAGE` | Parsea el log de Gurobi: «Multi-objectives: optimize objective N (nombre)», «Best objective …, best bound …, gap …», «Explored N nodes (M simplex iterations) in X seconds (W work units)», «Optimal solution found / Time limit reached / Solve interrupted». Coste cero y es la fuente más fiable de fronteras y esfuerzo por pasada |
| `MIPSOL` | Nuevo incumbente: lee la solución, calcula los indicadores de estructura (en XO: plazas llenas, recursos usados, rango de carga), decide si publicar una parcial, actualiza la historia de progreso |
| `MIP` / `MIPNODE` | Cota dual y GAP (sin solución); latido para parciales; aplica skip / stop / `stop_after` / cota externa |
| cualquiera | Si hay un stop pedido → `model.terminate()`; si hay un skip de la pasada activa → `cbStopOneMultiObj(pasada)` |

### 4.2 Indicadores

- **Por objetivo** (en cada tick): `value`, `bound`, `gap`, `prog = 100 − GAP` (fórmula de XO:
  `100·(2 − bound/best)` acotada a [0, 100], 0 si no hay incumbente), más los contadores de estructura del
  objetivo. Serie `objective_progress_history` (solo cuando algo cambia) y `objective_name` (orden real de pasadas).
- **Global** (`pct`, lo que pinta la barra del front): `(1 − F)·prog(objetivo principal) + F/(n−1)·Σ prog(otros)`
  con `F = 0,20` en XO. `⟨MDRP: decidir F y cuál es el principal⟩`. Serie `percentage_history`.
- **Estructura** (lo que el usuario entiende): en XO plazas llenas / a llenar y distribución de carga por recurso;
  en el MDRP `⟨pedidos asignados / total, a tiempo / tarde, repartidores usados, km…⟩`. Se calculan sobre el
  incumbente en `MIPSOL` con **un** `cbGetSolution` por lote de variables, nunca uno por variable.
- **`skip_states`** por objetivo (`requested` / `applied` / …) para el botón de skip del front.
- **Configuring**: sub-fases con avance y ETA (`details.configuring`), y perfil por cliente para la ETA siguiente.
- **Por pasada** (lección de la épica de indicadores de XO, llevarlo desde el día 1): `start_s`, `end_s`,
  `first_incumbent_s`, `last_improvement_s`, `proof_s`, `value`, `bound`, `gap_end`, **`end_reason`** grabado en el
  punto que decide (cada `terminate()` / `cbStopOneMultiObj` escribe el motivo y loguea), `nodes`,
  `simplex_iterations`, **`work_units`** (medida de esfuerzo de Gurobi independiente del hardware), `solutions`,
  `mip_gap_param`, `time_limit_param`. Y por corrida: versión del solver, máquina, hilos.

### 4.3 Parciales

- Cada incumbente aceptado se convierte en un resultado parcial completo (misma forma que el final) con `status
  RUNNING`; se publica por PATCH al `reply_url` y se guarda `<id>_partialN.json`.
- **Throttle**: mínimo 2 s entre parciales (`PARTIAL_MIN_INTERVAL_S`) y latido cada 20 s sin incumbente nuevo
  (`PARTIAL_HEARTBEAT_S`), así el front siempre ve «vivo» y el progreso de la cota.
- **Hilo publicador** con *coalescing*: si llegan varias parciales mientras una se envía, se manda la última;
  los ítems obligatorios (`STOPPING`, ack de skip) nunca se descartan y llevan una foto tomada en el momento.
- Si el PATCH falla, `<id>_pending_notify.json` y reintento al arrancar el servidor y al publicar el siguiente.

### 4.4 Estados de una corrida

| Estado | Cuándo | Qué lleva |
|---|---|---|
| `STARTED` | respuesta del `POST /process` | ids |
| `RUNNING` (+ sub-estado `Configuring` en `details`) | construcción y parciales | mejor solución hasta ahora, progreso, indicadores |
| `STOPPING` | en cuanto llega un stop; nunca vuelve a `RUNNING` | última foto |
| `FINISHED` | todas las pasadas terminaron (óptimo, `MIPGap`, `time_limit`, cota externa, skip) | resultado final + `inner_status` de Gurobi (`OPTIMAL`, `SUBOPTIMAL`, `TIME_LIMIT`, `INTERRUPTED`) |
| `STOPPED` | stop del usuario, `stop_after`, watchdog | mejor solución encontrada |
| `FAULTED` | excepción, infactible sin salida | motivo; con `compute_iis` el `.ilp` |

### 4.5 Las seis formas de que una pasada termine antes del óptimo

(1) skip de la pasada (`cbStopOneMultiObj`): Gurobi pasa a la siguiente con el mejor incumbente de esta;
(2) stop del usuario (`model.terminate()`): termina toda la optimización, estado `STOPPED`;
(3) `time_limit` de la pasada; (4) `mip_gap` de la pasada; (5) **cota externa** (una ejecución aparte o una cota
combinatoria demuestra que el incumbente ya es óptimo: se detiene la pasada y se marca al 100 %);
(6) `stop_after {minutes, percentage}` global del request (cuando el `pct` alcanza el porcentaje y pasaron los
minutos, termina **toda** la optimización); más el `next` de fase. Regla: **cada una deja escrito su motivo** en el
momento de decidir. En XO esto se añadió tarde y costó un caso sin diagnóstico.

---

## 5. Acciones en caliente (API)

| Acción | Endpoint | Efecto | Qué queda / qué se pierde |
|---|---|---|---|
| `stop` | `POST /process/action/{id}` `{action: "stop"}` | `STOPPING` inmediato (PATCH en segundo plano), `terminate()` en el siguiente callback, `STOPPED` con la mejor solución | Se pierden las pasadas que no corrieron |
| `skip_objective` | `{action: "skip_objective", argument: "<nombre>"}` | Marca la pasada; si está activa, `cbStopOneMultiObj`; si aún no empezó, se salta al llegar; ack inmediato al front | La pasada queda con su mejor incumbente (candado flojo para las siguientes) |
| `next` | `{action: "next"}` | Cierra la fase actual y pasa a la siguiente | — |
| `time_limit` / `mip_gap` | en el request, por pasada | §3.5 | — |
| `stop_after` | en el request | §4.5 (6) | — |
| `DELETE /process/{id}` | — | Limpia ficheros y memoria de la corrida | — |

Todas las acciones se materializan también en disco (`<id>_stop`, `<id>_skip_objective`) para sobrevivir a un
reinicio y para que `GET /process/{id}` responda aunque el hilo ya no exista (en XO hubo una carrera `get_status →
404` en corridas largas: la respuesta de estado debe salir del disco, no solo de la memoria).

---

## 6. Artefactos en disco y reproceso

| Fichero (`output/<id>/`) | Contenido |
|---|---|
| `<id>_input.json` | El request tal cual llegó. **Imprescindible**: es lo que permite reproducir offline y crear fixtures |
| `<id>_mapping.json` | alias internos ↔ ids externos |
| `<id>_pending.json` | configuración mínima (reply_url, tenant) para reintentar si el proceso muere |
| `<id>_partialN.json` | cada parcial publicada |
| `<id>_ph<fase>.sol` | pickle de la lista de tuplas elegidas (`x = 1`) al cerrar la fase |
| `<id>_ph<fase>.lp` | solo con `WRITE_LP=1` y `write_model` |
| `<id>_sol.json` | resultado final: solución + `details` (fases, stats, progreso, perfil de construcción) |
| `<id>_explanations.json` | cuerpo exacto del POST de explicaciones (§7) |
| `<id>_pending_notify.json` / `<id>_pending_explain.json` | publicaciones fallidas pendientes de reintento |
| `<id>_infeasible_model.ilp` | IIS (subconjunto irreducible de filas que se contradicen) cuando el modelo es infactible |

**Reproceso.** El request trae lo ya decidido (en XO, eventos con asignación); el contexto lo registra como fijo y
lo fuerza con `PrevSolution_* : x = 1`. Lo que la generación detecta imposible va a `IMPOSSIBLE: Σ x = 0`. El resto
se decide. Reglas aprendidas: (a) la historia fija **cuenta** para las reglas del recurso aunque esté fuera del
horizonte de decisión (en XO, un hueco en el horizonte contaba como descanso: ilegal); (b) nunca fijar a 1 algo que
otra fila fija a 0: guardas en los dos sitios y, si pasa, IIS de dos filas legible; (c) el reproceso de una unidad
suelta debe tardar segundos aunque la corrida completa tardara minutos.

**Fases.** Varias fases = varios contextos secuenciales; cada uno recibe el anterior y su solución como fijos
(`partial = fase < total`). En XO las «dos fases» reales son dos requests (devices y luego instructores); se midió
un prototipo de fase única con −54 % de coste y quedó bloqueado por la formulación de una regla. En el MDRP
`⟨decidir si hay fases: p. ej. asignación y luego secuencia⟩`.

**Infactible.** Con `compute_iis` se escribe el `.ilp`; con nombres de fila estables se lee en un minuto qué dos
reglas chocan. En XO todos los infactibles reales fueron «fila que fija a 1» contra «regla que lo prohíbe»: el
marco debe tener **salida** (no cubrir con coste) para que la demanda nunca haga infactible el modelo.

---

## 7. Explicaciones (recomendado, sprint aparte)

Qué es: un reporte por corrida que responde, con datos del propio modelo, «por qué esta unidad quedó sin cubrir»,
«por qué se eligió a este recurso y no a aquel», «qué pasaría si se forzara X» y «cuánto» (agregados). En XO lo
consume un agente LLM (chat de planificación) y el front; se ha medido que las preguntas de los usuarios son en su
mayoría de este tipo. Diseño que funcionó:

- **Hooks en el marco, no un módulo aparte**: cada prefiltro de candidatos anota su código de descarte; cada sitio
  que marca algo imposible lo etiqueta; el auditor con el **modelo vivo** (después del PATCH final, antes de
  `dispose`) prueba alternativas (flip / intercambio) y, con presupuesto, un contrafactual exacto (fijar y
  re-resolver, IIS si infactible, cambio mínimo).
- **Fuera del camino crítico**: el resultado final sale primero; el reporte se construye después y viaja por
  `POST reply_url_explanation` (canal propio, upsert en destino, reintentos, copia en disco). Un stop durante la
  construcción la corta y envía lo construido (`budget.aborted`).
- **Presupuestos** por tipo de análisis y reducidos en corridas paradas; lo que no se analizó lleva `NOT_EXPLAINED`.
- **Contrato versionado** con diccionario de códigos en inglés, topes de listas y tres casos reales de ejemplo
  (`docs/explanations_protocol.md` en XO; 1 168 líneas: el contrato es la mitad del trabajo).
- Coste medido en XO: 2 s (modelo pequeño) a 40 s (grande, presupuestos agotados); tamaño 150 KB – 1,6 MB.

En el MDRP: `⟨por qué este pedido llegó tarde / se quedó sin repartidor; por qué este repartidor no lo tomó; qué
pasaría si se le asignara; agregados por zona, restaurante, repartidor y franja⟩`.

---

## 8. Disciplina de ingeniería heredada (lo que más valor ha dado)

### 8.1 Gates por variable de entorno y bisección

- Cada comportamiento nuevo nace detrás de `DISABLE_<FEATURE>` (o `ENABLE_` si es opt-in). Con el gate activo el
  modelo debe ser **idéntico** al de antes; se comprueba con una huella del modelo (`PYTHONHASHSEED=0`, conteo y
  hash de filas/columnas/coeficientes por objetivo).
- **Trampa de XO a no repetir**: los gates se leen por *truthiness* (`os.getenv` no vacío), así que `DISABLE_X=0`
  **desactiva** la feature. En el MDRP: un helper `flag(name)` que trate `""`, `0`, `false`, `no` como apagado.
- Bisección: ante una regresión, apagar gates de uno en uno sobre el mismo input hasta aislar el responsable;
  patrón documentado en `docs/diag_toolkit.md`.
- Los defaults (`DEFAULT_MIPGAP_BY_NAME`, `DEFAULT_TIME_LIMIT_BY_NAME`, umbrales de tácticas) se centralizan en el
  contrato, no se esparcen.

### 8.2 Reproducción offline y herramientas `diag_*`

Patrón de 30 líneas: cargar `<id>_input.json` → apagar `reply_url` → `Repository.fill` → `Context.configure()` →
inspeccionar `context._model` (variables por prefijo, coeficientes por objetivo con `params.ObjNumber`, escribir
LP) → `context.optimize()`. Sobre ese patrón, XO acumuló 40 herramientas (`tools/diag_*.py`): correr un caso con
tope de tiempo, comparar dos soluciones, trazar por qué una variable es imposible, progreso por objetivo, tiempos por
pasada en lote, huella del modelo, verificar una solución contra las reglas. El MDRP necesita desde el S0:
`diag_run_case.py` (correr un input), `diag_check_solution.py` (verificar reglas sobre la salida),
`diag_compare_solutions.py` y `diag_model_fingerprint.py`.

### 8.3 Tests desde corridas reales

- `output/` es almacén local y efímero; **nunca** se referencia desde un test. Cuando una corrida interesa, se copia
  su `_input.json` a `tests/fixtures/<dominio>/<nombre>.json` **en el momento** (si no, se pierde) y se registra en
  `tests/fixtures/manifest.json` con `id` (`TC-<DOMINIO>-NN`), `source_execution`, `tags`, `summary`, `tests`.
- Regla «una corrida → un fixture → un TC → una clase de test»; pirámide unit (sin Gurobi) / integración ligera
  (`configure()` sin `optimize()`) / escenarios E2E (pocos, con Gurobi).
- **Baseline de KPI** (`tests/baseline_kpi.py`): valores de objetivo, unidades cubiertas y tiempo por escenario, para
  detectar regresiones de calidad y no solo de corrección.
- Gurobi sin semilla es no determinista en óptimos degenerados: los asserts comparan valores de objetivo y
  propiedades, no la asignación exacta; cuando haga falta exactitud, `Seed` fijo.

### 8.4 Documentación y memoria

`docs/solver_handbook.md` (flujo, artefactos, conceptos, quirks) + `docs/diag_toolkit.md` (reproducir e
inspeccionar) + `docs/epicas/*.md` (briefs como este) + `docs/presentaciones/<nombre>.{md,html}` (documentos de
decisión con la evidencia medida: el `.html` es la página publicada, el `.md` la copia revisable) + notas de memoria
por caso (`caso cliente@id`, gate, test, causa raíz). Cada bug cerrado deja: causa raíz, gate, fixture, test y nota.
`docs/` en XO está en `.gitignore`: lo que deba viajar se publica como página.

### 8.5 Catálogo de tácticas de rendimiento (aplicar solo cuando una medición lo pida)

| Táctica | Cuándo | Qué hizo en XO |
|---|---|---|
| Compactar decisiones que siempre van juntas | antes del modelo, por reglas del negocio | 488 884 → 30 317 filas; construcción 19 → 1,5 s; misma solución |
| Registro de variables por nombre | siempre | −16/−31 % de construcción |
| Orden entre recursos gemelos (`usado[a] ≥ usado[b]`) | objetivos de conteo con recursos intercambiables | de GAP 100 % sin cerrar a demostrar al encontrar |
| Ejecución aparte de una pasada en su propio `Env` + inyección con `cbSetSolution` | pasada que encuentra pero no demuestra | 62–80 s frente a 50–62 min |
| Cota combinatoria externa (capacidad, mochila, ventanas densas) y parada por cota | ídem, cuando ni la ejecución aparte cierra | detiene la pasada al alcanzar la cota; óptimo acotado en [17, 19] |
| `MIPFocus`, `NoRel` | solo opt-in; mueven el promedio, no curan | varianza inherente de Profit |
| Cortes de cadena para reglas de ventana (duty) | reglas de ventana deslizante | 448 k cortes; la reformulación por bloques dio LP más floja |
| Watchdog de memoria | servidor compartido | para con motivo antes del OOM |

### 8.6 Despliegue

Imagen `gurobi/optimizer:13.0.2` + `pip install -r requirements.txt` + `uvicorn solver_grb:app`; licencia por
fichero (`GRB_LICENSE_FILE`); **el servidor hay que reiniciarlo** tras cada cambio (no hay recarga); versión del
solver escrita en el build y publicada en cada resultado (en XO se añadió tarde: sin ella no se puede comparar
corridas de antes y después de un cambio de formulación).

---

## 9. Mapa de ficheros de referencia en `solver-smartbp` (para copiar o adaptar)

| Para | Fichero |
|---|---|
| Contrato HTTP y modelos pydantic (request, resultado, `ObjectiveSetting`, `SchedulingStopConfig`, `ActionType`) | `gurobi_xo/api/model.py` |
| Endpoints | `solver_grb.py` |
| Ciclo de vida, disco, publicador, acciones, watchdog, reintentos | `gurobi_xo/api/process.py` |
| Parseo y alias | `gurobi_xo/core/repo.py` |
| Orden de construcción, `optimize`, `_process_solution`, `signal_stop/skip/interrupt`, `report_objective_progress` | `gurobi_xo/core/context.py` |
| Objetivos, mapa nombre→índice→pasada, parámetros por pasada (`_apply_per_objective_envs`) | `gurobi_xo/core/build_model/configure_objectives.py` |
| Callback: pasadas, MESSAGE, MIPSOL, skip, cota externa, `stop_after` | `gurobi_xo/core/callbacks_model/optimize_callback.py` |
| Fórmulas de progreso (`calculate_objective_percentage`, `calculate_optimal_percentage`, `MULTI_OBJ_FACTOR`) | `gurobi_xo/core/utils.py` |
| Progreso y ETA de la construcción | `gurobi_xo/core/configuring_progress.py`, `configuring_profile.py` |
| Explicaciones y su contrato | `gurobi_xo/core/explanations.py`, `docs/explanations_protocol.md`, `docs/explanations_callback_endpoint.md` |
| Ejecución aparte, cota externa, orden entre gemelos | `gurobi_xo/core/lf_side_solve.py`, `lf_capacity_bound.py`, `build_model/lf_twin_order.py` |
| Patrón de herramientas y bisección | `docs/diag_toolkit.md`, `tools/diag_run_case.py`, `tools/diag_model_fingerprint.py` |
| Arquitectura de tests, manifest, baseline | `tests/ARCHITECTURE.md`, `tests/fixtures/manifest.json`, `tests/baseline_kpi.py` |
| Handbook y épica de indicadores (qué publicar por pasada) | `docs/solver_handbook.md`, `docs/epicas/indicadores-de-ejecucion-y-estimadores.md` |
| Clase para dirección sobre LP/MIP, GAP y jerarquía | `docs/presentaciones/clase-lp-mip-gap-objetivos.md` |

---

## 10. Plan por sprints (propuesta)

| Sprint | Objetivo | Entrega / criterio de hecho |
|---|---|---|
| S0 · Esqueleto | Repo, contrato pydantic del request/resultado del MDRP, `Process` con ciclo de vida y disco, runner offline, un `diag_run_case.py`, `manifest.json` vacío, gates con `flag()` | `POST /process` con un modelo trivial (una variable) recorre `STARTED → RUNNING → FINISHED` y deja los ficheros de §6 |
| S1 · Modelo base | `Repository` + `Context.configure()` con generación de candidatos anotada, variables, **una** familia de restricciones por módulo con nombres estables, **un** objetivo; salida con ids externos; `diag_check_solution.py` | Un input real del MDRP resuelto y verificado; fixture + TC-01; huella del modelo |
| S2 · Jerarquía | `setObjectiveN` con todos los objetivos, mapa nombre→pasada, `objective_settings` por pasada, callback con pasadas, progreso por objetivo y `pct`, parciales con throttle, acciones `stop` / `skip_objective` / `next`, `stop_after` | Front (o cliente de prueba) ve progreso por objetivo y puede parar y saltar; `end_reason` por pasada desde el principio |
| S3 · Observabilidad | Indicadores por pasada (§4.2) parseando `MESSAGE`, progreso y ETA de construcción, versión del solver, perfil de filas por familia, `diag_obj_progress.py`, `diag_pass_times.py` | Un resultado basta para contestar «qué pasada tardó, cuánto, por qué terminó» |
| S4 · Reproceso e infactibilidad | Solución previa como fijos, `IMPOSSIBLE` con guardas, historia fuera de horizonte, IIS automático en `FAULTED`, fases si D5 lo pide | Reprocesar una unidad suelta tarda segundos; un infactible provocado da un `.ilp` de pocas filas legible |
| S5 · Explicaciones | Hooks de descarte, auditor con modelo vivo, contrafactual con presupuesto, agregados, canal POST aparte, contrato v1 | Reporte en un caso real; 10 preguntas de usuario con respuesta esperada |
| S6 · Rendimiento | Solo con mediciones: tácticas de §8.5 que el MDRP necesite | Tiempos por pasada en el baseline antes y después |

---

## 11. Decisiones a tomar antes del S1

| # | Decisión | Recomendación |
|---|---|---|
| D1 | Modelo del tiempo (§3.6) | discretizar |
| D2 | Unidad de decisión y si hay variables de ruta/secuencia | `⟨MDRP⟩`; medir el nº de candidatos por pedido con el prefiltro antes de decidir |
| D3 | Qué es «cubierto» y la salida con coste | siempre con salida |
| D4 | Lista y orden de objetivos, sentido, protegidos | `⟨MDRP⟩` |
| D5 | Fases | una sola salvo que el negocio pida decidir en dos tiempos |
| D6 | Factor del `pct` global y objetivo principal | 0,20 como arranque |
| D7 | Canal de parciales y de explicaciones (PATCH / POST / cola) | copiar el de XO (PATCH `reply_url` + POST `reply_url_explanation`) |
| D8 | Qué es historia fija en el reproceso (pedidos en curso, posición del repartidor) | `⟨MDRP⟩` |
| D9 | Determinismo (`Seed`) en producción | sin semilla, como XO; semilla en tests que lo necesiten |

---

## 12. Riesgos y trampas heredadas

- **Candado de 1e-4**: dos corridas iguales pueden diferir en los objetivos secundarios; documentarlo para el
  negocio antes de que lo descubra.
- **Objetivos de conteo**: cota floja y prueba cara; prever ruptura de simetría desde el diseño (recursos gemelos).
- **Degeneración del primer objetivo**: la varianza de tiempo es inherente; publicar rangos, no puntos.
- **Gates por truthiness** y **servidor sin recarga**: dos horas perdidas en XO cada vez.
- **`get_status` tras morir el hilo**: el estado debe leerse del disco.
- **`output/` efímero**: el fixture se copia el mismo día o se pierde el caso.
- **Explicaciones en el camino crítico**: retrasan el `FINISHED`; construir después.
- **Historia fuera del horizonte** que cuenta para reglas del recurso: el hueco no es descanso.
- **LP de gigabytes**: `WRITE_LP` nunca por defecto; vigilar el disco temporal en ejecuciones aparte (.mps de 1,6 GB en XO).

---

## 13. Cómo arrancar en el otro repo

1. Copiar este brief a `docs/epicas/` del repo del MDRP y rellenar los huecos `⟨MDRP: …⟩` de §3.3, §3.6 y §11.
2. Leer en `solver-smartbp`, en este orden: `docs/solver_handbook.md` (§1 flujo, §4 multiobjetivo),
   `docs/diag_toolkit.md`, `gurobi_xo/api/model.py` (contrato), `gurobi_xo/api/process.py` (ciclo de vida),
   `gurobi_xo/core/build_model/configure_objectives.py` (`_apply_per_objective_envs`) y
   `gurobi_xo/core/callbacks_model/optimize_callback.py` (`_init_multiobj_tracking`, rama `MESSAGE`,
   `_maybe_skip_active_pass`).
3. Arrancar el S0 con el esqueleto de §2 y un modelo trivial; no escribir ninguna restricción del MDRP hasta que el
   ciclo `STARTED → RUNNING → FINISHED` deje los ficheros de §6 y el runner offline funcione.
4. Primera corrida real: guardar el input como fixture el mismo día y registrarlo en el manifest.

---

## 14. Decisiones tomadas (2026-10-20) — huecos ⟨MDRP⟩ rellenados

Cuestionario respondido en sesión sobre `docs/mdrp-jerarquia-objetivos.html`. Implementación en `hier/`.

| # | Pregunta | Decisión | Dónde queda |
|---|---|---|---|
| 1 | Orden de pasadas (D4) | **1A** cobertura › atraso › equidad › costo | `hier/objectives.py: DEFAULT_ORDER` |
| 2 | Medida del atraso | **2A** minutos sobre el *target click-to-door* | `routing.route_feasibility → lateness` |
| 3 | Equidad | **3C** déficit ponderado sobre la **ganancia acumulada del día**: d_c = max(0, media − ganancias_c) entre los ociosos de la ronda | `hier/context.py: _generate_candidates` |
| 4 | Candado entre pasadas | **4C** tolerancia 0 en cobertura, 1e-4 relativa en el resto | `DEFAULT_LOCK_REL_TOL_BY_NAME` |
| 5 | Objetivos protegidos | **5C** ninguno: toda pasada admite `mip_gap` y `time_limit` (el mecanismo queda en el código) | `ObjectiveSpec.protected = False` |
| 6 | Objetivo de repartidores usados / bundles | **6A** no por ahora; se mide `couriers_used` | indicadores por ronda |
| 7 | Horizonte (D1/D5) | **7A** una ronda por modelo en S1; dos rondas como fase 2 del S4 | — |
| 8 | Bono de fair_greedy | **8A** pago plano `pay_per_order × |r|`; sin bono en el MIP | `hier_policy.py` |
| 9 | Determinismo (D9) | **9A** semilla del simulador en corridas y tests; sin semilla en producción | `HierContext(seed=…)` |
| 10 | Siguiente paso | **10A** `batch_sensitivity --policies greedy hier` sobre las 240 instancias, lectura por cluster | `output/sensitivity_greedy_hier_240*.csv` |

Tabla §3.3 resultante (la prioridad más alta corre primero):

| Prioridad | Nombre | Qué maximiza | Sentido original | ¿Protegido? | Candado | ¿Cuándo existe? |
|---|---|---|---|---|---|---|
| 40 | `coverage` | Σ_o y_o | MAX | no | reltol 0 | siempre |
| 30 | `lateness` | −Σ ℓ_cr·x_cr | MIN → −MAX | no | reltol 1e-4 | siempre |
| 20 | `equity` | Σ d_c·\|r\|·x_cr | MAX | no | reltol 1e-4 | si algún ocioso está bajo la media de ganancia acumulada |
| 10 | `cost` | −Σ τ_cr·x_cr | MIN → −MAX | no | reltol 1e-4 | siempre |

D1 ronda = periodo, sin tiempo en el MIP · D2 x_cr sobre columnas enumeradas · D3 y_o, no cubierto = pendiente sin costo (`Impossible[O]`) · D6 F = 0,20, principal cobertura · D7 `on_partial` en proceso (HTTP en el S0 del servicio) · D8 `PrevSolution[C,R]` con guardas.

**Resultado de la decisión 10 (2026-10-20).** Sobre las 240 instancias, hier (orden 1A) frente a greedy: atraso medio
5,6 → 3,7 min (mejor en el 94 % de las instancias), F_Gini 0,1015 → 0,0906 (mejor en el 72 %), **cobertura del día
97,4 % → 95,7 %** (peor en el 62 %). Variantes: costo antes que equidad no cambia la cobertura; costo antes que atraso
la sube a 96,8 % pero devuelve el atraso a 5,0 min. La pérdida es estructural de la decisión por ronda (miopía): la
pasada de atraso deshace bundles y consume repartidores que faltan después. Reabre las dudas 6 (término de capacidad
antes del atraso) y 7 (horizonte de dos rondas). Detalle: `docs/mdrp-jerarquia-objetivos.md` §9.

**Las cuatro políticas de mdrp-sim bajo nuestros objetivos (2026-10-20).** Sobre las mismas 240 instancias
(238 completas): `mdrp`, `mdrp_graph` y `mdrp_graph_prospects` cubren el 54–59 % de los pedidos (su objetivo
throughput − 0,4·atraso descarta rutas que no «valen la pena») y no ganan ninguna instancia bajo ningún orden de
pasadas. `mdrp-sim greedy` (ETA mínimo, sin bundles) cubre el 97,6 % del día, una décima más que nuestro greedy, y
por eso gana la lectura lexicográfica 1A en el 62 % de las instancias pese a duplicar el atraso (11 856 frente a
6 172 min) y tener el mayor costo. La jerarquía 1A sigue siendo la mejor en atraso (3 821 min) y segunda en equidad.
Detalle en `docs/mdrp-jerarquia-objetivos.md` §10 y `simulator/output/compare_objectives.md`.
