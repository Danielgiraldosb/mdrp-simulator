"""
Tests for loader_real.py (Etapa 2). Run: python -m pytest tests/test_loader_real.py -q

Fixture tests/fixtures/real/Instancia_T (Bogota-like): 5 couriers (one in
Cartagena), 3 stores (one 80 km away), 6 orders (one at the far store, one
at a missing store, one in the late window).
"""
import math
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from config import Config  # noqa: E402
from distance import dist_m, speed_of  # noqa: E402
from loader_real import (haversine_m, hms_to_min, is_real_dir, is_real_instance,  # noqa: E402
                         list_real_instances, load_real_instance, nearest_city, parse_speeds,
                         project)
from routing import route_feasibility  # noqa: E402

FIX = os.path.join(ROOT, 'tests', 'fixtures', 'real')
C = (4.65, -74.10)


# -- helpers --------------------------------------------------------------------------------------

def test_hms_to_min():
    assert hms_to_min('0:00:03') == pytest.approx(0.05)
    assert hms_to_min('1:01:05') == pytest.approx(61 + 5 / 60)
    assert hms_to_min('23:55:02') == pytest.approx(23 * 60 + 55 + 2 / 60)
    assert hms_to_min('9:30') == 570.0


def test_projection_matches_haversine_within_0_1_percent():
    pts = [(4.50, -74.22), (4.80, -74.00), (4.65, -74.10), (4.72, -74.15)]
    for (la1, lo1) in pts:
        for (la2, lo2) in pts:
            if (la1, lo1) == (la2, lo2):
                continue
            d_proj = dist_m(project(la1, lo1, C), project(la2, lo2, C))
            d_hav = haversine_m(la1, lo1, la2, lo2)
            assert abs(d_proj - d_hav) / d_hav < 1e-3


def test_projection_origin_and_circuity():
    o = project(C[0], C[1], C)
    assert o.x == pytest.approx(0.0) and o.y == pytest.approx(0.0)
    a, b = project(4.60, -74.05, C), project(4.70, -74.15, C)
    a2, b2 = project(4.60, -74.05, C, circuity=1.3), project(4.70, -74.15, C, circuity=1.3)
    assert dist_m(a2, b2) == pytest.approx(1.3 * dist_m(a, b))


def test_nearest_city():
    assert nearest_city(4.66, -74.08) == 'Bogota'
    assert nearest_city(4.81, -75.70) == 'Pereira'
    assert nearest_city(7.10, -73.12) == 'Bucaramanga'
    assert nearest_city(10.95, -74.80) == 'Barranquilla'
    assert nearest_city(0.0, 0.0) == 'unknown'


def test_parse_speeds():
    assert parse_speeds(['bicycle=15', 'Motorcycle=27.5']) == {'bicycle': 15.0, 'motorcycle': 27.5}
    with pytest.raises(ValueError):
        parse_speeds(['bicycle'])


# -- discovery ------------------------------------------------------------------------------------

def test_discovery():
    assert is_real_dir(FIX)
    assert is_real_instance('Instancia_T', FIX)
    assert not is_real_instance('nope', FIX)
    assert list_real_instances(FIX) == ['Instancia_T']
    assert not is_real_dir(os.path.join(FIX, 'does_not_exist'))


# -- loading --------------------------------------------------------------------------------------

@pytest.fixture
def loaded():
    cfg = Config(seed=1)
    inst = load_real_instance('Instancia_T', FIX, cfg)
    return cfg, inst


def test_center_and_city(loaded):
    _, inst = loaded
    meta = inst['meta']
    assert meta['source'] == 'real' and meta['city'] == 'Bogota'
    # median of the 3 store coordinates: lat (4.65, 4.68, 5.30) -> 4.68, lng (-74.09, -74.06, -74.60) -> -74.09
    assert meta['center'] == pytest.approx((4.68, -74.09))


def test_filters_and_counts(loaded):
    cfg, inst = loaded
    meta = inst['meta']
    # c4 is in Cartagena -> farther than real_max_radius_km
    assert len(inst['couriers']) == 4
    assert meta['dropped']['couriers_far'] == 1
    # s3 is 80 km away -> dropped; o3 then has no store
    assert len(inst['stores']) == 2
    assert meta['dropped']['stores_far'] == 1
    # o3 (store dropped) and o5 (unknown store) dropped; o1,o2,o4,o6 kept
    assert sorted(o.order_id for o in inst['orders']) == [1, 2, 4, 6]
    assert meta['dropped']['orders_no_store'] == 2
    assert meta['vehicles'] == {'motorcycle': 2, 'bicycle': 1, 'walking': 1}


def test_courier_fields_and_speeds(loaded):
    cfg, inst = loaded
    by_id = {c.courier_id: c for c in inst['couriers']}
    assert by_id[1].vehicle == 'motorcycle'
    assert by_id[1].speed_m_per_min == pytest.approx(25 * 1000 / 60)
    assert by_id[2].speed_m_per_min == pytest.approx(15 * 1000 / 60)
    assert by_id[3].speed_m_per_min == pytest.approx(5 * 1000 / 60)
    assert speed_of(by_id[2], cfg) == by_id[2].speed_m_per_min
    # times in minutes from midnight (window starts at 0)
    assert by_id[2].on_time == pytest.approx(8 * 60)
    assert by_id[2].off_time == pytest.approx(19 * 60)
    assert by_id[1].off_time == pytest.approx(23 * 60 + 55 + 2 / 60)
    # the courier starts at its log-on point, projected around the centre
    assert dist_m(by_id[1].home_loc, project(4.65, -74.10, inst['meta']['center'])) == pytest.approx(0.0)
    # fleet mean speed written back for display
    assert cfg.meters_per_minute == pytest.approx((2 * 25 + 15 + 5) / 4 * 1000 / 60)


def test_order_sla_from_expected_drop_off(loaded):
    cfg, inst = loaded
    o = {o.order_id: o for o in inst['orders']}
    # o1: placement 0:01:05, expected 1:01:05 -> 60 min soft, 90 hard
    assert o[1].target_click_to_door == pytest.approx(60.0)
    assert o[1].max_click_to_door == pytest.approx(60.0 + cfg.real_max_ctd_extra_min)
    assert o[1].ready_time == pytest.approx(hms_to_min('0:06:53'))
    # o2: 9:01:49 -> 9:31:49 = 30 min
    assert o[2].target_click_to_door == pytest.approx(30.0)
    assert o[2].placement_time == pytest.approx(hms_to_min('9:01:49'))
    # store -> drop-off distance for o1 (4.65,-74.09)->(4.66,-74.09) ~ 1.11 km
    assert dist_m(o[1].store_loc, o[1].user_loc) == pytest.approx(haversine_m(4.65, -74.09, 4.66, -74.09), rel=1e-3)


def test_economics_written_back(loaded):
    cfg, _ = loaded
    assert cfg.pay_per_order == 2200.0
    assert cfg.guaranteed_pay_per_hour == 0.0
    assert cfg.min_wage_hourly == pytest.approx(4367.91)
    assert cfg.pickup_service_min == 20.0
    assert cfg.decision_mean_min == pytest.approx(16 / 60)


def test_min_wage_override_is_kept():
    cfg = Config(seed=1, min_wage_hourly=5000.0)
    load_real_instance('Instancia_T', FIX, cfg)
    assert cfg.min_wage_hourly == 5000.0


def test_time_window_filter():
    cfg = Config(seed=1, sim_start_clock_min=8 * 60, sim_end=4 * 60)   # 08:00-12:00
    inst = load_real_instance('Instancia_T', FIX, cfg)
    assert sorted(o.order_id for o in inst['orders']) == [2, 4]
    assert inst['orders'][0].placement_time == pytest.approx(hms_to_min('9:01:49') - 480)
    ids = sorted(c.courier_id for c in inst['couriers'])
    assert ids == [1, 2, 3]            # c5 logs on at 22:00 -> outside window
    c1 = next(c for c in inst['couriers'] if c.courier_id == 1)
    assert c1.on_time == 0.0 and c1.off_time == 240.0


def test_circuity_scales_distances():
    cfg_a, cfg_b = Config(seed=1), Config(seed=1, real_circuity=1.3)
    a = load_real_instance('Instancia_T', FIX, cfg_a)
    b = load_real_instance('Instancia_T', FIX, cfg_b)
    oa = next(o for o in a['orders'] if o.order_id == 1)
    ob = next(o for o in b['orders'] if o.order_id == 1)
    assert dist_m(ob.store_loc, ob.user_loc) == pytest.approx(1.3 * dist_m(oa.store_loc, oa.user_loc))


def test_explicit_center_and_radius():
    # a 1,000 km radius keeps the Cartagena courier (~650 km) and the far store
    cfg = Config(seed=1, real_max_radius_km=1000.0)
    inst = load_real_instance('Instancia_T', FIX, cfg, center=(4.65, -74.10))
    assert len(inst['couriers']) == 5 and len(inst['stores']) == 3
    assert inst['meta']['center'] == (4.65, -74.10)


def test_unknown_vehicle_raises():
    cfg = Config(seed=1, real_speeds_kmh={'bicycle': 15.0})
    with pytest.raises(ValueError):
        load_real_instance('Instancia_T', FIX, cfg)


def test_per_vehicle_speed_drives_feasibility(loaded):
    """Same order, same place: the walker's travel time must exceed the motorcycle's."""
    cfg, inst = loaded
    by_id = {c.courier_id: c for c in inst['couriers']}
    o = next(o for o in inst['orders'] if o.order_id == 4)
    by_id[1].location = by_id[3].location = o.store_loc.copy()
    moto = route_feasibility(by_id[1], (o,), o.placement_time, cfg)
    walk = route_feasibility(by_id[3], (o,), o.placement_time, cfg)
    assert moto is not None
    d = dist_m(o.store_loc, o.user_loc)
    assert moto['total_tt'] == pytest.approx(math.ceil(d / by_id[1].speed_m_per_min)
                                             + cfg.pickup_service_min + cfg.dropoff_service_min)
    if walk is not None:
        assert walk['total_tt'] > moto['total_tt']
