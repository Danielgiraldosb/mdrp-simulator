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

### 12.6 Análisis A1: el alcance del Gini invierte la conclusión (2026-10-21, 04:20)

`analyze_couriers.py` recalcula ex post, desde las tablas por repartidor (`output/paper/couriers/`), el Gini
con otros alcances. Hallazgo: **el F_Gini reportado (pago por hora conectada, solo repartidores con ≥ 1
entrega) está dominado por el 7 % de repartidores conectados menos de una hora** (hay turnos de 1 minuto:
una entrega de 2.200 COP en 0,02 h son 110.000 COP/h). El greedy, que es centrado en el repartidor (cada
repartidor libre toma su mejor ruta), les asigna pedidos y su F_Gini se dispara; los métodos centrados en
el pedido (ILP, MIP-Fair, BRKGA) no los usan y su F_Gini baja. Con la población **elegible** (conectados ≥ 1 h,
ceros incluidos) la lectura es la contraria. Media sobre 24 instancias, régimen manual (semilla 1):

| Método | F_Gini (activos) | Gini elegibles, por hora, ceros incl. | Gini elegibles activos, por hora | Gini elegibles, ingreso total | activos / elegibles | p25 COP/h elegibles |
|---|---|---|---|---|---|---|
| greedy | 0,525 | **0,301** | **0,279** | **0,191** | **0,97** | **481** |
| ilp | 0,414 | 0,524 | 0,347 | 0,529 | 0,73 | 127 |
| hier | 0,537 | 0,526 | 0,387 | 0,478 | 0,77 | 147 |
| brkga | 0,492 | 0,566 | 0,376 | 0,553 | 0,69 | 85 |
| brkga_fair_w20 | 0,504 | 0,539 | 0,387 | 0,517 | 0,75 | 107 |
| mipfair_a030 | 0,454 | 0,544 | 0,367 | 0,533 | 0,72 | 107 |
| paybrkga_l05 | 0,448 | 0,547 | 0,366 | 0,539 | 0,71 | 89 |

Diferencias pareadas contra greedy en el Gini de elegibles por hora (ceros incluidos): +0,22 a +0,27 para
todos los métodos, con IC 95 % que no cruzan cero (p. ej. mipfair_a030 +0,242 [+0,220; +0,266]; ilp +0,222
[+0,198; +0,249]). Entre los elegibles activos también son peores (+0,06 a +0,11). El p25 de pago por hora
entre elegibles cae de ≈ 480 COP/h (greedy) a ≤ 150 con cualquier otro método; bajo todos ellos entre el 21
y el 31 % de los elegibles termina el día sin una entrega (greedy: 3 %). En auto-aceptación es igual.

**Lectura.** Los tres métodos propuestos, el ILP y el jerárquico bajan el estadístico que el modelo
restringe (hourly entre activos) **excluyendo** repartidores, no igualando ingresos: asignación óptima por
ronda y decodificador genético reutilizan a los mejor posicionados; el greedy reparte porque es centrado en
el repartidor. El sesgo por déficit de BRKGA-Fair y el bloque de Gini de MIP-Fair (sobre todos los conectados,
H_all, pero sin holgura frente a cobertura, L4) no alcanzan a compensarlo. Es el resultado central del paper
y debe presentarse como tal ("equidad para quién"): la garantía de fin de día tiene que definirse sobre una
población que el despachador no pueda encoger.

**Decisión E9 (provisional, para ratificar por el director, cambia el modelo).** El estadístico de la
restricción (ec. fair_const) y el reportado pasan a ser el Gini del pago por hora conectada sobre los
repartidores **elegibles** (conectados ≥ 1 h en el día, ceros incluidos); F_Gini sobre activos se reporta
como vista secundaria. No exige recorrer X1: todos los alcances salen de las tablas por repartidor. Lo que sí
cambia es el objetivo interno de los métodos (BRKGA-Fair: déficit sobre elegibles ociosos con prefiltro que
los incluya; MIP-Fair: Gini sobre elegibles con holgura de cobertura, E8; Pay-BRKGA: déficit sobre elegibles);
esas variantes de "segunda generación" se implementan al terminar X1 y se evalúan en X3 (840 corridas) y, si
la ganancia es clara, en una repetición parcial de X1 (5 semillas, 3 métodos). Alternativa si el director
prefiere no tocar el modelo: mantener F_Gini y añadir la tabla de alcances como advertencia; no la
recomiendo, porque el resultado principal sería una ilusión del estadístico.

Nota técnica: la recomputación difiere de F_Gini hasta 0,027 porque `shift_h` se guarda con dos decimales
(0,02 h para turnos de un minuto); confirma que los turnos cortos dominan el estadístico.

### 12.7 E9 ratificada; segunda pasada con cuatro semillas; análisis A2 y decisión E10 (2026-10-21, 16:30)

**E9 ratificada por el director** ("Ratifico E9, sigue con esa definición"). Desde ahora: F_Gini del paper =
Gini del pago por hora conectada sobre los repartidores elegibles (`shift_h ≥ 1`, ociosos con cero), calculado
ex post con `analyze_couriers.py --out output/paper/main_couriers.csv`; `analyze_paper.py --main --gini elig
--couriers-table …` y `figures_paper.py --fig f3f4` lo leen de esa tabla. El F_Gini de `metrics.py` (activos)
se conserva como `F_Gini_active` y como vista secundaria (tabla de alcances del paper). No se toca código que
X1 importe.

Semillas 1–4 completas (3.456 celdas; `output/paper/main_e9_stats.txt`, `main_e9_analysis.txt`). Media sobre
24 instancias (EE del Gini de elegibles 0,008 para greedy y 0,010–0,017 para el resto):

| Método (manual) | cobertura | Gini elegibles | activos / elegibles | p25 COP/h | Gini activos | atraso | pago/tarifa | cumple 0,40 / 0,50 |
|---|---|---|---|---|---|---|---|---|
| greedy | 0,759 | **0,301** | **0,97** | **481** | 0,509 | 19,9 | 1,00 | **97 % / 100 %** |
| ilp | 0,737 | 0,522 | 0,73 | 130 | **0,411** | 19,4 | 0,97 | 0 / 51 % |
| hier | 0,769 | 0,526 | 0,77 | 148 | 0,527 | **18,1** | 1,01 | 0 / 33 % |
| brkga | 0,769 | 0,565 | 0,70 | 86 | 0,484 | 18,5 | 1,01 | 0 / 23 % |
| brkga_fair w5…w40 | **0,770** | 0,546…0,534 | 0,74…0,75 | 121…134 | 0,498…0,504 | 18,6 | 1,01 | 0 / 38–47 % |
| mipfair α 0,20…1,00 | 0,763 | 0,544…0,545 | 0,72 | 104 | 0,461…0,474 | 19,0 | 1,01 | 0 / 38–42 % |
| paybrkga λ 0,1…1,0 | 0,757…0,752 | 0,537…0,547 | 0,73…0,71 | 119…95 | 0,486…0,457 | 18,8 | 0,95…0,87 | 0 / 46–33 % |

Auto-aceptación: greedy 0,296, ilp 0,502, hier 0,515, brkga 0,567, brkga_fair 0,536–0,547, mipfair 0,531–0,536,
paybrkga 0,534–0,535; cobertura 0,786 en todos. Diferencias pareadas contra greedy en el Gini de elegibles:
+0,205 (ilp auto) a +0,271 (brkga auto); ningún IC se acerca a menos de 0,17 de cero. Por ciudad (manual):
greedy 0,28–0,32; los demás 0,45–0,64 (Bucaramanga y Pereira las más desiguales). Pérdida de régimen
(manual − auto): cobertura −1,6 a −4,9 pts; Gini de elegibles ±0,02.

**A2: por qué H_t no lo evitó.** `EquityHistory.hourly_earnings` es `earnings / active_time` (minutos en
movimiento o sirviendo), no por hora conectada. Es una tasa de productividad casi igual entre repartidores:
uno con una entrega de diez minutos y otro con veinte valen casi lo mismo; solo el que nunca entregó tiene
déficit. Por eso (i) el déficit de BRKGA-Fair y Pay-BRKGA separa "con trabajo" de "sin trabajo" pero no
"poco" de "mucho", (ii) el Gini proyectado de MIP-Fair es casi plano y α es inerte (explica L4 junto con la
prioridad de cobertura), y (iii) la señal compite con la cobertura, que es la prioridad lexicográfica de
MIP-Fair y el fitness del BRKGA. Además la población interna es la conectada a la ronda (H_all), no la
elegible. BRKGA-Fair sí empuja en la dirección correcta (activos 0,70 → 0,75, Gini 0,565 → 0,534 con w de 5
a 40, en ambos regímenes), pero es una fracción de la brecha con el greedy. Esto es un hallazgo del paper, no
un bug: el modelo del paper define w_c por hora conectada (sección de métricas) y las políticas de primera
generación leían otra cosa.

**Decisión E10 (tomada; segunda generación, para X3).** Las tres políticas con la historia leída como pago por
hora *conectada hasta t* (`earnings / (t − on_time)`), sobre los repartidores elegibles (turno declarado
≥ 1 h), con el ocioso elegible a déficit máximo y, en MIP-Fair, con la holgura de cobertura ε de E8
(perder hasta ε de la cobertura máxima de la ronda a cambio del exceso de Gini). Configuraciones X3:
BRKGA-Fair-X (w = 20), Pay-BRKGA-X (λ_pay = 0,5), MIP-Fair-X (α = 0,30; ε ∈ {0, 0,02, 0,05}), contra su base
de primera generación y contra greedy; 24 instancias × 2 regímenes × 5 semillas = 1.200 corridas (X3 pasa
de 840 a ≈ 2.040). Implementación en un worktree de git (`C:/MDRP-dev`, rama `e10-variants`) para no tocar
los módulos que X1 importa; se funde en master al terminar X1. α* para X2 se decide después de X3 sobre el
Gini de elegibles (el 0,40 provisional se eligió sobre el de activos y ya no aplica: solo greedy lo cumple).

Hipótesis a contrastar en X3: (H1) con exposición en vez de productividad, BRKGA-Fair-X y MIP-Fair-X con
ε > 0 cierran una parte sustancial de la brecha 0,30–0,54 a un costo de cobertura menor que el 1,0–1,1 pts
que paga el greedy; (H2) ε mueve a MIP-Fair-X donde α no lo hacía; (H3) Pay-BRKGA-X sigue sin alcanzar a los
ociosos, porque el pago no llega a quien no recibe oferta.

### 12.8 E10 implementada y piloteada; E10b (prefiltro por déficit) es la palanca; el greedy ya lee H_t (2026-10-21, 17:15)

**Implementación** (worktree `C:/MDRP-dev`, rama `e10-variants`, commits 73b8e81 y siguientes; master no se toca
mientras corre X1): `fair_history.py` (base `exposure` = pago / horas conectadas hasta t con piso de 30 min;
población `eligible` = turno declarado ≥ 60 min, ocioso con cero), leído por BRKGA-Fair, Pay-BRKGA y MIP-Fair;
`mipfair_cov_slack` (E8); el estado lleva `C_all`; `batch_paper.py --experiment gen2`; 84 tests en verde (7
nuevos en `tests/test_fair_history.py`). Los valores por defecto reproducen la primera generación.

**Piloto 1 (Instancia_4 y 10, Pereira, semilla 1, ambos regímenes).** La base de exposición y la población
elegible solas (`_x`) mueven el Gini de elegibles ≤ 0,03: BRKGA-Fair 0,605 → 0,577 (manual), MIP-Fair 0,582 → 0,586.
Diagnóstico por ronda (`gen2_diag.py`): en la ronda mediana hay 33 elegibles ociosos sin ingreso y **ninguno es
candidato** de ninguna ruta; solo el 12–16 % de ellos entra alguna vez al conjunto de candidatos. Los métodos
centrados en el pedido no alcanzan a los ociosos porque el prefiltro (k más cercanos a la tienda) nunca los
incluye; la historia no puede actuar sobre quien no es candidato.

**E10b (tomada): prefiltro consciente del déficit.** `fair_cand_deficit_k`: además de los k más cercanos, cada
ruta prueba a los k_d repartidores ociosos con mayor déficit y, a igual déficit (todo ocioso sin ingreso tiene
déficit 1), los más cercanos a la tienda de esa ruta. (La primera versión desempataba por id y los mismos ocho
lejanos bloqueaban los cupos ronda tras ronda.) Piloto 2, Gini de elegibles, media de las dos zonas:

| configuración | manual: Gini elig. | activos/elig. | cobertura | CPU (s) | auto: Gini elig. | activos/elig. |
|---|---|---|---|---|---|---|
| greedy | **0,279** | **0,97** | 0,721 | 5 | **0,282** | **0,98** |
| brkga_fair_w20 (1.ª gen.) | 0,605 | 0,68 | 0,738 | 12 | 0,585 | 0,69 |
| brkga_fair_w20_x | 0,577 | 0,70 | 0,734 | 14 | 0,588 | 0,71 |
| brkga_fair_w20_xk (k_d = 8) | 0,547 | 0,73 | 0,732 | 17 | 0,556 | 0,73 |
| brkga_fair_w40_xk25 | 0,522 | 0,76 | 0,729 | 21 | 0,504 | 0,78 |
| mipfair_a030 (1.ª gen.) | 0,582 | 0,68 | 0,728 | 13 | 0,595 | 0,68 |
| mipfair_a030_x_e000 | 0,586 | 0,67 | 0,728 | 12 | 0,565 | 0,72 |
| mipfair_a030_xk_e000 (k_d = 8) | 0,492 | 0,83 | 0,736 | 31 | 0,447 | 0,91 |
| mipfair_a030_xk_e005 | 0,483 | 0,83 | 0,742 | 31 | 0,447 | 0,91 |
| mipfair_a030_xk25_e000 | 0,450 | 0,83 | 0,731 | 79 | 0,417 | 0,87 |
| paybrkga_l05_xk | 0,570 | 0,69 | 0,702 | 26 | 0,548 | 0,72 |

Lecturas: (i) el prefiltro es la palanca: MIP-Fair pasa de 0,58 a 0,45–0,49 sin perder cobertura (incluso
gana) y activa al 83–91 % de los elegibles; BRKGA-Fair de 0,61 a 0,50–0,52; (ii) la holgura ε de E8 apenas
mueve (el exceso de Gini de la ronda casi no cambia con una asignación); (iii) Pay-BRKGA sigue sin llegar a
los ociosos (H3 confirmada: el pago no alcanza a quien no recibe oferta); (iv) queda una brecha de 0,15–0,20
con el greedy, que activa al 97 %; (v) CPU: k_d = 8 duplica el tiempo de MIP-Fair y k_d = 25 lo multiplica por
seis (en Bogotá puede superar la hora; X3 con timeout de 150 min).

**El greedy ya lee H_t.** `GreedyPolicy.assign` recorre a los repartidores libres en orden creciente de
`history.orders_delivered` ("el menos servido elige primero") y cada uno toma la mejor ruta factible en su
tienda más cercana. No es "pedidos por urgencia al repartidor más cercano" como decía el paper (corregido,
commit 1b41ac6): es una regla centrada en el repartidor con prioridad al rezagado, es decir, la lectura más
barata posible de H_t (un entero por repartidor). Esto refuerza el mensaje: la historia importa, y la forma de
leerla (a quién se le ofrece trabajo) importa más que la sofisticación del término de equidad. El director
confirmó (21 oct, 21:00) que la práctica de la plataforma es centrada en el repartidor: el greedy del simulador
la reproduce y vuelve a ser "la práctica de la plataforma" en el paper (todo resuelto).

**Grilla gen2 de X3 (fijada).** brkga_fair_w20_x, brkga_fair_w20_xk, brkga_fair_w40_xk25, paybrkga_l05_xk,
mipfair_a030_x_e000, mipfair_a030_xk_e000, mipfair_a030_xk_e005, mipfair_a030_xk25_e000: 8 × 24 × 2 regímenes
× 5 semillas = 1.920 corridas; más `supp` (7 ablaciones + 2 de holgura E8, manual, 5 semillas = 1.080).
X3 ≈ 3.000 corridas, ≈ 12–15 h con 12 procesos. Se lanza al terminar X1 (fusión de `e10-variants` en master
primero). Hipótesis para X3: H1' el prefiltro cierra más de la mitad de la brecha 0,30–0,54 en las 24 zonas a
costo de cobertura nulo o negativo; H2 refutada en el piloto (ε no mueve); H3 confirmada en el piloto.

### 12.9 X1 cerrado con las diez semillas; X3 (gen2) lanzado (2026-10-24, 20:30)

**X1 terminó el 22 oct a las 11:01**: 8.640 corridas, 0 fallos, 2.037 min de pared con 12 procesos (≈ 254
corridas/h). `e10-variants` fusionada en master (e1939e9, 84 tests en verde). Pipeline de cierre ejecutado:
`analyze_couriers.py --out main_couriers.csv`, `tables_paper.py` (cuerpos de T3, tabla de alcances y T5 en
`output/paper/tables/`, números de la prosa en `stats.txt`), `figures_paper.py --fig f3f4`. El paper (`main.tex`)
lleva ya las tablas y la prosa con 10 semillas; los todo "seeds 1–4" desaparecen.

**Las diez semillas confirman las cuatro** (diferencias de ± 0,001–0,003 en todas las celdas). Manual, media de
las 24 instancias:

| configuración | cobertura | Gini elegibles | activos/elegibles | p25 COP/h | Gini activos | atraso | cumple α 0,40 / 0,50 |
|---|---|---|---|---|---|---|---|
| greedy | 0,758 | **0,301** | **0,97** | **481** | 0,509 | 19,9 | **98 % / 100 %** |
| ilp | 0,738 | 0,521 | 0,73 | 130 | **0,414** | 19,4 | 0 / 52 % |
| hier | 0,769 | 0,527 | 0,77 | 146 | 0,530 | **18,1** | 0 / 34 % |
| brkga | 0,770 | 0,565 | 0,70 | 86 | 0,488 | 18,5 | 0 / 24 % |
| brkga_fair w5–w40 | 0,769–0,770 | 0,545–0,534 | 0,74–0,75 | 122–134 | 0,496–0,504 | 18,5–18,6 | 0 / 38–46 % |
| mipfair α 0,20–1,00 | 0,764 | 0,544–0,545 | 0,72 | 103–105 | 0,460–0,468 | 19,0 | 0 / 39–40 % |
| paybrkga λ 0,1–1,0 | 0,758–0,753 | 0,537–0,547 | 0,73–0,71 | 118–95 | 0,488–0,455 | 18,7–18,8 | 0 / 46–35 % |

Diferencias pareadas contra greedy (Gini elegibles): +0,205 (ilp, auto) a +0,270 (brkga, auto); ningún IC 95 %
baja de +0,178. Por ciudad: greedy 0,27–0,32; el resto 0,43–0,64 (Bucaramanga y Pereira son las zonas más
desiguales bajo todos los métodos order-centric, 0,58–0,64). Pérdida por régimen (manual − auto) en cobertura:
greedy 2,8 pts, ilp 4,8, familia BRKGA 1,6–1,7, MIP-Fair 2,2, Pay-BRKGA 2,8–3,3; el régimen mueve el Gini de
elegibles ≤ 0,02. Pago sobre tarifa: 100 % en todos salvo Pay-BRKGA (λ 0,1–1,0: 95–88 % manual, 80 % auto).
Tiempos: MIP-Fair 4,5 min/día (máx. 21,9 en Bogotá); el resto 1,4–3,2.

**X3 gen2 lanzado el 24 oct a las 20:14** (`batch_paper.py --experiment gen2 --workers 12 --timeout-min 150`,
1.920 corridas, `output/paper/gen2.csv`, reanudable); estimación 8–10 h. Después, `--experiment supp` (1.080)
y X2 con el α* decidido tras X3. Hipótesis H1' (el prefiltro por déficit cierra más de la mitad de la brecha
0,30–0,54 sin costo de cobertura) se evalúa con `tables_paper.py output/paper/main.csv output/paper/gen2.csv
--couriers-table ...` tras `analyze_couriers.py` sobre gen2.

### 12.10 X3 gen2, lectura preliminar (semilla 1, 13 instancias; 2026-10-24, 22:30)

Con 256 de 1.920 corridas (≈ 125/h; fin estimado 25 oct ≈ 11:30), las 13 instancias completas de la semilla 1
(0, 1, 10–16 y otras cuatro) pareadas con las corridas de X1 de la misma semilla e instancia (`analyze_gen2.py`,
`output/paper/gen2_prelim_seed1.txt`). Gini de elegibles, media de las 13 instancias; "brecha" = fracción de la
distancia padre → greedy que cierra la variante:

| variante (manual / auto) | padre | Gini padre | Gini variante | Δ vs padre | brecha cerrada | Δ cobertura | min/corrida | inst. con Gini ≤ 0,40 (de 13) |
|---|---|---|---|---|---|---|---|---|
| brkga_fair_w20_x | brkga_fair_w20 | 0,555 / 0,552 | 0,531 / 0,533 | −0,023 / −0,019 | 0,11 / 0,09 | 0,000 | 2,1 | 0 / 0 |
| brkga_fair_w20_xk (k_d 8) | brkga_fair_w20 | 0,555 / 0,552 | 0,498 / 0,495 | −0,056 / −0,058 | 0,25 / 0,25 | 0,000 | 3,5 | 2 / 2 |
| brkga_fair_w40_xk25 | brkga_fair_w40 | 0,549 / 0,552 | **0,456 / 0,434** | −0,093 / −0,119 | **0,41 / 0,51** | 0,000 | 3,7 | 5 / 7 |
| mipfair_a030_x_e000 | mipfair_a030 | 0,558 / 0,548 | 0,553 / 0,538 | −0,006 / −0,010 | 0,02 / 0,04 | +0,002 | 4,0 | 0 / 0 |
| mipfair_a030_xk_e000 (k_d 8) | mipfair_a030 | 0,558 / 0,548 | 0,479 / 0,437 | −0,079 / −0,111 | 0,32 / 0,45 | **+0,010** / 0,000 | 8,3 | 1 / 3 |
| mipfair_a030_xk_e005 | mipfair_a030 | 0,558 / 0,548 | 0,474 / 0,437 | −0,084 / −0,112 | 0,34 / 0,46 | +0,009 / 0,000 | 8,3 | 1 / 3 |
| mipfair_a030_xk25_e000 | mipfair_a030 | 0,558 / 0,548 | **0,447 / 0,420** | −0,111 / −0,128 | **0,46 / 0,53** | +0,005 / 0,000 | 17,9 | 4 / 5 |
| paybrkga_l05_xk (k_d 8) | paybrkga_l05 | 0,559 / 0,545 | 0,542 / 0,521 | −0,017 / −0,025 | 0,08 / 0,11 | −0,003 / 0,000 | 3,8 | 0 / 0 |

Greedy en las mismas 13 instancias: 0,307 / 0,299. Lecturas:

1. **La base de exposición sola no mueve nada** (−0,01 a −0,02; confirma el piloto). **El prefiltro por déficit es
   la palanca, y escala con k_d**: k_d = 8 cierra un cuarto a un tercio de la brecha; k_d = 25 cierra la mitad
   (0,41–0,53), sin costo de cobertura (MIP-Fair incluso gana 0,5–1,0 pt en manual porque los candidatos extra
   absorben rechazos) y con +0,2–0,4 min de atraso. Los activos entre elegibles suben de 0,70–0,73 a 0,83–0,89 y
   el p25 de 70–100 a 240–310 COP/h.
2. **H1' (cerrar más de la mitad) queda en el borde** con k_d = 25: 0,46–0,53 en MIP-Fair y 0,41–0,51 en
   BRKGA-Fair. El gradiente 8 → 25 sugiere que k_d mayor sigue cerrando. ε (holgura de cobertura E8) no mueve
   nada: H2 refutada también aquí (e000 ≡ e005).
3. **Costo**: MIP-Fair xk25 cuesta 17,9 min/día en manual (máximo Bogotá; el ILP por ronda crece con los
   candidatos); BRKGA-Fair xk25 3,7 min. Si la calidad es similar, BRKGA-Fair w40 xk25 es la variante a
   recomendar.
4. **Pay-BRKGA xk** apenas responde (−0,02): el término de déficit en su fitness compite con el de pago; la
   palanca de pago no llega a los repartidores ociosos (ya dicho en el paper).

**Decisión E11 (tomada, pendiente de visto bueno):** al terminar gen2 se añaden a `supp` dos ablaciones de
k_d, `brkga_fair_w40_xk50` y `mipfair_a030_xk50_e000` (k_d = 50, ≈ "todos los elegibles ociosos cercanos"),
manual + auto, 5 semillas (24 × 2 × 2 × 5 = 480 corridas más) para cerrar la curva k_d ∈ {0, 8, 25, 50} y
decidir si la brecha se cierra del todo o satura. No se toca `batch_paper.py` hasta que gen2 termine. α* para
X2 se decide con la curva completa; con k_d = 25 el valor alcanzable por las políticas propuestas está en
0,42–0,46, lo que apunta a α* = 0,45 (y no 0,40) como umbral de la rodilla.

**Semilla 1 completa (24 instancias; 2026-10-25, 02:00; 686/1.920 corridas).** Confirma la lectura de las 13
instancias. Gini de elegibles manual / auto, media de las 24: brkga_fair_w20_x 0,514 / 0,517 (brecha 0,11 / 0,10);
brkga_fair_w20_xk 0,483 / 0,480 (0,26 / 0,25); **brkga_fair_w40_xk25 0,438 / 0,417 (0,44 / 0,54)**;
mipfair_a030_x_e000 0,540 / 0,523 (0,01 / 0,04); mipfair_a030_xk_e000 0,463 / 0,424 (0,34 / 0,46); e005 idéntica;
**mipfair_a030_xk25_e000 0,434 / 0,403 (0,47 / 0,56)**; paybrkga_l05_xk 0,527 / 0,508 (0,09 / 0,11). Cobertura sin
cambios (MIP-Fair xk +0,4–0,7 pt en manual). Instancias con Gini ≤ 0,40 (de 24): BRKGA-Fair w40 xk25 12 / 14,
MIP-Fair xk25 10 / 12, MIP-Fair xk 2 / 10; el greedy 24 / 24. Activos entre elegibles 0,85–0,91 con k_d = 25
(0,69–0,76 en la primera generación); p25 282–342 COP/h (85–134). Tiempos: MIP-Fair xk25 21 min/día en manual,
BRKGA-Fair xk25 4,5. H1' (> la mitad de la brecha) se cumple en auto (0,54–0,56) y queda justo por debajo en manual
(0,44–0,47): E11 (k_d = 50) decide si satura. Con k_d = 25 la mitad de los días cumplen α = 0,40 y casi todos
cumplirían 0,45: α* = 0,45 se mantiene como candidato para X2.

### 12.11 X3 gen2 cerrado con cinco semillas; E11 ejecutada; α* = 0,45 (2026-10-26, 14:10)

**X3 gen2 terminó el 25 oct a las 14:31**: 1.920 corridas, 0 fallos, 1.157 min de reloj (12 procesos). Tabla de
repartidores con `analyze_couriers.py output/paper/gen2.csv --out output/paper/gen2_couriers.csv`; análisis final con
`analyze_gen2_final.py` (`output/paper/gen2_final.txt`): 120 zona-días por régimen, pareados con X1 (mismas semillas
1–5). Resultados (Gini de elegibles, manual / auto):

- La base de exposición sola cierra 0,02–0,12 de la brecha greedy → padre (BRKGA-Fair 0,514; MIP-Fair 0,540 / 0,525).
- k_d = 8 cierra 0,25 (BRKGA-Fair) y 0,33 / 0,46 (MIP-Fair); k_d = 25 cierra 0,45 / 0,54 (BRKGA-Fair w40: 0,437 /
  0,416) y 0,47 / 0,57 (MIP-Fair: 0,435 / 0,401). Activos 0,85–0,91 de los elegibles; p25 282–343 COP/h.
- IC 95 % pareados frente al padre excluyen cero en todos los casos; con k_d = 25 ningún zona-día es peor que su padre;
  las medias por semilla difieren ≤ 0,008.
- Costo de servicio nulo: Δ cobertura −0,001 … +0,003 frente al padre; tardanza +0,1–0,3 min; pérdida de régimen igual.
- ε = 0,05 frente a 0: Gini dentro de 0,002, cobertura dentro de 0,001 (H2 refutada).
- Pay-BRKGA responde 0,09–0,12 de la brecha.
- CPU: BRKGA-Fair xk25 4,3–4,9 min/corrida (máx. 25); MIP-Fair xk25 11,1–23,5 min (máx. 110 en Bogotá manual).
- Cumplimiento (fracción de zona-días con Gini ≤ α), manual / auto, k_d = 25: α 0,40: 0,49 / 0,56 (BRKGA-Fair) y
  0,40 / 0,63 (MIP-Fair); α 0,45: 0,62 / 0,67 y 0,61 / 0,83; α 0,50: 0,72 / 0,81 y 0,82 / 0,96; α 0,30: 0 (0,03).
- Por ciudad (manual, k_d = 25): Barranquilla, Bogotá y Medellín 0,37–0,38; Cali 0,45–0,47; Bucaramanga y Pereira
  0,49–0,55 (el greedy está en 0,27–0,32).

**Veredicto de H1'**: se cumple en auto (0,54–0,57) y queda justo debajo en manual (0,45–0,47). La mitad de la brecha
que queda se atribuye a la estructura de la ronda order-centric (una ruta por repartidor y cobertura primero); la
ablación k_d = 50 (E11) prueba si es cuestión de candidatos.

**E11 ejecutada**: `batch_paper.py` añade a `ABLATIONS` `brkga_fair_w40_xk50` y `mipfair_a030_xk50_e000`
(`fair_cand_deficit_k = 50`) y la rama `supp` corre esas dos también en auto-aceptación (`E11_BOTH_REGIMES`). Grilla
supp: 11 ablaciones × 24 × 5 en manual + 2 × 24 × 5 en auto = 1.560 corridas. **Lanzado el 26 oct a las 14:00**
(`batch_paper.py --experiment supp --workers 12 --timeout-min 240`, `output/paper/supp.csv`, stdout en
`supp.stdout.txt`); estimación 12–16 h por el costo de MIP-Fair con k_d = 50.

**α\* = 0,45 para X2** (criterios del paper, tabla de α): A (Gini histórico del greedy) y B (banda) coinciden en 0,30,
que ninguna política order-centric alcanza ningún día; C (codo de Pareto) no aplica porque la cobertura es plana
(±0,3 puntos) a lo largo de α y de k_d; el intervalo es [0,30, 0,45] y el punto de operación recomendado es 0,45 con
BRKGA-Fair w40 xk25 (4–5 min/día frente a 11–24 de MIP-Fair con el mismo cumplimiento). Pendiente (E12, al terminar
supp, para no tocar código de corrida mientras corre): la rama `threshold` de `batch_paper.py` debe usar
`{**METHODS, **GEN2}` y los métodos greedy, hier, brkga_fair_w40_xk25, mipfair_a030_xk25_e000 y paybrkga_l05
(la `--mipfair-knee` original ya no tiene sentido porque α es inerte en MIP-Fair).

**En el paper** (`main.tex`, 45 pp., 0 errores, 44 todos): párrafo y tabla T7 (`tab:gen2`, de
`tables_paper.py main.csv gen2.csv --out-dir output/paper/tables_gen2 --configs …`), bloque de segunda generación en
la tabla de cumplimiento con la elección de α*, puntos huecos de la segunda generación en F3/F4
(`figures_paper.py --fig f3f4 --extra-csv output/paper/gen2.csv`), tabla de criterios de α completa, discusión
(pregunta 2), viñetas de la introducción sin todos de X1, y prosa por ciudad.

### 12.12 supp relanzado sin fairfirst (2026-10-27, 16:05)

Tras 26 h el lote supp llevaba 429 de 1.560 corridas (16/h; fin estimado 30 oct) con 6 timeouts de 240 min, todos de
MIP-Fair en la Instancia_0 de Bogotá en manual (total, fairfirst, idle, k25, xk50) y fairfirst en la Instancia_12.
`mipfair_a030_fairfirst` costaba 98 min/corrida (el 40 % del tiempo restante) y ya se sabe desde el piloto que es
degenerada (equidad-primero no asigna nada desde el arranque en frío; E5'). **Decisión**: se detiene el lote y se
relanza con `--methods` excluyendo fairfirst (las 27 corridas hechas bastan para la fila de la tabla de ablaciones);
el lote es reanudable, así que las 429 filas de `supp.csv` se conservan. Quedan 10 ablaciones × 24 × 5 en manual
+ 2 × 24 × 5 en auto = 1.440 celdas, 1.011 por correr; fin estimado 29 oct por la mañana. Los timeouts de Bogotá se
reportan como tales en el apéndice (el día más grande con los solvers más pesados). Primera lectura de E11: MIP-Fair
k_d = 50 en auto llega a 0,36 en la Instancia_8 (k_d = 25: 0,40 de media) y BRKGA-Fair k_d = 50 cuesta 6,7 min/corrida.
Registro del primer lote en `output/paper/supp.stdout.run1.txt`.

### 12.13 supp: lectura preliminar con cuatro semillas; E12 (2026-10-29, 18:30)

El lote supp murió con la sesión el 28 oct a las 21:49 con 1.012 filas en `supp.csv` (de 1.453 celdas: 1.440 sin
fairfirst más las 27 de fairfirst; 13 timeouts de 240 min: MIP-Fair idle / k25 / total / xk50 en la Instancia_0 de
Bogotá, semillas 1–3, e idle en la Instancia_6). Reanudado el 29 oct a las 17:48 con `output/paper/supp_resume.cmd`
lanzado con Start-Process (sobrevive a la sesión; log en `supp.stdout.txt`): (A) 428 celdas en las 23 instancias
restantes con `--retries 1`; (B) 13 celdas en la Instancia_0 sin las cuatro MIP-Fair manual que no terminan en 4 h
(`--retries 0`). **Decisión**: esas celdas (seis timeouts conocidos por semilla) no se reintentan; la tabla del
apéndice las reporta como timeout y usa 76–80 pares para esas filas.

Lectura preliminar (`analyze_supp.py` → `supp_analysis.txt`; cuerpo LaTeX en `tables/ablations.tex`; pareada con la
base de cada ablación en los mismos pares instancia-semilla; semillas 1–4, 84 pares por fila salvo las anteriores):

- **E11 (k_d = 50).** BRKGA-Fair w40: 0,403 / 0,351 (manual / auto) frente a 0,436 / 0,415 con k_d = 25
  (Δ −0,033 [−0,036, −0,030] y −0,064 [−0,069, −0,060]); ningún par peor; cobertura −0,001 / 0; 45/84 y 61/84 días
  ≤ 0,40; brecha cerrada 0,59 / 0,81 (k_d = 25: 0,45 / 0,54); 7,1 / 6,1 min por día (1,5×), máximo 34. MIP-Fair:
  0,418 / 0,399 frente a 0,440 / 0,402 (Δ −0,023 [−0,029, −0,017] y −0,003 [−0,008, +0,002], no significativa);
  cobertura −0,004 en manual; 52 / 25 min por día (2,7× / 2,3×), máximo 234, Instancia_0 manual fuera de las 4 h.
  Curvas k_d: BRKGA-Fair 0,533 → 0,436 → 0,403 (manual), 0,535 → 0,415 → 0,351 (auto), sigue bajando con costo
  lineal; MIP-Fair 0,549 → 0,468 → 0,440 → 0,418 y 0,533 → 0,426 → 0,402 → 0,399, se aplana con costo superlineal.
  Respuesta a la pregunta abierta en el paper: candidatos para la heurística; estructura de la ronda (una ruta por
  mensajero) y límite de 10 s para el modelo exacto. α* se mantiene en 0,45 (manual es el régimen de referencia;
  con k_d = 50 BRKGA-Fair cumple 0,40 el 54 % de los días en manual).
- **Ablaciones de primera generación (manual).** BRKGA score finish: −0,007, 1,6× CPU. BRKGA 20×20: +0,007 (peor en
  56/84), cobertura igual, 3× CPU: se mantiene 10×10. BRKGA-Fair w10 base total: −0,004. MIP-Fair sobre libres:
  −0,046 y +0,006 de cobertura (la expectativa de un Gini de cierre mayor no se cumple); base total: −0,035; k = 25:
  −0,041 y +0,007; las tres a 9–10× CPU (30–37 min/día, hasta 240 en Bogotá; consistente con rondas al límite de
  10 s cuando la restricción muerde) y ninguna alcanza a k_d = 25 (0,435). Equidad-primero (27 pares): cobertura
  0,285, Gini 0,153 por no asignar, 36× CPU. ε 0,02 / 0,05: dentro de 0,001 de la base.
- **Paper.** Tabla C.12 (`tab:ablations`) con cinco párrafos en el apéndice de ablaciones; cierre del párrafo de
  segunda generación con k_d = 50; párrafo de calibración (20×20 y k = 25) en el apéndice; timeouts por experimento
  (90 / 150 / 240 min) en implementación. 47 pp., 0 errores, 41 todos (uno nuevo: refrescar la tabla con la quinta
  semilla).

**E12 (decisión, 2026-10-29).** La rama `threshold` de `batch_paper.py` pasa al catálogo METHODS ∪ GEN2 con
THRESHOLD_METHODS = greedy, hier, brkga_fair_w40_xk25, mipfair_a030_xk25_e000, paybrkga_l05; θ ∈ {615, 1.242}
(IC 95 % del ajuste); **solo régimen manual** porque bajo auto-accept el umbral nunca se lee (`acceptance.py`,
toda oferta se acepta) y las filas de X1/gen2 con θ = 903 son la referencia; 5 semillas; `--mipfair-knee` se
acepta y se ignora. X2 pasa de 2.400 a 1.200 corridas (dry-run verificado). Hecho en el worktree `C:/MDRP-dev`
(rama `e12-threshold`) para no tocar el código mientras supp corre; se fusiona y se lanza (`--timeout-min 150`,
12 workers) al terminar supp.
