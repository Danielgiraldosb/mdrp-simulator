# Etapa 1 — El modelo CMDP contra la evidencia empírica

Borrador 2026-10-20. Entregable de la Etapa 1 de `plan.md`. Cruza cada supuesto del CMDP
(`formulacion.md`) con la evidencia de las dos fuentes cuantitativas y propone qué cambia en el
paper. Las decisiones marcadas **[autor]** quedan pendientes de Daniel y del director.

## 1. Fuentes y grados

| Fuente | Qué es | n | Período | Archivo |
|---|---|---|---|---|
| Entrevistas | 44 entrevistas semiestructuradas a domiciliarios de Rappi en Bogotá, codificadas por lectores independientes; 32 decisiones de aceptación de 11 personas estimadas con logit | 44 (32 decisiones) | 2020–2021 | `docs/Comportamiento_domiciliarios_cuantitativo.xlsx` (hoja `Parametros_modelo`) |
| Encuesta | Cuestionario por intercepción en puntos de Bogotá; modelos logit y OLS con error robusto HC1 | 135 | mayo–junio 2021 | `docs/Encuesta_cuantitativo_domiciliarios.xlsx` (hojas `Trazabilidad_tesis`, `Modelos_logit`, `Racha`, `Ingreso`, `Triangulacion`) |

Grados (como en las hojas): **A** consistente en ≥15 entrevistados o convergencia clara de las dos fuentes;
**B** 5–14 entrevistados o una sola fuente sólida; **C** <5, ambiguo o n pequeño con IC amplio. Ninguna
fuente es inferencial a la población (muestreo por intercepción, autorreporte); el paper debe decirlo.

Las dos fuentes son de **Bogotá**. Las 24 instancias reales, en cambio, cubren seis ciudades (sección 5).
Toda calibración conductual que se aplique a Medellín, Cali, Barranquilla, Bucaramanga o Pereira es un
**supuesto de transferencia** y así se declara.

## 2. Tabla supuesto → evidencia → grado → cómo se declara

Numeración por sección de `formulacion.md`. "Entra" = cambia el modelo del paper; "Parámetro" = se
mantiene la forma y solo se calibra; "Sensibilidad" = se reporta el efecto del intervalo; "Futuro" =
limitación declarada.

| # | Supuesto del CMDP | Evidencia entrevistas | Evidencia encuesta | Grado | Cómo se declara | Recomendación |
|---|---|---|---|---|---|---|
| 1 | §1.2.1 Capacidad de ruta Q (bundles) | Pedidos "dobles" existen y pagan mejor; sin cifra | — | C | Q = 3 como en el simulador; sin evidencia de campo | Parámetro; sensibilidad Q ∈ {1,2,3} |
| 2 | §1.2.2 Tiempos de viaje deterministas por OSRM | — | — | — | Las instancias traen lat/lng, no rutas: se usa proyección plana + factor de circuidad (1.0 haversine, ~1.3 red vial) y velocidad por vehículo (externa) | Entra: tiempo = dist·circuidad / v(vehículo). **[autor]** circuidad y velocidades |
| 3 | §1.2.3 Solo se notifica a couriers ociosos o en recogida | — | — | — | Regla del simulador; sin evidencia | Se mantiene; declarar |
| 4 | §1.2.4 Un pedido por usuario y día | — | — | — | Verificable en los datos (ids de pedido únicos) | Se mantiene |
| 5 | §1.2.5 Cancelación definitiva; modelo de riesgo a dos umbrales | — | — | — | Sin evidencia empírica de cancelación; el simulador la trae apagada | Apagada en el experimento base; futuro |
| 6 | §2.1 Estado con historial de equidad H_t (acumulado del día) | La racha concentra pedidos y pago; umbrales por nivel | Racha: pedidos/día 4→14,5; pago/pedido 2.300→5.000; ingreso/día 20k→60k; Gini diario 0,39→0,26; mediana 2 días para entrar (47/133 en 1 día, 18 tardan ≥7) | A | H_t justificado como estado con memoria; en el paper es intradía (un día de operación) y se declara que la racha es multi-día | Entra como está; futuro: H_t multi-día |
| 7 | §2.5 Restricción de equidad por Gini de fin de día | Desigualdad en acceso a racha y puntos | Gini ingreso mensual 0,22; horas/semana 0,14; ingreso diario sin racha 0,39, en racha 0,26 | B | El umbral α del Gini se calibra con estos valores: 0,26 (meta, régimen racha), 0,39 (statu quo sin racha) | Parámetro: α ∈ {0,25; 0,30; 0,35; 0,40}; sensibilidad |
| 8 | §2.5 / eq:minwage Restricción de salario mínimo | Ingreso/hora conectado mediana 3.957 COP (RIC 2.799–5.950) | Ingreso/hora conectada mediana 2.622 (P25 1.931, P75 3.405); 91,9 % por debajo del SMMLV/hora 2021 (4.368 COP) | B | SMMLV/hora como umbral externo de F_Deficit; la plataforma no garantiza pago por hora (no hay "true-up") | Parámetro: `min_wage_hourly` = 4.368; `guaranteed_pay_per_hour` = 0 |
| 9 | §2.6 Aceptación logística lineal en pago, distancia y fatiga | Logit sobre ln(pago/km): umbral 903 COP/km [615; 1.242], pendiente 2,89 [2,02; 5,23]; n = 32 decisiones / 11 personas; régimen manual 2020 | Pago (5,71) y distancia (5,65) son los factores dominantes, en ese orden; autoaceptar reduce su importancia | B (forma) / C (parámetros) | Se reemplaza la forma lineal por σ(b·(ln(pago/km) − ln θ)); se declara n pequeño, elección declarada, régimen 2020 | **Entra** (ya implementado: `acceptance_mode = logit_ppk`); sensibilidad sobre θ y b en el IC |
| 10 | §2.6 Régimen de decisión único | 2020: autoaceptar 0/12, rechazo común 13/14; 2021: autoaceptar 23/25, rechazo 2/12 | 64 % autoaceptan siempre o casi siempre; 21 nunca; M4: a más horas (OR 1,30 por 10 h) y menos peso al pago (OR 0,61) más autoaceptar | A | Dos regímenes: `manual` (p por oferta) y `autoaccept` (p = 1, la decisión es estar conectado) | **Entra** (implementado: `accept_regime`); correr ambos |
| 11 | §2.6.1 Tarifa π₀ + π₁·dist | π₀ ≈ 3.138, π₁ ≈ 155 COP/km, IC95 [−103; 413], R² 0,02; pago/km mediana 1.000 (2020) y 833 (2021) | Pago/pedido sin racha 2.200 (V116), en racha 5.000; 93 % reportan cambio de pago tras aceptar; razón final/mostrado 0,60 | C | La tarifa real es casi plana en distancia. Base: pago plano 2.200 COP. π₁ se mantiene solo como **palanca de política** de Pay-BRKGA, no como descripción | **[autor]**: plano (recomendado) o π₀ + π₁·d con π₁ = 155 |
| 12 | §2.6.1 Balance de rutas de alto valor (κ) | Pedidos de supermercado pagan "el doble"; la racha da acceso a mejores pedidos | Racha ⇒ pago/pedido ×2,2 | C | Hay evidencia de que existen rutas de alto valor y de que su acceso es desigual, no del valor de κ | Parámetro; sensibilidad κ ∈ {0,5; 0,75; 1} |
| 13 | §2.4 / §2.8 Costo operativo con pago | Ingreso bruto/día mediana 46.500 COP | Ingreso diario sin racha 20.000, en racha 60.000 | B | Unidades en COP; pago total del día como componente de costo | Parámetro |
| 14 | §2.9 Emisiones proxy por vehículo ε(v) | Bici / moto / mixto: 26 / 17 / 1 (59 % bici) | Moto 36 %, bici 53 %, e-bici 10 % | B (composición) | Las instancias traen el vehículo por courier (bici, moto, a pie, carro); factores de emisión externos | Parámetro; declarar factores (ninguna fuente propia) |
| 15 | Tiempos de servicio (recogida / entrega) | Espera en tienda mediana 60 min (RIC 39–90), episodios relatados | Espera en local con pedido comprado mediana 20 min (RIC 15–30, máx 180); pico 30 / valle 10 | B / C | Caso típico 20 min (encuesta); escenario de estrés 60 min (entrevistas). Entrega: sin dato, 4 min | Parámetro: `real_pickup_service_min` 20 (base) y 60 (estrés) |
| 16 | Ventana de decisión por oferta | 16 s mediana (RIC 9–28); la app muestra 20 s | — | C | Media 16 s, desvío 8 s | Parámetro (implementado) |
| 17 | Jornada / disponibilidad | 11 h/día conectado (RIC 9–13) | 78 h/semana mediana, 6,6 días; meseta 11–19 h; 31 % de horas-conexión en 11–15 h | A / B | Los turnos vienen en los datos (`on_time`/`off_time`); la encuesta sirve para validar la forma de la curva de conexión | Validación, no parámetro |
| 18 | Reubicación de couriers ociosos | Esperan en sitio 17, se mueven 5, ambos 12 | 96 esperan, 39 se mueven; 33/39 a zonas de alta demanda | B | El simulador trae reposicionamiento apagado; la evidencia dice que la mayoría espera | Apagado en base; sensibilidad opcional |
| 19 | Sanciones y bloqueos por rechazar (no está en el CMDP) | 28/32 bloqueados; umbral 2,75 rechazos; bajar la tasa es rápido (−1 a −5 pts), subir lento | 60 % bloqueados; mediana 24 h (RIC 2–48); M1: autoaceptar OR 2,76, antigüedad ≥1 año OR 2,62 | B | Explica por qué el régimen autoaceptar domina en 2021; no se modela la dinámica de la tasa | Futuro (declarar como mecanismo detrás del régimen) |
| 20 | Restricción de caja / efectivo (no está en el CMDP) | Tope mediana 80.000 COP | Tope 70.000 (RIC 50–80k); consigna al 100 % tras ~5 pedidos | A/B | Las instancias no traen marca de pago en efectivo: no se puede modelar | Futuro (extensión) |
| 21 | Heterogeneidad de couriers (no está en el CMDP) | 75 % venezolanos, 91 % hombres | Venezolanos: tasa ≥90 % OR 8,2 [2,4; 28,3], +0,94 en importancia del pago, +11 h/semana; antigüedad ≥1 año: +1,6 h | B | Las instancias solo traen vehículo; nacionalidad y antigüedad no son observables | Futuro; el vehículo sí entra como tipo |
| 22 | Recorte de pago tras aceptar (no está en el CMDP) | 39/42 reportan cambio; razón final/mostrado 0,60 (RIC 0,53–0,69) | — | A (ocurre) / B (magnitud) | La aceptación responde al pago **mostrado**; el ingreso realizado puede ser menor. No entra al modelo base | Futuro; posible sensibilidad "pago realizado = 0,6 × ofrecido" |

## 3. Cambios propuestos al modelo del paper

1. **Aceptación por pago/km (entra).** Reemplazar eq:acceptance por
   p = σ(b·(ln(π/d) − ln θ)), θ = 903 COP/km, b = 2,89. Justificación: es la forma que estima la
   evidencia disponible (fila 9) y es la que usan los couriers al razonar ("ni yo ni nadie agarra 4,1 km
   por 3.300"). Costo: cero, ya implementado (`simulator/acceptance.py`, modo `logit_ppk`). Se reporta
   la sensibilidad sobre los extremos del IC: θ ∈ {615; 903; 1.242}, b ∈ {2,02; 2,89; 5,23}.
2. **Dos regímenes de decisión (entra).** `manual` y `autoaccept`. El experimento principal corre en
   los dos; el de 2021 (autoaceptar) es el relevante para la plataforma hoy, el manual es el que hace
   visible la palanca de pago (Pay-BRKGA). Costo: cero, implementado.
3. **Tarifa plana como base, π₁ como palanca (entra).** Pago base 2.200 COP/pedido (fila 11). Las
   políticas con pago (Pay-BRKGA) mueven π₁ dentro de un rango declarado; se cita que π₁ observado no es
   distinguible de cero. **[autor]** confirmar.
4. **Calibración de α del Gini (parámetro).** Usar 0,26 (régimen racha) como meta y 0,39 como statu
   quo; reportar la frontera coverage–Gini sobre α.
5. **Salario mínimo como umbral externo (parámetro).** F_Deficit con 4.368 COP/hora; sin pago
   garantizado por hora.
6. **Tiempos de servicio y ventana de decisión (parámetro).** 20 min en tienda (base), 60 (estrés);
   16 ± 8 s para decidir.
7. **Vehículo como tipo de courier (entra).** Velocidad por vehículo y proxy de emisiones; la
   composición de flota viene de cada instancia (sección 5), no de la encuesta.
8. **Declarar como futuro:** sanciones y dinámica de la tasa de aceptación, restricción de caja,
   heterogeneidad por nacionalidad y antigüedad, racha multi-día, recorte de pago tras aceptar,
   cancelaciones.

## 4. Decisiones de la Etapa 1 (tomadas el 2026-10-20 por encargo del autor: "toma las decisiones")

| # | Decisión | Tomada | Justificación | Dónde |
|---|---|---|---|---|
| D1 | Tarifa | **Plana, 2.200 COP por pedido** | Es lo que reporta la encuesta (bandas); π₀ + π₁·d no tiene soporte en los datos y Pay-BRKGA ya introduce la variación por oferta (±30 %) | `config.real_pay_per_order_cop` |
| D2 | Circuidad | **1,3 como base; 1,0 en sensibilidad (suplemento)** | Sin OSRM, 1,3 es el factor estándar de red vial urbana frente a haversine; se declara como supuesto. El piloto X0 corrió con 1,0 (solo tiempos); X0 se repite con 1,3 para la regla de α | `config.real_circuity = 1.3`, `batch_paper.py --circuity` |
| D3 | Velocidades por vehículo | **Bici 15, moto 25, a pie 5, carro 20 km/h, declaradas como supuesto** | Del mismo orden que los 320 m/min (19 km/h) de mdrplib (Reyes et al. 2018) y que los tiempos de las entrevistas; no hay fuente local citable por vehículo. Sensibilidad ±20 % solo si queda tiempo | `config.real_speeds_kmh` |
| D4 | SLA duro | **`expected_drop_off_time` + 30 min** | Mantiene la lectura del dato real (hora prometida) con la holgura que las entrevistas describen como tolerada; × 1,5 castiga de forma desigual pedidos cortos y largos | `config.real_max_ctd_extra_min` |
| D5 | Alcance geográfico | **Las seis ciudades: Bogotá como caso calibrado, las otras cinco como robustez bajo transferencia declarada** | 24 instancias en vez de 4; la calibración conductual es de Bogotá y así se dice en limitaciones | diseño §1 (T1, T8) |
| D6 | Factores de emisión | **Moto 0,114 y carro 0,167 kg CO₂e/km (DEFRA/BEIS 2023, "average motorbike" y "average car"); bici y a pie 0; moto pequeña 0,083 (DEFRA 2024) como sensibilidad** | Fuente pública y citable; factores locales no existen por tipo de vehículo y quedan como trabajo futuro | diseño §5, `batch_paper.EMISSION_KG_PER_KM` |
| D7 | Semillas por celda | **10, comunes a todas las celdas** | Aceptación Bernoulli y BRKGA estocástico; comparación pareada por (instancia, semilla) | diseño §2 |

Siguen siendo supuestos declarados en el paper (sección de limitaciones): D2, D3 y D6.

## 5. Las instancias reales no son solo Bogotá

Al proyectar las coordenadas se vio que las 24 carpetas de `real_instancies/` corresponden a seis
ciudades colombianas (centroide de tiendas contra ciudades de referencia; tabla completa en
`docs/paper-cmdp/instancias_reales.csv`):

| Ciudad | Instancias | Pedidos (total) | Couriers (total) | Pedidos/courier (rango) | Flota típica |
|---|---|---|---|---|---|
| Bogotá | 0, 6, 12, 18 | 177.234 | 58.862 | 2,4–3,5 | 45 % bici, 39 % moto, 9 % a pie, 7 % carro |
| Medellín | 2, 8, 14, 20 | 74.002 | 23.150 | 2,7–3,8 | 15 % bici, 72 % moto |
| Barranquilla | 5, 11, 17, 23 | 26.343 | 10.305 | 1,9–3,3 | 20 % bici, 64 % moto, 10–15 % carro |
| Cali | 7, 13, 19 | 16.262 | 6.427 | 2,3–2,8 | 21 % bici, 72 % moto |
| Bucaramanga | 1, 3, 9, 15, 21 | 11.163 | 5.426 | 1,4–2,5 | 9 % bici, 89 % moto |
| Pereira | 4, 10, 16, 22 | 2.656 | 1.696 | 1,3–2,0 | 5 % bici, 90 % moto |

Consecuencias: (i) el paper gana generalidad (seis ciudades, tamaños de 400 a 16.800 couriers por día);
(ii) la calibración conductual (aceptación, servicio, régimen) es de Bogotá y se transfiere; (iii) los
nombres `loader_bogota.py` del plan pasaron a `loader_real.py`, con centro de proyección y filtro de
radio por instancia; (iv) la fracción de bici es muy distinta entre ciudades, lo que vuelve relevante el
proxy de emisiones por ciudad. Los archivos tienen unos pocos puntos (≤10 por instancia) a cientos de km
del centro; el loader los descarta y los cuenta en `meta['dropped']`.

Nota de calidad de datos: las instancias 1 y 3 comparten exactamente el mismo `stores.csv` pero no
pedidos ni couriers (días distintos de Bucaramanga). Las instancias 16 y 17 tienen tantas tiendas como
pedidos (538 y 4.390): cada pedido trae su propia tienda, probablemente una exportación sin
deduplicar; no afecta al simulador.

## 6. Parámetros calibrados que ya están en `simulator/config.py`

| Campo | Valor | Fuente | Grado |
|---|---|---|---|
| `accept_ppk_threshold` | 903 COP/km (IC 615–1.242) | Entrevistas, `Parametros_modelo` | C |
| `accept_ppk_slope` | 2,89 (IC 2,02–5,23) | Entrevistas | C |
| `accept_regime` | manual / autoaccept | Entrevistas (A), encuesta 64 % | A |
| `real_pay_per_order_cop` | 2.200 | Encuesta V116 (n=132) | B |
| `real_min_wage_cop_per_hour` | 4.367,91 | SMMLV 2021 / (48 h × 4,33) | — |
| `real_pickup_service_min` | 20 (base), 60 (estrés) | Encuesta V88 / entrevistas | B / C |
| `real_dropoff_service_min` | 4 | mdrplib (sin dato propio) | — |
| `real_decision_mean_min` / `_std_min` | 16 s / 8 s | Entrevistas (RIC 9–28 s) | C |
| `real_speeds_kmh` | bici 15, moto 25, a pie 5, carro 20 | Supuesto de trabajo **[autor]** | — |
| `real_circuity` | 1,0 (haversine) **[autor]** | — | — |
| `real_max_ctd_extra_min` | 30 | Supuesto **[autor]** | — |
| `real_max_radius_km` | 40 | Limpieza de datos | — |

Comprobación del logit: a 1.000 / 1.500 / 2.000 COP/km el modelo da 0,57 / 0,81 / 0,91, que coincide
con la hoja `Parametros_modelo` (test `tests/test_acceptance_ppk.py`).
