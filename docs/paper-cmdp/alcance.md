# Alcance del paper: revista, pregunta y contribuciones (Etapa 0, entregables 3 y 4)

Fecha: 2026-10-20. Versión 2, tras las decisiones del autor del mismo día.

## 1. Revista objetivo: decidida

**European Journal of Operational Research (EJOR), sección Innovative Applications of O.R.**

Reglas que condicionan la escritura (guía de autores, verificada 2026-10-20):

- 35 páginas de manuscrito como máximo, **incluyendo** tablas, figuras, referencias y apéndices.
- Resumen ≤ 250 palabras.
- Material no esencial va a un suplemento en línea. Para este paper: calibración completa de la aceptación,
  tablas por instancia, parámetros del BRKGA, pruebas sobre la instancia de juguete, y el detalle de la
  encuesta.
- EJOR premia la novedad metodológica más que TR-E; la pregunta y las contribuciones de abajo se reescribieron
  con ese sesgo: el modelo y los algoritmos van primero, la evidencia de Bogotá los valida.

Alternativas descartadas: TR-E (mejor encaje con datos y comportamiento, menos con el modelo), Omega (ángulo
gerencial, también 35 pp), C&OR (solo algoritmos).

## 2. Pregunta de investigación del paper (versión 2)

Lo que cambia frente a la versión 1: la pregunta ya no es "cuánto cuesta la equidad" (una medición) sino
"cómo se despacha con una garantía de equidad de fin de día cuando el repartidor responde al precio" (un
problema de decisión), que es lo que EJOR espera de una Innovative Application. El costo de la equidad
pasa a ser el resultado principal, no la pregunta.

> ¿Cómo debe una plataforma de domicilios asignar rutas y fijar el pago por oferta, ventana a ventana,
> para garantizar al cierre del día un Gini del ingreso por hora de los repartidores no mayor que α,
> cuando cada repartidor acepta o rechaza según el pago por kilómetro, y qué pierde en cobertura y
> puntualidad frente al despacho corporativo por hacerlo?

Para el manuscrito:

> *How should a meal-delivery platform assign routes and set per-offer pay, window by window, so that the
> end-of-day Gini coefficient of couriers' hourly earnings does not exceed a threshold α when each courier
> accepts or rejects offers according to pay per kilometre, and what does it give up in coverage and
> punctuality relative to corporate dispatching for doing so?*

Las dos mitades son falsables: la primera se responde con políticas que cumplen o no la restricción en 24
días reales; la segunda, con el frente de Pareto cobertura/atraso vs. Gini por método y por régimen de
aceptación.

## 3. Las tres contribuciones (versión 2)

1. **Un CMDP con equidad intertemporal y aceptación endógena al precio.** El estado incluye la historia de
   equidad $\mathcal{H}_t$ (ingreso, pedidos y tiempo activo acumulados por repartidor); la restricción Gini
   se impone sobre el ingreso por hora de fin de día, no por ventana; la aceptación de cada oferta es un
   logit sobre el pago por kilómetro con dos regímenes (manual y autoaceptación). Se muestra que la
   formulación contiene como casos particulares el modelo corporativo (α = 1), los de balance de carga
   ($F_{\text{Orders}}$) y los de salario mínimo ($F_{\text{Deficit}}$), y por qué la equidad por ventana no
   garantiza la de fin de día (Gaps 2 y 4 de la tesis).
2. **Tres métodos de solución para el mismo CMDP, en un solo simulador.** BRKGA-Fair (decodificador que usa
   el déficit de $\mathcal{H}_t$ para sesgar la asignación), Pay-BRKGA (biobjetivo cobertura vs.
   $F_{\text{Deficit}}$ con λ, ajustando $\pi_1$ dentro de una banda) y MIP-Fair (MIP por ventana con la
   restricción Gini linealizada sobre $\mathcal{H}_t$). Los tres comparten candidatos de ruta, ventana de
   2 min, modelo de aceptación y métricas con los baselines (greedy corporativo, BRKGA-Coverage, ILP de
   cobertura, jerárquico cov › lat › eq › cost), y se verifican contra el óptimo por fuerza bruta en una
   instancia de juguete. Es lo que hace comparables los frentes de Pareto en α y λ (Gaps 1 y 3).
3. **El costo de la garantía de equidad medido en operación real.** 24 instancias de Bogotá con aceptación
   calibrada en campo (135 encuestas, 44 entrevistas, umbral 903 COP/km con su intervalo): frente de Pareto
   por método, pérdida por régimen de aceptación, sensibilidad al umbral del logit, selección de α por los
   tres criterios (histórico, bandas, rodilla del Pareto) y efecto colateral en emisiones por composición de
   flota. De aquí sale la recomendación operativa: qué α es sostenible y con qué política.

Fuera del paper (trabajo futuro declarado): restricción de caja en efectivo, heterogeneidad por antigüedad y
nacionalidad, factores de emisión locales, y las 240 instancias de Grubhub (ver decisión pendiente).

## 4. Decisiones tomadas el 2026-10-20

| Decisión | Resultado |
|---|---|
| Revista | EJOR, Innovative Applications |
| Pregunta y contribuciones | reescritas (esta versión 2); pendiente visto bueno |
| ¿Un simulador o dos? | **Uno solo**: `simulator/`. Los scripts MIC 2026 quedan como referencia de los baselines, no se corren para el paper. |
| ¿Existe código de GRASP o de los métodos fair en otro lado? | **No.** Todo lo que hay está en el repo; lo que falta se construye: BRKGA-Fair, Pay-BRKGA, MIP-Fair y el porte del BRKGA-Coverage a `Policy.assign`. El GRASP se cita como trabajo previo, no se reimplementa. |

Siguen abiertas (con la recomendación del plan como valor por defecto si no se dice otra cosa):

- Unidades de pago: COP en Bogotá; aceptación en pago/km normalizado.
- Grubhub: fuera del paper salvo que sobre tiempo en la Etapa 5; si entra, solo con políticas ya portadas.
