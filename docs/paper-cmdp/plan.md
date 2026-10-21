# Plan del paper de mayor ambición: CMDP con equidad para el MDRP (Bogotá)

Fecha: 2026-10-20. Decisión previa: se descarta el Research Topic de Frontiers; el modelo jerárquico
(`simulator/hier/`) queda como enfoque de apoyo y benchmark. Este plan se revisa por etapas: cada etapa
termina con un entregable concreto y una lista corta de decisiones para el autor y el director.

## Qué hay y qué falta (estado al 2026-10-20)

| Pieza | Estado | Dónde |
|---|---|---|
| Simulador DES (SimPy, minutos) con 11 políticas | hecho | `simulator/` |
| Modelo jerárquico cov › lat › eq › cost, corrido en 240 instancias | hecho | `simulator/hier/`, `docs/mdrp-jerarquia-objetivos.md` |
| Aceptación logística | existe pero **sin calibrar** (β ilustrativos sobre pago, km, fatiga) | `simulator/acceptance.py`, `config.py` |
| 24 instancias reales de Bogotá (lat/lng, vehículo, turnos) | datos sí, **loader no** | `real_instancies/` |
| Encuesta n=135 (2021) y 44 entrevistas (2020–21), con trazabilidad al modelo | hecho | `docs/Encuesta_cuantitativo_domiciliarios.xlsx`, `docs/Comportamiento_domiciliarios_cuantitativo.xlsx` |
| Formulación del CMDP (Gini α, estado H_t, tarifa π0+π1·d, balance de rutas, emisiones E(a_t), costo w1/w2) | **no está en este equipo**; solo descrita en `docs/contexto_revista.txt` | tesis |
| BRKGA-Fair, Pay-BRKGA (λ), MIP-Fair, GRASP, horizonte rodante | **no están en este repo** | simulador anterior (mdrp-sim) |
| Revista objetivo y pregunta de investigación del paper | por definir | — |

## Etapa 0 — Insumos y alcance (1 semana)

Objetivo: tener en el repo todo lo que el paper necesita y fijar el alcance.

Entregables:
- `docs/paper-cmdp/formulacion.md`: la formulación del CMDP tal como está en la tesis (conjuntos, estado, acción,
  transición, recompensa, restricción Gini α, H_t, tarifa, balance, emisiones, costo w1/w2), copiada sin cambios.
- El código del BRKGA-Fair / Pay-BRKGA / MIP-Fair / GRASP ubicado (repo o carpeta) y una nota de qué simulador
  lo corre hoy y con qué interfaz.
- Revista objetivo y tipo de artículo (p. ej. Transportation Research Part E, Omega, C&OR, EJOR), con su
  extensión máxima y si acepta material suplementario.
- Pregunta de investigación en una frase y las 3 contribuciones que la responden.

Decisiones para el autor:
1. ¿Un solo simulador (este, `simulator/`) o se mantiene el anterior para los métodos BRKGA? Recomendación: uno
   solo, para que todas las políticas compartan ventana, métricas y aceptación.
2. ¿Unidades de pago en COP (Bogotá) o en unidades mdrplib? Recomendación: COP en Bogotá, mdrplib en las 240
   instancias, con la aceptación expresada en pago/km normalizado para que funcione en ambos.
3. ¿Las 240 instancias de Grubhub entran al paper como generalización o se queda solo Bogotá?

## Etapa 1 — Revisión del modelo contra la evidencia (1–2 semanas)

Objetivo: que cada supuesto del CMDP tenga su evidencia y su grado, y decidir qué cambia.

Entregables:
- `docs/paper-cmdp/modelo-vs-evidencia.md`: tabla supuesto → evidencia entrevistas → evidencia encuesta → grado →
  cómo se declara. Parte de la hoja `Trazabilidad_tesis` y la completa con lo que la tesis asume y la encuesta no
  cubre.
- Lista de cambios propuestos al modelo, cada uno con su justificación empírica.

Cambios que ya se ven venir (a confirmar en la etapa):
- Aceptación: pasar de σ(β0 + β1·pago + β2·km + β3·fatiga) a σ(a + b·ln(pago/km)) con umbral 903 COP/km
  [615, 1 242] y pendiente 2,89 [2,02, 5,23]. Grado C (n=32 decisiones, 11 personas): declararlo y hacer
  sensibilidad sobre el intervalo.
- Dos regímenes de decisión del repartidor: manual (2020, rechazo común) y autoaceptar (2021, 64 %, rechazo casi
  nulo, decisión sobre disponibilidad y no por pedido). Grado A. El CMDP debe poder correr en ambos.
- Estado H_t: la racha triplica el ingreso diario y baja el Gini diario de 0,39 a 0,26; mediana 2 días para
  conseguirla. Justifica memoria de días en H_t. Grado A.
- Tarifa π0 + π1·d: π1 ≈ 155 COP/km no distinguible de 0 (R² 0,02). Grado C. Opciones: tarifa plana, o mantener π1
  como parámetro de política (lo que la plataforma podría hacer), no como descripción de lo que hace.
- Restricción de caja (tope de efectivo 70–80 k COP, consigna cada ~5 pedidos). Grado A/B. Entra solo si las
  instancias de Bogotá tienen marca de pago en efectivo; si no, se declara como extensión.
- Emisiones E(a_t): proxy por vehículo (bici 53 %, e-bici 10 %, moto 37 %). Solo composición, sin factor de
  emisión en la encuesta: usar factores externos y declararlo.
- Heterogeneidad: estratos por vehículo y antigüedad (venezolanos +11 h/semana, OR 8,2 de tasa ≥90 %). Decidir si
  entran como tipos de repartidor o se mencionan como limitación.
- Tiempos de servicio: espera en local 20 min (RIC 15–30) en encuesta vs 60 min en entrevistas (cola). Usar la
  encuesta para el caso típico y las entrevistas para el escenario de estrés.

Decisiones para el autor: cuáles de estos cambios entran al modelo del paper y cuáles quedan como trabajo futuro.

## Etapa 2 — Simulador y datos de Bogotá (2–3 semanas)

Objetivo: que el simulador corra las 24 instancias reales con parámetros calibrados.

Entregables:
- `simulator/loader_bogota.py`: lee `real_instancies/Instancia_k/{couriers,orders,stores}.csv` (lat/lng, vehículo,
  turnos, `expected_drop_off_time` como SLA), velocidad por vehículo, distancias haversine o Manhattan.
- Modo de aceptación `logit_ppk` en `acceptance.py`: σ(a + b·ln(pago/km)), con a y b en `config.py` y los dos
  regímenes (`manual` / `autoaccept`).
- Parámetros de servicio y jornada desde la encuesta (espera en local, decisión en 16–20 s, turnos de 11 h).
- Validación de cara: con greedy y aceptación calibrada, comparar contra la encuesta pedidos/día sin racha
  (mediana 4), pedidos por hora conectada (0,35 sin racha, 1,15 en racha) e ingreso/hora. No se espera igualar;
  se espera estar en el mismo orden de magnitud y explicar las diferencias.
- Tests: `tests/test_loader_bogota.py`, `tests/test_acceptance_ppk.py`.

Decisiones: tratamiento de los pedidos sin tienda cercana, velocidad por vehículo (fuente), y si se usan 10 o más
semillas por corrida (la aceptación es Bernoulli, así que hace falta replicar).

## Etapa 3 — Métodos en un mismo simulador (3–4 semanas)

Objetivo: BRKGA-Fair, Pay-BRKGA, MIP-Fair, GRASP y horizonte rodante corriendo como políticas de `Policy.assign`,
junto a greedy, fair_greedy, los ILP, las 4 de mdrp-sim y el jerárquico.

Entregables:
- Un módulo por método en `simulator/`, con la misma interfaz y los mismos candidatos de ruta (`routing.py`).
- Verificación en `tests/fixtures/hier/toy.json` (3 repartidores, 4 pedidos, 121 asignaciones factibles, óptimo
  conocido por fuerza bruta) y en una instancia de Bogotá.
- Nota de qué se adaptó y qué no se portó, como ya hace `mdrpsim_policies.py`.

Riesgo: si el BRKGA del simulador anterior decide con otra información (p. ej. horizonte completo o pago
variable), la comparación no es justa. Documentarlo antes de correr.

## Etapa 4 — Diseño experimental (1 semana, antes de correr nada)

Factores: método × régimen de aceptación (manual / autoaceptar) × α (restricción Gini) × λ (Pay-BRKGA) ×
umbral del logit (puntual y extremos del IC). Instancias: 24 de Bogotá (principal), 240 de Grubhub (generalización,
si se decidió en la etapa 0). Semillas: ≥10 por celda.
Métricas: cobertura, atraso (minutos y pedidos tarde), Gini de ingreso por hora, F_Deficit frente al salario mínimo
(SMMLV 2021 por hora 4 368 COP), costo, emisiones, repartidores usados, tiempo de cómputo por ronda.
Entregables: `simulator/batch_paper.py` (un proceso por corrida, reintentos, como `batch_hier_clusters.py`),
lista cerrada de tablas y figuras del paper, y estimación del tiempo de cómputo antes de lanzar.

## Etapa 5 — Corridas y análisis (2–3 semanas)

- Frentes de Pareto cobertura/atraso vs Gini para cada método (λ en Pay-BRKGA, α en MIP-Fair, candado en el
  jerárquico).
- Efecto del régimen de aceptación: cuánto pierde cada método cuando el repartidor puede rechazar.
- Sensibilidad al umbral del logit dentro del IC.
- La miopía del jerárquico (−1,7 pts de cobertura) como argumento a favor del estado H_t y del horizonte.
- Comparación con mdrp-sim: sus políticas cubren 54–59 % con su objetivo original; cuidado con leer sus Gini bajos.

## Etapa 6 — Escritura (3–4 semanas, solapada con la 5)

Estructura propuesta: introducción (bienestar del repartidor como objetivo de despacho, no como sanción);
literatura (FairFoody AAAI 2022, WORK4FOOD IJCAI 2022, Southampton ESWA 2024, RL arXiv 2501.05808, mdrplib);
datos de comportamiento (encuesta + entrevistas, con grados de evidencia y limitaciones); modelo CMDP; métodos;
simulador y calibración; experimentos; discusión; limitaciones (muestreo por intercepción, logit n=32, 2020 vs
2021, pago en bandas, autorreporte).

## Calendario tentativo

| Etapa | Semanas | Fin estimado |
|---|---|---|
| 0 Insumos y alcance | 1 | 27 oct 2026 |
| 1 Modelo vs evidencia | 2 | 10 nov 2026 |
| 2 Simulador y Bogotá | 3 | 1 dic 2026 |
| 3 Métodos | 4 | 12 ene 2027 (con receso) |
| 4 Diseño experimental | 1 | 19 ene 2027 |
| 5 Corridas y análisis | 3 | 9 feb 2027 |
| 6 Escritura | 4 | 9 mar 2027 |

Las etapas 1 y 2 pueden ir en paralelo si el autor revisa el modelo mientras se construye el loader.

## Estado de la Etapa 0 (actualizado 2026-10-20)

| Entregable | Estado | Archivo |
|---|---|---|
| Formulación del CMDP copiada de la tesis | hecho | `docs/paper-cmdp/formulacion.md` |
| Código BRKGA/MIP-Fair/GRASP ubicado y nota de interfaz | hecho; hallazgo: BRKGA-Fair, Pay-BRKGA y MIP-Fair no existen como código, hay que construirlos en la Etapa 3 | `docs/paper-cmdp/codigo-metodos.md` |
| Revista objetivo | borrador con recomendación (TR-E, EJOR de respaldo); falta decisión del director | `docs/paper-cmdp/alcance.md` |
| Pregunta y 3 contribuciones | borrador; falta aprobación | `docs/paper-cmdp/alcance.md` |

Pendiente del autor antes de cerrar la Etapa 0: las tres decisiones de arriba, la revista, la pregunta, y
confirmar si existe código de GRASP o de los métodos fair en otro equipo o repo.

## Decisiones del autor (2026-10-20, tarde)

1. Revista: EJOR, Innovative Applications (35 pp con todo; suplemento en linea).
2. Pregunta y contribuciones: reescritas en alcance.md (version 2, sesgo EJOR); pendiente visto bueno.
3. Un solo simulador (simulator/). Los scripts MIC 2026 son solo referencia.
4. No hay codigo fuera del repo. BRKGA-Fair, Pay-BRKGA, MIP-Fair y el porte del BRKGA-Coverage se construyen.
   El GRASP se cita, no se reimplementa.

Efecto sobre la Etapa 3: pasa de "portar" a "construir" cuatro piezas (porte BRKGA-Coverage, BRKGA-Fair,
Pay-BRKGA, MIP-Fair). Se sugiere 5-6 semanas en vez de 3-4, en este orden: porte del BRKGA (reusa decoder.py
y operators.py), BRKGA-Fair (cambio solo en el decoder), MIP-Fair (extiende ilp_policy.py con Gini
linealizado sobre H_t), Pay-BRKGA (el unico que toca el pago). Calendario revisado: Etapa 3 hasta
26 ene 2027, Etapa 4 hasta 2 feb, Etapa 5 hasta 23 feb, Etapa 6 hasta 23 mar 2027. Lo que no cambia:
Etapas 1 y 2 pueden ir en paralelo y arrancan ya.

## Estado de las Etapas 1 y 2 (2026-10-20, noche)

| Entregable | Estado | Archivo |
|---|---|---|
| Etapa 1: tabla supuesto -> evidencia -> grado -> declaración (22 filas), cambios propuestos, decisiones | borrador completo; falta visto bueno del autor | `docs/paper-cmdp/modelo-vs-evidencia.md` |
| Etapa 2: loader de instancias reales (proyección plana por instancia, filtro de radio, velocidad por vehículo, SLA por pedido, COP, sin pago garantizado) | hecho, 17 tests | `simulator/loader_real.py`, `tests/test_loader_real.py` |
| Etapa 2: aceptación `logit_ppk` con regímenes `manual` / `autoaccept` | hecho, 12 tests; reproduce 0,57 / 0,81 / 0,91 de la hoja `Parametros_modelo` | `simulator/acceptance.py`, `tests/test_acceptance_ppk.py` |
| Etapa 2: velocidad por courier en el motor (`speed_of`), sin cambio para mdrplib | hecho; `test_hier` sigue verde | `distance.py`, `routing.py`, `simulator.py`, `models.py` |
| Etapa 2: CLI (`--acceptance-mode logit_ppk --regime --ppk-threshold --ppk-slope --circuity --speeds --pickup-service`, detección automática de `real_instancies`) | hecho | `simulator/run.py`, `config.py` |
| Etapa 2: validación de cara contra la encuesta | script listo, **sin correr**: la máquina falla (ver abajo) | `simulator/validate_real.py` |
| Clasificación de las 24 instancias por ciudad | hecho: seis ciudades, no solo Bogotá | `docs/paper-cmdp/instancias_reales.csv`, sección 5 de `modelo-vs-evidencia.md` |

Cambio respecto al plan: el entregable `loader_bogota.py` se llama `loader_real.py` y los campos de
configuración `real_*`, porque las instancias cubren Bogotá, Medellín, Barranquilla, Cali, Bucaramanga y
Pereira. La calibración conductual (encuesta y entrevistas) es de Bogotá; para las otras cinco ciudades
es un supuesto de transferencia declarado. Decisión para el autor: usar las seis ciudades (recomendado)
o solo las cuatro de Bogotá.

**Bloqueo de hardware (2026-10-20).** Cualquier simulación de más de 1-2 s de CPU sostenida muere en
este equipo con violación de acceso o errores de tipo imposibles, en Python 3.10 y 3.14, con sandbox o
sin él, con cualquier afinidad y también con el reloj limitado al 70 %. Windows registra 23 pantallazos
azules (BugCheck 0x3B, c0000005) entre el 24 sep y el 20 oct. CPU: i9-14900K (microcódigo 0x12B ya
instalado). Es el patrón conocido de degradación de Intel 13.ª/14.ª gen o inestabilidad de memoria
XMP. Los tests unitarios (menos de 1 s) sí pasan: 42 en Python 3.10. Hasta que el equipo se repare o
se cambie, las corridas de las Etapas 2 (validación), 4 y 5 deben hacerse en otra máquina; el repo es
autocontenido (`simulator/`, `real_instancies/`, `public_instances/`).

Siguiente paso cuando haya máquina: `python validate_real.py --instances Instancia_22 Instancia_4
Instancia_10 --seeds 3 --pickup-service 20 60` y comparar con la encuesta (4 pedidos/día, 0,35
pedidos/h, 2.622 COP/h); luego la Etapa 3 (porte del BRKGA) según el orden ya decidido.

## Estado de la Etapa 3 (2026-10-20, noche)

| Pieza | Estado | Archivo |
|---|---|---|
| 1. Porte del BRKGA-Coverage/Travel a `Policy.assign` | hecho, 12 tests (54 en total, verdes); `--policy brkga` | `simulator/brkga_policy.py`, `tests/test_brkga.py`, nota `docs/paper-cmdp/porte-brkga.md` |
| 2. BRKGA-Fair (decoder con déficit de H_t) | hecho, 6 tests (60 en total, verdes por archivo); `--policy brkga_fair`, `brkga_fair_weight` (min), `brkga_fair_basis` hourly/total | `simulator/brkga_fair.py`, `tests/test_brkga_fair.py`, sección BRKGA-Fair de `porte-brkga.md` |
| 3. MIP-Fair (Gini linealizado sobre H_t) | hecho, 7 tests con CBC (67 en total, verdes por archivo); `--policy mip_fair`, α elástica, prioridad fairness/coverage, base hourly/total | `simulator/mip_fair.py`, `tests/test_mip_fair.py`, sección MIP-Fair de `porte-brkga.md` |
| 4. Pay-BRKGA (cobertura + F_Deficit, pago variable) | hecho, 8 tests (75 en total, verdes por archivo); `--policy pay_brkga`, gen de pago por repartidor en ±`pay_range`, fitness con cobertura esperada bajo el modelo de aceptación | `simulator/pay_brkga.py`, `tests/test_pay_brkga.py`, sección Pay-BRKGA de `porte-brkga.md` |

Hallazgo de la pieza 1 (decisión del autor): el decodificador original puntúa por hora de fin, así que
nunca elegía lotes; `max_batch_size=3` del MIC 2026 era inoperante. El porte conserva la regla
(`brkga_score=finish`) y añade `finish_per_order`, que sí agrupa. Recomendación: usar `finish_per_order`
como BRKGA-Coverage en el paper y citar la variante original en el suplemento. Detalle en
`porte-brkga.md`. Sin correr un día completo en esta máquina (bloqueo de hardware).

Etapa 3 cerrada en código el 2026-10-20 (ver "Cierre de la Etapa 3" en `porte-brkga.md`). Pendiente de la
Etapa 3: verificación en una instancia real cuando haya máquina, y las decisiones del autor (brkga_score,
peso y base de BRKGA-Fair, alcance del Gini y prioridad de MIP-Fair, pesos de Pay-BRKGA). Siguiente: Etapa 4
(diseño experimental), que no requiere corridas.

Decisiones de la Etapa 3 tomadas el 2026-10-20 por encargo del autor (E1–E6, tabla "Decisiones tomadas" en
`porte-brkga.md` y slide 13 del deck): `finish_per_order`, déficit por hora, peso 10 min con barrido, Gini
sobre todos los conectados (`H_all`), prioridad equidad › cobertura sin minwage/routebalance, Pay-BRKGA como
suma ponderada con barrido de λ_pay. Siguen abiertas solo las de la Etapa 1 (`modelo-vs-evidencia.md` §4).

## Estado de la Etapa 4 (2026-10-20, noche)

| Entregable | Estado | Archivo |
|---|---|---|
| Diseño experimental: zona de 3 km, factores, 18 configuraciones, X0–X3 (11.922 corridas), métricas, análisis pareado, T1–T8 / F1–F8, presupuesto | hecho | `docs/paper-cmdp/diseno-experimental.md` |
| `batch_paper.py`: malla por experimento, un proceso por corrida, reintentos, timeout, reanudable, tablas por repartidor, `--dry-run`, `--estimate` | hecho y probado en local | `simulator/batch_paper.py` |
| Piloto local: Pereira día completo con los 7 métodos; Bogotá 12:00–14:00 con 6 configuraciones; **X0 completo** (42 corridas, 0 fallos, 2 h 50 min): cobertura plana entre métodos, Gini corporativo medio 0,419 (malla de α se mantiene), greedy el más lento (H7, 35 min en Bogotá) | hecho; números en §8 del diseño | `simulator/output/paper/pilot.csv` |
| Presupuesto: ≈ 615 h de CPU en total (cota superior) = 1,6 días con 16 procesos | estimado | diseño §9 |

Hallazgos que cambiaron código (detalle en diseño §10 y `porte-brkga.md`, "E5 revisada"): MIP-Fair era
O(n²) por ronda y no terminaba (reformulado, exacto, tests verdes); la prioridad equidad › cobertura
entrega cobertura 0 desde el arranque en frío (default ahora cobertura › Gini, E5'); MIP-Fair en la malla
con top-k 8; el loader tolera los ids con prefijo `c` de la instancia 3.

**Bloqueo resuelto (pieza 1b, misma noche):** BRKGA-Coverage cubría 0,16–0,21 en Bogotá frente a 0,44 del greedy (en Pereira
igualaba) porque el decodificador buscaba los K = 3 repartidores de mayor clave global dentro del prefiltro de la
ruta; ahora los toma entre los candidatos de la ruta (`porte-brkga.md`, cambio 6). Bogotá 12–14 h: 0,446 en 30 s.
Pay-BRKGA (0,555 en Pereira) era el mismo defecto: ahora 0,731. Presupuesto total baja a ≈ 475 h de CPU.
Pendiente del autor: visto bueno a E5' y las decisiones de la Etapa 1. Siguiente: X0 (42 corridas) aquí o en la máquina de cómputo.

## Estado de las Etapas 5 y 6 (2026-10-21, madrugada)

- X1 lanzado el 21 oct 00:05 en la máquina del autor (`batch_paper.py --experiment main --workers 4`, orden por
  semilla, reanudable; `simulator/output/paper/main.csv`). Estimación: ≈ 235 h de CPU, 2,5 días de pared.
  Después: X3 (840) y X2 (2.400, con el α de la rodilla). Resúmenes con `analyze_paper.py --main`.
- Etapa 6 arrancada en paralelo: el director dejó sus dos manuscritos EJOR en `papers/`; guía de estilo
  extraída en `docs/paper-cmdp/paper/estilo-ejor.md` y borrador reescrito con esa estructura
  (`main.tex`, 878 líneas, 61 TODO, la mayoría celdas de resultados; borrador anterior `main_v0.tex`).
  No compilado: no hay TeX en esta máquina. Figuras F1 y F2 en `docs/paper-cmdp/figures/`.
- **2026-10-21, 04:30.** X1 relanzado a 01:15 con 12 procesos (≈ 290 corridas por hora); semilla 1 completa a
  las 04:06 (864 celdas, 0 fallos) y analizada: `diseno-experimental.md` §12, slide 16 del deck, T3 y T4 del
  paper con valores preliminares. Lecturas: cobertura idéntica en auto-aceptación; garantía barata; el ILP
  exacto baja más el Gini que MIP-Fair porque el Gini sobre activos premia concentrar el trabajo; α no mueve
  a MIP-Fair; Pay-BRKGA responde a λ. Decisiones: E8 (ablación MIP-Fair con holgura de cobertura, X3), α*
  provisional 0,40 para X2, columnas 0,45 y 0,50 en la tabla de cumplimiento; análisis A1 pendiente (Gini
  sobre todos los conectados y sobre ingreso total, desde `output/paper/couriers/`). X1 completo estimado el
  22 oct por la mañana; después X3 y X2. El paper compila (tectonic, 36 pp.) y vive también en
  `dalvarezmartinez/mdrp-paper` (subtree de `docs/paper-cmdp/paper`), importado en Overleaf por el director.
- **2026-10-21, 04:20 (A1).** El Gini sobre elegibles (conectados ≥ 1 h, ceros incluidos) invierte la
  conclusión: greedy 0,30 frente a 0,52–0,57 de todos los demás métodos; los métodos bajan el F_Gini sobre
  activos excluyendo repartidores. Decisión provisional E9 (ratificar con el director): la restricción y el
  reporte pasan al Gini sobre elegibles; variantes de segunda generación (déficit sobre elegibles ociosos,
  MIP-Fair con holgura E8) tras X1, evaluadas en X3. `analyze_couriers.py` nuevo; F3 y F4 preliminares
  generadas (`figures_paper.py --fig f3f4`). Detalle en `diseno-experimental.md` §12.6.
- **2026-10-21, 16:30 (E9 ratificada).** El director ratificó E9. Paper reescrito sobre la población elegible
  (resumen, introducción, descripción, métricas con C^e y F_Gini^act, T3 con 10 columnas, tabla de alcances,
  T5 de cumplimiento con α 0,30–0,50, frentes F3/F4, discusión y conclusión), con las semillas 1–4 de X1
  (3.456 celdas). Resultado central confirmado: greedy 0,30, todos los demás 0,50–0,57. A2: las políticas de
  primera generación leen pago por hora *activa* (productividad), no conectada; explica que α sea inerte.
  Decisión E10: variantes de segunda generación (exposición, población elegible, ε de E8) en el worktree
  `C:/MDRP-dev` mientras corre X1; X3 crece a ≈ 2.040 corridas; α* para X2 se decide tras X3. Detalle en
  `diseno-experimental.md` §12.7.
- **2026-10-21, 17:15 (E10 piloteada).** Segunda generación implementada en el worktree `C:/MDRP-dev` (rama
  `e10-variants`, 84 tests). Piloto en dos zonas: la base de exposición sola no mueve el Gini de elegibles; el
  prefiltro consciente del déficit (E10b, `fair_cand_deficit_k`) sí: MIP-Fair 0,58 → 0,45–0,49 y BRKGA-Fair
  0,61 → 0,50–0,52 sin perder cobertura; brecha restante 0,15–0,20 con el greedy. Hallazgo: el greedy del
  simulador ya ordena por pedidos entregados (el menos servido elige primero); el paper lo describía mal y
  se corrigió (1b41ac6). Grilla gen2 de X3 fijada (1.920 corridas) + supp (1.080). Detalle en
  `diseno-experimental.md` §12.8. X1 en 4.177/8.640 a las 17:03; fin estimado 22 oct ≈ 10–11 h.
