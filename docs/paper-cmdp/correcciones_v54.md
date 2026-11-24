# Correcciones v54 de `main.tex` (sobre `64804f8`)

Para David y su agente. Preparado del lado de Daniel el 24 nov 2026. **Solo texto: no hay corridas nuevas.** Cada cambio corrige una frase que no coincide con una tabla del propio artículo, con otra sección, con el código o con los CSV de `simulator/output/paper/`. El script `apply_correcciones_v54.py` (misma carpeta) aplica exactamente los textos de este documento, con la misma numeración.

## Antes de empezar

1. **Haz `git pull` en `correcciones-v53`.** La rama está en `64804f8` (19 nov), con las 29 correcciones de la revisión de `5dfb528`, `6b79f19` y `bf7800a`. La #17 se escribió desde `bf7800a`, y una copia local que circuló estaba incluso en `6b79f19` (α* = 0.45 y el resumen viejo). Todo lo de abajo supone `64804f8`.
2. Para no pisarnos (#17, punto 4): desde ahora **solo tu sesión toca `main.tex`** hasta que subas esta corrección. Del lado de Daniel no se edita.

## Cómo aplicarla

```bash
python docs/paper-cmdp/apply_correcciones_v54.py --check   # debe decir OK: 43 reemplazos y 5 rangos
python docs/paper-cmdp/apply_correcciones_v54.py           # aplica y deja paper/main.before_v54.tex
```

Luego compila (0 errores, sin `??`), haz las tareas M1–M10 y sube todo a `correcciones-v53`, no a `master`. Probado en una copia de `64804f8`: aplica limpio, las llaves cuadran y compila sin errores ni referencias indefinidas. **El cuerpo crece unas 15 líneas**: «Data availability» pasa de la p. 34 a la p. 35, las referencias terminan en la p. 38 y el apéndice empieza en la p. 39 (60 páginas). Las páginas siguen aparcadas (D3).

Las opcionales OPC1 y OPC2 (decisiones D1 y D2) solo se aplican con `--opcionales`, y solo si Daniel y David las aprueban.

## Resumen

| Bloque | Cambios |
|---|---|
| Introducción y §7 contra las tablas | C1–C7 |
| Límite del solver, fuentes de la Tabla 3, Tabla C.16 | C8–C10 |
| §6.1 y §6.3 contra las Tablas C.5, C.6 y C.11 | C11–C18 |
| §3–§5 contra el código | C19–C27 |
| Apéndices B y C | C28–C35 |
| Rangos de ecuaciones con guion | C23 (5 lugares) |

**Verificado sin cambio:** el «−0.3 to −1.1 under auto-accept» de §6.1 (L520) es correcto. La diferencia pareada Hierarchical − Greedy en auto-accept es −1.14 min (`main.csv`); el −1.2 sale de restar las medias redondeadas de la Tabla 2.

## Cambios de texto

### C1 · §1 Introducción · L140

**Por qué.** La introducción decía «ten points of Gini»; §7 (L610) dice «five to ten» desde 64804f8. Además, ninguna tabla da el atraso con k_d = 50: emparejado con Greedy en las cinco semillas de X3 (`supp.csv` y `main.csv`), BRKGA-Fair con k_d = 50 tiene 1.0 min menos de atraso en manual y 0.7 en auto-accept, no «one to two minutes».

**Texto actual:**
```latex
a managerial trade-off of a point of coverage and one to two minutes of lateness against ten points of Gini.
```

**Texto nuevo:**
```latex
a managerial trade-off of a point of coverage and about a minute of lateness against five to ten points of Gini.
```

### C2 · §7 Hallazgos y discusión · L610

**Por qué.** Igual que C1, en §7: el atraso de α* = 0.40 frente a Greedy es 1.0 min (manual) y 0.7 (auto-accept). El cálculo se agrega a `claims_text.py` (tarea M8).

**Texto actual:**
```latex
is a managerial trade-off of a point of coverage and one to two minutes of lateness against five to ten points of Gini.
```

**Texto nuevo:**
```latex
is a managerial trade-off of a point of coverage and about a minute of lateness (1.0 manual, 0.7 auto-accept) against five to ten points of Gini.
```

### C3a · §1 Introducción · L136

**Por qué.** 0.5–1.8 / 0.2–1.1 es el rango frente a las seis políticas centradas en el pedido, ILP incluida (Tabla 2; `claims_v53.txt`: 0.48–1.79 y 0.23–1.14), mientras §6.1 (L520) da −0.9 a −1.8 sin ILP ni Pay-BRKGA. Se dice el alcance para que no parezcan cifras distintas.

**Texto actual:**
```latex
and in lateness ($0.5$--$1.8$ minutes under manual acceptance, $0.2$--$1.1$ under auto-accept).
```

**Texto nuevo:**
```latex
and in lateness ($0.5$--$1.8$ minutes under manual acceptance and $0.2$--$1.1$ under auto-accept against the six order-centric policies).
```

### C3b · §7 Hallazgos y discusión · L608

**Por qué.** Igual que C3a, en §7.

**Texto actual:**
```latex
of $0.5$--$1.8$ minutes of lateness ($0.2$--$1.1$ under auto-accept),
```

**Texto nuevo:**
```latex
of $0.5$--$1.8$ minutes of lateness against the six order-centric policies ($0.2$--$1.1$ under auto-accept),
```

### C4 · §7 Hallazgos y discusión · L608

**Por qué.** §6.1 (L524, L526) y C.7 (L1303) concluyen que el α de MIP-Fair queda inerte por el conjunto de candidatos (k = 8) con cobertura primero, «and not the lexicographic priority»; §7 atribuía la inercia solo a la prioridad.

**Texto actual:**
```latex
the $\alpha$ of \textbf{MIP-Fair} is inert because coverage has priority in every round;
```

**Texto nuevo:**
```latex
the $\alpha$ of \textbf{MIP-Fair} is inert because, with coverage first and only $k = 8$ candidates per route, the coverage-optimal assignments of a round leave the Gini block almost nothing to choose;
```

### C5 · §7 Hallazgos y discusión · L610

**Por qué.** La Tabla C.8 no reporta el % de días que cumplen α = 0.30; reporta Gini medios: 0.212/0.211 (Greedy), 0.249/0.240 (BRKGA-Fair) y 0.224/0.207 (k_d = 25). Se reemplaza «on most days» por lo que la tabla sostiene.

**Texto actual:**
```latex
\textbf{Greedy} and the two \textbf{BRKGA-Fair} variants run on it meet $\alpha = 0.30$ on most days,
```

**Texto nuevo:**
```latex
\textbf{Greedy} and the two \textbf{BRKGA-Fair} variants run on it end the day at a mean Gini coefficient of $0.21$--$0.25$, below $\alpha = 0.30$ (Table~\ref{tab:review_thin}),
```

### C6 · §7 Hallazgos y discusión · L610

**Por qué.** Tabla C.11: con k_d = 25 en auto-accept, BRKGA-Fair cumple 0.40 el 56 % de los días y MIP-Fair el 64 %. «Only with the widest candidate set» solo vale en manual, o «under both regimes», como dice §6.4 (L528).

**Texto actual:**
```latex
the order-centric policies reach its upper bound on most days only with the widest candidate set,
```

**Texto nuevo:**
```latex
the order-centric policies reach its upper bound on most days under both regimes only with the widest candidate set ($k_d = 50$; $k_d = 25$ suffices under auto-accept),
```

### C7a · §1 Introducción · L138

**Por qué.** Tabla 2, manual: BRKGA 0.769 y Pay-BRKGA 0.753, es decir 1.6 puntos (frente a BRKGA-Fair serían 1.7). Se nombra la referencia.

**Texto actual:**
```latex
and $1.7$ points less under manual acceptance,
```

**Texto nuevo:**
```latex
and $1.6$ points less than \textbf{BRKGA} under manual acceptance,
```

### C7b · §6.4 Sensibilidad · L591

**Por qué.** CSV de la Figura C.5: pérdida de régimen de Pay-BRKGA 3.327 menos la de BRKGA 1.677 = 1.65, que redondea a 1.6.

**Texto actual:**
```latex
\textbf{Pay-BRKGA} loses $1.7$ points more than \textbf{BRKGA}
```

**Texto nuevo:**
```latex
\textbf{Pay-BRKGA} loses $1.6$ points more than \textbf{BRKGA}
```

### C8a · §5.5 Implementación · L472

**Por qué.** En `simulator/mip_fair.py` cada etapa lexicográfica es un `prob.solve(...)` con el límite de tiempo (líneas 282–285), así que el límite de 10 s es por etapa, como ya dicen §4.2 (L401) y C.4 (L1056).

**Texto actual:**
```latex
Mixed-integer programmes are solved with a limit of 10 seconds per round,
```

**Texto nuevo:**
```latex
Mixed-integer programmes are solved with a limit of 10 seconds per stage, each lexicographic stage being a separate solve,
```

### C8b · §8 Conclusión · L621

**Por qué.** Igual que C8a, en §8.

**Texto actual:**
```latex
and a 10-second limit per round;
```

**Texto nuevo:**
```latex
and a 10-second limit per stage;
```

### C9a · §6.4 Sensibilidad · L559

**Por qué.** X1 solo tiene configuraciones de primera generación (L460); las filas con k_d = 25 de las Tablas 3 y C.15 salen de X3 (cinco semillas), y sus guiones de α son niveles que X3 no corrió.

**Texto actual:**
```latex
the regime and $\alpha$ columns come from X1, the $\theta$ columns from X2,
```

**Texto nuevo:**
```latex
the regime and $\alpha$ columns come from X1 (from X3 for the rows with $k_d = 25$), the $\theta$ columns from X2,
```

### C9b · §6.4 Sensibilidad · L559

**Por qué.** Igual que C9a.

**Texto actual:**
```latex
on the seeds of its experiment (ten in X1, five in X2), and a dash marks a parameter the policy does not have or a configuration not run in X2.
```

**Texto nuevo:**
```latex
on the seeds of its experiment (ten in X1, five in X2 and X3), and a dash marks a parameter the policy does not have or a level not run in X2 or X3.
```

### C9c · §6.4 Sensibilidad · L587

**Por qué.** Igual que C9a, en el pie de la Tabla 3 (el de la Tabla C.15 remite a este).

**Texto actual:**
```latex
Regime and $\alpha$ from X1 (ten seeds); $\theta$ from X2 (five seeds, the five configurations of the threshold experiment); a dash marks a parameter the policy does not have or a configuration not run in X2.
```

**Texto nuevo:**
```latex
Regime and $\alpha$ from X1 (ten seeds) and, for the rows with $k_d = 25$, from X3 (five seeds); $\theta$ from X2 (five seeds, the five configurations of the threshold experiment); a dash marks a parameter the policy does not have or a level not run in X2 or X3.
```

### C10 · Ap. C.8 Sensibilidad y emisiones · L1360

**Por qué.** MIP-Fair en manual va de 0.762 (k_d = 50, Tabla C.14) a 0.769 (k_d = 8, Tabla C.5): 0.7 puntos. El 0.3 solo vale para α y para BRKGA-Fair.

**Texto actual:**
```latex
none: coverage flat within 0.3 points along $\alpha$ and along $k_d$
```

**Texto nuevo:**
```latex
none: coverage flat within 0.3 points along $\alpha$ and within 0.7 along $k_d$
```

### C11 · §6.1 Calidad y cumplimiento · L524

**Por qué.** `Table~\ref{tab:scope}` es la Tabla C.12, en el apéndice; las variantes se evalúan en el párrafo siguiente de §6.1.

**Texto actual:**
```latex
The second-generation variants that correct this are evaluated after Table~\ref{tab:scope}.
```

**Texto nuevo:**
```latex
The second-generation variants that correct this are evaluated in the next paragraph.
```

### C12 · §6.1 Calidad y cumplimiento · L526

**Por qué.** Tabla C.5, auto-accept: 0.415 (BRKGA-Fair, k_d = 25) y 0.401 (MIP-Fair, k_d = 25).

**Texto actual:**
```latex
and $0.401$--$0.416$ under auto-accept,
```

**Texto nuevo:**
```latex
and $0.401$--$0.415$ under auto-accept,
```

### C13 · §6.1 Calidad y cumplimiento · L526

**Por qué.** La Tabla C.6 no tiene el conteo de pares peores que su padre (ese conteo solo existe en la Tabla C.14); la cita se mueve a la frase de los intervalos. El agente confirma el conteo con `gen2_couriers.csv` (tarea M9); si algún par empeora más de 0.005, se borra la segunda mitad de la frase.

**Texto actual:**
```latex
Every paired interval excludes zero and no (instance, seed) pair is worse than its parent at $k_d = 25$ (Table~\ref{tab:gen2_paired}).
```

**Texto nuevo:**
```latex
Every paired interval excludes zero (Table~\ref{tab:gen2_paired}), and no (instance, seed) pair is worse than its parent at $k_d = 25$.
```

### C14 · §6.1 Calidad y cumplimiento · L526

**Por qué.** Tabla C.6, «Gap closed» de Pay-BRKGA: 9 % (manual) y 11 % (auto-accept).

**Texto actual:**
```latex
(9--12\% of the gap over the two regimes)
```

**Texto nuevo:**
```latex
(9--11\% of the gap over the two regimes)
```

### C15 · §6.1 Calidad y cumplimiento · L526

**Por qué.** Tabla C.6, Δ atraso: en manual de −0.0 a +0.3; en auto-accept de −0.0 a +0.1 (cinco de seis variantes en ±0.0). 64804f8 ya corrigió §7 a «at most 0.3 minutes».

**Texto actual:**
```latex
lateness rises by $0.1$--$0.3$ minutes,
```

**Texto nuevo:**
```latex
lateness rises by at most $0.3$ minutes ($0.1$ under auto-accept),
```

### C16 · §6.1 Calidad y cumplimiento · L528

**Por qué.** Tabla C.11 a α = 0.50: BRKGA-Fair 46/46, MIP-Fair 40/46 y Pay-BRKGA 37/45 (manual/auto-accept).

**Texto actual:**
```latex
and at $0.50$ the proposed policies reach 35--50\%.
```

**Texto nuevo:**
```latex
and at $0.50$ the proposed policies reach 37--46\%.
```

### C17 · §6.1 Calidad y cumplimiento · L530

**Por qué.** Tabla C.6: ΔF_Gini de Pay-BRKGA frente a su padre −0.021 (manual) y −0.027 (auto-accept).

**Texto actual:**
```latex
\textbf{Pay-BRKGA} moves least ($0.02$).
```

**Texto nuevo:**
```latex
\textbf{Pay-BRKGA} moves least ($0.02$--$0.03$).
```

### C18 · §6.3 Decisiones · L554

**Por qué.** §6.3 usa la Figura C.4 (semilla 1, 24 instancias agrupadas, L1257) y da 523 COP y 19–25 % de ociosos; §6.1 (L522) usa medias por instancia de X1 (481 COP, 21–30 %). Las dos cifras son correctas; se avisa que la muestra es distinta.

**Texto actual:**
```latex
\textbf{Greedy} leaves 3\% of the eligible couriers idle and its interquartile range
```

**Texto nuevo:**
```latex
In this pooled one-seed sample, \textbf{Greedy} leaves 3\% of the eligible couriers idle and its interquartile range
```

### C19 · §3.2 Proceso de decisión · L243

**Por qué.** `metrics.py` calcula el ingreso por hora del final del día con la duración del turno declarado (`shift_duration`, off − on) y `fair_history.py` usa t − on_time para quienes siguen conectados: las dos son min(t, l_c) − e_c. Para eso ℒ_t debe llevar e_c y l_c, que no estaban en su lista (L243).

**Texto actual:**
```latex
status $\sigma_c(t) \in \{\text{idle, picking-up, in-transit, dropping-off, offline}\}$ and time to next availability $\eta_c(t)$,
```

**Texto nuevo:**
```latex
status $\sigma_c(t) \in \{\text{idle, picking-up, in-transit, dropping-off, offline}\}$, time to next availability $\eta_c(t)$ and on- and off-times $e_c$ and $l_c$ (the declared shift),
```

### C20a · §3.2 Proceso de decisión · L252

**Por qué.** Con conn_c(t) = t − e_c el tiempo conectado seguiría corriendo después de la desconexión l_c, y t es el índice de la ventana. Ver C19.

**Texto actual:**
```latex
the connected time $\conn_c(t) = t - e_c$ follows from the on-time recorded in $\mathcal{L}_t$,
```

**Texto nuevo:**
```latex
the connected time $\conn_c(t) = \min(t, l_c) - e_c$ (in hours, $t$ read as clock time) follows from the declared shift recorded in $\mathcal{L}_t$,
```

### C20b · Ap. B.1 Notación · L685

**Por qué.** La Tabla B.1 con la misma definición.

**Texto actual:**
```latex
$\conn_c(t)$, $w_c(t)$ & connected time since log-in;
```

**Texto nuevo:**
```latex
$\conn_c(t)$, $w_c(t)$ & connected time since log-in, $\min(t, l_c) - e_c$;
```

### C21 · §3.2 Proceso de decisión · L302

**Por qué.** L263 define pay(c, s, ρ) = z·ρ; la Ec. (6) volvía a multiplicar por z.

**Texto actual:**
```latex
\lambda \sum_{(c,s) \in x_t} z_{c,s}\, \pay(c, s, \rho_{c,s}),
```

**Texto nuevo:**
```latex
\lambda \sum_{(c,s) \in x_t} \pay(c, s, \rho_{c,s}),
```

### C22 · §3.2 Proceso de decisión · L309

**Por qué.** El pago se abona al aceptar (L290), así que w_c es cero cuando el repartidor no ha ganado nada, no «cuando no entregó nada». Relacionado con la tarea M5 (`eligibility_thresholds.py`).

**Texto actual:**
```latex
be the hourly earnings of courier $c$ at the end of the day, zero if it delivered nothing.
```

**Texto nuevo:**
```latex
be the hourly earnings of courier $c$ at the end of the day, zero if it has earned nothing.
```

### C24 · §4.1 Motivación · L359

**Por qué.** G no estaba definido (L472: 10 generaciones), y Pay-BRKGA no usa el sesgo de déficit (L346, L395): su decodificador es el de la Ec. (11) con γ = 0.

**Texto actual:**
```latex
\STATE{run the BRKGA for $G$ generations with decoder of Algorithm~\ref{alg:decoder} and score of Eq.~\eqref{eqn:brkgafair} (fitness of Eq.~\eqref{eqn:paybrkga} for \textbf{Pay-BRKGA})}
```

**Texto nuevo:**
```latex
\STATE{run the BRKGA for $G = 10$ generations with decoder of Algorithm~\ref{alg:decoder} and score of Eq.~\eqref{eqn:brkgafair} ($\gamma = 0$, and fitness of Eq.~\eqref{eqn:paybrkga}, for \textbf{Pay-BRKGA})}
```

### C25 · §4.1 Motivación · L357

**Por qué.** w_c(t) por hora conectada es la base de exposición (segunda generación); la primera generación lee ingreso por hora ocupada (L350, L395).

**Texto actual:**
```latex
\STATE{compute from $\Hist_t$ (Eq.~\eqref{eqn:history}) the hourly earnings so far $w_c(t)$ of every connected courier}
```

**Texto nuevo:**
```latex
\STATE{compute from $\Hist_t$ (Eq.~\eqref{eqn:history}) the value $w_c(t)$ of every connected courier under the basis in use (earnings per busy hour in the first generation, per connected hour in the second)}
```

### C26a · §4.2 Políticas · L406

**Por qué.** ε aparecía en L462, L526, L1005 y L1303 sin definirse. En `simulator/mip_fair.py` (línea 293) las etapas siguientes mantienen cobertura ≥ (1 − ε) × óptimo de la etapa 1.

**Texto actual:**
```latex
The equity-first variant is reported as an ablation.
```

**Texto nuevo:**
```latex
The equity-first variant is reported as an ablation, and so is a coverage slack $\varepsilon$ that lets the later stages give up a fraction $\varepsilon$ of the stage-1 coverage ($\varepsilon = 0$ otherwise).
```

### C26b · Ap. B.4 MIP-Fair por ronda · L766

**Por qué.** La misma definición en la formulación completa de B.4.

**Texto actual:**
```latex
Stage 1 maximises $\sum_o y_o$; stage 2 fixes that value and minimises $v$;
```

**Texto nuevo:**
```latex
Stage 1 maximises $\sum_o y_o$; stage 2 keeps $\sum_o y_o \ge (1 - \varepsilon) \sum_o y_o^*$, with $y^*$ the stage-1 optimum, and minimises $v$;
```

### C26c · Ap. B.1 Notación · L694

**Por qué.** ε en la tabla de notación.

**Texto actual:**
```latex
$v$, $W_{\text{ref}}$, $d_{ij}$ & Gini excess, its scale and the pairwise differences of \textbf{MIP-Fair} \\
```

**Texto nuevo:**
```latex
$v$, $W_{\text{ref}}$, $d_{ij}$, $\varepsilon$ & Gini excess, its scale, the pairwise differences and the coverage slack of \textbf{MIP-Fair} \\
```

### C27 · §5.3 Diseño experimental · L460

**Por qué.** §3.1 da las anclas de la encuesta (0.28 y 0.41); la banda [0.30, 0.40] se define después, en §6.4 (L595).

**Texto actual:**
```latex
The $\alpha$ grid is centred on the inequality band of Section~\ref{sec:Problem_description}.
```

**Texto nuevo:**
```latex
The $\alpha$ grid is placed around the survey anchors of Section~\ref{sec:Problem_description} (0.28 and 0.41).
```

### C28a · §4.2 Políticas · L420

**Por qué.** 64804f8 cambió la contribución a «verified against the all-pairs model on 117 real rounds»; el párrafo de verificación de §4.2 solo nombraba la enumeración.

**Texto actual:**
```latex
are covered by unit tests against exhaustive enumeration on a test instance of three couriers and four orders; \ref{sec:App_verification} lists what each test checks.
```

**Texto nuevo:**
```latex
are covered by unit tests against exhaustive enumeration on a test instance of three couriers and four orders, and the block linearisation against the all-pairs model on 117 real rounds (\ref{sec:App_verification}).
```

### C28b · Ap. B.6 Verificación · L773

**Por qué.** El título de B.6 con las dos verificaciones que contiene.

**Texto actual:**
```latex
\subsection{Verification against enumeration}
```

**Texto nuevo:**
```latex
\subsection{Verification against enumeration and the all-pairs model}
```

### C29 · Ap. B.2 Ejemplo · L707

**Por qué.** En el ejemplo, B está libre y sin trabajo a las 12:30: su tiempo ocupado (tercera componente de h_c, L252) es 0.

**Texto actual:**
```latex
and $h_B = (0, 0, 30)$,
```

**Texto nuevo:**
```latex
and $h_B = (0, 0, 0)$,
```

### C30 · Ap. B.5 Ajuste · L771

**Por qué.** Fila «MIP-Fair prefilter k = 25» de la Tabla C.14: +0.008.

**Texto actual:**
```latex
and raises coverage by $0.007$ at eight times the CPU time
```

**Texto nuevo:**
```latex
and raises coverage by $0.008$ at eight times the CPU time
```

### C31 · Ap. C.3 Segunda generación · L970

**Por qué.** Tabla C.6: Pay-BRKGA con k_d = 8 mueve el Gini 0.021–0.027; el rango 0.054–0.131 es de BRKGA-Fair y MIP-Fair.

**Texto actual:**
```latex
the prefilter moves it by $0.054$--$0.131$, with every interval excluding zero
```

**Texto nuevo:**
```latex
the prefilter moves it by $0.054$--$0.131$ for \textbf{BRKGA-Fair} and \textbf{MIP-Fair} and by $0.021$--$0.027$ for \textbf{Pay-BRKGA}, with every interval excluding zero
```

### C32 · Ap. C.3 Segunda generación · L1041

**Por qué.** La columna de atraso de la Tabla C.6 no trae intervalos; solo Gini y cobertura los tienen.

**Texto actual:**
```latex
paired differences of the end-of-day Gini coefficient, coverage and mean lateness with 95\% intervals ($\pm 1.96$ SE over the pairs),
```

**Texto nuevo:**
```latex
paired differences of the end-of-day Gini coefficient and coverage with 95\% intervals ($\pm 1.96$ SE over the pairs) and of mean lateness,
```

### C33 · Ap. C.7 Ablaciones · L1264

**Por qué.** Tabla C.14, fila de prioridad de equidad primero: 98.7 min por corrida.

**Texto actual:**
```latex
(98 minutes per run
```

**Texto nuevo:**
```latex
(98.7 minutes per run
```

### C34 · Ap. C.7 Ablaciones · L1303

**Por qué.** Tabla C.14: ε = 0.02 da 25/37 pares peores/mejores y ε = 0.05 da 28/25, no «as many worse as better». Las filas con ε = 0.05 de la segunda generación están en la Tabla C.6, no en la C.5.

**Texto actual:**
```latex
with as many pairs worse as better; this is the first-generation counterpart of the $\varepsilon$ result in Table~\ref{tab:gen2},
```

**Texto nuevo:**
```latex
with 25--28 pairs worse and 25--37 better out of 120; this is the first-generation counterpart of the $\varepsilon$ result in Table~\ref{tab:gen2_paired},
```

### C35 · Ap. C.7 Ablaciones · L1299

**Por qué.** El 0.460 es el Gini de activos de la base sobre los mismos 115 pares (`supp.csv` y `main.csv`, semillas 1–5; verificado). La Tabla C.5 da 0.458 con los 120 pares; por eso se aclara.

**Texto actual:**
```latex
and the active-courier Gini from $0.460$ to $0.413$.
```

**Texto nuevo:**
```latex
and the active-courier Gini from $0.460$ to $0.413$ on the same 115 pairs.
```

### C23 · Rangos de ecuaciones · L325, L361, L404 y dos en B.4

**Por qué.** Los rangos salían con guion espaciado («Eqs. (8) - (10)»). Se reemplazan las 5 apariciones de `} - \eqref{` por `}--\eqref{` (raya corta).

## Opcionales, pendientes de decisión (D1 y D2)

### OPC1 · Resumen · L111

**Por qué.** D1: el recorte del resumen quitó la única mención de que la aceptación se estima con datos de campo. Añade 8 palabras (el resumen queda en unas 235).

**Texto actual:**
```latex
and logit acceptance on pay per kilometre under manual and auto-accept regimes.
```

**Texto nuevo:**
```latex
and logit acceptance on pay per kilometre, estimated from field interviews and a survey, under manual and auto-accept regimes.
```

### OPC2 · §8 Conclusión · L619

**Por qué.** D2: §6.4 (L593) ya dice que X2 no corrió k_d = 50; §8 no lo repetía entre las limitaciones.

**Texto actual:**
```latex
but the slope interval was not swept and the parameters are grade C.
```

**Texto nuevo:**
```latex
but the slope interval was not swept and the parameters are grade C. The operating point $\alpha^* = 0.40$ rests on the five seeds of X3 and was not rerun in X2, so its sensitivity to the threshold is not measured.
```

## Tareas que necesitan la máquina de David

Las M1–M7 son las de mi comentario del 20 nov en la #16; se repiten aquí para tener todo en un solo lugar.

| | Qué | Detalle |
|---|---|---|
| M1 | Figura 2 (`snapshots_f6.py`) | Dibujar la línea de α con un estilo que no use ninguna política (p. ej. `ax.axhline(args.alpha, color="#bdbdbd", lw=0.6, ls="-")`); hoy es gris discontinua, igual que Hierarchical, y el texto ya dice «horizontal line». Usar `NaN` hasta la primera entrega en vez de Gini 0 (hoy las curvas arrancan en 0 y saltan a ~1 a las 00:50). |
| M2 | Figuras 1 y C.3 (`figures_paper.py`) | La guía de «α 0.20–1.00» cruza su propia etiqueta; en auto-accept el marcador de ILP tapa el de Pay-BRKGA k_d = 8; hay guías de hasta 112 pt; «k_d = 25 (γ = 40)» y «k_d = 8» se tocan. Rotular los extremos de BRKGA-Fair (γ = 5 y 40) y de Pay-BRKGA (λ = 0.1 y 1.0). |
| M3 | Tamaños | F7 (Figura C.4) y F2 (Figura C.2) quedan a 7.5 pt; subirlas a 8 pt como las demás. |
| M4 | Tablas | `\usepackage[figuresright]{rotating}` para que las apaisadas giren todas igual; quitar `lscape`. La Tabla C.4 se sale unos 15 pt del margen. Tabla 2 a 6.9 pt: con `\setlength{\tabcolsep}{4pt}` sube a ~7.3. Columnas `>{\raggedright\arraybackslash}p{...}` en B.1, C.3 y C.16 («man- ual», «refer- ence»). La Tabla C.9 (dos filas) ocupa una página apaisada entera. Los flotantes de C.6 salen después del título de C.7. |
| M5 | `eligibility_thresholds.py` | Contar como activo a quien entregó (`orders > 0`), no a quien cobró (`payment > 0`): cambia una celda en 0.01. Implementar la comprobación contra `main_couriers.csv` que promete el docstring. Regenerar `eligibility.tex` y pegarlo en la Tabla C.13. |
| M6 | Reproducibilidad | Las filas k_d = 50 de la tabla de cumplimiento (C.11) no las genera ningún script: añadir `--extra-runs output/paper/supp.csv` en la llamada de gen2 de `tables_paper.py`. `analyze_supp.py` todavía escribe `w =` (líneas 23 y 30): al regenerar se perdería la γ. Añadir `claims_text.py` a `regen_paper.sh`. |
| M7 | Compilar y subir el PDF | Recompilar después de M1–M6 y de esta corrección, subir `main.pdf` y decir en qué página terminan el cuerpo y las referencias. |
| M8 | Cifras nuevas en `claims_text.py` | Que imprima las dos cifras que introduce esta corrección: (a) atraso de BRKGA-Fair (γ = 40, exposure, k_d = 50) menos Greedy, emparejado por (instancia, semilla) en las semillas 1–5: −1.01 min (manual) y −0.69 (auto-accept), base de C1–C2; (b) Gini de activos de la base de MIP-Fair sobre los 115 pares de la ablación free-only: 0.460, base de C35. |
| M9 | Comprobar C13 | Con `gen2_couriers.csv` y los padres en `main_couriers.csv` (semillas 1–5), contar los pares (instancia, semilla) en los que las variantes con k_d = 25 terminan con F_Gini más de 0.005 por encima de su padre. Si hay alguno, borrar «, and no (instance, seed) pair is worse than its parent at $k_d = 25$». |
| M10 | Avisar en la #17 | Commit y push a `correcciones-v53` con el resumen, el enlace al PDF y las páginas. No fusionar a `master` hasta cerrar D1–D6. |

## Decisiones para Daniel y David (en la llamada)

| | Tema | Detalle |
|---|---|---|
| D1 | Calibración de campo en el resumen | El recorte la quitó y es la única señal de que la aceptación se estima con datos. Texto propuesto: OPC1 (+8 palabras; el resumen queda en unas 235). |
| D2 | Alcance de α* = 0.40 | Se apoya en cinco semillas y X2 no corrió k_d = 50 (ya dicho en §6.4). Opciones: (a) dejarlo como limitación declarada y añadir OPC2 en §8; (b) correr X2 con k_d = 50: unas 240 corridas (una configuración, θ = 615 y 1,242, 24 instancias, cinco semillas, solo manual). |
| D3 | Páginas | La guía de autores de EJOR cuenta en las 35 páginas (11 pt, interlineado 1.5) tablas, figuras, referencias **y apéndices**; con v54 el PDF tiene 60. La salida habitual es mandar los apéndices como material suplementario. |
| D4 | Highlights | La guía de EJOR los pide como archivo aparte; `estilo-ejor.md` dice que no. Resolver antes del envío. |
| D5 | Las cinco objeciones de árbitro de la #16 | Benchmark a la medida de la métrica; artefacto de la sobreoferta; población elegible elegida a posteriori; políticas mal especificadas; modelo de aceptación débil. Decidir cuáles se atienden en el texto y cuáles van a limitaciones. |
| D6 | Fusión a `master` | Después de v54, M1–M10 y D1–D5. |
