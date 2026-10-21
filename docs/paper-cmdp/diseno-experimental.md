# Diseño experimental (Etapa 4) — 2026-10-20

Objetivo de la etapa: dejar cerrado, antes de correr nada, qué se corre, cuántas veces, con qué métricas,
qué tablas y figuras salen de ahí y cuánto cómputo cuesta. Entregables: este documento,
`simulator/batch_paper.py` (malla, un proceso por corrida, reintentos, reanudable, piloto y estimación),
la lista cerrada de tablas y figuras (§7) y el piloto local (§8–§9), que sí se corrió: la máquina del autor
quedó estable el 2026-10-20 por la noche con el turbo del CPU desactivado (ver `plan.md`).

## 1. Unidad experimental: la zona de 3 km

Las 24 instancias reales son días completos de ciudad entera (Bogotá: 56.420 pedidos y 16.710 repartidores
en un día; `instancias_reales.csv`). Un MIP por ventana de 2 minutos sobre 270 pedidos por ronda y 16.000
repartidores no es el problema que el paper plantea (una zona operativa de despacho) ni es computable en
10 semillas × 18 configuraciones. La unidad experimental es por tanto la **zona**: pedidos (por punto de
entrega) y repartidores (por punto de conexión) a ≤ 3 km del centro de la instancia, día completo
(00:00–24:00), con `--radius 3` (`cfg.real_max_radius_km`). Tamaños que entrega el loader (T1):

| Instancia | Ciudad | Pedidos zona | Repartidores zona | Tiendas | Pedidos / repartidor |
|---|---|---|---|---|---|
| 0 | Bogotá | 10.215 | 2.650 | 926 | 3,9 |
| 6 | Bogotá | 9.743 | 2.489 | 997 | 3,9 |
| 12 | Bogotá | 5.618 | 1.967 | 859 | 2,9 |
| 18 | Bogotá | 5.875 | 1.931 | 912 | 3,0 |
| 2 | Medellín | 6.169 | 1.692 | 602 | 3,6 |
| 8 | Medellín | 5.778 | 1.773 | 628 | 3,3 |
| 14 | Medellín | 3.953 | 1.244 | 614 | 3,2 |
| 20 | Medellín | 3.918 | 1.259 | 587 | 3,1 |
| 5 | Barranquilla | 7.773 | 1.442 | 470 | 5,4 |
| 11 | Barranquilla | 7.116 | 1.532 | 474 | 4,6 |
| 17 | Barranquilla | 3.606 | 1.168 | 4.014 | 3,1 |
| 23 | Barranquilla | 3.612 | 1.046 | 431 | 3,5 |
| 7 | Cali | 1.813 | 745 | 269 | 2,4 |
| 13 | Cali | 1.262 | 488 | 260 | 2,6 |
| 19 | Cali | 1.292 | 476 | 264 | 2,7 |
| 1 | Bucaramanga | 1.851 | 574 | 216 | 3,2 |
| 3 | Bucaramanga | 1.851 | 574 | 216 | 3,2 |
| 9 | Bucaramanga | 1.527 | 610 | 218 | 2,5 |
| 15 | Bucaramanga | 976 | 536 | 202 | 1,8 |
| 21 | Bucaramanga | 948 | 498 | 204 | 1,9 |
| 4 | Pereira | 568 | 253 | 135 | 2,2 |
| 10 | Pereira | 498 | 277 | 140 | 1,8 |
| 16 | Pereira | 342 | 268 | 401 | 1,3 |
| 22 | Pereira | 374 | 246 | 122 | 1,5 |

Media: 3.612 pedidos por zona. Dos avisos para el autor sobre los datos: las instancias 1 y 3 tienen
conteos idénticos pero contenido distinto (días diferentes de Bucaramanga; la 3 trae los `order_id` con
prefijo `c`, el loader ya lo tolera); las instancias 16 y 17 traen tantas tiendas como pedidos (401 y
4.014), es decir, una tienda por pedido, lo que conviene verificar en la fuente.

Por qué 3 km y no otro valor: (i) con 2 km Pereira queda en pocos cientos de pedidos y los Gini de fin de
día se vuelven ruidosos; (ii) con 5 km Bogotá pasa de 27.000 pedidos y el MIP por ronda deja de ser viable
en el presupuesto de §9; (iii) 3 km es del orden del radio de prospección que usa mdrp-sim
(`mdrpsim_prospects_max_distance_km = 3`), lo que hace comparable la lectura. **Regla de ajuste** (cerrada
aquí para no reabrirla): si en el piloto de la máquina de cómputo la mediana del método más caro sobre
Bogotá supera 20 min por corrida, el radio baja a 2 km **para las seis ciudades** (no se mezclan radios).
Con lo medido en §8 (MIP-Fair ≈ 15 min estimados en Bogotá) el radio se mantiene.

La zona hereda del loader (`loader_real.py`): proyección plana por instancia, velocidad por vehículo,
SLA duro = `expected_drop_off_time` + 30 min, tarifa plana 2.200 COP, sin pago garantizado, SMMLV/hora
4.367,91 COP, tiempos de servicio 20 / 4 min, ventana de decisión 16 ± 8 s. Lo que sigue pendiente del
autor (`modelo-vs-evidencia.md` §4: circuidad, velocidades, SLA, emisiones) entra como parámetro de
`batch_paper.py` (`--circuity`, `--speeds`) sin cambiar la malla.

## 2. Factores y niveles

| Factor | Niveles | Dónde actúa |
|---|---|---|
| **Método** (18 configuraciones, §3) | 4 baselines + BRKGA-Fair (4) + MIP-Fair (6) + Pay-BRKGA (4) | `--policy` y parámetros |
| **Régimen de aceptación** | `manual`, `autoaccept` | `cfg.accept_regime` (logit sobre pago/km, umbral 903 COP/km, pendiente 2,89) |
| **α** (solo MIP-Fair) | {0,20; 0,25; 0,30; 0,35; 0,40; 1,00} | `cfg.mipfair_alpha`; α = 1 es el MIP corporativo |
| **w** (solo BRKGA-Fair) | {5; 10; 20; 40} min (w = 0 ≡ BRKGA-Coverage) | `cfg.brkga_fair_weight` |
| **λ_pay** (solo Pay-BRKGA) | {0,1; 0,2; 0,5; 1,0} con λ_def = 0,5 y banda ±30 % | `cfg.paybrkga_lambda_pay` |
| **Umbral del logit** (solo X2) | 615 / **903** / 1.242 COP/km (IC del ajuste, n = 32) | `cfg.accept_ppk_threshold`; pendiente fija en 2,89 |
| **Instancia** | 24 (6 ciudades × 4 días), zona 3 km | bloque |
| **Semilla** | 10 por celda, las mismas 1..10 en todas las celdas | aceptación Bernoulli, tiempos de decisión, RNG del BRKGA |

Las semillas comunes entre métodos (common random numbers) son deliberadas: toda comparación entre métodos
se hace **pareada por (instancia, semilla)**.

**Regla de recentrado de α** (se aplica una sola vez, con el piloto): si el Gini corporativo medio de fin
de día (greedy, manual) queda fuera de [0,35; 0,55], la malla de α pasa a
{0,5; 0,6; 0,7; 0,8; 0,9} × Gini_corporativo redondeado a 0,05, más 1,00. En Pereira (día completo) el
greedy dio 0,387, dentro del rango; la regla se confirma con las seis ciudades del piloto X0.

## 3. Las 18 configuraciones de método

| Clave en `batch_paper.py` | Política | Parámetros | Papel |
|---|---|---|---|
| `greedy` | `greedy` | — | corporativo miope (referencia principal) |
| `ilp` | `ilp`, `max_coverage` | lotes ≤ 3, top-k 25 | corporativo exacto por ventana |
| `hier` | `hier`, orden cov › lat › eq › cost | candados por defecto | equidad por ventana (muestra la miopía) |
| `brkga` | `brkga`, `finish_per_order` | pop 10, gen 10 | BRKGA-Coverage (MIC 2026, con lotes) |
| `brkga_fair_w5` … `w40` | `brkga_fair`, base `hourly` | w ∈ {5,10,20,40} | contribución 2a |
| `mipfair_a020` … `a100` | `mip_fair`, **prioridad cobertura › exceso de Gini** (E5', §10), alcance `all`, base `hourly`, top-k **8** | α ∈ {0,20 … 0,40; 1,00} | contribución 2c; traza el frente en α |
| `paybrkga_l01` … `l10` | `pay_brkga`, λ_def 0,5, banda ±0,30 | λ_pay ∈ {0,1; 0,2; 0,5; 1,0} | contribución 2b; único que toca el pago |

Todos comparten: ronda de 2 min, candidatos de ruta de `brkga_policy.build_candidates` / ILP, modelo de
aceptación `logit_ppk`, `max_bundle_size = 3`, sin reposicionamiento ni cancelación (igual que en los 240
de mdrplib; la cancelación queda para el suplemento si hay tiempo). MIP-Fair usa top-k 8 en lugar de 25
por el presupuesto (§8: con 25 no terminó dos horas de Bogotá en 7 min; con 8 tardó 4,5 min y cubrió más
que el greedy); la sensibilidad a ese corte es la ablación `mipfair_a030_k25`.

## 4. Experimentos (celdas y corridas)

| Exp. | Pregunta | Celdas | Corridas |
|---|---|---|---|
| **X0 piloto** | tiempo por corrida y Gini corporativo (regla de α y de radio) | 6 instancias (una por ciudad: 0, 1, 2, 4, 5, 7) × 7 métodos en defaults × manual × semilla 1 | 42 |
| **X1 principal** | frentes de Pareto cobertura/atraso vs Gini por método y régimen; costo de la garantía | 18 configuraciones × 2 regímenes × 24 instancias × 10 semillas | 8.640 |
| **X2 umbral** | sensibilidad al umbral del logit dentro del IC | 5 configuraciones seleccionadas (greedy, hier, `brkga_fair_w10`, `mipfair_a*` en la rodilla, `paybrkga_l02`) × {615, 1.242} × 2 regímenes × 24 × 5 semillas | 2.400 |
| **X3 suplemento** | ablaciones: `brkga_score = finish`; `mipfair_scope = idle`; base `total` en BRKGA-Fair y MIP-Fair; MIP-Fair equidad-primero; MIP-Fair top-k 25; BRKGA 20 × 20 | 7 configuraciones × manual × 24 × 5 semillas | 840 |
| Total | | | **11.922** |

X2 se lanza después de X1 porque la configuración de MIP-Fair en la rodilla (α*) sale de X1. Todo lo demás
es independiente y puede correr en paralelo.

## 5. Métricas (por corrida, columnas de `output/paper/<exp>.csv`)

Todas salen de `metrics.compute_metrics` salvo las marcadas como derivadas.

| Grupo | Columna | Lectura |
|---|---|---|
| Servicio | `coverage_rate`, `n_delivered`, `n_orders` | P1 cobertura |
| Puntualidad | `overage_mean`, `overage_total_min`, `lateness` (pedidos tarde), `c2d_mean`, `c2d_p90` | P2 atraso; el SLA duro ya filtró lo infactible |
| Equidad (fin de día, sobre H_t) | `F_Gini` (ingreso/hora), `F_MaxMin`, `F_Orders`, `F_Deficit` (frente a SMMLV/hora), `F_Dist` | P3; `F_Gini ≤ α` es la restricción |
| Costo plataforma | `total_payment` (COP), `n_couriers_active`, `throughput_cost`, `bundle_size_mean` | P4 |
| Ingreso repartidor | `mean_hourly_earn`, tabla por repartidor (`couriers/<run_id>.csv`: `payment`, `earn_per_hr`, `active_h`, `dist_km`, `vehicle`) | distribución, violines, emisiones |
| Cómputo | `solve_mean`, `solve_max` (s por ronda), `wall_clock_sec` | reproducibilidad y viabilidad operativa |
| **Derivadas** | emisiones = Σ_v `dist_km_v` × EF_v desde la tabla por repartidor; EF por vehículo pendiente del autor (valores de trabajo: moto 0,09, carro 0,19, bici y a pie 0 kg CO₂/km) | efecto colateral por composición de flota |
| **Derivadas** | cumplimiento = 1[`F_Gini` ≤ α] por (instancia, semilla); pérdida por régimen = diferencia pareada manual − autoaccept | T4, F5 |

El Gini de fin de día del paper es el de `F_Gini` (ingreso por hora conectada, repartidores activos). La
decisión E4 (Gini sobre todos los conectados dentro del MIP) afecta a lo que el método **optimiza**; la
métrica reportada es una sola para todos.

## 6. Análisis

- **Pareto**: por método y régimen, media sobre (instancia, semilla) de (`F_Gini`, `coverage_rate`) y
  (`F_Gini`, `overage_mean`) para cada nivel del parámetro de barrido; envolvente no dominada; rodilla =
  punto de máxima distancia a la cuerda entre extremos (el mismo criterio en los tres métodos).
- **Costo de la garantía**: diferencia pareada frente a `greedy` (misma instancia y semilla), IC 95 % por
  bootstrap sobre las 24 instancias (la instancia es el bloque; las semillas se promedian dentro). Prueba
  de Wilcoxon pareada como complemento, no como argumento.
- **Cumplimiento**: fracción de (instancia, semilla) con `F_Gini ≤ α` por método y α (T4); es la primera
  mitad de la pregunta de investigación.
- **Régimen**: pérdida de cobertura manual − autoaccept por método, pareada (F5).
- **Umbral**: X2, tres niveles, misma lectura pareada (T5).
- **Selección de α** por los tres criterios de la tesis: histórico (Gini corporativo observado), bandas
  (Gini de las bandas de pago de la encuesta) y rodilla del Pareto (T6).
- **Miopía del jerárquico**: su Gini por ventana vs el de fin de día, con la trayectoria intradía de F6.

## 7. Lista cerrada de tablas y figuras

Cuerpo (≤ 35 páginas EJOR): T1–T6 y F1–F6. Suplemento: T7–T8 y F7–F8.

| Id | Contenido | Fuente |
|---|---|---|
| T1 | Las 24 instancias: ciudad, día, pedidos y repartidores en zona, pedidos/repartidor, mezcla de vehículos | tabla de §1 + `instancias_reales.csv` |
| T2 | Parámetros y fuentes (tarifa, velocidades, SLA, servicio, logit con IC, SMMLV) | `modelo-vs-evidencia.md` |
| T3 | Resultados principales: por método (en su mejor configuración) × régimen, media ± IC de cobertura, atraso, Gini, déficit, pago total, repartidores activos, s/ronda | X1 |
| T4 | Cumplimiento `F_Gini ≤ α` (% de instancia-semilla) por α y método | X1 |
| T5 | Sensibilidad al umbral del logit: cobertura y Gini a 615 / 903 / 1.242 | X2 |
| T6 | α por los tres criterios y política recomendada | X1 + encuesta |
| T7 (sup.) | Ablaciones: `finish` vs `finish_per_order`, alcance `idle`, base `total`, equidad-primero, top-k 25, BRKGA 20 × 20 | X3 |
| T8 (sup.) | Resultados por ciudad (seis bloques de T3) | X1 |
| F1 | Mapa de una zona de 3 km (Bogotá) con tiendas, entregas y conexiones | CSV |
| F2 | Curva de aceptación logit con IC y los dos regímenes | `acceptance.py` |
| F3 | Frentes de Pareto cobertura vs Gini por método (paneles manual / autoaccept) | X1 |
| F4 | Frentes atraso vs Gini | X1 |
| F5 | Pérdida por régimen, diferencias pareadas con IC, por método | X1 |
| F6 | Trayectoria intradía del Gini (greedy, hier, MIP-Fair α*) en un día de Bogotá | snapshots de corridas seleccionadas |
| F7 (sup.) | Distribución del ingreso/hora por repartidor (violines) corporativo vs α* | tablas por repartidor |
| F8 (sup.) | Emisiones por α y composición de flota | derivada |

## 8. Piloto local (2026-10-20, noche; i9-14900K sin turbo, Gurobi 11, Python 3.10)

Pereira, instancia 4, día completo (568 pedidos, 253 repartidores), manual, semilla 1:

| Método | s por día | s por ronda (media / máx) | Cobertura | Gini | F_Deficit |
|---|---|---|---|---|---|
| brkga | 9 | 0,013 / 0,045 | 0,736 | 0,430 | 0,994 |
| brkga_fair_w10 | 9 | 0,013 / 0,042 | 0,732 | 0,369 | 1,000 |
| greedy | 16 | 0,023 / 0,073 | 0,734 | 0,387 | 0,992 |
| hier | 16 | 0,023 / 0,051 | 0,736 | 0,459 | 0,990 |
| paybrkga_l02 | 17 | 0,025 / 0,077 | 0,555 | 0,417 | 0,993 |
| ilp | 22 | 0,031 / 0,173 | 0,732 | 0,387 | 1,000 |
| mipfair_a030 (cob. › Gini, top-k 25) | 36 | 0,051 / 0,472 | 0,739 | 0,382 | 0,994 |

Bogotá, instancia 0, ventana 12:00–14:00 (2.995 pedidos, 2.266 repartidores), manual, semilla 1:

| Método | s por ventana | s por ronda (media / máx) | Cobertura | Gini | Día completo estimado (× 3,4) |
|---|---|---|---|---|---|
| brkga (10 × 10, decodificador corregido) | 30 | 0,5 / — | 0,446 | 0,313 | 1,7 min |
| paybrkga_l02 (corregido) | 35 | 0,6 / — | 0,446 | 0,371 | 2,0 min |
| hier | 39 | 0,66 / 1,2 | 0,452 | 0,338 | 2,2 min |
| greedy | 116 | 2,0 / 3,9 | 0,437 | 0,102 | 6,6 min |
| mipfair_a030 top-k 8 | 268 | 4,5 / 12,5 | 0,443 | 0,324 | 15 min |
| mipfair_a030 top-k 25 | > 420 (timeout) | — | — | — | descartado |
| brkga antes del arreglo (10 × 10 / 20 × 20) | 92 / 117 | 1,5 / 2,0 | 0,155 / 0,210 | 0,211 / 0,206 | (H4) |

Pereira tras el arreglo del decodificador: brkga 0,734 (10 s), brkga_fair_w10 0,734 (10 s), paybrkga_l02
0,731 (14 s); sustituyen a las filas BRKGA de la primera tabla.

### X0 (2026-10-20, 23:30): 42 corridas, 6 ciudades × 7 métodos, día completo, manual, semilla 1, circuidad 1,0

2 h 50 min con 3 procesos, 0 fallos (`output/paper/pilot.csv`, resumen con `analyze_paper.py`).

| Método | Cobertura (media 6 zonas) | Gini fin de día | min / corrida media (máx, Bogotá) |
|---|---|---|---|
| greedy | 0,752 | 0,418 | 11,6 (34,8) |
| ilp | 0,741 | 0,389 | 2,1 (6,1) |
| hier | 0,754 | 0,466 | 3,8 (11,1) |
| brkga | 0,754 | 0,431 | 2,8 (7,5) |
| brkga_fair_w10 | 0,755 | 0,444 | 2,8 (7,6) |
| mipfair_a030 | 0,753 | 0,406 | 4,9 (15,4) |
| paybrkga_l02 | 0,751 | 0,414 | 3,2 (8,3); pago total 8–18 % menor |

Gini corporativo (greedy) por ciudad: Barranquilla 0,468, Bogotá 0,372, Bucaramanga 0,361, Cali 0,528,
Medellín 0,394, Pereira 0,387; media **0,419**, dentro de [0,35; 0,55]: **la malla de α se mantiene**.
Lecturas con una semilla: (i) la cobertura es plana entre métodos (±0,5 pt; el ILP pierde 1 pt); (ii) el
jerárquico **sube** el Gini de fin de día frente al greedy en 5 de 6 ciudades (la equidad por ventana no
produce la de fin de día: argumento de la contribución 1); (iii) MIP-Fair α = 0,30 baja el Gini 0,01 de
media y no alcanza 0,30 en ninguna zona; (iv) Pay-BRKGA mantiene la cobertura con 8–18 % menos pago porque
el pago/km sigue por encima del umbral; (v) F_Deficit 0,98–1,00 en todos (coherente con el 91,9 % bajo el
SMMLV de la encuesta). **Regla de radio:** el método más lento es el greedy (34,8 min en Bogotá), por un
defecto de implementación (H7, recorre los 2.650 repartidores por pedido) y no por el tamaño del problema;
MIP-Fair tarda 15,4 min, bajo el límite de 20. Decisión: se arregla H7 (rejilla espacial) antes de X1 y
**el radio se mantiene en 3 km**. Confirmación con circuidad 1,3 (D2, seis corridas greedy,
`output/paper/pilot_c13.csv`): cobertura 0,63–0,78 (unos 4 pts menos que con 1,0, como corresponde a
distancias 30 % mayores), Gini corporativo por ciudad 0,457 / 0,418 / 0,326 / 0,539 / 0,321 / 0,392, media
**0,409**: la malla de α {0,20 … 0,40; 1,00} queda confirmada. Greedy Bogotá día completo con H7 resuelto:
10,7 min (antes 34,8). X1 lanzado el 2026-10-21 a las 00:05 en la máquina del autor (4 procesos, orden por
semilla, reanudable; `output/paper/main.csv`).

## 9. Presupuesto de cómputo y plan de corridas

Con los segundos por pedido de Bogotá (el peor caso, porque el costo por ronda crece con los repartidores
conectados) aplicados a las 24 zonas (media 3.612 pedidos; 480 corridas por configuración en X1):

| Configuraciones | s / pedido (Bogotá) | CPU X1 |
|---|---|---|
| greedy, ilp | 0,039 | 38 h |
| hier | 0,013 | 6 h |
| brkga + brkga_fair (5) | 0,010 | 24 h |
| pay_brkga (4) | 0,012 | 23 h |
| mip_fair (6, top-k 8) | 0,090 | 260 h |
| **X1 total (cota superior)** | | **≈ 350 h** |

X2 y X3 añaden ≈ 35 % (3.240 corridas): **≈ 475 h de CPU en total**, es decir 1,2 días con 16 procesos o
0,6 días con 32. MIP-Fair es tres cuartos del presupuesto.

**Con los tiempos medidos en X0** (`--estimate output/paper/pilot.csv`, s/pedido medianos: greedy 0,097,
mip_fair 0,039, hier 0,035, pay_brkga 0,031, brkga 0,026, ilp 0,019): X1 = **308 h de CPU** (19 h con 16
procesos); el greedy pesa 93 h por H7 y bajará a ≈ 20 h con la rejilla espacial, con lo que X1 queda en
≈ 235 h y el total X1–X3 en ≈ 320 h. En la máquina del autor (3–4 procesos con el turbo apagado) X1 son
≈ 3 días de pared; en una máquina de 16 núcleos, menos de un día. La cota es holgada: las zonas medianas cuestan menos por pedido que Bogotá. Salvaguardas
en el script: límite de 10 s por ronda para los MIP (`--ilp-time-limit`), timeout por corrida
(`--timeout-min 60`), reintento ×2, reanudación por `run_id`, fallos a `<out>.failed.jsonl`.

Orden de lanzamiento en la máquina de cómputo (requisitos: Python 3.10–3.12, `simulator/requirements.txt`,
gurobipy con licencia para `hier` y para que `ilp` / `mip_fair` usen Gurobi vía pulp; sin licencia caen a
CBC y el presupuesto de MIP-Fair se multiplica):

```
cd simulator
python batch_paper.py --experiment pilot --workers 6 --out output/paper/pilot.csv
python batch_paper.py --estimate output/paper/pilot.csv            # confirma radio y malla de α
python batch_paper.py --experiment main --workers 16 --out output/paper/main.csv
python batch_paper.py --experiment supp --workers 16 --out output/paper/supp.csv
python batch_paper.py --experiment threshold --mipfair-knee 0.30 --workers 16 --out output/paper/threshold.csv
```

Salida: una fila por corrida en el CSV del experimento (métricas + columnas de la celda: `run_id`,
`experiment`, `instance`, `city`, `method`, `policy`, `regime`, `alpha`, `weight`, `lambda_pay`,
`ppk_threshold`, `radius_km`, `seed`, `cfg_json`), tabla por repartidor en
`output/paper/couriers/<run_id>.csv`. `--dry-run` imprime las celdas sin correr nada.

## 10. Hallazgos del piloto y qué cambió en el código

| # | Hallazgo | Qué se hizo | Estado |
|---|---|---|---|
| H1 | MIP-Fair construía d_ij para **todos los pares** de repartidores conectados (O(n²) por ronda): con 188 conectados no terminó dos horas de Pereira en 4 min; en Bogotá serían 3,5 millones de pares por ronda | Reformulación exacta por bloques (fijo–fijo constante, libre–fijo lineal en x, libre–libre con d_ij) en `mip_fair.py::_solve`; `get_solver` usa `pulp.GUROBI` (API) en vez de `GUROBI_CMD` (archivos LP). Los 8 tests contra fuerza bruta siguen verdes; Pereira día completo pasa a 36 s | resuelto (E4') |
| H2 | Con prioridad **equidad › cobertura** (E5) MIP-Fair entregó cobertura 0,000: desde el arranque en frío cualquier asignación sube el Gini, así que "no asignar" minimiza el exceso en cada ronda | Default `mipfair_priority = coverage` (E5'); la variante equidad-primero queda como ablación `mipfair_a030_fairfirst` | resuelto |
| H3 | MIP-Fair con top-k 25 no termina dos horas de Bogotá en 7 min; con top-k 8 tarda 4,5 min y cubre 0,443 (greedy 0,437) | Malla X1 con top-k 8; `mipfair_a030_k25` en X3 | resuelto en la malla; vigilar en X0 |
| H4 | **BRKGA-Coverage colapsaba en Bogotá**: cobertura 0,155 (10 × 10) y 0,210 (20 × 20) frente a 0,437 del greedy, mientras en Pereira igualaba al greedy | Causa (pieza 1b): el decodificador tomaba los K = 3 repartidores de mayor clave entre *todos* los libres y luego los buscaba en el prefiltro de 25 de la ruta; con 2.266 repartidores casi nunca coincidían y el pedido se saltaba. Ahora toma los K entre los candidatos de la ruta (`porte-brkga.md`, cambio 6). Bogotá 12:00–14:00: cobertura 0,446 en 30 s (greedy 0,437 en 116 s); Pereira sin cambio (0,734) | resuelto |
| H5 | Pay-BRKGA perdía 18 pts de cobertura en Pereira (0,555 vs 0,734) | Era el mismo defecto de H4 (comparte el decodificador): tras el arreglo 0,731 en Pereira y 0,446 en Bogotá 12:00–14:00 | resuelto |
| H6 | Instancia 3 trae `order_id` con prefijo `c` y el loader fallaba | `loader_real._id_int` tolera cualquier prefijo; 17 tests verdes | resuelto |
| H7 | Greedy costaba 2 s por ronda en Bogotá y 35 min por día (X0): cada uno de los ~1.700 repartidores libres evaluaba la factibilidad de todos los pedidos pendientes, incluidos los "muertos" (listos después del SLA duro), que nunca salen de la cola | `routing.best_route_for_courier`: tiendas ordenadas por distancia (la primera factible es la más cercana) y cota exacta por pedido (llegada, listo, servicio, tienda→cliente frente al SLA); `GreedyPolicy`: grupos por tienda mantenidos de forma incremental. Resultado idéntico (1.309 entregas, cobertura 0,4371, Gini 0,1021 en la ventana de Bogotá); 116 s → 26 s. Día de Bogotá estimado ≈ 8 min | resuelto |

## 11. Lo que esta etapa deja decidido y lo que no

Decidido aquí: zona de 3 km con regla de ajuste; 10 semillas comunes; 18 configuraciones; malla de α, w y
λ_pay; X0–X3; métricas y derivadas; análisis pareado por bloque; T1–T8 y F1–F8; E4' y E5'.
Pendiente del autor (no bloquea X0): circuidad, velocidades, SLA, factores de emisión (§4 de
`modelo-vs-evidencia.md`), y el visto bueno a E5'. Pendiente de código antes de X1: H4 (BRKGA a escala de
Bogotá) y la revisión de H5. Pendiente del piloto X0 en la máquina de cómputo: tiempo real por corrida en
las seis ciudades y confirmación de la malla de α.

**Nota de ejecución (2026-10-21, 01:15).** Con 4 procesos X1 avanzaba a 20 corridas por hora (las primeras
celdas son las de Bogotá). El tiempo medio real por corrida en X0 es 3,3 min sin el greedy (≈ 4 min con el
greedy ya optimizado), es decir ≈ 500 h de CPU para X1, más que la cota por pedido de §9 porque el costo
por ronda crece con los repartidores conectados y no con los pedidos. Relanzado con 12 procesos (reanudable):
≈ 1,7 días de pared; la primera pasada (semilla 1, 864 celdas) en ≈ 4 h.

## 12. X1, primera pasada: semilla 1 completa (2026-10-21, 04:06)

864 celdas (24 instancias × 18 configuraciones × 2 regímenes, semilla 1, circuidad 1,3, día completo), 0 fallos,
2 h 50 min con 12 procesos (≈ 290 corridas por hora; X1 completo estimado para el 22 oct por la mañana).
Resúmenes en `output/paper/main_pass1_analysis.txt` (`analyze_paper.py --main`) y `main_pass1_stats.txt`
(media y error estándar sobre las 24 instancias, Wilcoxon pareado). Todo lo que sigue es **preliminar: una
semilla**; con 10 semillas cambian los errores estándar, no necesariamente las lecturas.

### 12.1 Media sobre las 24 instancias (error estándar entre paréntesis)

Régimen manual:

| Configuración | Cobertura | Gini fin de día | Atraso medio (min) | F_Deficit | Pago / greedy | min por corrida (máx) |
|---|---|---|---|---|---|---|
| greedy | 0,759 (0,013) | 0,525 (0,031) | 19,9 | 0,980 | 1,00 | 2,1 (10,3) |
| ilp | 0,738 (0,013) | **0,414** (0,012) | 19,4 | 0,993 | 0,97 | 1,8 (7,7) |
| hier | 0,770 (0,013) | 0,537 (0,019) | **18,1** | 0,981 | 1,01 | 3,1 (13,4) |
| brkga | **0,771** (0,013) | 0,492 (0,019) | 18,5 | 0,985 | 1,02 | 2,3 (8,9) |
| brkga_fair w5 / w10 / w20 / w40 | 0,768 / 0,770 / 0,771 / 0,770 | 0,501 / 0,506 / 0,504 / 0,509 | 18,5–18,6 | 0,985 | 1,01 | 2,3 (9,0) |
| mipfair α 0,20 / 0,25 / 0,30 / 0,35 / 0,40 / 1,00 | 0,764 / 0,763 / 0,763 / 0,763 / 0,765 / 0,764 | 0,454 / 0,472 / 0,454 / 0,464 / 0,470 / 0,463 | 19,0 | 0,988 | 1,01 | 4,5 (22,0) |
| paybrkga λ 0,1 / 0,2 / 0,5 / 1,0 | 0,760 / 0,756 / 0,754 / 0,754 | 0,482 / 0,463 / 0,448 / 0,471 | 18,8 | 0,990 | 0,95 / 0,90 / 0,88 / 0,87 | 2,8 (12,1) |

Régimen auto-aceptación: la cobertura es **idéntica en las 18 configuraciones, 0,786 (0,013)**. Gini: greedy
0,586 (0,034); ilp **0,395** (0,010); hier 0,571; brkga 0,498; brkga_fair 0,507–0,521; mipfair 0,448–0,473;
paybrkga 0,444–0,468. Atraso: hier 17,9; brkga 18,1; mipfair e ilp 18,8; greedy 19,0.

### 12.2 Diferencias pareadas contra greedy (misma instancia; IC 95 % bootstrap sobre las 24 instancias)

| Configuración | Manual: ΔGini | Manual: Δcobertura | Auto: ΔGini |
|---|---|---|---|
| ilp | −0,111 [−0,168; −0,053] | −0,021 [−0,027; −0,017] | −0,192 [−0,251; −0,136] |
| hier | +0,012 [−0,023; +0,048] | +0,011 [+0,008; +0,013] | −0,015 [−0,054; +0,025] |
| brkga | −0,032 [−0,064; +0,001] | +0,012 [+0,010; +0,014] | −0,089 [−0,143; −0,038] |
| brkga_fair_w10 | −0,018 [−0,055; +0,022] | +0,011 [+0,008; +0,012] | −0,065 [−0,107; −0,020] |
| mipfair_a030 | −0,071 [−0,121; −0,023] | +0,004 [+0,001; +0,007] | −0,138 [−0,191; −0,079] |
| paybrkga_l05 | −0,077 [−0,134; −0,027] | −0,005 [−0,008; −0,002] | −0,140 [−0,194; −0,088] |

Atraso medio: todos los métodos lo bajan frente al greedy (manual: hier −1,8 min, brkga −1,4, paybrkga −1,1,
mipfair −0,9, ilp −0,5; Wilcoxon p < 10⁻⁴ en todos). Pérdida de régimen (cobertura manual − auto): greedy
−2,7 pts; ilp −4,8; brkga y brkga_fair −1,5 a −1,8; hier −1,7; mipfair −2,1 a −2,3; paybrkga −2,6 a −3,2.

### 12.3 Cumplimiento (% de instancias con Gini de fin de día ≤ α, semilla 1)

Ninguna configuración alcanza α ≤ 0,30 en ninguna instancia, en ningún régimen. α = 0,35: ilp 17 % (auto) /
4 % (manual); greedy 4 / 21. α = 0,40: ilp 71 / 46; paybrkga_l05 33 / 33; mipfair_a030 21 / 33; greedy 13 / 25;
brkga 4 / 0; hier 0 / 0. El Gini del greedy por instancia va de 0,33 (Pereira 22, Medellín 2) a 0,83 (Cali 19,
Bogotá 12): la desigualdad de fin de día en pago por hora es alta por construcción de las instancias
(muchos repartidores conectados con una o dos entregas).

### 12.4 Lecturas

- **L1. En auto-aceptación la cobertura no distingue métodos.** Los pedidos no entregados (21 %) son
  infactibles para cualquier repartidor bajo el SLA duro; la flota no es restrictiva. Toda la diferencia entre
  métodos está en la equidad y el atraso. En manual el rechazo abre la dispersión de cobertura (0,738–0,771).
- **L2. La garantía es barata o gratis.** En auto, MIP-Fair y Pay-BRKGA bajan el Gini 0,11–0,14 sin costo de
  cobertura. En manual, MIP-Fair baja 0,05–0,07 **ganando** 0,4 pts de cobertura y 0,9 min de atraso (greedy
  queda dominado); Pay-BRKGA baja 0,06–0,08 perdiendo 0,3–0,5 pts y pagando 10–13 % menos.
- **L3. El ILP exacto es el que más baja el Gini** (0,414 manual, 0,395 auto) y en manual el que más cobertura
  pierde (−2,1 pts). Mecanismo: el Gini se calcula sobre los repartidores *activos* (≥ 1 entrega) en pago por
  hora; greedy activa ≈ 1.010 repartidores por instancia (muchos con una sola entrega), ilp ≈ 800, mipfair ≈ 790,
  brkga ≈ 765. **Los métodos que bajan el Gini lo hacen concentrando el trabajo en menos repartidores, no
  subiendo a los de abajo.** BRKGA-Fair falla por la misma razón: el sesgo por déficit prefiere al ocioso
  (déficit 1), activa más repartidores (826–836 frente a 764 del BRKGA) y el Gini sube (0,50–0,52 frente a 0,49).
  Este es el hallazgo central para la discusión ("equidad para quién"): el estadístico de fin de día sobre
  activos premia la exclusión. Análisis pendiente A1: recalcular el Gini sobre **todos los conectados** (ceros
  incluidos) y sobre ingresos totales desde las tablas por repartidor (`output/paper/couriers/`), sin recorrer.
- **L4. α no mueve a MIP-Fair** (0,448–0,473 en ambos regímenes, dentro del error estándar, incluido α = 1,00
  que apaga la restricción). Con prioridad cobertura › exceso de Gini (E5') y candidatos top-k 8, las
  asignaciones óptimas en cobertura por ronda dejan poca holgura al término de Gini; la mejora de MIP-Fair
  frente al greedy viene de la asignación exacta por ronda (como en el ILP), no del bloque de Gini. Decisión
  E8 (ablación nueva para X3): variante con **holgura de cobertura** (perder hasta ε del máximo de la ronda a
  cambio de Gini), `mipfair_a030_eps`, además de las ya previstas (equidad-primero, base total, ociosos, k = 25).
- **L5. El jerárquico** gana cobertura (+1,1 pts) y es el más puntual (−1,8 min), pero no baja el Gini de fin de
  día (+0,012, n. s.): el balance por ventana no controla el estadístico del día (pregunta 1 del paper).
- **L6. Pay-BRKGA** es la única palanca que responde a su parámetro: el Gini baja de 0,482 a 0,448 al subir
  λ_pay de 0,1 a 0,5 (λ = 1,0 vuelve a 0,471), a costa de 0,3–0,5 pts de cobertura y con 5–13 % menos pago.
- **L7. Rodilla y α\*.** El frente cobertura–Gini de MIP-Fair es plano (L4) y la rodilla no está definida.
  Decisión provisional para X2: α\* = 0,40, único nivel con cumplimiento observable (46–71 % en ilp); se
  confirma con las 10 semillas. La tabla de cumplimiento del paper añade las columnas α = 0,45 y 0,50 (el
  cumplimiento se calcula ex post, sin recorrer).

### 12.5 Tiempos

Media (máximo) de minutos por corrida en manual: ilp 1,8 (7,7); greedy 2,1 (10,3); brkga y brkga_fair 2,3
(9,0); paybrkga 2,8 (12,1); hier 3,1 (13,4); mipfair 4,5 (22,0; Bogotá 12). Auto es 10–30 % más rápido. MIP-Fair
sigue bajo la regla de 20 min salvo en Bogotá 12 (22 min, una celda).
