# Guía de estilo EJOR extraída de los dos manuscritos del director

Fuentes: `papers/Dani_Calling_New__unmarked_/main.tex` (Cuellar-Usaquén, Ulmer, Hildebrandt, Gomez,
Álvarez-Martínez, *Sequential supplier selection in grocery collection operations*, EJOR, publicado) y
`papers/Dynamic_Purchasing_vol_1___EJOR/revision2.tex` (*Adaptive stochastic lookahead policies for dynamic
multi-period purchasing and inventory routing*, EJOR 318(3), 2024, tras dos rondas), más `response.tex` y
`response2.tex` (respuestas a los tres árbitros). Fecha: 2026-10-20. Todo lo que sigue se aplica en
`main.tex`; `main_v0.tex` es el borrador anterior.

## 1. Esqueleto y títulos de sección

Los dos manuscritos usan exactamente la misma secuencia; los títulos son cortos y genéricos (no "Problem
setting and behavioural evidence" sino "Problem definition"):

| # | Título | Subsecciones típicas | Extensión aprox. |
|---|---|---|---|
| 1 | Introduction | sin subsecciones | 8–10 párrafos (1,5–2 págs. a 1,5 espacios) |
| 2 | Related work | párrafos con `\paragraph{}` o 2–3 subsecciones; tabla de clasificación en el cuerpo | 1,5–2 págs.; la revisión larga va al apéndice |
| 3 | Problem definition | 3.1 Problem description; 3.2 Sequential decision process (decision point and state / decisions / cost function / exogenous information and transition / objective); 3.3 Example (o ejemplo en apéndice) | 3–4 págs. |
| 4 | Method | 4.1 Motivation and overview (+ Algorithm 1); 4.2 Detailed description (un `\paragraph{}` por componente) | 3–5 págs. |
| 5 | Experimental setting | 5.1 Instances; 5.2 Benchmark policies; 5.3 Implementation details | 2 págs. |
| 6 | Computational study | 6.1 Objective values / Solution quality; 6.2–6.3 análisis en profundidad del mecanismo propio; 6.4 Decision making; 6.5 Sensitivity analysis across operational settings | 5–7 págs. |
| 7 | Findings and Discussion (solo en el paper publicado) | responde una a una las preguntas de investigación | 1 pág. |
| 8 | Conclusion | contribución, generalización, limitaciones, trabajo futuro | 1 pág. |
| – | Acknowledgment; bibliografía; `\appendix` con A Detailed literature review, B Illustrative example and algorithmic details, C Additional results | |

Observaciones: no hay sección "Limitations" separada (las limitaciones van en dos párrafos de la
conclusión); no hay "Discussion" separada en el paper de 2024 (los *insights* se resumen en la introducción
porque un árbitro pidió "a clear high-level synthesis"); el ejemplo numérico es obligatorio (lo pidieron
los árbitros en los dos papers) y el tercer paper lo mueve al apéndice y lo cita desde la formulación.

## 2. Resumen y palabras clave

- Un párrafo, 180–230 palabras, sin cifras en el de 2024 y con dos cifras en el publicado: "reducing the
  average gap by $6.5-13.6$ percentage points relative to rule-based benchmarks and by $10.9$ percentage
  points relative to the uncorrected lookahead". Un árbitro pidió explícitamente "key quantitative results"
  en el resumen (R3-Q12), así que hay que dejar hueco para dos cifras.
- Orden fijo: clase de problema → aplicación focal (una frase) → decisiones → método con nombre propio
  ("We develop the Stochastic Look-Ahead with Penalized Perfect Information policy (SLAPPI)") → datos
  reales ("Using real procurement data from the Colombian agricultural sector") → resultado principal →
  cuándo es mayor la ganancia.
- `\begin{keyword}` con 4–5 términos separados por `\sep`, el primero siempre "Routing".
- Sin *highlights* (comentados en ambos).

## 3. Cómo se motiva el problema

- Primer párrafo de la introducción: la clase general del problema con dos citas clásicas y una moderna
  ("Resource allocation problems arise when ... \citep{Mazzola1986,Dantzig1959}"; "In recent years, there
  has been a growing demand for fresh, locally sourced ... \citep{fukase2020economic}").
- Tercer párrafo: tres o cuatro contextos operativos donde aparece la misma estructura, con cita cada uno,
  y "Another example, and the focus of this work, is ...".
- Colombia entra como origen de los datos y de la colaboración, no como argumento: "based on an ongoing
  collaboration with agri-food e-commerce platforms in Colombia"; "Using data from an e-commerce platform".
  Las cifras de contexto industrial son pocas; el peso de la motivación es metodológico.
- Siempre un párrafo "Methodologically, these problems are challenging because ..." que enumera las
  dependencias entre decisiones, y luego un párrafo que presenta el método con su nombre y su acrónimo.
- Preguntas de investigación: tres, numeradas en prosa ("First, what is the value of ...? Second, does ...?
  Third, under which operational conditions ...?") y retomadas una a una en "Findings and Discussion".
- Contribuciones: exactamente tres, en un párrafo, etiquetadas "as a theoretical and modeling contribution",
  "as a methodological contribution", "as a managerial contribution". El paper de 2024 añade antes una
  lista `compactitem` de 6–7 *insights* de los resultados (respuesta a R3-Q44).
- Último párrafo: "The remainder of this paper is organized as follows. Section~\ref{} ...".

## 4. Cómo se presenta el modelo

- Primero prosa ("Problem description"): quién decide, qué se revela y cuándo, qué se asume, y cada
  supuesto con su justificación práctica en la misma frase ("Based on discussions with the company, we
  assume that the calling process is limited to one hour"; "We assume that split collection is not
  allowed. Thus, each supplier can only be visited by one vehicle"). Sin lista numerada de supuestos.
- Luego "Sequential decision process" con la plantilla de Powell: "we model the problem as a sequential
  decision process \citep{powell2021reinforcement}. In the following, we define its components: decision
  point, state, decision, cost function, exogenous information, and the transition to a new state."
- Notación: estado $S_t$, decisión $x_t \in \mathcal{X}(S_t)$ (o $a_t$ en 2024), información exógena
  $\omega_{t+1}$, transición $\mathcal{T}(S_t, x_t, \omega_{t+1})$, costo $\mathcal{C}(S_t, x_t)$, política
  $\pi \in \Pi$, $\mathcal{X}^\pi_t(S_t)$, óptimo
  $\pi^* = \arg\min_{\pi\in\Pi} \mathbb{E}[\sum_t \mathcal{C}(S_t, \mathcal{X}^\pi_t(S_t)) \mid S_0]$.
  Vectores en negrita ($\mathbf{c}_t$, $\mathbf{p}_t$), conjuntos en mayúscula ($M$, $K$, $T$), grafos
  caligráficos ($\mathcal{G}=(\mathcal{V},\mathcal{A})$).
- Los componentes del estado y las actualizaciones de la transición van en `compactitem` (paquete
  `paralist`), una viñeta por componente, terminadas en coma y la última en "and ...".
- Todas las ecuaciones numeradas (`equation`, `alignat` con `\label`), referidas como "Eq.~\eqref{}" y
  rangos "Eqs.~\eqref{} - \eqref{}". Tras un bloque de restricciones, un párrafo que explica cada
  ecuación en orden ("Eq.~\eqref{eqn:demand} ensures that ... Finally, Eqs.~\eqref{} - \eqref{} define the
  domain of the variables").
- Sin proposiciones ni teoremas en el cuerpo (define `\newtheorem{insight}{Insight}` con una caja
  `tcolorbox`, pero no la usa). Los casos particulares se enuncian en prosa.
- El modelo matemático completo del subproblema (MIP) va al apéndice; el cuerpo solo da la idea y la
  referencia.
- Cierre de la sección con un puente al método (pedido por R3-Q26): "Even in this small example ..., the
  challenges in decision making become evident, underscoring the need for an integrated solution approach".

## 5. Cómo se describen los algoritmos

- "Motivation and overview" explica primero por qué es difícil (dos retos en viñetas: **Search** y
  **Evaluate**) y después el método paso a paso en prosa, cerrando con "The resulting policy is denoted as
  SLAPPI (...) and is summarized in Algorithm~\ref{}".
- Pseudocódigo con `algorithm` + `algorithmic` en mayúsculas (`\FOR`, `\STATE`, `\ENDFOR`), 10–20 líneas,
  `\caption` debajo del bloque, sin `\Require`; las entradas se listan en texto ("**Input:** ...
  **Output:** ...") en los algoritmos del apéndice.
- Se clasifica el método en el marco de Powell (pedido por R3-Q2): "In terms of the framework on
  approximate dynamic programming by \cite{powell2022designing}, we propose combining a stochastic lookahead
  method with a cost function approximation (CFA)".
- Parámetros: se dan con su valor y su justificación de calibración ("The number of scenarios is set to
  $|\Omega_t| = 40$. This setting strikes the right balance between runtime and solution quality, as
  shown in \ref{sec:app_tunning}") y la tabla de calibración va al apéndice.
- Complejidad: una frase cuando importa ("with complexity $O(|\mathcal{A}|)$"; "NP-hard ... exact methods
  typically require several minutes per instance, which is unsuitable for the dynamic setting").
- Nombres de políticas en negrita y con sufijo "-policy": "\textbf{STAR}-policy", "\textbf{Bellman+RL}".

## 6. Cómo se reportan los experimentos

- "Experimental setting" = instancias + benchmarks + detalles de implementación; "Computational study" =
  resultados. Un árbitro objetó el título "Design of experiments" por no decir qué se buscaba (R3-Q38).
- Instancias: procedencia de los datos en un párrafo ("derived from data shared by a Colombian agri-food
  e-commerce platform and publicly accessible data ... The instance generator can be found on ..."),
  luego `\paragraph{Layout}`, `\paragraph{Vehicles}`, `\paragraph{Products}`, `\paragraph{Supply and
  demand}`, `\paragraph{Prices}` con cada valor y su fuente. Número de realizaciones de entrenamiento y
  evaluación explícito ("50 instance realizations, 20 for training and 30 for evaluation").
- Benchmarks: `compactitem` con el nombre en negrita, una frase de qué hace y una de por qué está (qué
  componente aísla): "Comparing it with \textbf{Bellman+RL} isolates the value of making the correction
  state dependent". Cada benchmark enlazado a un trabajo de la literatura en Related work.
- Implementación: hardware, SO, Python, Gurobi con versión, y parámetros calibrados "based on preliminary
  experiments".
- Resultados: tabla principal con "gap (%) ± SE" o "Improvement over MYOPIC (in %)" y "CPU time (in
  sec/period)"; SE = SD/√N con N explícito; mejor valor en negrita. Comparación siempre relativa a un
  benchmark base (PILB, MYOPIC). Tiempos de CPU obligatorios (R2-Q4, R3-Q39).
- Lectura de tablas de arriba hacia abajo: "We first examine the rule-based purchasing policies in the
  upper part of Table~\ref{}... In the lower part ...". Cada bloque de números cierra con una frase de
  interpretación ("These results show that retaining the option to reject a revealed offer is important").
- Análisis del mecanismo: una subsección dedicada al componente nuevo (el penalizador $\gamma$, los
  $\gamma$-values) con figura + tabla + mapa, y explicación cualitativa de por qué toma esos valores.
- "Decision making": cómo cambia la decisión frente al benchmark (qué se compra, cuándo, a quién).
- Sensibilidad: "one-factor-at-a-time sensitivity analysis around the base case", tabla "Relative
  difference over the ``Basis'' setting (in %)" con tres políticas representativas; condiciones
  adicionales (correlación, distribuciones mal estimadas, rutas más largas) en el apéndice.
- Sin tests estadísticos formales: solo media ± SE y variabilidad (box plots en apéndice). Nuestro diseño
  pareado con bootstrap e intervalos de 95 % es un añadido compatible (se reporta junto al SE).
- Ablaciones de componentes (R2-Q5): separar el valor de cada parte y de su combinación (MY-AR, ST-MY,
  STAR).

## 7. Figuras, tablas y captions

- Tablas: `tabular` con `\hline` (no `booktabs`), dentro de `\begin{adjustbox}{max width=\textwidth}`,
  encabezados en negrita, `\caption` debajo de la tabla, caption nominal corta sin punto final ("Supplier
  metrics summary"; "Sensitivity analysis across operational settings"). Tablas grandes con `\scriptsize`,
  `\setlength{\tabcolsep}{3pt}`, `\renewcommand{\arraystretch}{1.1}`.
- Figuras: PDF, `\includegraphics[width=0.6\textwidth]` o `0.7`, dos figuras lado a lado en `minipage`
  de 0.495; caption nominal corta ("Geographical distribution of suppliers"); el texto describe ejes
  ("The x-axis indicates decision points, the left y-axis displays ...") porque un árbitro pidió leyenda y
  explicación (R3-Q43).
- Tabla de clasificación de la literatura en el cuerpo (los tres árbitros la pidieron), con bloques de
  columnas por dimensión y `\checkmark`, última fila "Our work".
- Numeración: T1, T2 en nuestro borrador desaparece; se usan solo `\label` y referencias.

## 8. Fraseo y tono

- Primera persona del plural siempre: "We study", "We propose", "We note that", "We observe that".
- Cada sección y subsección abre con una frase-mapa: "In this section, we present our computational
  study. We first compare ... Then ... Finally ...". Cada sección cierra con una frase de síntesis.
- Conectores favoritos: "Notably,", "Interestingly,", "In essence,", "To this end,", "Thus,", "In
  summary,", "To the best of our knowledge, ... is the first to ...".
- Las afirmaciones se gradúan: "likely", "may", "rather", "relatively", "we conjecture". Tras una ronda,
  las afirmaciones fuertes se suavizaron ("we softened the statement").
- Términos definidos una vez y reutilizados sin variación (period, scenario, sample path, iteration,
  realization): un árbitro detectó inconsistencias (R2-Q2) y la respuesta fue una figura y definiciones.
- Inglés americano ("organized", "behavior") en el publicado; comillas con `\enquote{}` (`csquotes`).
- Se evita el "nosotros medimos": los resultados se cuentan como hallazgos ("The results show that ...").

## 9. Limitaciones y trabajo futuro

- Dos párrafos al final de la conclusión, tras el párrafo de generalización: "The study also has several
  limitations related to the decision environment. ... These assumptions exclude settings with ... Future
  research could extend ..." y "There are also methodological limitations that motivate further research."
- Cada limitación va pegada a su extensión futura, en la misma frase o la siguiente.
- La conclusión equilibra (R3-Q47): resumen de contribución y resultado → implicación gerencial en una frase
  ("the central implication is that information should not trigger automatic commitment") → cuándo
  conviene el método simple → generalización del método (qué propiedades debe tener otro problema) →
  limitaciones → futuro.

## 10. Lo que pidieron los árbitros y cómo se respondió (para anticiparlo)

| Petición (ronda 1, tres árbitros) | Respuesta | Qué hacemos en main.tex |
|---|---|---|
| Aclarar la contribución y el porqué de la ventaja del método (R1-Q1, R3-Q13) | párrafo "Our contributions are as follows" con tres contribuciones y lo que es "first" | tres contribuciones etiquetadas; lista de *insights* |
| Revisión de literatura en el cuerpo, no solo en apéndice; marco de Powell (R1-Q2, R2-Q1, R3-Q18) | tabla de clasificación al cuerpo + párrafo sobre lookahead/PFA/CFA/VFA | tabla de posicionamiento en Related work; clasificación de nuestras políticas como CFA |
| Definir términos (period, iteration, simulation, scenario) y dar figura del proceso (R2-Q2, R3-Q29) | definiciones y figura nueva | "window", "round", "day", "run", "seed" definidos una vez; figura de arquitectura compartida |
| Cómo se calcula el objetivo y sobre cuántas realizaciones (R2-Q3) | "30 evaluation instance realizations ... average" | 24 instancias × 10 semillas, promedio por instancia, SE sobre instancias |
| Tiempos de CPU (R2-Q4, R3-Q39) | fila de CPU en la tabla principal + apéndice de intratabilidad | columna s/round en la tabla principal; tiempos por método |
| Separar el valor de cada componente (R2-Q5) | política nueva MY-AR | ablaciones X3 (decodificador, base de ingreso, alcance del Gini, prioridad) |
| Resumen más específico con cifras (R2-Q6, R3-Q12) | resumen reescrito | hueco para dos cifras del X1 |
| Supuestos realistas y justificados (perecibilidad, cosecha, precios) (R2-Q8, R3-Q6, R3-Q7) | justificación con la empresa y la literatura; ejemplo con cifras realistas | cada supuesto con su evidencia (entrevistas, encuesta, grado) |
| Escalabilidad y error de la aproximación con rutas más largas (R3-Q3, R3-Q4, R3-Q10) | experimentos nuevos en apéndice; limitación en intro y conclusión | tiempos por ciudad (Bogotá como peor caso), top-k 8 vs 25, limitación declarada |
| Generalización del método: qué propiedades debe tener otro problema (R3-Q5, R3-Q48) | párrafo "SLAPPI is particularly suited to sequential problems in which ..." | párrafo equivalente para el historial de equidad y la linealización |
| Correlación y distribuciones mal estimadas (R1-Q3, R3-Q8, R3-Q9) | experimentos nuevos | sensibilidad al umbral θ del logit (X2) y a los dos regímenes |
| Datos reales: qué se usó y qué se transformó (R3-Q11, R3-Q34) | párrafo de procedencia + generador público | párrafo de procedencia de los 24 días y del repositorio |
| Síntesis de alto nivel de los resultados (R3-Q44) | *insights* en la introducción | lista de *insights* en la introducción |
| Conclusión con contribuciones, resultados y limitaciones (R3-Q47) | conclusión reescrita | conclusión con esa estructura |
| Erratas y frases ambiguas (muchas) | corrección + "We carefully proofread the entire paper" | pasada final pendiente |

Ronda 2 (menor): describir columnas de tablas en el texto; evitar "therefore" redundante; decir
explícitamente qué se resuelve en cada etapa de un método de dos etapas; no sugerir criterios de parada
que no existen ("until convergence" → "for a large number of iterations").

## 11. Preámbulo y bibliografía

- `\documentclass[a4paper,11pt,review,3p,authoryear]{elsarticle}` + `setspace` con `\onehalfspacing`;
  `\journal{European Journal of Operational Research}`.
- Paquetes: amssymb, amsmath, amsthm, csquotes, graphicx, subfig, xcolor, comment, lscape, algorithmic
  (`[noend]`), algorithm, mathtools, url, adjustbox, multirow, paralist, pifont (`\cmark`, `\xmark`),
  tcolorbox, float, microtype; natbib con `\bibpunct[, ]{(}{)}{,}{a}{}{,}` y `\bibfont\small`; `multibib`
  con `\newcites{Appx}{Appendix references}` para que el apéndice tenga su propia lista
  (`ReferencesAppx.bib`) y no cuente contra las 35 páginas.
- `\rev{}` en azul (RGB 0,90,181) para cambios de revisión y `\todo{}` en rojo (220,50,32).
- `\bibliographystyle{elsarticle-harv}` y `\bibliography{References}`; claves de BibTeX en minúsculas
  "autorAñoPalabra" (`powell2021reinforcement`) o la clave de Elsevier en mayúsculas (`ULMER2020183`).
- Citas: `\citep{}` para paréntesis, `\cite{}`/`\citet{}` para sujeto de frase, `\citealt{}` dentro de
  paréntesis propios.
