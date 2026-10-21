# Jerarquía de objetivos para el despacho del MDRP (copia revisable del deck)

Página publicada: `docs/mdrp-jerarquia-objetivos.html`. Código en `simulator/hier/` (el repo se reestructuró el 2026-10-20: todo el simulador vive en `simulator/`).
Página publicada: `docs/mdrp-jerarquia-objetivos.html` (construir con `python docs/build_deck.py`
desde `docs/mdrp-jerarquia-objetivos.src.html`). Épica de referencia:
`Epicas/mdrp-marco-de-optimizacion.md`. Fecha: 2026-10-19.

## 1. Objetivos actuales (inventario)

Los cinco objetivos del ILP (`ilp_policy.py`) maximizan **cobertura** y difieren sólo en el desempate,
forzado con un término dominante `M·|r|`:

| `cfg.objective` | expresión | veredicto |
|---|---|---|
| `max_coverage` | Σ \|r\|·x | se conserva como pasada 1 |
| `max_throughput` | Σ (M\|r\| − 0,01·τ − 0,02·ℓ)·x | **desaparece**: suma ponderada de dos objetivos (prohibida por el marco §1.2) |
| `min_lateness` | Σ (M\|r\| − ℓ)·x | pasada 2 |
| `min_cost` | Σ (M\|r\| − τ)·x | pasada 4 |
| `max_equity` | Σ \|r\|·(M + 1/(1+e_c))·x | pasada 3, con un déficit con unidades en lugar de 1/(1+e) |

`greedy` y `fair_greedy` son reglas sin función objetivo; `fair_greedy` paga un bono fuera del modelo.
Las métricas (`metrics.py`) son salidas, no objetivos, pero cada pasada queda alineada con una:
P1 ↔ `coverage_rate`, P2 ↔ `overage_mean`, P3 ↔ `F_Deficit`/`F_Gini`, P4 ↔ minutos de repartidor.

## 2. Orden propuesto (tabla §3.3 de la épica)

| Prioridad | Nombre | Qué maximiza | Sentido original | ¿Protegido? | ¿Cuándo existe? |
|---|---|---|---|---|---|
| 40 | `coverage` | Σ_o y_o (pedidos asignados en la ronda) | MAX | no (candado 0) | siempre |
| 30 | `lateness` | −Σ ℓ_cr·x_cr (minutos sobre el target c2d) | MIN → −MAX | no (candado 1e-4) | siempre |
| 20 | `equity` | Σ d_c·\|r\|·x_cr, d_c = max(0, w̄ − w_c) sobre la ganancia acumulada del día | MAX | no (candado 1e-4) | si algún ocioso está bajo la media |
| 10 | `cost` | −Σ τ_cr·x_cr (minutos de repartidor) | MIN → −MAX | no (candado 1e-4) | siempre |

Razones: cobertura es lo que el negocio no negocia; el atraso es la promesa al cliente y lo que mide el
evaluador oficial; la equidad es el tema de la tesis y va antes que el costo; el costo es el residuo y
de paso prefiere bundles y deja repartidores libres.

## 3. Modelo de una ronda (`hier/context.py`)

Conjuntos: C repartidores ociosos, O pedidos pendientes, R rutas enumeradas (`routing.generate_store_routes`),
K ⊂ C×R candidatos tras el prefiltro anotado (`NOT_TOPK`, `REJECTED`, `SLA_INFEASIBLE`).
Variables: x_cr ∈ {0,1}, y_o ∈ {0,1}. Familias con nombre estable: `Cover[O]` (y_o = Σ x),
`CourierOnce[C]` (Σ x ≤ 1), `Impossible[O]` (y_o = 0, código `NO_CANDIDATE`), `PrevSolution[C,R]` (x = 1,
reproceso con guardas). Una pasada por objetivo con `setObjectiveN`, todos MAX, candado `abstol`/`reltol`
por pasada, `time_limit`/`mip_gap` en el `MultiobjEnv` de cada pasada; cobertura rechaza `mip_gap`.

## 4. Ejemplo didáctico (`tests/fixtures/hier/toy.json`)

3 repartidores, 4 pedidos, 2 restaurantes, bundles de 2 → 18 candidatos, 121 asignaciones factibles.

| Orden | Resultado | cobertura | atraso | equidad | minutos |
|---|---|---|---|---|---|
| cov › lat › eq › cost | C1→(O1,O2), C2→O4, C3→O3 | 4 | 8 | 22,0 | 44 |
| cov › eq › lat › cost | C1→(O1,O2), C3→(O4,O3) | 4 | 14 | 25,3 | 36 |

Una suma ponderada `−λ·atraso − minutos + equidad` salta de la segunda a la primera en λ = 2.
Verificado contra Gurobi: `python diag_hier_case.py --toy --brute-force` → MATCH.

## 5. Resultados en 0o100t100s1p100 (505 pedidos, 113 repartidores)

| política | cobertura | c2d medio | atraso medio | pago | F_Gini | tiempo |
|---|---|---|---|---|---|---|
| greedy | 100 % | 35,9 | 2,2 | 5 190,75 | 0,0741 | 0,03 s |
| ilp max_coverage (CBC) | 100 % | 37,6 | 3,1 | 5 310,50 | 0,0809 | 4,3 s |
| ilp min_lateness | 100 % | 36,1 | 2,3 | 5 275,75 | 0,0772 | 4,0 s |
| ilp max_equity | 100 % | 37,3 | 2,7 | 5 200,75 | 0,0666 | 4,0 s |
| ilp min_cost | 100 % | 35,0 | 2,1 | 5 315,75 | 0,0824 | 4,1 s |
| **hier cov›lat›eq›cost** | 100 % | 35,3 | 2,2 | 5 213,25 | 0,0684 | 0,58 s |
| hier cov›eq›lat›cost | 100 % | 35,4 | 2,3 | 5 211,25 | 0,0703 | 0,57 s |

235 rondas, todas las pasadas `optimal`, 2,3 ms de media por ronda; la pasada de equidad existió en 135 rondas.

## 6. Dudas y decisiones (2026-10-20)

1. ¿Atraso antes que equidad? → **1A** atraso primero (como se recomendó).
2. ¿Atraso en minutos o en pedidos tarde? → **2A** minutos.
3. ¿Déficit ponderado o max-min real? → **3C** déficit sobre la ganancia acumulada del día (distinto a la recomendación, que era por hora).
4. ¿Tolerancia del candado? → **4C** 0 en cobertura, 1e-4 relativo en el resto (distinto a la recomendación).
5. ¿Qué objetivos son protegidos? → **5C** ninguno (distinto a la recomendación).
6. ¿Objetivo de repartidores usados / bundles? → **6A** no por ahora; medir `couriers_used`.
7. ¿Modelo por ronda o con horizonte? → **7A** por ronda en S1; dos rondas como fase 2 del S4.
8. ¿Bono de fair_greedy? → **8A** pago plano.
9. Determinismo → **9A** semilla del simulador en corridas y tests, sin semilla en producción.
10. Siguiente paso → **10A** batch greedy + hier sobre las 240 instancias, leído por cluster.

## 7. Decisiones D1–D9

D1 ronda = periodo, sin tiempo en el MIP (hecho) · D2 x_cr sobre columnas enumeradas (hecho) · D3 y_o, no cubierto = pendiente sin costo (hecho) · D4 orden decidido 1A, candado 4C, sin protegidos 5C (hecho) · D5 una fase (decidido 7A) · D6 F = 0,20, principal cobertura (hecho) · D7 `on_partial` en proceso; HTTP en el S0 del servicio · D8 `PrevSolution` con guardas (hecho) · D9 semilla del simulador en corridas, sin semilla en producción (hecho).

## 8. Cómo reproducir

```
cd simulator
python diag_hier_case.py --toy --brute-force
python diag_hier_case.py --toy --order coverage equity lateness cost
python diag_hier_case.py --toy --skip lateness --mip-gap 0.05
python diag_hier_case.py --instance 0o100t100s1p100 --time 720 --window 10
python run.py --instance 0o100t100s1p100 --policy hier --save
python diag_hier_day.py --instance 0o100t100s1p100
python -m pytest tests/test_hier.py -q
```

## 9. Resultados en las 240 instancias (decisión 10A, 2026-10-20)

`batch_hier_clusters.py --policies greedy hier` (una corrida por proceso, 3 reintentos, 0 fallos, 466 s con 3 workers).
Medias por cluster; «mejor» = porcentaje de instancias donde hier mejora a greedy en esa métrica.

| Cluster | n | cobertura greedy · hier | atraso greedy · hier (min) | hier mejor atraso | F_Gini greedy · hier | hier mejor Gini | s/día hier |
|---|---|---|---|---|---|---|---|
| 0 Dispersas, con holgura | 24 | 99,5 % · 99,6 % | 5,9 · 3,3 | 100 % | 0,0381 · 0,0459 | 21 % | 5,0 |
| 1 Pequeñas y compactas | 105 | 98,4 % · 97,0 % | 4,4 · 3,3 | 86 % | 0,1049 · 0,0953 | 70 % | 2,6 |
| 2 Medianas y cargadas | 87 | 96,2 % · 93,8 % | 6,5 · 4,2 | 100 % | 0,1132 · 0,0982 | 87 % | 5,4 |
| 3 Grandes y saturadas | 24 | 95,4 % · 93,2 % | 7,1 · 4,1 | 100 % | 0,1073 · 0,0871 | 79 % | 9,8 |
| **Todas** | 240 | 97,4 % · 95,7 % | 5,6 · 3,7 | 94 % | 0,1015 · 0,0906 | 72 % | 4,6 |

Lectura: la jerarquía gana en atraso (−1,9 min, mejor en el 94 % de las instancias) y en equidad (mejor en el 72 %),
pero **pierde 1,7 puntos de cobertura del día** (peor en el 62 % de las instancias). El modelo cubre el máximo en cada
ronda; la pérdida viene de la miopía por ronda: entre candidatos con atraso cero, la pasada de equidad elige
repartidores lejanos (bajo la media) y gasta minutos; pedidos posteriores superan su SLA dura antes de que alguien
quede libre. Es la duda 7 (horizonte) apareciendo en los datos. Variante en evaluación: costo antes que equidad.

### Variantes de orden (240 instancias, mismas condiciones)

| Orden | Cobertura | Atraso medio | F_Gini | Bundle medio |
|---|---|---|---|---|
| greedy | 97,4 % | 5,6 | 0,1015 | 1,11 |
| hier cov › lat › eq › cost (decisión 1A) | 95,7 % | 3,7 | 0,0906 | 1,09 |
| hier cov › lat › cost › eq | 95,8 % | 3,7 | 0,0988 | 1,09 |
| hier cov › cost › lat › eq | 96,8 % | 5,0 | 0,1083 | — |

Costo antes que equidad no cambia la cobertura: la equidad no es la causa. Costo antes que atraso recupera 1,1 puntos
(el costo en minutos prefiere los bundles y deja repartidores libres) pero devuelve 1,3 min de atraso y la equidad.
Conclusión: la pérdida de cobertura del día es estructural de la decisión por ronda (miopía), no del orden elegido.
Opciones para recuperarla sin perder el atraso: (a) un término de capacidad antes del atraso (repartidores usados o
minutos comprometidos, duda 6, que se pospuso); (b) el horizonte de dos rondas (duda 7, fase 2 del S4).

## 10. Las cuatro políticas de mdrp-sim bajo nuestros objetivos (2026-10-20)

Políticas de `sebastian-quintero/mdrp-sim` (`policies/dispatcher/matching/`: `greedy`, `mdrp`, `mdrp_graph`,
`mdrp_graph_prospects`; `modified_mdrp` no se porta porque exige un motor de repartidores distinto), ya portadas en
`simulator/mdrpsim_policies.py` con su objetivo original (throughput − 0,4·atraso). Corridas sobre las 240 instancias
con `batch_hier_clusters.py` (238 completas para las ocho políticas; 2 corridas de `mdrp_graph_prospects` fallaron
por violación de acceso tras tres reintentos, sin Gurobi de por medio). Medias por instancia; detalle en
`simulator/output/compare_objectives.md`.

| Política | Optimiza por dentro | P1 cobertura | P2 atraso (min totales) | P3 F_Gini | P4 minutos de repartidor | s/día |
|---|---|---|---|---|---|---|
| greedy | regla | 97,4 % | 6 172 | 0,1013 | 14 554 | 0,15 |
| hier cov›lat›eq›cost (1A) | jerarquía | 95,7 % | 3 821 | 0,0906 | 14 303 | 5,1 |
| hier cov›lat›cost›eq | jerarquía | 95,9 % | 3 842 | 0,0933 | 13 508 | 5,1 |
| hier cov›cost›lat›eq | jerarquía | 96,8 % | 5 093 | 0,1004 | 12 584 | 4,9 |
| mdrp-sim greedy | ETA mínimo, sin bundles | 97,6 % | 11 856 | 0,0895 | 16 160 | 0,10 |
| mdrp-sim mdrp (MIP) | throughput − 0,4·atraso | 59,1 % | 1 | 0,0579 | 6 582 | 19,8 |
| mdrp-sim mdrp_graph | relajación LP del MIP | 59,1 % | 1 | 0,0579 | 6 582 | 17,2 |
| mdrp-sim mdrp_graph_prospects | LP con prospectos a 3 km | 54,2 % | 232 | 0,0745 | 5 661 | 9,2 |

Ganador lexicográfico por instancia (% de las 238), leyendo los mismos resultados con cada orden de pasadas:

| Orden de lectura | greedy | hier 1A | hier cov›lat›cost›eq | hier cov›cost›lat›eq | mdrp-sim greedy | mdrp / graph / prospects |
|---|---|---|---|---|---|---|
| cov›lat›eq›cost (1A) | 19,3 | 3,8 | 10,1 | 5,0 | 61,8 | 0 |
| cov›lat›cost›eq | 19,3 | 3,8 | 10,9 | 5,0 | 60,9 | 0 |
| cov›cost›lat›eq | 18,9 | 0 | 2,1 | 42,4 | 36,6 | 0 |
| cov›eq›lat›cost | 27,3 | 8,0 | 4,2 | 7,1 | 53,4 | 0 |

Lectura:
- Las tres variantes con objetivo propio de mdrp-sim (`mdrp`, `mdrp_graph`, `mdrp_graph_prospects`) cubren entre el
  54 % y el 59 % de los pedidos: su función throughput − 0,4·atraso deja sin asignar las rutas que no «valen la pena».
  Con cobertura como primera pasada no ganan ninguna instancia bajo ningún orden. Sus cifras de atraso, Gini y costo
  son bajas porque entregan la mitad de los pedidos, no porque sean mejores. `mdrp` y `mdrp_graph` coinciden
  exactamente (relajación LP integral del mismo modelo).
- `mdrp-sim greedy` (ETA mínimo por repartidor, sin bundles) es la que más pedidos cubre en el día (97,6 %, una décima
  más que nuestro greedy) y por eso gana la lectura lexicográfica en el 62 % de las instancias con el orden 1A, pese a
  tener el doble de atraso (11 856 min frente a 6 172) y el mayor costo. Es la consecuencia literal de poner cobertura
  del día con tolerancia 0 por delante de todo.
- La jerarquía (1A) sigue siendo la mejor en atraso (−38 % frente a greedy, mejor en el 94 % de las instancias) y la
  segunda en equidad; su pérdida de 1,7 puntos de cobertura del día es lo que la deja sin ganar la lectura
  lexicográfica. Con el orden cov›cost›lat›eq la variante correspondiente gana el 42 % de las instancias.
- Conclusión: ninguna política domina. Si la cobertura del día manda con tolerancia 0, gana `mdrp-sim greedy`;
  si se admite una tolerancia de cobertura de ~2 puntos, la jerarquía 1A domina en atraso y equidad. Eso vuelve a
  poner sobre la mesa el horizonte de dos rondas (duda 7) o un término de capacidad (duda 6) para que la jerarquía
  no pierda cobertura del día.

## 11. Decisiones de la Etapa 3 del paper CMDP (2026-10-20, slide 13)

Los cuatro métodos (porte BRKGA, BRKGA-Fair, MIP-Fair, Pay-BRKGA) corren bajo `Policy.assign`
(`docs/paper-cmdp/porte-brkga.md`). Seis decisiones tomadas y justificadas:

- **E1 Puntaje del decodificador BRKGA: `finish_per_order`** (default). Con la regla original `finish` un
  lote nunca gana a un singleton del mismo repartidor, así que el BRKGA del MIC 2026 nunca agrupó; el ILP y
  la jerarquía sí agrupan y la comparación sería injusta. La regla original se reporta en el suplemento.
- **E2 Base del déficit de BRKGA-Fair: ingresos por hora activa.** Es la base de F_Gini y de eq:fair_const;
  «total» castiga a quien se conectó tarde, no a quien fue mal servido.
- **E3 Peso del déficit: 10 min por defecto, barrido {0, 5, 10, 20, 40} en la Etapa 4.** Una ruta dura 15–25
  min; 10 min pesan como media ruta. El control myopic-fair es el `brkga` liso (una ruta por repartidor y ronda).
- **E4 Gini de MIP-Fair sobre todos los conectados** (`mipfair_scope=all`, nuevo `H_all` en el estado; los
  ocupados entran con ingresos fijos). eq:fair_const es sobre C; los libres de una ronda son los que menos
  llevan y su Gini aparte es sesgado.
- **E5 (revisada el 20 oct, E5': cobertura › exceso de Gini › desempate; ver sección 14). Texto original:** MIP-Fair con prioridad equidad › cobertura, sin eq:minwage ni eq:routebalance. Es la lectura de
  eq:fair_const como restricción dura y la única que traza la curva Pareto al barrer α. El salario mínimo lo
  ataca Pay-BRKGA y se reporta como F_Deficit; el balance de rutas es extensión de tesis.
- **E6 Pay-BRKGA como suma ponderada**, rango ±30 % provisional, λ_def = 0,5, barrido λ_pay ∈ {0,1; 0,2; 0,5; 1}.
  Cada ronda despacha una sola acción, un frente por ronda no es accionable; la tesis pide el barrido de λ.
  El rango se ajusta con la dispersión de pago de la encuesta (V116) en la Etapa 4.

Abiertas para el autor: las decisiones de la Etapa 1 (tarifa, circuidad, velocidades, holgura SLA, seis
ciudades, emisiones, semillas) en `docs/paper-cmdp/modelo-vs-evidencia.md` §4.

## 12. Etapa 4: diseño experimental (2026-10-20, slide 14)

Diseño cerrado en `docs/paper-cmdp/diseno-experimental.md`; malla y lanzador en `simulator/batch_paper.py`.

- **Unidad experimental: zona de 3 km** alrededor del centro de cada instancia, día completo. Bogotá
  10.215 pedidos y 2.650 repartidores; Pereira 568 y 253; media 3.612 pedidos por zona. Regla: si el
  método más caro supera 20 min por corrida en Bogotá, 2 km para las seis ciudades.
- **Factores:** método (18 configuraciones) × régimen (manual / autoaccept) × 24 instancias × 10 semillas
  comunes; α ∈ {0,20; 0,25; 0,30; 0,35; 0,40; 1} en MIP-Fair; w ∈ {5, 10, 20, 40} min en BRKGA-Fair;
  λ_pay ∈ {0,1; 0,2; 0,5; 1} en Pay-BRKGA; umbral del logit 615 / 903 / 1.242 COP/km en X2.
- **Experimentos:** X0 piloto (42), X1 principal (8.640), X2 umbral (2.400), X3 suplemento (840):
  11.922 corridas.
- **Métricas:** cobertura, atraso, F_Gini de fin de día, F_Deficit, pago total, repartidores activos,
  segundos por ronda; derivadas: cumplimiento 1[Gini ≤ α], pérdida por régimen, emisiones por vehículo.
- **Salidas cerradas:** T1–T6 y F1–F6 en el cuerpo, T7–T8 y F7–F8 en el suplemento.
- **Presupuesto:** ≈ 475 h de CPU (cota superior), 1,2 días con 16 procesos; MIP-Fair es tres cuartos.

## 13. Piloto local: resultados y hallazgos (2026-10-20, slide 15)

Pereira, día completo (568 pedidos, 253 repartidores), manual, semilla 1:

| Método | Cobertura | Gini | s por corrida |
|---|---|---|---|
| greedy / ilp / hier | 0,734 / 0,732 / 0,736 | 0,387 / 0,387 / 0,459 | 16 / 22 / 16 |
| brkga / brkga_fair_w10 | 0,734 / 0,734 | 0,405 / 0,475 | 10 / 10 |
| paybrkga_l02 | 0,731 (antes del arreglo 0,555) | 0,412 | 14 |
| mipfair_a030 | 0,739 (equidad-primero: 0,000) | 0,382 | 36 (antes > 240) |

Bogotá, 12:00–14:00 (2.995 pedidos, 2.266 repartidores):

| Método | Cobertura | Gini | s por ventana |
|---|---|---|---|
| greedy / hier | 0,437 / 0,452 | 0,102 / 0,338 | 116 / 39 |
| brkga | 0,446 (antes 0,155) | 0,313 | 30 (antes 92) |
| paybrkga_l02 | 0,446 | 0,371 | 35 |
| mipfair_a030 top-k 8 | 0,443 (top-k 25 no termina en 7 min) | 0,324 | 268 |

Hallazgos: H1 MIP-Fair era O(n²) por ronda (reformulado, exacto); H2 equidad-primero entrega cobertura 0
desde el arranque en frío (E5'); H3 MIP-Fair con top-k 8 en la malla; H4 el decodificador BRKGA tomaba los
K = 3 repartidores de mayor clave entre todos y los buscaba en el prefiltro de la ruta (corregido: pieza
1b); H5 la pérdida de Pay-BRKGA era H4; H6 la instancia 3 trae ids con prefijo `c`; H7 greedy tarda 2 s
por ronda en Bogotá (no bloquea). X0 (42 corridas) en curso.

## 14. Decisiones revisadas y de la Etapa 1 (2026-10-20, slide 16)

- **E4' Gini de MIP-Fair por bloques, exacto** (fijo–fijo constante, libre–fijo lineal en x, libre–libre
  con d_ij). Todos los pares era O(n²); 8 tests contra fuerza bruta en verde.
- **E5' Prioridad de MIP-Fair: cobertura › exceso de Gini › desempate.** Equidad-primero entrega
  cobertura 0 desde el arranque en frío; la variante va al suplemento.
- **D1 Tarifa plana 2.200 COP.** **D2 Circuidad 1,3** (1,0 en sensibilidad). **D3 Velocidades** bici 15,
  moto 25, a pie 5, carro 20 km/h como supuesto. **D4 SLA duro** hora prometida + 30 min. **D5 Seis
  ciudades**, Bogotá calibrada y las otras como robustez. **D6 Emisiones** moto 0,114 y carro 0,167
  kg CO₂e/km (DEFRA/BEIS 2023), bici y a pie 0, moto pequeña 0,083 en sensibilidad. **D7 Diez semillas
  comunes.** Detalle y justificación en `docs/paper-cmdp/modelo-vs-evidencia.md` §4.

## 15. Esquema de desarrollo y avance (2026-10-20, slide 17)

| Etapa | Contenido | Estado |
|---|---|---|
| E0 Insumos y alcance | EJOR; pregunta y contribuciones v2; un simulador; GRASP citado | hecho |
| E1 Modelo contra evidencia | 22 supuestos con grado; D1–D7 | hecho |
| E2 Simulador y datos | loader 24 instancias, logit pago/km, velocidad por vehículo; validación de cara sin correr | casi |
| E3 Métodos | BRKGA, BRKGA-Fair, MIP-Fair, Pay-BRKGA; 77 tests; E1–E6, E4', E5'; pieza 1b | hecho |
| E4 Diseño experimental | zona 3 km, 18 configuraciones, X0–X3, batch_paper.py, piloto local | hecho |
| E5 Corridas y análisis | X0 en curso; X1, X3, X2; Pareto, cumplimiento, régimen, umbral, α | en curso |
| E6 Escritura | borrador completo en estilo EJOR del director (`docs/paper-cmdp/paper/main.tex`, guía `estilo-ejor.md`); resultados con huecos para X1–X3 | en curso |

Pendiente del autor: visto bueno a E5' y D1–D7; verificar las instancias 16 y 17 (una tienda por pedido).

### X0 completado (2026-10-20, 23:30; slide 15)

42 corridas (6 ciudades × 7 métodos, día completo, manual, semilla 1, circuidad 1,0), 2 h 50 min con 3
procesos, 0 fallos. Media de las seis zonas:

| Método | Cobertura | Gini fin de día | min por corrida (máx, Bogotá) |
|---|---|---|---|
| greedy | 0,752 | 0,418 | 11,6 (34,8) |
| ilp | 0,741 | 0,389 | 2,1 (6,1) |
| hier | 0,754 | 0,466 | 3,8 (11,1) |
| brkga | 0,754 | 0,431 | 2,8 (7,5) |
| brkga_fair_w10 | 0,755 | 0,444 | 2,8 (7,6) |
| mipfair_a030 | 0,753 | 0,406 | 4,9 (15,4) |
| paybrkga_l02 | 0,751 | 0,414 | 3,2 (8,3); pago 8–18 % menor |

Gini corporativo por ciudad: Barranquilla 0,468, Bogotá 0,372, Bucaramanga 0,361, Cali 0,528, Medellín
0,394, Pereira 0,387 (media 0,419): la malla de α se mantiene. Lecturas: cobertura plana entre métodos; el
jerárquico empeora el Gini de fin de día; F_Deficit ≈ 0,98–1,00. El greedy es el método más lento (35 min
en Bogotá) porque cada repartidor evaluaba todos los pedidos pendientes: resuelto (H7, 116 → 26 s en la ventana de Bogotá, resultado idéntico); el
radio de 3 km se mantiene (MIP-Fair 15 min < 20). Estimación de X1 con estos tiempos: 308 h de CPU (≈ 235 h
con el greedy arreglado).

Confirmación con circuidad 1,3 (seis corridas greedy): Gini corporativo medio 0,409, malla de α confirmada;
cobertura unos 4 pts menor que con 1,0; greedy Bogotá 10,7 min con H7 resuelto. X1 lanzado el 21 oct a las
00:05 (4 procesos, orden por semilla, reanudable).

## 16. X1, primera pasada: resultados preliminares (2026-10-21, 04:06; slide 16 nueva; las antiguas 16 y 17 pasan a 17 y 18)

864 celdas (24 instancias × 18 configuraciones × 2 regímenes, semilla 1, circuidad 1,3), 0 fallos, 2 h 50 min
con 12 procesos. Media sobre las 24 instancias, régimen manual (detalle y errores estándar en
`docs/paper-cmdp/diseno-experimental.md` §12):

| Configuración | Cobertura | Gini | Atraso (min) | Pago / greedy | ΔGini vs greedy [IC 95 %] | Auto: Gini |
|---|---|---|---|---|---|---|
| greedy | 0,759 | 0,525 | 19,9 | 1,00 | — | 0,586 |
| ilp | 0,738 | **0,414** | 19,4 | 0,97 | −0,111 [−0,168; −0,053]; cobertura −2,1 pts | **0,395** |
| hier | 0,770 | 0,537 | **18,1** | 1,01 | +0,012 [−0,023; +0,048] | 0,571 |
| brkga | **0,771** | 0,492 | 18,5 | 1,02 | −0,032 [−0,064; +0,001] | 0,498 |
| brkga_fair w5–w40 | 0,768–0,771 | 0,501–0,509 | 18,5 | 1,01 | −0,016 a −0,024 (n. s.) | 0,507–0,521 |
| mipfair α 0,20–1,00 | 0,763–0,765 | 0,454–0,472 | 19,0 | 1,01 | α 0,30: −0,071 [−0,121; −0,023]; cobertura +0,4 pts | 0,448–0,473 |
| paybrkga λ 0,1–1,0 | 0,760–0,754 | 0,482–0,448 | 18,8 | 0,95–0,87 | λ 0,5: −0,077 [−0,134; −0,027]; cobertura −0,5 pts | 0,444–0,468 |

Lecturas (una semilla): L1 en auto-aceptación la cobertura es idéntica en las 18 configuraciones (0,786): el
21 % no entregado es infactible bajo el SLA. L2 en auto, MIP-Fair y Pay-BRKGA bajan el Gini 0,11–0,14 sin
costo; en manual MIP-Fair baja 0,05–0,07 ganando cobertura y puntualidad. L3 el ILP exacto es el que más baja
el Gini porque activa ≈ 800 repartidores frente a ≈ 1.010 del greedy: el Gini sobre activos premia
concentrar el trabajo; BRKGA-Fair falla por lo contrario (el déficit prefiere al ocioso). Pendiente A1: Gini
sobre todos los conectados e ingreso total desde las tablas por repartidor. L4 α no mueve a MIP-Fair (ni
α = 1,00); ablación E8 con holgura de cobertura para X3. L5 el jerárquico es el más puntual pero no baja el
Gini del día. L6 Pay-BRKGA responde a λ. L7 nadie cumple α ≤ 0,30; a 0,40 solo ilp (46–71 %); α* provisional
para X2 = 0,40; la tabla de cumplimiento añade 0,45 y 0,50. Tiempos 1,8–4,5 min por corrida (máx. 22). X1
completo ≈ 22 oct por la mañana.

### A1: el alcance del Gini invierte la conclusión (2026-10-21, 05:30; slide 16)

Recalculado ex post desde las tablas por repartidor (`simulator/analyze_couriers.py`): el F_Gini (pago por
hora entre activos) está dominado por el 7 % de repartidores conectados menos de una hora (turnos de 1 min:
110.000 COP/h por una entrega), a los que solo el greedy asigna. Sobre la población elegible (conectados
≥ 1 h, ceros incluidos), manual, semilla 1: greedy 0,301 frente a 0,52–0,57 de todos los demás (ilp 0,524,
mipfair_a030 0,544, paybrkga_l05 0,547, brkga 0,566); diferencias pareadas +0,22 a +0,27 con IC que no
cruzan cero. Activos entre elegibles: greedy 97 %, los demás 69–77 %; p25 del pago por hora 481 frente a
≤ 150. Los métodos bajan el estadístico restringido excluyendo repartidores. Decisión provisional E9 (cambia
el modelo; ratificar): la restricción y el reporte pasan al Gini sobre elegibles con ceros; variantes de
segunda generación de los tres métodos tras X1, evaluadas en X3. Detalle en `diseno-experimental.md` §12.6.
