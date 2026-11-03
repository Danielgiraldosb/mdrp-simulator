# Prompts para corregir `main.tex` (versión del 3 nov 2026, 53 páginas)

Este documento reemplaza a todos los anteriores (`correcciones_main_v53.md`, `cambios_explicitos_literatura_y_tabla1.md` y versiones previas). Contiene **todo** lo que hay que cambiar en el artículo: la instancia duplicada, la literatura y la referencia que falta (Cheng y Sharif Azadeh 2025), la bibliografía, las cifras que no cuadran con las tablas, la notación, la redacción, las tablas, las figuras y la portada. Cada bloque trae el cambio explícito y el prompt listo para pegar.

Lo revisé contra el `main.tex`, el `references.bib` y el PDF de 53 páginas del repositorio (HEAD 76c726f), contra los datos de `real_instancies/` y contra las páginas renderizadas del PDF.

## Decisiones ya tomadas por ti

| Tema | Decisión |
|---|---|
| Instancias 1 y 3 | Son el mismo día (verificado: filas idénticas en `orders.csv`, `couriers.csv` y `stores.csv`; solo cambian el prefijo del id y el formato de la hora; no hay otros duplicados entre las 24). **Se quita la instancia 3: el artículo pasa a 23 instancias.** |
| Encuadre | La contribución principal es el **diagnóstico** (población, base de la historia y oferta); la segunda generación es la mitigación. |
| Fila de Cheng en la Tabla 1 | Horizonte "shift"; datos "(✓)" con nota. |
| Plataforma | Anónima; no se nombra. |
| Datos y código | Públicos, en el repositorio `github.com/Danielgiraldosb/mdrp-simulator`. |
| Término para "ablation" | "component analysis" (títulos) y "variant" (frases). |
| Artículo MIC 2026 | "A Biased Random-Key Genetic Algorithm with Rolling Horizon for the Meal Delivery Routing Problem", Daniel Giraldo-Herrera y David Álvarez-Martínez (tomado de `BRKGA_model/nuevo_articulo/MIC2026_paper_82 _final.pdf`). |
| Financiación y agradecimientos | Sin financiación. No se agradece a nadie: se elimina la sección y se pone la declaración estándar de financiación. |
| c1 y c2 | Se borra el TODO y se deja la lectura lexicográfica (cobertura ≻ latencia), que es lo que hace el código. |

## Lo que asumí y debes confirmar (no bloquea los prompts)

1. **CSV de resultados.** En tu computador, `simulator/output/paper/` solo tiene `review.csv`, `review_couriers.csv`, `supply.csv` y `blocks_check*.csv`. Faltan `main.csv`, `main_couriers.csv`, `gen2.csv`, `gen2_couriers.csv`, `supp.csv` y los de X2 (`simulator/output/` está en `.gitignore`). El prompt P1 los busca y **se detiene si no los encuentra**. Si están en el computador de experimentos (i9-14900K), cópialos a `simulator/output/paper/` antes de correr P1.
2. **Correo y autor de correspondencia.** Puse Daniel con `ds.giraldoh@uniandes.edu.co`, el correo de tu artículo MIC 2026 y de tu cuenta. Hoy `main.tex` dice `d.giraldoh@uniandes.edu.co`.
3. **Estado del artículo MIC 2026.** Lo cité como "to appear" en las actas del congreso. Si ya está publicado, cambia la entrada por la de la editorial.
4. **Coordenadas de entrega en el repositorio público.** `orders.csv` tiene la latitud y la longitud de entrega con 7 decimales, lo que identifica casas. Confirma que publicarlas está permitido por el acuerdo con la plataforma y por la Ley 1581 de 2012. Si no lo está, redondea a 3 decimales o desplaza las coordenadas antes de enviar (prompt P20).

---

## Reglas para todos los prompts (pégalas una vez al inicio de la sesión con Claude)

```
Vas a corregir docs/paper-cmdp/paper/main.tex y references.bib siguiendo prompts_correccion_main_v53.md.
Reglas fijas para todos los prompts:
1. Antes de cambiar, busca con grep cada frase que el prompt cita y dime en cuántos lugares aparece y en qué líneas. Si el texto ya no coincide, muéstrame lo que hay y espera.
2. Toda cifra se recalcula desde simulator/output/paper/*.csv con un script que guardas en simulator/ (nunca desde el PDF ni de memoria). Muéstrame el valor recalculado junto al del texto antes de reemplazarlo.
3. Cambia solo lo que dice el prompt. No reescribas párrafos enteros si el prompt pide una frase.
4. Al terminar cada prompt: muéstrame el diff, recompila (tectonic o latexmk), y confirma que no hay "undefined reference", "??" ni "Citation undefined", y cuántas páginas tiene el PDF.
5. Lo marcado como DECISIÓN MÍA no lo decides: muéstrame las opciones y espera.
6. Trabaja en una rama nueva (git checkout -b correcciones-v53) y haz un commit por prompt con el número del prompt en el mensaje.
```

## Orden de ejecución

1. **Fase 0 (P0):** rama y libro de cifras.
2. **Fase 1 (P1–P3):** quitar la instancia 3 y recalcular todo. Va primero porque cambia casi todas las cifras.
3. **Fase 2 (P4–P11):** literatura y bibliografía. No depende de las cifras y puede hacerse en paralelo con la fase 1.
4. **Fase 3 (P12–P18):** coherencia de cifras, sobre los valores ya recalculados.
5. **Fase 4 (P19–P23):** portada, declaraciones, título y contribuciones.
6. **Fase 5 (P24–P29):** notación y redacción.
7. **Fase 6 (P30–P36):** tablas y figuras.
8. **Fase 7 (P37–P39):** verificación final.

---

# FASE 0. Preparación

## P0. Rama y libro de cifras

**Qué se hace:** crear la rama y un registro de todas las cifras del artículo con su fuente. Sirve para comprobar después de la fase 1 que ninguna cifra quedó con el valor de 24 instancias.

```
Crea la rama correcciones-v53. Luego crea docs/paper-cmdp/paper/numbers_ledger.csv con una fila por cada cifra numérica del resumen, la introducción (viñetas), §5.1, §5.3, §6, §7, §8 y los apéndices C (excepto las celdas de las tablas, que salen de scripts). Columnas: id, sección, línea de main.tex, texto con la cifra, valor, tabla o figura que la respalda (o "ninguna"), CSV y columna de origen, script, estado (pendiente). Escribe además simulator/check_ledger.py, que recalcula desde los CSV las cifras que tengan origen y marca "difiere" si el valor del .tex difiere más que el redondeo. No cambies main.tex en este prompt. Dime cuántas cifras hay, cuántas tienen tabla y cuáles no tienen ninguna tabla que las respalde.
```

---

# FASE 1. Quitar la instancia 3 (duplicado de la instancia 1)

## P1. Localizar los CSV y reagregar sin la instancia 3

**Qué se hace:** las corridas existentes se filtran (`instance != 3`) y se recalcula todo. No hay que correr nada nuevo.

```
Paso 1. Busca main.csv, main_couriers.csv, gen2.csv, gen2_couriers.csv, supp.csv, los CSV de X2, review.csv, review_couriers.csv y supply.csv en simulator/output/paper/ y en cualquier carpeta del repositorio (find . -name "*.csv" -path "*output*"). Si falta alguno de los primeros cinco, DETENTE y dime cuáles faltan: no inventes ni reconstruyas resultados.
Paso 2. Confirma el duplicado: compara real_instancies/Instancia_1 y Instancia_3 (orders, couriers y stores) ignorando la columna de id y normalizando las horas (00:00:01 = 0:00:01). Deben ser idénticas fila a fila. Repite la comparación para todos los pares de las 24 instancias y dime si aparece otro duplicado.
Paso 3. En cada script de análisis (tables_paper.py, analyze_paper.py, analyze_gen2_final.py, analyze_supp.py, analyze_x2.py, analyze_couriers.py, analyze_review.py, analyze_review2.py, figures_paper.py, diag_supply.py) añade una única constante EXCLUDED_INSTANCES = {3} en config.py y filtra con ella al cargar cada CSV. No borres las filas de los CSV ni la carpeta Instancia_3.
Paso 4. Regenera todas las tablas (output/paper/tables/*.tex) y figuras (docs/paper-cmdp/paper/figures/) con los scripts. Lista cada tabla y figura regenerada.
Paso 5. Dame el nuevo conteo de corridas por experimento contando las filas de los CSV filtrados (X0, X1, X2 completadas, X3 segunda generación, suplemento, revisión) y las CPU-horas sumando el tiempo de pared de cada corrida. Confirma si la instancia 3 estaba en el piloto X0 (una instancia por ciudad).
```

## P2. Actualizar en el texto todo lo que depende de "24 instancias"

**Dónde:** 28 apariciones de "24" ligadas a instancias o días (20 "24 instances", "24 operating days", "24 real", "24 full operating days", "the 24 instances", "24 (six cities)", más N = 24 en §5.4). También las cifras derivadas del número de instancias.

**Cambios explícitos:**

| Dónde | Hoy dice | Debe decir |
|---|---|---|
| Resumen, §1, §8 | "24 operating days" / "24 real operating days" | "23 operating days" / "23 real operating days" |
| §5.1 | "We test our policies on 24 full operating days" | "We test our policies on 23 full operating days" |
| §5.1 | "(four days each, except three for Cali and five for Bucaramanga)" | "(four days each, except three for Cali)" |
| §5.1 | "zone sizes range from 342 to 10,215 orders (mean 3,612)" | "zone sizes range from 342 to 10,215 orders (mean 3,688)" (recalcula) |
| §5.3 | "the 24 instances and ten seeds", "(8,640 runs)", "(1,200 runs, 1,197 completed)", "1,920 runs", "1,453 runs completed", "1,680 runs", "14,935 runs and 1,289 CPU-hours" | valores de P1 paso 5 (X1 = 18 × 2 × 23 × 10 = 8,280; X2 = 1,150 programadas; X3 = 1,840; revisión = 920 + 690 = 1,610; el suplemento y el total se cuentan desde los CSV) |
| §5.4 | "SE = SD/√N with N = 24" | "N = 23" |
| §6.3 | "(23,944 couriers, manual regime)" | recalcula sin la instancia 3 |
| Tablas C.10 y C.17, Apéndice C.5 y C.7 | "n = 120", "120 (instance, seed) pairs", "115–116 pairs", "240 manual-regime runs" | 115, 110–111 (recalcula) y 230 |
| Pie de la Tabla C.6 | "Instances 1 and 3 are different days with identical counts." | se borra la fila de la instancia 3 y la frase; nota nueva: "Instance 3 of the export duplicates instance 1 and is excluded." |
| Tabla C.6 | 24 filas | 23 filas (se conservan los números originales 0–23 sin el 3, para que coincidan con las carpetas del repositorio) |

```
Aplica P2 de prompts_correccion_main_v53.md. Primero lista con grep -n todas las apariciones de "24" en main.tex y clasifícalas en (a) número de instancias o días, (b) número de pares (instancia, semilla) o de corridas, (c) otra cosa (24 horas, 00:00–24:00, etc.). Muéstrame la lista y espera mi visto bueno. Luego reemplaza (a) por 23 y (b) por los valores recalculados en P1, usando la tabla de cambios del documento. Borra la fila 3 de la Tabla C.6 y cambia su nota al pie como dice el documento. Recalcula la media del tamaño de zona (debe dar 3,688) y "23,944 couriers". En §5.4 cambia N = 24 por N = 23. No toques todavía las demás cifras de resultados: eso es P3.
```

## P3. Sustituir todas las cifras de resultados por las recalculadas

**Qué se hace:** con 23 instancias cambian las medias, los errores estándar, los intervalos, los porcentajes de cumplimiento y los rangos del texto. Se reemplaza cada cifra desde el libro de cifras de P0.

```
Corre simulator/check_ledger.py sobre los CSV ya filtrados (sin la instancia 3). Para cada cifra marcada "difiere", muéstrame una tabla con: línea, texto actual, valor nuevo, tabla de origen. Espera mi visto bueno y luego reemplaza en main.tex. Incluye el resumen (0.30; 0.52–0.57; "a quarter"; 0.21–0.25), las siete viñetas de §1, §6.1–§6.4, §7 y §8, y los apéndices B.5, C.2, C.3, C.5, C.7 y C.8. Inserta las tablas regeneradas en P1 en lugar de las actuales (Tablas 2, 3, C.6, C.8–C.20) y comprueba que las cifras del texto que citan cada tabla coinciden con ella. Si alguna afirmación cualitativa cambia (un ranking, "every interval excludes zero", "the ranking holds in each of the six cities", "no pair is worse"), dímelo aparte antes de cambiarla. Al final vuelve a correr check_ledger.py: no debe quedar ninguna cifra "difiere".
```

---

# FASE 2. Literatura y bibliografía

El trabajo que falta incorporar es **Cheng y Sharif Azadeh (2025), arXiv:2501.05808**. En mi búsqueda solo aparecen versiones de arXiv (v1 del 10 de enero de 2025).

Resumen del trabajo, para no afirmar de más:
- **Problema:** despacho de pedidos y reposicionamiento de domiciliarios ociosos con DDQN, con demanda predicha a 15 minutos en el estado.
- **Domiciliarios y pago:** son empleados pagados por hora que obedecen todas las instrucciones. El pago no es una decisión.
- **Estado y recompensa:** el estado no tiene ingresos acumulados y la recompensa no tiene término de equidad.
- **Equidad:** el equilibrio de carga entre domiciliarios (desviación estándar de pedidos, tiempo de entrega y distancia en un turno de 2 horas) se mide solo a posteriori.
- **Datos:** pedidos sintéticos generados a partir de transacciones reales.

## P4. Entrada bibliográfica de Cheng y Sharif Azadeh

**Dónde:** `references.bib`, entrada `rl2025fairdelivery`.

**Hoy dice:**
```bibtex
@misc{rl2025fairdelivery,
  author = {{TODO authors}},
  title  = {{TODO title: reinforcement learning for fair courier assignment in food delivery}},
  year   = {2025}, eprint = {2501.05808}, archivePrefix = {arXiv} }
```

**Reemplazar por:**
```bibtex
@misc{cheng2025realtime,
  author        = {Cheng, Jingyi and {Sharif Azadeh}, Shadi},
  title         = {Real-Time Integrated Dispatching and Idle Fleet Steering with Deep Reinforcement Learning for A Meal Delivery Platform},
  year          = {2025},
  eprint        = {2501.05808},
  archivePrefix = {arXiv},
  primaryClass  = {eess.SY},
  note          = {Preprint (v1, 10 January 2025)}
}
```

```
En references.bib reemplaza la entrada rl2025fairdelivery por la entrada cheng2025realtime exactamente como está en P4 de prompts_correccion_main_v53.md. En main.tex reemplaza todas las apariciones de la clave rl2025fairdelivery por cheng2025realtime (grep -n "rl2025fairdelivery" main.tex; deben ser la Tabla 1, §2 y el Apéndice A.3). Recompila y confirma que en la lista de referencias aparece "Cheng, J., Sharif Azadeh, S., 2025. Real-time integrated dispatching..." entre Cachon et al. (2017) y Corbett-Davies et al. (2023), y que ya no aparece "TODO authors".
```

## P5. Tabla 1: fila de Cheng y Sharif Azadeh y formato

**Hoy dice (fila del grupo Behaviour):**
```
TODO authors (2025) | [TODO: ] | reward term | [TODO: ] | [TODO: ] | [TODO: ] | [TODO: ]
```

**Debe decir** (columnas: Paper, Fairness metric, Guarantee horizon, Acceptance, Pay decided, History in state, Real data):

| Paper | Fairness metric | Guarantee horizon | Acceptance | Pay decided | History in state | Real data |
|---|---|---|---|---|---|---|
| Cheng and Sharif Azadeh (2025) | workload s.d. | shift | perfect | | | (✓) |

**Orden del grupo Behaviour:** Ahamed et al. (2021), Bozanta et al. (2022), Cheng and Sharif Azadeh (2025), Quintero Rojas (2020).

**Pie de la Tabla 1.** Se borra "[TODO: complete the row of TODO authors (2025) (placeholder bib entry).]" y se añade al final:
> Workload s.d.: standard deviation of orders, delivery time and distance among couriers, reported ex post and not constrained; (✓): synthetic orders generated from real transactions.

**Formato (visto en la página 5):** las etiquetas verticales de los grupos se salen y se montan entre sí ("Fairness and pay" encima de "MDRP operations"; "Behaviour" queda cortada, porque el grupo solo tiene cuatro filas).

```
Aplica P5 de prompts_correccion_main_v53.md en la Tabla 1 (label tab:Litclass). (1) Reemplaza la fila de \cite{cheng2025realtime} por: workload s.d. & shift & perfect & & & (\checkmark), con el mismo símbolo de check que usa el resto de la tabla, y muévela entre Bozanta et al. (2022) y Quintero Rojas (2020). (2) En el pie borra el \todo y añade la frase de P5. (3) Arregla las etiquetas verticales de grupo: usa \multirow{n}{*}{\rotatebox{90}{\parbox{...}{\centering ...}}} con el n correcto de filas de cada grupo, o reemplázalas por filas de encabezado horizontales en cursiva ("\textit{MDRP operations}", "\textit{Fairness and pay}", "\textit{Behaviour}") como en la Tabla 2. Prefiero las filas horizontales si las verticales no caben. Muéstrame la página 5 renderizada (pdftoppm) antes y después.
```

## P6. §2: frases nuevas sobre Cheng y Sharif Azadeh

**Cambio 1.** Párrafo "Courier behaviour has been modelled mainly as availability", al final, después de "(Archetti et al. 2016, Dayarian and Savelsbergh 2020, Ulmer and Savelsbergh 2020)."

Hoy dice: "[TODO: One sentence on what TODO authors (2025) (arXiv:2501.05808) actually does, after reading it.]"

Debe decir:
> Cheng and Sharif Azadeh (2025) train double deep Q-networks for order dispatching and idle-courier steering with predicted short-term demand in the state, with hourly-paid couriers who follow every instruction, and report workload balance among couriers (standard deviation of orders, delivery time and distance) as an ex-post outcome rather than a constraint; no earnings history enters their state, so the end-of-day distribution of earnings is neither a decision input nor a guarantee.

**Cambio 2.** Mismo párrafo, frase de aprendizaje por refuerzo.

Hoy dice: "Reinforcement-learning approaches (Ahamed et al. 2021, Bozanta et al. 2022) include courier availability in the state but keep acceptance exogenous"

Debe decir: "Reinforcement-learning approaches (Ahamed et al. 2021, Bozanta et al. 2022, Cheng and Sharif Azadeh 2025) include courier availability in the state but keep acceptance exogenous"

**Cambio 3.** Párrafo "Fairness has entered delivery and ride-hailing platforms mostly as balance". Ahí está `jozefowiez2009evolutionary`, que está en el .bib pero no se cita en ningún lugar.

Hoy dice: "Wen et al. (2010) balance workload and income opportunities within a multi-period routing model"

Debe decir: "Workload balance has a long tradition in vehicle routing (Jozefowiez et al. 2009); Wen et al. (2010) balance workload and income opportunities within a multi-period routing model"

**Cambio 4.** Mismo párrafo. Hoy dice: "fairness is enforced per window or per instance, or amortised over the day through an objective or a reward term rather than constrained at its end". La fila provisional de Cheng era la única que hablaba de "reward term", y el artículo real no tiene término de equidad en la recompensa.

Debe decir (salvo que otro trabajo citado use un término de recompensa para la equidad): "fairness is enforced per window or per instance, amortised over the day through an objective, or evaluated only ex post, rather than constrained at its end"

```
Aplica P6 de prompts_correccion_main_v53.md en §2 (Related work) de main.tex: los cambios 1 a 4, con el texto exacto del documento y \citet/\citep como el resto del párrafo (cheng2025realtime, jozefowiez2009evolutionary). Para el cambio 4, antes de editar revisa si alguno de los trabajos citados en ese párrafo (wen2010dynamic, liao2020multi, lesmana2019balancing, gupta2022fairfoody, nair2022work4food, martinez2024exploring, sobhanan2024equity) usa un término de recompensa o de objetivo para la equidad según lo que dice el propio §2, y dime cuáles; si ninguno usa "reward", aplica el texto nuevo. Confirma que no queda ningún \todo en §2.
```

## P7. Apéndice A: introducción, A.1, A.2 y A.3

**Introducción del Apéndice A.** Hoy termina con "[TODO: Move the fuller review of the thesis here (operational, economic and behavioural blocks), one subsection each, closing with the gap; switch citations to citeAppx (multibib…)…]". El cambio de citas depende de P38 (límite de páginas); aquí se borra el marcador.

**A.1 (Operational block).** Se reemplaza "[TODO: expand.]" por:
> Soeffker et al. (2022) and Hildebrandt et al. (2023) review the stochastic dynamic vehicle routing problems to which these models belong, and Ulmer et al. (2020) their modelling as sequential decision processes. The gap in this block is therefore the courier: the models optimise coverage, punctuality or cost with couriers as vehicles, and none of them carries what each courier has earned in the state.

**A.2 (Economic block).** Se reemplaza "[TODO: expand.]" por:
> Inequity-averse optimisation gives the Gini constraint its operational-research lineage (Ogryczak 2000, Karsu and Morton 2015), and in ride-hailing Sühr et al. (2019) and Xu and Xu (2020) balance driver income over repeated matchings under perfect acceptance. The gap in this block is therefore the horizon and the lever: fairness is balanced per window or per instance, pay is a given tariff, and no model constrains the end-of-day distribution of earnings while pay is a decision to which acceptance responds.

**A.3 (Behavioural block).** Hoy dice: "…reinforcement-learning approaches (Ahamed et al. 2021, Bozanta et al. 2022) include availability in the state but keep acceptance exogenous; … (Corbett-Davies et al. 2023). [TODO: expand; add TODO authors (2025).]"

Cambio 1: "(Ahamed et al. 2021, Bozanta et al. 2022)" pasa a ser "(Ahamed et al. 2021, Bozanta et al. 2022, Cheng and Sharif Azadeh 2025)".

Cambio 2: se reemplaza el marcador por:
> Cheng and Sharif Azadeh (2025) dispatch and steer idle couriers with deep reinforcement learning on synthetic orders generated from real transactions: couriers are hourly-paid and obey every instruction, pay is not a decision, the state carries no earnings, and workload balance (standard deviation of orders, delivery time and distance over a two-hour shift) is evaluated ex post. The empirical literature on gig work shows that pay shapes the supply of self-scheduling workers (Cachon et al. 2017, Allon et al. 2023), and crowdsourced-delivery models treat participation and compensation as decisions (Archetti et al. 2016, Dayarian and Savelsbergh 2020, Ulmer and Savelsbergh 2020). In none of these works does the acceptance of an individual offer respond to the pay the platform decides, which is the gap this paper addresses.

```
Aplica P7 de prompts_correccion_main_v53.md en el Apéndice A de main.tex (secciones Detailed literature review, Operational block, Economic block, Behavioural block). Borra el \todo de la introducción del apéndice; en A.1, A.2 y A.3 reemplaza cada "[TODO: expand...]" por el texto exacto del documento, con \citet/\citep y estas claves: SOEFFKER2022801, hildebrandt2022opportunities, ulmer2020modeling, ogryczak2000inequality, karsu2015inequity, suhr2019twosided, xu2020trade, cheng2025realtime, cachon2017surge, allon2023gig, archetti2016occasional, dayarian2020crowdshipping, ulmer2020workforce. En A.3 añade cheng2025realtime a la cita de los enfoques de aprendizaje por refuerzo. Confirma que ninguna clave queda sin resolver y que no hay \todo en el Apéndice A.
```

## P8. Opcional (recomendado): dos filas más en la Tabla 1

§2 ya dice que Sühr et al. (2019) y Xu y Xu (2020) "balance driver income over repeated matchings, again under perfect acceptance". Son los trabajos más cercanos en la idea de equidad de ingresos acumulada y no están en la Tabla 1. Un revisor de EJOR lo notará.

```
DECISIÓN MÍA antes de ejecutar: dime si agrego las filas. Si digo que sí: lee los artículos suhr2019twosided y xu2020trade (fuente primaria, no de memoria) y propón para cada uno las celdas de la Tabla 1: Fairness metric (p. ej. "income (amortised)" o "income Gini"), Guarantee horizon, Acceptance ("perfect", como dice §2), Pay decided, History in state, Real data. Para cada celda dime de qué página del artículo sale. Ponlas en el grupo "Fairness and pay" después de Lesmana et al. (2019). No pongas ninguna celda que no hayas verificado.
```

## P9. Bibliografía: entradas incompletas o con errores

| Clave | Problema | Corrección |
|---|---|---|
| `giraldo2026brkga` | autores y título con TODO | `author = {Giraldo-Herrera, Daniel and {\'A}lvarez-Mart{\'i}nez, David}`, `title = {A Biased Random-Key Genetic Algorithm with Rolling Horizon for the Meal Delivery Routing Problem}`, `booktitle = {Metaheuristics International Conference (MIC 2026)}`, `note = {To appear}` (cambia `@misc` por `@inproceedings`) |
| `giraldo2024grasp` | coautor "Álvarez, David" | `{\'A}lvarez-Mart{\'i}nez, David`; `booktitle = {Metaheuristics. MIC 2024}`, `series = {Lecture Notes in Computer Science}`, `volume = {14754}` |
| `sobhanan2024equity` | nombre del primer autor equivocado ("Anoop"); figura como preprint de SSRN | el autor es **Abhay** Sobhanan. Aparece publicado en *Production and Operations Management* (DOI 10.1177/10591478261425875, 2026); verifica volumen y páginas. Si no puedes verificarlo, usa el preprint de Optimization Online (2024, https://optimization-online.org/?p=27199) |
| `bi2023meal` | sin volumen | `volume = {18}`, `number = {4}`, artículo 91 en MDPI JTAER (verifica páginas y DOI) |
| `hildebrandt2022opportunities` | sin volumen | `volume = {150}` (registro de dblp; verifica) |
| `stein2024learning` | sin volumen | `volume = {59}`, `number = {5}`, `pages = {1153--1171}` |
| `reyes2018meal` | sin URL | `url = {https://optimization-online.org/?p=15139}` |
| `defra2023factors` | sin URL | URL oficial de "Greenhouse gas reporting: conversion factors 2023" en gov.uk (verifica) |
| `defra2024factors` | no se cita | bórrala |
| `colombia2021smmlv` | no se cita | se cita en P27 (fuente del salario mínimo) |
| `jozefowiez2009evolutionary` | no se citaba | se cita en P6 |
| Bloque "added after the referee-style review" | el comentario dice "Volumes and pages entered from memory" | verifica Karsu y Morton 2015, Ogryczak 2000, Sühr 2019, Xu y Xu 2020, Cachon 2017, Allon 2023, Ulmer y Savelsbergh 2020, Archetti 2016, Dayarian y Savelsbergh 2020 y Borkar 2005 contra la editorial y borra el comentario |
| Comentario inicial del .bib | habla de "source: thesis", "source: plan" y "TODO notes" | bórralo o déjalo neutro |

```
Aplica P9 de prompts_correccion_main_v53.md en references.bib. Para cada fila de la tabla: (1) haz el cambio; (2) si la tabla dice "verifica", búscalo en la página de la editorial, en DOI.org o en dblp y dime la URL de donde lo sacaste; si no puedes confirmarlo, deja el campo sin poner y avísame (nunca lo completes de memoria). Para sobhanan2024equity cambia la clave solo si el año cambia a 2026, y entonces actualiza la clave en main.tex. Borra defra2024factors. Al terminar, corre un script que compare las claves citadas en main.tex con las del .bib y dime: claves citadas sin entrada (debe ser 0) y entradas no citadas (debe ser 0 cuando termine P27). Recompila y muéstrame la lista de referencias renderizada.
```

## P10. Citas de los trabajos propios en el texto

**Dónde:** §2 (párrafo metodológico) y §4.2 ("Coverage BRKGA and decoder").

**Hoy dice:** "ported from our earlier work on the MDRP (Giraldo-Herrera and TODO co-authors 2026, Giraldo-Herrera and Álvarez 2024)" y "(Giraldo-Herrera and TODO co-authors 2026)"

**Después de P9 dirá automáticamente:** "Giraldo-Herrera and Álvarez-Martínez 2026, 2024"

```
Después de P9, recompila y verifica en el PDF que las dos citas de §2 y §4.2 salen como "Giraldo-Herrera and Álvarez-Martínez (2026)" y "(Giraldo-Herrera and Álvarez-Martínez 2024, 2026)" sin la palabra TODO. Si natbib las agrupa de forma rara, usa \citep{giraldo2024grasp,giraldo2026brkga}. En §4.2, cambia "is ported from our earlier work on the MDRP" por "is ported from our earlier work on the MDRP, where it was evaluated against the platform's dispatching rule on the same instances"; antes de aplicarlo, confirma en BRKGA_model/nuevo_articulo/ que el artículo MIC 2026 usa instancias de la misma plataforma.
```

## P11. Volumen de la literatura en el cuerpo

Después de P6 el cuerpo crece unas cinco líneas. Si eso empuja la bibliografía más allá de la página 35, ver P38.

---

# FASE 3. Cifras que no cuadran con las tablas (sobre los valores recalculados)

Los valores de referencia de esta fase son los de la versión de 24 instancias. Después de P3 cambian, pero el error de fondo es el mismo: la frase del texto y la tabla no dicen lo mismo.

## P12. Cumplimiento a α = 0.50 (§6.1)

**Hoy dice:** "at 0.50 the proposed policies reach 35–50%"

**Problema:** la Tabla C.15 da 37–46% (manual) y 45–46% (autoaceptar) para BRKGA-Fair, MIP-Fair y Pay-BRKGA de primera generación.

**Debe decir:** "at 0.50 the proposed policies reach 37–46%" (con el rango recalculado).

```
Aplica P12: en §6.1, párrafo que empieza "Table C.15 in Appendix C.6 reports the compliance", recalcula desde la Tabla C.15 regenerada el rango de cumplimiento a α = 0.50 de las tres políticas propuestas de primera generación en ambos regímenes y reemplaza "35–50%". Comprueba también las demás cifras del párrafo contra la tabla: Greedy a 0.30/0.35/0.40, "more than 4%", ILP a 0.45, segunda generación a 0.30, 0.40, 0.45 y 0.50. En §7 haz lo mismo con "62–67%" y "98% of the days".
```

## P13. Cobertura y CPU de la segunda generación (§6.1)

**Hoy dice:** "coverage changes by −0.001 to +0.003 with respect to the parent" y "MIP-Fair with k_d = 25 costs 11–24 minutes on average … five times its parent"

**Problema:** la Tabla C.10 da +0.005 y +0.006 para MIP-Fair con k_d = 8 en el régimen manual, así que el rango llega a +0.006 (y el Apéndice C.3 ya dice "within 0.006"). "Five times" vale en manual (23.5 / 4.6) pero no en autoaceptar (11.1 / 3.2 = 3.5).

**Debe decir:** "coverage changes by −0.001 to +0.006" y "3.5 to 5 times its parent" (recalculado).

```
Aplica P13 en §6.1, párrafo "Second-generation variants": recalcula desde la Tabla C.10 el rango de Δcobertura de todas las variantes respecto a su padre y reemplaza "−0.001 to +0.003"; recalcula desde la Tabla C.9 el cociente de CPU de MIP-Fair k_d = 25 sobre su padre en cada régimen y reemplaza "five times its parent". Revisa que el Apéndice C.3 ("within 0.006") quede igual que §6.1.
```

## P14. Variante de holgura ε (Apéndice C.7)

**Hoy dice:** "The slack ε ∈ {0.02, 0.05} leaves F_Gini and coverage within 0.001 of the base, with as many pairs worse as better"

**Problema:** en la Tabla C.17, la fila ε = 0.02 tiene 26 peores y 39 mejores (solo la de 0.05 está equilibrada: 27 / 24).

**Debe decir:** "The slack ε ∈ {0.02, 0.05} leaves F_Gini and coverage within 0.001 of the base, with no systematic effect: the 95% intervals include zero"

```
Aplica P14 en el Apéndice C.7, párrafo "Coverage slack": reemplaza la frase por la del documento después de comprobar en la Tabla C.17 regenerada que ambos intervalos incluyen el cero. Si alguno ya no lo incluye con 23 instancias, dímelo antes de escribir.
```

## P15. Cifras del texto que ninguna tabla respalda

Cada una necesita una tabla o columna nueva, o se quita del texto:

| # | Dónde | Cifra del texto | Arreglo |
|---|---|---|---|
| 1 | §6.4 "Supply, the benchmark's priority…" | "meets α = 0.30 on 83–92% of the days" (flota reducida) | columna "F_Gini ≤ 0.30 (% of days)" en la Tabla C.12, completa y a un tercio |
| 2 | §6.4 "Behavioural threshold" | "compliance … with α = 0.45 falls from 61–62% to 50–52% at the upper end" | columna de cumplimiento a α = 0.45 por θ en la Tabla C.18 (o tabla nueva en C.8) |
| 3 | §6.4 "Behavioural threshold" | "Greedy … falls from fourth to last at the upper end, where Pay-BRKGA overtakes it" | tabla de cobertura absoluta por θ en C.8, o quitar la frase del ranking |
| 4 | Apéndice C.7 "k_d = 50" | "55% and 73% of the days meet α = 0.40" | filas k_d = 50 de BRKGA-Fair y MIP-Fair en la Tabla C.15 |
| 5 | Apéndice C.2 | segunda generación por ciudad: "0.37–0.38 … 0.45–0.47 … 0.49–0.55" | bloque "Second generation (k_d = 25, five seeds)" en la Tabla C.8 |
| 6 | §6.3 | media 801 / 708–796 / 689; mediana 685, 547–621; rango intercuartílico 519–876; Q1 0–205; Q3 1,066–1,206; COP/km 929 / 816 y 789 / 669; "idle 19–25%" | tabla nueva en el Apéndice C.6: política × (media, mediana, Q1, Q3, % ociosos, mediana de COP/km recibido), de la misma semilla de la Figura C.6 |

```
Aplica P15 de prompts_correccion_main_v53.md. Para cada una de las seis filas: (1) escribe o amplía el script que genera la tabla indicada (tables_paper.py u otro) para que produzca la columna o la tabla nueva desde los CSV filtrados sin la instancia 3; (2) insértala en main.tex con su \label y su pie, con el mismo formato que las tablas vecinas; (3) cambia la cifra del texto por la de la tabla y añade la referencia (Table~\ref{...}). Si para alguna fila no hay datos en los CSV (por ejemplo, COP/km por corrida), DETENTE en esa fila y dime qué falta; no la completes de otra fuente. Para la fila 3, si la tabla muestra que el ranking no cambia como dice el texto, reescribe la frase con lo que muestre la tabla.
```

## P16. Dos juegos de cuartiles y de ociosos para la misma cosa

**Dónde:** §6.1 (Tabla C.16: Q1 = 481 para Greedy frente a 86–146; "between 21% and 31% … without a single delivery"); §6.3 (Figura C.6: rango intercuartílico 519–876, Q1 0–205, "19–25% idle"); el resumen ("a quarter").

**Problema:** son agregaciones distintas (media de 24 instancias frente a la semilla 1 con las instancias juntas) y el texto no lo avisa.

**Debe decir:** añadir en §6.3, después de "the share of couriers who end the day idle is printed under each violin":
> These quartiles are pooled over the couriers of all instances of seed 1 and are therefore not comparable with the per-instance means of Table C.16.

Al pie de la Figura C.6 se añade la misma aclaración. En el resumen, "it leaves a quarter of the eligible couriers idle" pasa a "it leaves between a fifth and a third of the eligible couriers idle", con el rango que dé la Tabla 2 recalculada.

```
Aplica P16: añade la frase del documento en §6.3 y al pie de la Figura C.6; recalcula desde la Tabla 2 regenerada el rango de 1 − "active eligible" de las seis políticas centradas en el pedido en ambos regímenes, úsalo en §6.1 ("between X% and Y%") y ajusta el resumen y §8 para que digan el mismo rango en palabras.
```

## P17. Afirmaciones que valen solo para una parte

| Dónde | Hoy dice | Problema | Debe decir |
|---|---|---|---|
| §6.4 "Acceptance regime" | "The regime moves the end-of-day Gini coefficient by at most 0.02" | vale para la primera generación; MIP-Fair k_d = 25 baja 0.435 → 0.401 (−0.034) | "by at most 0.02 for the first-generation policies and 0.03 for the second generation" |
| Apéndice C.2 | "79–86% active" (Bogotá y Medellín) | la Tabla C.8 da 79–87% (BRKGA-Fair en Bogotá 0.87) | rango recalculado |
| §1, viñeta del pago | "1.7 points less under manual acceptance" | no dice contra qué: es contra BRKGA (0.753 frente a 0.770); contra Greedy son 0.5 | "1.7 points less than the coverage BRKGA under manual acceptance" |
| Apéndice B.5 | "the deficit-aware prefilter of Section 6.1 obtains more than twice that reduction for the same order of CPU time" | vale para BRKGA-Fair (−0.097 con 2× CPU), no para MIP-Fair (−0.109 con 5×) | "the deficit-aware prefilter of Section 6.1 obtains more than twice that reduction in BRKGA-Fair at twice the CPU time of its parent" |
| §6.4 emisiones | "Greedy drives 30% more per delivered order" | son km (2.94 frente a 2.25–2.33 = 26–31%); en kg CO₂e son 12–31% | "Greedy drives 26–31% more kilometres per delivered order" (recalculado) |
| Apéndice C.8 emisiones | "2.25–2.33 for the six order-centric policies, 30% more" | ídem | "26–31% more" (recalculado) |
| §6.2 / pie de la Figura 2 | "computed every round" y "recomputed every ten minutes" | se contradicen | "recomputed every ten minutes" en ambos (o "every round" si el script calcula cada dos minutos: verifica en figures_paper.py) |

```
Aplica P17: para cada fila, recalcula la cifra desde la tabla regenerada y cambia el texto como dice la columna "Debe decir". Para la fila de la Figura 2, abre simulator/figures_paper.py, mira cada cuánto calcula la trayectoria y deja en §6.2 y en el pie lo que hace el código.
```

## P18. Figura C.3 frente a la Tabla C.6 (la misma zona)

**Dónde:** Figura C.3 (leyenda: 13,827 entregas, 2,651 conexiones, 924 tiendas), Tabla C.6 y §6.2 (instancia 0: 10,215 pedidos, 2,650 domiciliarios, 926 tiendas).

**Causa verificada en el código:** `simulator/figures_paper.py`, función `fig_f1`, usa un centro fijo `(4.679, -74.065)` y recorta a 3 km sobre los CSV crudos. El cargador `simulator/loader_real.py` (~línea 171) usa por defecto la mediana de las coordenadas de las tiendas. Centros distintos dan zonas distintas.

**Cambios en el texto:** §5.1 dice dos veces "store centroid" ("within 3 km of the instance's store centroid"; "Each day is projected on a plane centred on the store centroid"): se cambia por "median store location". El título interno de la figura dice "Instancia_0 (Bogota): the 3 km zone used in the experiments" y pasa a "Instance 0 (Bogotá): the 3-km zone used in the experiments".

```
Aplica P18: en simulator/figures_paper.py haz que fig_f1 construya la zona con la misma función y el mismo centro que usa loader_real.py (mediana de las tiendas) en lugar del centro fijo; cambia el título de la figura a "Instance 0 (Bogotá): the 3-km zone used in the experiments"; regenera la Figura C.3 y confirma que la leyenda da los mismos conteos que la fila 0 de la Tabla C.6 (10,215 / 2,650 / 926). En §5.1 cambia las dos apariciones de "store centroid" por "median store location". Si el cargador en realidad usa el centroide, dímelo y cambia la figura, no el texto.
```

---

# FASE 4. Portada, declaraciones, título y contribuciones

## P19. Portada

| Dónde | Hoy dice | Debe decir |
|---|---|---|
| `\ead` de Daniel | `d.giraldoh@uniandes.edu.co` | `ds.giraldoh@uniandes.edu.co` (confírmalo) |
| Comentario después de `\author` | "%% TODO: confirm Daniel's e-mail and who is the corresponding author…" | borrar |
| `\affiliation` | `organization={Universidad de Los Andes}` | `organization={Department of Industrial Engineering, Universidad de los Andes}` |

```
Aplica P19 en el frontmatter de main.tex: cambia el correo de Daniel a ds.giraldoh@uniandes.edu.co, borra el comentario TODO sobre el correo y el autor de correspondencia (Daniel sigue como corresponding author), y cambia la afiliación a "Department of Industrial Engineering, Universidad de los Andes" (con "los" en minúscula). Confirma que el nombre de David es "David Álvarez-Martínez" en la portada y en todas las referencias propias.
```

## P20. Disponibilidad de datos y código, y plataforma anónima (§5.1)

**Hoy dice:** "exported by a leading on-demand delivery platform operating in Colombia [TODO: confirm whether the platform may be named]" y "The simulator, the policies, the instance loader and the batch scripts are available at https://github.com/Danielgiraldosb/mdrp-simulator [TODO: confirm whether the instance data can be shared; otherwise state the access conditions]."

**Debe decir:**
> …exported by a leading on-demand delivery platform operating in Colombia, which is not named at its request.

> The simulator, the policies, the instance loader, the batch scripts and the 23 anonymised instances (folder `real_instancies`) are available at https://github.com/Danielgiraldosb/mdrp-simulator.

**Al final del artículo, antes de la bibliografía,** se añade la sección que pide Elsevier:
> **Data availability.** The 23 anonymised instances, the simulator and the scripts that produce every table and figure are available at https://github.com/Danielgiraldosb/mdrp-simulator.

```
Aplica P20: en §5.1 reemplaza los dos \todo con el texto del documento. Si la frase "which is not named at its request" no es exacta (por ejemplo, si la decisión de no nombrarla es de los autores), DECISIÓN MÍA: pregúntame si pongo "which is not named for confidentiality". Añade la sección "Data availability" antes de la bibliografía. Antes de terminar, comprueba en el repositorio que real_instancies/ tiene 24 carpetas y que la Instancia_3 queda documentada como duplicado en real_instancies/README.md (créalo si no existe, con una línea por instancia: ciudad, número de pedidos, número de domiciliarios, y la nota de que la 3 duplica la 1). Avísame si orders.csv contiene coordenadas de entrega con más de 4 decimales: DECISIÓN MÍA si se redondean antes de enviar.
```

## P21. Agradecimientos y financiación

**Hoy dice:** sección "Acknowledgment" con "[TODO: funding, the platform that provided the data, the couriers who answered the survey and the interviews.]"

**Debe decir:** se borra la sección "Acknowledgment". En su lugar va:
> **Funding.** This research did not receive any specific grant from funding agencies in the public, commercial, or not-for-profit sectors.

**Además (DECISIÓN MÍA, recomendado):** EJOR pide declarar el consentimiento cuando hay datos de personas. Se puede añadir en §3.1, después de "(44 semi-structured interviews in 2020–2021 and an intercept survey of 135 couriers in May–June 2021", la frase "conducted by the authors' university with informed consent and anonymised responses". Confirma que hubo consentimiento informado y qué comité lo avaló.

```
Aplica P21: borra la sección Acknowledgment con su \todo y añade la declaración de financiación del documento justo después de la sección Data availability de P20. No agradezcas a nadie. DECISIÓN MÍA: pregúntame si añado la frase de consentimiento informado en §3.1 antes de hacerlo.
```

## P22. c1 y c2 (Ec. 5)

**Hoy dice:** "the lexicographic reading coverage ≻ lateness used by all policies corresponds to c1 ≫ c2. [TODO: state the values of c1 and c2 if a scalar cost is reported.]"

**Debe decir:** "the lexicographic reading coverage ≻ lateness used by all policies corresponds to c1 ≫ c2, so no scalar cost is reported."

```
Aplica P22: en el párrafo "Cost function" de §3.2 borra el \todo y deja la frase del documento. Comprueba con grep que ninguna tabla ni figura reporta un costo escalar C; si alguna lo hace, dímelo.
```

## P23. Título y contribuciones con el encuadre de diagnóstico

**Problema:** el título ("Fair dispatching with price-responsive couriers: an end-of-day earnings guarantee for the meal delivery routing problem") y el párrafo de contribuciones de §1 siguen siendo los de cuando las políticas propuestas ganaban. Ahora el resultado dice tres cosas:
- el despacho centrado en el domiciliario (Greedy) supera a las tres políticas propuestas;
- la brecha casi desaparece con la flota al ratio de campo;
- la mitigación (exposición + k_d) cierra la mitad de la brecha.

**Opciones de título (DECISIÓN MÍA):**
1. "Who gets work: end-of-day earnings fairness in meal-delivery dispatching with price-responsive couriers"
2. "An end-of-day earnings guarantee for meal-delivery dispatching: population, history and supply"
3. "Fair dispatching with price-responsive couriers: why end-of-day earnings fairness depends on who is counted"

**Cambios en las contribuciones (§1, párrafo "The paper makes three contributions"):**
- **Primera (modelación):** se mantiene.
- **Segunda (metodológica):** se mantiene, con "small instance" en lugar de "toy instance" (P28).
- **Tercera (gerencial):** pasa a ser el diagnóstico. La garantía de fin de día depende de (i) la población sobre la que se mide, porque el estadístico sobre los activos invierte el ranking; (ii) la base de la historia, porque la exposición (ingreso por hora conectada) y el prefiltro k_d cierran cerca de la mitad de la brecha a costo nulo en cobertura; y (iii) la oferta, porque con la flota al ratio de campo la brecha cae a 0.03–0.04.
- **Frase final** ("To the best of our knowledge, this is the first MDRP formulation that combines…"): se mantiene.

Los verbos de §7 y §8 deben ser coherentes con esto: "diagnose", "narrow" y "close half of", no "achieve" ni "guarantee" aplicados a las políticas propuestas.

```
DECISIÓN MÍA: muéstrame las tres opciones de título del documento y espera mi elección. Luego reescribe el párrafo de contribuciones de §1 con la estructura del documento (cifras del libro de cifras ya recalculado, con 23 instancias), y revisa §7 y §8 frase por frase: lista cada frase que atribuya a BRKGA-Fair, MIP-Fair o Pay-BRKGA el cumplimiento de la garantía en general (no a un α o a un régimen concreto) y propón su corrección. Espera mi visto bueno antes de aplicar los cambios de §7 y §8.
```

---

# FASE 5. Notación y redacción

## P24. Ejemplo del Apéndice B.2: tiempo activo → tiempo conectado

**Hoy dice:** "Couriers A and B are connected from 12:00 to 13:00, so act_A(T) = act_B(T) = 60 minutes whatever is dispatched" y "the same active time" (dos veces).

**Problema:** la Ec. (1) y la Ec. (7) ya usan tiempo conectado (`conn_c(t)`); `act` ya no existe en la notación (Tabla B.4).

**Debe decir:** "so conn_A(T) = conn_B(T) = 60 minutes whatever is dispatched" y "the same connected time". Verifica la aritmética: w_A = 13,200; F_Gini = 0.5; w_B(s) = 3,474; w_A(s) = 13,895 COP/h.

```
Aplica P24 en el Apéndice B.2 (Illustrative numerical example): reemplaza act_A(T), act_B(T) por conn_A(T), conn_B(T) y "active time" por "connected time". Luego recalcula a mano, con un script corto, w_A, w_B y F_Gini al final del día, y w_A(s), w_B(s) con la Ec. (12) usando τ_base = conn_c(t) (base de exposición): con conn = 30 min a las 12:30 y τ_s = 8 min, w_B(s) = 2,200/(38/60) = 3,474 y w_A(s) = (6,600 + 2,200)/(38/60) = 13,895. Si coincide, déjalo; si no, dime qué cambia. Usa T o t_max de forma consistente con §3.2 (el texto usa t_max).
```

## P25. Choques de símbolos (Tabla B.4 y texto)

| Símbolo | Usos que chocan | Propuesta |
|---|---|---|
| `C` | conjunto de domiciliarios y función de costo C(S_t, x_t, z_t, ω_{t+1}) | costo = `\mathcal{C}` (Ecs. 5, 6, 8) |
| `T` | conjunto de puntos de decisión y función de transición | transición = `S^M(·)` (notación de Powell) |
| `K_t` y `K` | pares candidatos y domiciliarios que evalúa el decodificador | decodificador = `K^{\text{dec}}` |
| `w` en la Tabla C.7 | "BRKGA-Fair w ∈ {5, 10, 20, 40} min" | `γ ∈ {5, 10, 20, 40}` |
| `E` | emisiones E(x_t) y esperanza 𝔼 | emisiones = `\text{Em}(x_t)` |

```
DECISIÓN MÍA: muéstrame la tabla de P25 y espera mi aprobación de cada símbolo. Luego cambia cada símbolo en todas sus apariciones (ecuaciones, texto, Algoritmos 1 y 2, Tabla B.4, Tabla C.7), con macros nuevas en el preámbulo si hace falta, y dame la lista de líneas cambiadas.
```

## P26. Tres estadísticas con nombres parecidos, y la población de F_Deficit

**Problema 1:** hay tres estadísticas.
- F_Gini (Ec. 7): elegibles, con los ociosos en cero.
- "active only" (Tabla C.16): elegibles que entregaron.
- F_Gini^act: todos los que entregaron, incluidos los conectados menos de 1 h.

§8 dice "restricted to the couriers who delivered, the same policies appear more equitable than the corporate one", pero con "active only" Greedy sigue siendo el más equitativo (0.279 frente a 0.345–0.387). La frase solo vale para F_Gini^act.

**Debe decir (§8):** "restricted to all the couriers who delivered, including those connected for less than one hour (F_Gini^act), the same policies appear more equitable than the corporate one".

**Problema 2:** §3.2 define F_Deficit sobre los activos, y el pie de la Tabla 2 no dice sobre quién se calcula.

**Debe decir (pie de la Tabla 2 y de la C.9):** "F_Deficit is the share of active couriers below w\*."

```
Aplica P26: corrige la frase de §8 como dice el documento; en la Tabla C.16 cambia el encabezado "active only" por "eligible and active"; en los pies de las Tablas 2 y C.9 añade la frase sobre F_Deficit. Comprueba en el código (metrics.py) sobre qué población se calcula F_Deficit; si no es sobre los activos, dímelo y corrige §3.2 en lugar del pie.
```

## P27. Salario mínimo w\* (§5.1 y Tabla C.5)

**Hoy dice:** "w\* = 4,367.91 COP (2021 monthly minimum divided by 48 × 4.33 hours)" y en la Tabla C.5 "statutory 2021 / (48 h × 4.33)".

**Problema:** el salario mínimo de 2021 es 908,526 COP (Decreto 1785 de 2020). 908,526 / (48 × 4.33) = 908,526 / 207.84 = 4,371.3, no 4,367.91. El valor del artículo sale de dividir por 208 horas (48 × 52/12 = 48 × 4.333…). Además falta citar la fuente, y `colombia2021smmlv` está en el .bib sin citar.

**Debe decir (§5.1):** "The statutory minimum hourly wage is w\* = 4,367.91 COP: the 2021 monthly minimum of 908,526 COP (Gobierno de Colombia 2020) divided by 208 hours (48 hours a week × 52/12 weeks)."

**Tabla C.5, columna Source:** "Decreto 1785 de 2020: 908,526 / 208 h"

```
Aplica P27: primero confirma en simulator/config.py el valor de w* y cómo se calcula (debe ser 908526/208). Si es así, reemplaza el texto de §5.1 y la celda de la Tabla C.5 como dice el documento, citando colombia2021smmlv. Si el código usa 4.33, dímelo: entonces el valor correcto es 4,371.3 y habría que recalcular F_Deficit.
```

## P28. Redacción

| Dónde | Hoy dice | Debe decir |
|---|---|---|
| §1 contribuciones; §4.2 MIP-Fair; §4.2 Verification; Apéndice B.6 (4 veces) | "toy instance" | "small instance" |
| Algoritmo 1, línea 8; §3.2 ("Eqs. (8) - (10)"); §4.2 ("Eqs. (12) - (13)"); Apéndice B.4 ("(B.2) - (B.3)", "(B.4) - (B.5)") | guion con espacios | `Eqs.~\eqref{a}--\eqref{b}` |
| §5.1 | "Each day is projected on a plane centred on the store centroid" | ver P18 |
| Encabezados del apéndice | "Appendix  A.", "Appendix  C.1." (doble espacio, visible en la página 41 y en las referencias "Appendix  C.6" del texto) | un solo espacio |

```
Aplica P28: (1) reemplaza las cuatro apariciones de "toy instance" por "small instance" (grep -n "toy" main.tex debe dar 0); (2) reemplaza los cinco rangos de ecuaciones con " - " por "--" sin espacios; (3) el doble espacio en "Appendix  A" sale de cómo elsarticle o el preámbulo definen \thesection en el apéndice: busca la redefinición (grep -n "Appendix" main.tex en el preámbulo y en elsarticle) y corrígela para que salga "Appendix A." con un espacio, también en las referencias cruzadas del texto ("in Appendix C.6"). Muéstrame la página 36 y la 41 renderizadas.
```

## P29. "ablation" → "component analysis" / "variant"

**Dónde (32 apariciones de "ablat" en main.tex, contando las claves `\label`/`\ref`, que no se cambian):**
- §4.2 (cuatro veces: decodificador, base de ingresos totales, alcance libre-solo, equity-first) y "0.285 over the 27 runs of the ablation".
- §5.3 ("a supplement of eleven ablations", "18.7 in the ablations").
- §5.5 ("is an ablation" dos veces, "in the ablations of X3").
- §6.1 ("the ablation with k_d = 50").
- Apéndice B.5 ("the two tuning ablations").
- Apéndice C (introducción: "the ablations of X3").
- Título "Appendix C.7. Ablations", párrafos de C.7, encabezado "Ablation (base)" y pie de la Tabla C.17.

**Reglas:**
- Títulos → "component analysis": "Appendix C.7. Component analysis"; pie de la Tabla C.17 "Component analysis of the supplement of X3…".
- Frases → "variant": "is an ablation in Appendix C.7" → "is reported as a variant in Appendix C.7"; "a supplement of eleven ablations" → "a supplement of eleven variants"; "the ablation with k_d = 50" → "the k_d = 50 variant"; "Three ablations tighten…" → "Three variants tighten…"; encabezado "Ablation (base)" → "Variant (base)".
- No usar "sensitivity analysis" (es §6.4). No cambiar `\label` ni `\ref` (`sec:App_ablations`, `tab:ablations`) ni el código.

```
Aplica P29: lista con grep -n -i "ablat" main.tex todas las apariciones, propón el reemplazo de cada una siguiendo las reglas del documento, y espera mi visto bueno. Luego aplícalos. Reescribe a mano las frases que queden raras. Al final grep -n -i "ablat" main.tex solo debe devolver las claves \label/\ref. Recompila y confirma que no hay referencias rotas.
```

## P30. "Courier-centric" y "order-centric": definirlos

**Problema:** el resultado central descansa en estos dos términos, que se usan en §5.2, §6.1, §7 y §8 pero no se definen en §3 ni en §4.

**Debe añadirse al final de §4.1 (antes de "Content and population of the history"):**
> We call a dispatching rule *courier-centric* when each round visits the free couriers in a given order and lets each take its best feasible route, and *order-centric* when each round assigns the ready orders to the best-placed couriers under the constraints that each order is in at most one route and each courier receives at most one route (Eqs. (B.2)–(B.3)). The Greedy benchmark is courier-centric and visits the couriers least served first, which is a reading of one component of H_t (ord_c); the ILP, the Hierarchical policy, the BRKGA family and MIP-Fair are order-centric, whatever they read from H_t.

```
Aplica P30: inserta el párrafo del documento al final de §4.1, antes del párrafo "Content and population of the history", con las referencias \eqref a (B.2) y (B.3). Revisa que §5.2 (Greedy: "Courier-centric") y §6.1 ("Greedy is courier-centric … are order-centric") usen los términos igual que la definición, y que no se definan de nuevo con otras palabras.
```

---

# FASE 6. Tablas y figuras

## P31. Negritas "mejor valor por columna"

**Problema (verificado en el .tex):**
- **Tabla 2, régimen manual:** la mejor cobertura (0.770, BRKGA y BRKGA-Fair) no está en negrita, y el menor F_Deficit (0.981, Greedy y Hierarchical) tampoco. El pie dice "the best value per column and regime is in bold (higher for coverage…)".
- **Tabla C.9:** solo tienen negrita Greedy (Gini, activos, CPU) y F_Gini^act. Falta en cobertura (0.770 manual), latencia (18.6 manual, 18.2 auto) y F_Deficit (0.981 manual, 0.973 auto).
- **Tabla C.8:** dice "Best value per column and city in bold"; hay que revisarla igual.

```
Aplica P31: escribe simulator/check_bold.py, que lee las tablas regeneradas (o los CSV) de las Tablas 2, C.8 y C.9 y, por columna y por bloque (régimen o ciudad), marca el mejor valor con estas reglas: máximo en cobertura y "active eligible"; mínimo en F_Gini, F_Gini^act, latencia, F_Deficit y CPU; los empates van todos en negrita; la columna de pago no se marca (como dice el pie). Compara con las negritas del .tex y dime cada diferencia. Luego corrige las negritas en las tres tablas. Si en el régimen de autoaceptar la cobertura empata en todas las filas, no pongas negrita y añade al pie "(coverage ties across all policies under auto-accept)".
```

## P32. Ecuaciones del Apéndice B.4 (B.1–B.9)

**Problema (visto en la página 39):** las ecuaciones están en un `alignat{2}` donde la (B.7) es mucho más ancha que las demás. Por eso todo el bloque se desplaza a la derecha, los cuantificadores "∀o", "∀c", "∀i" se salen del margen, los números de ecuación quedan en líneas aparte y la (B.7) se sale por la izquierda.

```
Aplica P32: en el Apéndice B.4 (subsection "Per-round formulation of MIP-Fair") separa la (B.7) del alignat: deja (B.1)–(B.6), (B.8) y (B.9) en un align con los cuantificadores tras \quad, y escribe (B.7) en un multline o en un split de dos o tres líneas, con su propio \label{eqn:app_gini} para que las referencias no cambien. Quita el {\small ...} si ya no hace falta. Muéstrame la página renderizada: nada debe salirse del margen y cada ecuación debe tener su número en la misma línea.
```

## P33. Figura 1 y Figura C.5 (fronteras)

**Problema (visto en la página 26):**
- En el panel manual, la leyenda está encima de la zona donde está Greedy (x ≈ 0.30, cobertura 0.758) y lo tapa.
- La etiqueta del eje y aparece dos veces y se monta.
- Las etiquetas "25 (γ = 40)", "8" y "4020" se superponen a los puntos.
- La letra está por debajo de 8 pt al ancho de la página.

```
Aplica P33 en simulator/figures_paper.py (funciones de las Figuras 1 y C.5): saca la leyenda fuera de los ejes (debajo de los dos paneles, en dos o tres columnas), usa una sola etiqueta de eje y compartida (fig.supylabel), sustituye las etiquetas sueltas de los puntos por anotaciones con flecha solo en los extremos de cada barrido (γ = 5 y 40; α = 0.20 y 1.00; λ_pay = 0.1 y 1.0; k_d = 8 y 25), y fija la letra a 8 pt como mínimo con la figura al ancho de \textwidth. Asegúrate de que el punto de Greedy se vea en los dos paneles. Regenera y muéstrame las dos figuras.
```

## P34. Figura 2 (trayectoria del Gini en el día)

**Problema (visto en la página 27):**
- La letra es diminuta y los títulos de los paneles se cortan y se montan: "eligible couriers connected so far, idle at zero (Eq. of the paper)" y "active couriers so far (statistic read by the first-generation policies)".
- La leyenda dice "(Eq. of the paper)".
- Hierarchical y MIP-Fair tienen colores casi iguales.
- La línea punteada marca α = 0.40, mientras el artículo recomienda α\* = 0.45.

**Debe decir:**
- Título del panel izquierdo: "Eligible couriers, idle at zero (Eq. (7))".
- Título del panel derecho: "Couriers with at least one delivery".
- Línea punteada (DECISIÓN MÍA): α = 0.40 (el límite de la banda, como ahora) o las dos líneas, 0.40 y 0.45.

```
Aplica P34 en simulator/figures_paper.py (figura de la trayectoria intradía): títulos de panel como dice el documento, letra de 8 pt como mínimo, colores y estilos de línea distintos para las cuatro políticas (que se distingan en gris: sólida, discontinua, punteada, punto-raya), leyenda fuera de los ejes. DECISIÓN MÍA: pregúntame si dibujo solo α = 0.40 o también α = 0.45; actualiza el pie según lo que elija. Regenera y muéstrame la figura.
```

## P35. Figuras del apéndice (C.3, C.4, C.6, C.7, C.8)

| Figura | Problema | Arreglo |
|---|---|---|
| C.3 | título en español y conteos de otra zona | ver P18 |
| C.4 | la leyenda se monta sobre la curva y el intervalo; letra pequeña | leyenda abajo a la derecha o fuera de los ejes; 8 pt |
| C.6 | las anotaciones "idle x%" no se leen | ponerlas como segunda línea de la etiqueta del eje x ("Greedy\nidle 3%") |
| C.7 | la etiqueta de Pay-BRKGA (λ_pay = 0.5) se monta sobre el eje | ajustar márgenes (`tight_layout` o `subplots_adjust(left=…)`) |
| C.8 | la leyenda tapa la barra de Pereira y corta "BRKGA-Fair" | leyenda fuera del panel izquierdo; nombres de ciudad con tilde (Bogotá, Medellín) |

Además, cada política debe tener el mismo color en todas las figuras.

```
Aplica P35 en simulator/figures_paper.py para las Figuras C.4, C.6, C.7 y C.8 según la tabla del documento. Define al principio del script un diccionario único POLICY_STYLE (color, marcador, línea) y úsalo en todas las figuras del artículo, incluidas las Figuras 1, 2 y C.5. Regenera todas y muéstramelas.
```

## P36. Numeración del apéndice y tablas anchas

**Problema:** el contador del apéndice continúa el del cuerpo (Tabla B.4, Tabla C.5, Figura C.3…). Las Tablas C.8, C.9, C.10, C.15 y C.17 tienen la letra muy pequeña por `adjustbox{max width}`.

```
Aplica P36: (1) en el preámbulo, después de \appendix, reinicia los contadores de tablas, figuras y ecuaciones por sección del apéndice (\counterwithin{table}{section} y equivalentes, o lo que use elsarticle) para que salgan Tabla A.1, B.1, C.1… y comprueba que todas las referencias cruzadas siguen funcionando; dame la correspondencia vieja → nueva de cada tabla y figura del apéndice y actualiza las menciones explícitas en el texto si las hay. (2) Para las Tablas C.8, C.9, C.10, C.15 y C.17: si la letra efectiva queda por debajo de 7 pt, ponlas en landscape (pdflscape) o divídelas en dos (por régimen o por bloque). Muéstrame las páginas antes y después.
```

---

# FASE 7. Verificación final

## P37. Riesgos de árbitro que el texto aún no cubre

**Problema 1:** el 1.2 pedidos por domiciliario-hora sale de 2,622 / 2,200, y la flota reducida a un tercio descansa en ese número. Hay que escribir la cuenta en §5.1 y decir a quiénes corresponde la mediana: ¿incluye a quienes no hicieron entregas?

**Problema 2:** la población elegible (≥ 1 h conectado, ociosos en cero) puede leerse como elegida a posteriori. Una sensibilidad con umbrales de 0.5 h, 1 h y 2 h la protege, y no necesita corridas nuevas: se recalcula desde los `*_couriers.csv`.

```
Aplica P37: (1) en §5.1, después de "against about 1.2 implied by the survey median of 2,622 COP/h at the flat tariff", añade "(2,622 / 2,200 = 1.19 orders per connected hour, among respondents who reported hourly earnings)" después de confirmar en los archivos de la encuesta del repositorio (docs/ o Tesis/) a qué población corresponde la mediana; si no lo encuentras, dímelo. (2) Con main_couriers.csv (sin la instancia 3) recalcula F_Gini de la Ec. (7) con umbrales de elegibilidad de 0.5 h, 1 h y 2 h para las siete políticas de la Tabla 2 en ambos regímenes; si el ranking Greedy < resto se mantiene, añade una tabla corta al Apéndice C.6 y una frase en §6.1 ("The ranking is the same with eligibility thresholds of 0.5 and 2 hours (Table C.x)"). Si no se mantiene, DETENTE y muéstrame los números.
```

## P38. Límite de páginas y lista de referencias del apéndice

**Contexto:** `estilo-ejor.md` y el preámbulo dicen que el cuerpo y su bibliografía no deben pasar de 35 páginas, y que tu director usa `multibib` con `ReferencesAppx.bib` para que las referencias del apéndice no cuenten. Hoy el cuerpo termina en la página 33 y la bibliografía en la 35. Después de P6 y P23 puede pasarse.

```
Aplica P38: recompila y dime en qué página termina la bibliografía. Si pasa de 35: (1) activa multibib como dice el comentario del preámbulo (\usepackage{multibib}, \newcites{Appx}{Appendix references}), cambia las citas del Apéndice A que no aparecen en el cuerpo a \citeAppx y crea ReferencesAppx.bib con esas entradas; (2) si aún se pasa, propón qué párrafos de §6 o §7 se pueden mover al apéndice, sin moverlos. Confirma también el límite en la guía oficial de autores de EJOR (elsevier.com) y dime si es de 35 páginas o si es una convención de tu director.
```

## P39. Revisión final

```
Haz la verificación final del artículo:
1. grep -n '\\todo' main.tex no devuelve nada; grep -n -i "TODO" main.tex solo devuelve comentarios del preámbulo que no salen en el PDF; grep -n -i "ablat\|toy instance\|Los Andes\|store centroid\|rl2025fairdelivery" main.tex no devuelve nada salvo las claves \label/\ref.
2. Corre simulator/check_ledger.py: ninguna cifra "difiere".
3. Corre simulator/check_bold.py: ninguna diferencia.
4. Cada cifra del resumen, de las viñetas de §1 y de §8 aparece en una tabla o figura: dame la lista cifra → tabla.
5. El número 24 ya no aparece referido a instancias o días; Bucaramanga tiene 4 días en §5.1 y en la Tabla C.6.
6. Todas las claves citadas tienen entrada en references.bib y todas las entradas se citan.
7. El PDF compila sin "undefined reference", "??", "Citation undefined" ni "Overfull \hbox" mayores de 10 pt; dime cuántas páginas tiene y en cuál termina la bibliografía del cuerpo.
8. Actúa como revisor de EJOR y dame las cinco objeciones más probables al resultado de que Greedy supera a las tres políticas propuestas, con la evidencia del artículo que tiene o le falta cada una. No cambies nada en este punto: solo el informe.
```

---

## Resumen de qué corrige cada prompt

| Prompt | Qué corrige | Necesita decisión tuya |
|---|---|---|
| P0 | libro de cifras | no |
| P1–P3 | instancia 3 duplicada; 23 instancias; todas las cifras recalculadas | visto bueno de las listas |
| P4–P7 | Cheng y Sharif Azadeh: bibliografía, Tabla 1, §2, Apéndice A; Jozefowiez citado; frase "reward term" | no |
| P8 | filas de Sühr y de Xu y Xu en la Tabla 1 | sí (opcional) |
| P9–P10 | bibliografía incompleta o errónea (MIC 2026, Sobhanan, Bi, Hildebrandt, Stein, Reyes, DEFRA, GRASP) | no |
| P12–P18 | cifras del texto que no cuadran con las tablas o que no tienen tabla; Figura C.3 | no |
| P19–P22 | portada, datos, plataforma, financiación, c1/c2 | P20 (redacción), P21 (consentimiento) |
| P23 | título y contribuciones con el encuadre de diagnóstico | sí (título) |
| P24–P30 | notación, w\*, redacción, "ablation", definición de centrado en el domiciliario y en el pedido | P25 (símbolos) |
| P31–P36 | negritas, ecuaciones B.4, Figuras 1, 2 y del apéndice, numeración, tablas anchas | P34 (línea α) |
| P37–P39 | riesgos de árbitro, límite de páginas, verificación final | no |
