"""
Builds tests/fixtures/hier/toy.json -- the didactic round used by the deck
(docs/mdrp-jerarquia-objetivos.html), the tests and `diag_hier_case.py --toy`.

Units: metres and minutes; speed 1000 m/min so 1 km = 1 min and every number
can be checked by hand. Round at t = 0. Two restaurants (A, B), four orders,
three idle couriers with different earnings so far.
"""
import json, os

doc = {
    'version': 1, 'time': 0.0,
    'params': {'meters_per_minute': 1000.0, 'pickup_service_min': 2.0, 'dropoff_service_min': 2.0,
               'late_tolerance_min': 0.0, 'max_bundle_size': 2, 'pay_per_order': 10.0,
               'guaranteed_pay_per_hour': 15.0, 'top_k': 3, 'order': None},
    'couriers': [
        {'id': 1, 'x': 0.0,     'y': -2000.0, 'on_time': -120, 'off_time': 240, 'earnings': 8.0,  'orders_delivered': 1, 'active_time': 60.0, 'dist_traveled': 6.0},
        {'id': 2, 'x': 5000.0,  'y': 0.0,     'on_time': -120, 'off_time': 240, 'earnings': 30.0, 'orders_delivered': 3, 'active_time': 60.0, 'dist_traveled': 20.0},
        {'id': 3, 'x': 10000.0, 'y': -3000.0, 'on_time': -120, 'off_time': 240, 'earnings': 14.0, 'orders_delivered': 2, 'active_time': 60.0, 'dist_traveled': 12.0},
    ],
    'orders': [
        {'id': 1, 'placement_time': -20.0, 'ready_time': -2.0, 'store': [0.0, 0.0],     'user': [0.0, 5000.0],     'target_click_to_door': 30.0, 'max_click_to_door': 60.0, 'rejected_by': []},
        {'id': 2, 'placement_time': -8.0,  'ready_time': 0.0,  'store': [0.0, 0.0],     'user': [3000.0, 4000.0],  'target_click_to_door': 30.0, 'max_click_to_door': 60.0, 'rejected_by': []},
        {'id': 3, 'placement_time': -24.0, 'ready_time': -3.0, 'store': [10000.0, 0.0], 'user': [10000.0, 6000.0], 'target_click_to_door': 30.0, 'max_click_to_door': 60.0, 'rejected_by': []},
        {'id': 4, 'placement_time': -4.0,  'ready_time': 1.0,  'store': [10000.0, 0.0], 'user': [14000.0, 3000.0], 'target_click_to_door': 30.0, 'max_click_to_door': 60.0, 'rejected_by': []},
    ],
}
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'toy.json')
with open(out, 'w', encoding='utf8') as f:
    json.dump(doc, f, indent=1)
print('wrote', out)
