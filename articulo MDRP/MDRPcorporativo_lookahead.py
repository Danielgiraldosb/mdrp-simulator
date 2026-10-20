import pandas as pd
import numpy as np
import os
import time
from datetime import datetime, time as dt_time
from math import radians, sin, cos, sqrt, atan2
from itertools import permutations

# ============================================
# CONFIGURACIÓN
# ============================================
LOOKAHEAD_PERIODS = 4  # 4 períodos × 2 min = 8 minutos
LOOKAHEAD_MINUTES = LOOKAHEAD_PERIODS * 2  # 8 minutos
MAX_TIME_PER_WINDOW = 120  # 2 minutos = 120 segundos
ROLLING_HORIZON_STEP = 2.0  # minutos

# ============================================
# FUNCIONES AUXILIARES
# ============================================

speed_map = {'motorcycle': 25.0, 'bicycle': 20.0, 'car': 15.0, 'walking': 5.0}

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi/2.0)**2 + cos(phi1)*cos(phi2)*sin(dlambda/2.0)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

def travel_time_min(lat1, lon1, lat2, lon2, vehicle_type):
    if pd.isnull(lat1) or pd.isnull(lat2) or pd.isnull(lon1) or pd.isnull(lon2):
        return 1e6
    sp = speed_map.get(str(vehicle_type).lower(), 15.0)
    dist = haversine_km(lat1, lon1, lat2, lon2)
    return (dist / sp) * 60.0

def time_to_min(t):
    if t is None or (isinstance(t, float) and np.isnan(t)):
        return None
    if isinstance(t, dt_time):
        return t.hour*60 + t.minute + t.second/60.0
    try:
        tt = pd.to_datetime(t).time()
        return tt.hour*60 + tt.minute + tt.second/60.0
    except:
        return None

def to_time_obj(x):
    try:
        return pd.to_datetime(x).time()
    except:
        return None

# ============================================
# CARGA DE DATOS
# ============================================

def load_instance(instance_name):
    """Carga una instancia desde las carpetas de datos"""
    carpeta_principal = 'Instancias'
    subcarpeta = instance_name

    ruta_domiciliarios = os.path.join(carpeta_principal, subcarpeta, 'couriers.csv')
    ruta_tiendas = os.path.join(carpeta_principal, subcarpeta, 'stores.csv')
    ruta_ordenes = os.path.join(carpeta_principal, subcarpeta, 'orders.csv')

    df_couriers = pd.read_csv(ruta_domiciliarios)
    df_stores = pd.read_csv(ruta_tiendas)
    df_orders = pd.read_csv(ruta_ordenes)

    # Normalizar nombres
    df_couriers.columns = [c.strip() for c in df_couriers.columns]
    df_stores.columns = [c.strip() for c in df_stores.columns]
    df_orders.columns = [c.strip() for c in df_orders.columns]

    # Parsear tiempos
    for col in ['on_time', 'off_time']:
        if col in df_couriers.columns:
            df_couriers[col] = df_couriers[col].apply(to_time_obj)

    for col in ['placement_time', 'preparation_time', 'ready_time', 'expected_drop_off_time']:
        if col in df_orders.columns:
            df_orders[col] = df_orders[col].apply(to_time_obj)

    # Merge store coords
    if 'store_id' in df_orders.columns and 'store_id' in df_stores.columns:
        df_orders = df_orders.merge(
            df_stores[['store_id', 'pick_up_lat', 'pick_up_lng']],
            on='store_id',
            how='left'
        )

    return df_couriers, df_stores, df_orders, subcarpeta

# ============================================
# PREPARACIÓN DE ESTRUCTURAS
# ============================================

def prepare_orders(df_orders):
    """Convierte DataFrame de órdenes a diccionario"""
    orders = {}
    for idx, row in df_orders.iterrows():
        oid = row.get('order_id', idx)
        orders[oid] = {
            'order_id': oid,
            'store_id': row.get('store_id'),
            'pickup_lat': row.get('pick_up_lat'),
            'pickup_lng': row.get('pick_up_lng'),
            'drop_lat': row.get('drop_off_lat'),
            'drop_lng': row.get('drop_off_lng'),
            'placement_min': time_to_min(row.get('placement_time')),
            'preparation_min': time_to_min(row.get('preparation_time')),
            'ready_min': time_to_min(row.get('ready_time')),
            'expected_drop_min': time_to_min(row.get('expected_drop_off_time')),
            'assigned': False
        }
    return orders

def prepare_couriers(df_couriers, start_min, end_min):
    """Convierte DataFrame de couriers a diccionario"""
    couriers = {}
    for idx, row in df_couriers.iterrows():
        cid = row.get('courier_id', idx)
        couriers[cid] = {
            'courier_id': cid,
            'vehicle': row.get('vehicle', 'motorcycle'),
            'home_lat': row.get('on_lat'),
            'home_lng': row.get('on_lng'),
            'current_lat': row.get('on_lat'),
            'current_lng': row.get('on_lng'),
            'status': 'idle',
            'available_at': time_to_min(row.get('on_time')) or start_min,
            'on_time_min': time_to_min(row.get('on_time')) or start_min,
            'off_time_min': time_to_min(row.get('off_time')) or end_min,
            'assigned_routes': []
        }
    return couriers

# ============================================
# FUNCIONES DE OPTIMIZACIÓN
# ============================================

def courier_available(courier, cur_min):
    """Verifica si un courier está disponible en cur_min"""
    if courier['status'] != 'idle':
        return False
    if courier['available_at'] is not None and cur_min < courier['available_at'] - 1e-6:
        return False
    if courier['on_time_min'] is not None and cur_min < courier['on_time_min'] - 1e-6:
        return False
    if courier['off_time_min'] is not None and cur_min > courier['off_time_min'] + 1e-6:
        return False
    return True

def best_route_for_courier_and_orders(courier, store_lat, store_lng, order_list, start_min,
                                      max_permutations=120):
    """
    Encuentra la mejor ruta para un courier con un grupo de órdenes.
    Optimizado para limitar el número de permutaciones evaluadas.
    """
    vehicle = courier['vehicle']

    # Tiempo de viaje del courier a la tienda
    t_to_store = travel_time_min(
        courier['current_lat'], courier['current_lng'],
        store_lat, store_lng,
        vehicle
    )
    arrive_store_min = start_min + t_to_store

    # El courier debe esperar hasta que TODAS las órdenes estén listas
    group_ready_min = max([od['ready_min'] for od in order_list])
    depart_store_min = max(arrive_store_min, group_ready_min)

    best = None

    # Limitar permutaciones si hay muchas órdenes
    n_orders = len(order_list)
    if n_orders <= 3:
        # Para 3 o menos, evaluar todas las permutaciones (máx 6)
        perms_to_eval = list(permutations(order_list))
    else:
        # Para más órdenes, usar heurística: ordenar por expected_drop_min
        # y evaluar solo algunas permutaciones
        sorted_orders = sorted(order_list, key=lambda x: x.get('expected_drop_min', 1e9))
        perms_to_eval = [tuple(sorted_orders)]  # Al menos la heurística

        # Agregar algunas permutaciones aleatorias si hay tiempo
        import random
        for _ in range(min(max_permutations - 1, 20)):
            perm = list(sorted_orders)
            random.shuffle(perm)
            perms_to_eval.append(tuple(perm))

    for r in perms_to_eval:
        cur_time = depart_store_min
        cur_lat, cur_lng = store_lat, store_lng
        feas = True
        deliveries = []

        for od in r:
            tt = travel_time_min(cur_lat, cur_lng, od['drop_lat'], od['drop_lng'], vehicle)
            cur_time += tt
            exp = od.get('expected_drop_min')

            if exp is not None and cur_time > exp + 1e-6:
                feas = False
                break

            deliveries.append({
                'order_id': od['order_id'],
                'drop_time_min': cur_time,
                'drop_lat': od['drop_lat'],
                'drop_lng': od['drop_lng']
            })
            cur_lat, cur_lng = od['drop_lat'], od['drop_lng']

        if not feas:
            continue

        # Tiempo de regreso a home
        t_back = travel_time_min(cur_lat, cur_lng, courier['home_lat'], courier['home_lng'], vehicle)
        finish_min = cur_time + t_back
        total_travel = finish_min - start_min

        if best is None or total_travel < best['total_travel']:
            best = {
                'sequence': [d['order_id'] for d in deliveries],
                'deliveries': deliveries,
                'depart_store_min': depart_store_min,
                'finish_min': finish_min,
                'total_travel': total_travel
            }

    return best

def get_orders_with_lookahead(orders, cur_min, lookahead_min):
    """
    Obtiene órdenes disponibles considerando lookahead.

    Estrategia:
    - Órdenes ya colocadas (placement_min <= cur_min)
    - Que estarán listas dentro del horizonte de lookahead (ready_min <= cur_min + lookahead_min)
    """
    lookahead_orders = []

    for o in orders.values():
        if o['assigned']:
            continue

        # Orden ya fue colocada
        if o['placement_min'] is not None and o['placement_min'] <= cur_min + 1e-6:
            # Estará lista dentro del lookahead
            if o['ready_min'] is not None and o['ready_min'] <= cur_min + lookahead_min + 1e-6:
                lookahead_orders.append(o)

    return lookahead_orders

# ============================================
# ALGORITMO PRINCIPAL CON LOOKAHEAD
# ============================================

def optimize_with_lookahead(couriers, orders, stores_df, start_min=0, end_min=1440):
    """
    Algoritmo greedy con lookahead de 4 períodos (8 min) y límite de tiempo por ventana.
    """
    assignments = []
    window_times = []  # Para registrar tiempo de ejecución por ventana

    cur_min = start_min
    window_idx = 0

    while cur_min <= end_min + 1e-6:
        window_start_time = time.time()
        window_idx += 1

        # Liberar couriers que terminaron sus rutas
        for cid, c in couriers.items():
            if c['status'] == 'busy' and c['available_at'] is not None:
                if cur_min >= c['available_at'] - 1e-6:
                    c['status'] = 'idle'
                    c['current_lat'] = c['home_lat']
                    c['current_lng'] = c['home_lng']

        # Obtener órdenes con lookahead
        lookahead_orders = get_orders_with_lookahead(orders, cur_min, LOOKAHEAD_MINUTES)

        if window_idx % 50 == 0:
            available_couriers_count = sum(1 for c in couriers.values() if courier_available(c, cur_min))
            print(f"[Time {cur_min:6.1f}] Lookahead orders: {len(lookahead_orders):5d}, "
                  f"Available couriers: {available_couriers_count:5d}")

        # Agrupar por tienda
        stores_pending = {}
        for o in lookahead_orders:
            stores_pending.setdefault(o['store_id'], []).append(o)

        # Procesar cada tienda
        for sid, pending in stores_pending.items():
            # Verificar timeout de ventana
            elapsed = time.time() - window_start_time
            if elapsed > MAX_TIME_PER_WINDOW:
                print(f"  ⚠️  Timeout en ventana {window_idx} (tiempo {cur_min:.1f} min)")
                break

            # Ordenar por expected_drop_min
            pending = sorted(pending, key=lambda x: x.get('expected_drop_min', 1e9))

            # Obtener datos de la tienda
            store_row = stores_df[stores_df['store_id'] == sid]
            if store_row.empty:
                continue

            store_lat = float(store_row.iloc[0]['pick_up_lat'])
            store_lng = float(store_row.iloc[0]['pick_up_lng'])

            # Asignar órdenes de esta tienda
            while pending:
                # Verificar timeout nuevamente
                elapsed = time.time() - window_start_time
                if elapsed > MAX_TIME_PER_WINDOW:
                    break

                available_couriers_list = [
                    (cid, c) for cid, c in couriers.items()
                    if courier_available(c, cur_min)
                ]

                if not available_couriers_list:
                    break

                # Máximo 3 órdenes por grupo (como en el original)
                max_group = min(3, len(pending))
                best_assignment = None
                best_cid = None
                best_group = None

                # Evaluar diferentes tamaños de grupo
                for k in range(1, max_group + 1):
                    group = pending[:k]

                    # Evaluar solo los primeros N couriers (optimización)
                    # Si hay muchos, tomar una muestra
                    max_couriers_to_eval = 50
                    if len(available_couriers_list) > max_couriers_to_eval:
                        import random
                        couriers_to_eval = random.sample(available_couriers_list, max_couriers_to_eval)
                    else:
                        couriers_to_eval = available_couriers_list

                    for cid, c in couriers_to_eval:
                        route = best_route_for_courier_and_orders(
                            c, store_lat, store_lng, group, cur_min
                        )

                        if route is None:
                            continue

                        if best_assignment is None or route['finish_min'] < best_assignment['finish_min']:
                            best_assignment = route
                            best_cid = cid
                            best_group = group

                # Si encontramos una asignación, ejecutarla
                if best_assignment is not None:
                    # Marcar órdenes como asignadas
                    for g in best_group:
                        orders[g['order_id']]['assigned'] = True

                    # Actualizar estado del courier
                    couriers[best_cid]['status'] = 'busy'
                    couriers[best_cid]['available_at'] = best_assignment['finish_min']
                    couriers[best_cid]['assigned_routes'].append({
                        'time_depart_min': cur_min,
                        'store_id': sid,
                        'orders': [g['order_id'] for g in best_group],
                        'finish_min': best_assignment['finish_min'],
                        'total_travel_min': best_assignment['total_travel']
                    })

                    # Registrar asignación
                    assignments.append({
                        'time_depart_min': cur_min,
                        'courier_id': best_cid,
                        'store_id': sid,
                        'orders': [g['order_id'] for g in best_group],
                        'depart_store_min': best_assignment['depart_store_min'],
                        'deliveries': best_assignment['deliveries'],
                        'finish_min': best_assignment['finish_min'],
                        'total_travel_min': best_assignment['total_travel']
                    })

                    # Remover órdenes asignadas de pending
                    pending = [p for p in pending if not orders[p['order_id']]['assigned']]
                else:
                    # No se pudo asignar, pasar a la siguiente tienda
                    break

        # Registrar tiempo de ejecución de la ventana
        window_elapsed = time.time() - window_start_time
        window_times.append({
            'time_min': cur_min,
            'execution_seconds': window_elapsed,
            'exceeded_limit': window_elapsed > MAX_TIME_PER_WINDOW
        })

        # Avanzar al siguiente período
        cur_min += ROLLING_HORIZON_STEP

    return assignments, window_times

# ============================================
# GUARDAR RESULTADOS
# ============================================

def save_results(assignments, couriers, orders, window_times, output_folder, instance_name,
                 execution_time_total):
    """Guarda resultados en formato Excel"""
    os.makedirs(output_folder, exist_ok=True)

    # DataFrame de asignaciones
    df_assign = pd.DataFrame([
        {
            'time_depart_min': a['time_depart_min'],
            'courier_id': a['courier_id'],
            'store_id': a['store_id'],
            'orders': ",".join(map(str, a['orders'])),
            'depart_store_min': a['depart_store_min'],
            'finish_min': a['finish_min'],
            'total_travel_min': a['total_travel_min']
        }
        for a in assignments
    ])

    # Estadísticas generales
    total_orders = len(orders)
    assigned_orders_count = sum(len(a['orders']) for a in assignments)
    coverage_rate = (assigned_orders_count / total_orders * 100) if total_orders > 0 else 0
    avg_travel = df_assign['total_travel_min'].mean() if not df_assign.empty else 0.0

    # Couriers utilizados
    unique_couriers = set(a['courier_id'] for a in assignments)

    # DataFrame de estadísticas
    df_stats = pd.DataFrame([{
        'Parametros': f'Lookahead={LOOKAHEAD_MINUTES}min, MaxTime={MAX_TIME_PER_WINDOW}s',
        'Tiempo_ejecucion_segundos': execution_time_total,
        'Ordenes_totales': total_orders,
        'Ordenes_cumplidas': assigned_orders_count,
        'Tasa_cobertura': f'{coverage_rate:.2f}%',
        'Domiciliarios_utilizados': len(unique_couriers),
        'Rutas_creadas': len(assignments),
        'Tiempo_viaje_promedio_min': f'{avg_travel:.2f}'
    }])

    # DataFrame de tiempos por ventana
    df_window_times = pd.DataFrame(window_times)
    exceeded_count = sum(1 for w in window_times if w['exceeded_limit'])

    # Guardar en Excel
    out_path = os.path.join(output_folder, f'resultados_{instance_name}_lookahead.xlsx')

    with pd.ExcelWriter(out_path) as writer:
        df_stats.to_excel(writer, sheet_name='Estadisticas', index=False)
        df_assign.to_excel(writer, sheet_name='Asignaciones', index=False)
        df_window_times.to_excel(writer, sheet_name='Tiempos_Ventanas', index=False)

        # Resumen de couriers
        resumen_couriers = pd.DataFrame([
            {
                'courier_id': cid,
                'vehicle': c['vehicle'],
                'assigned_routes_count': len(c['assigned_routes']),
                'next_available_min': c.get('available_at')
            }
            for cid, c in couriers.items()
        ])
        resumen_couriers.to_excel(writer, sheet_name='Couriers', index=False)

    print(f"\n{'='*60}")
    print(f"RESULTADOS - {instance_name}")
    print(f"{'='*60}")
    print(f"Total órdenes:           {total_orders:,}")
    print(f"Órdenes asignadas:       {assigned_orders_count:,}")
    print(f"Tasa de cobertura:       {coverage_rate:.2f}%")
    print(f"Rutas creadas:           {len(assignments):,}")
    print(f"Domiciliarios usados:    {len(unique_couriers):,}")
    print(f"Tiempo promedio viaje:   {avg_travel:.2f} min")
    print(f"Tiempo total ejecución:  {execution_time_total:.2f} s")
    print(f"Ventanas con timeout:    {exceeded_count}/{len(window_times)}")
    print(f"\n✅ Resultados guardados en: {out_path}")
    print(f"{'='*60}\n")

    return out_path

# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    import sys

    # Obtener nombre de instancia desde argumentos
    if len(sys.argv) > 1:
        instance_name = sys.argv[1]
    else:
        instance_name = 'Instancia_18'  # Default

    print(f"\n{'='*60}")
    print(f"MODELO CORPORATIVO CON LOOKAHEAD")
    print(f"{'='*60}")
    print(f"Instancia:           {instance_name}")
    print(f"Lookahead:           {LOOKAHEAD_MINUTES} min ({LOOKAHEAD_PERIODS} períodos)")
    print(f"Rolling Horizon:     {ROLLING_HORIZON_STEP} min")
    print(f"Max tiempo/ventana:  {MAX_TIME_PER_WINDOW} s")
    print(f"{'='*60}\n")

    # Cargar datos
    print("Cargando datos...")
    start_load = time.time()
    df_couriers, df_stores, df_orders, subcarpeta = load_instance(instance_name)
    print(f"✓ Datos cargados en {time.time() - start_load:.2f}s")
    print(f"  - Couriers: {len(df_couriers):,}")
    print(f"  - Stores:   {len(df_stores):,}")
    print(f"  - Orders:   {len(df_orders):,}\n")

    # Preparar estructuras
    print("Preparando estructuras...")
    start_min = 0
    end_min = 1440
    orders = prepare_orders(df_orders)
    couriers = prepare_couriers(df_couriers, start_min, end_min)
    print(f"✓ Estructuras preparadas\n")

    # Ejecutar optimización
    print("Iniciando optimización con lookahead...\n")
    start_opt = time.time()

    assignments, window_times = optimize_with_lookahead(
        couriers, orders, df_stores, start_min, end_min
    )

    execution_time_total = time.time() - start_opt

    # Guardar resultados
    output_folder = 'outputs_corporativo_lookahead'
    save_results(
        assignments, couriers, orders, window_times,
        output_folder, instance_name, execution_time_total
    )
