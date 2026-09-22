from app.psychometrics.presentation import (
    DEFAULT_BLOCK_ORDER,
    mulberry32,
    present_items,
    normalize_presentation,
)


def test_default_presentation_is_231():
    spec = normalize_presentation(None)
    assert spec["block_order"] == list(DEFAULT_BLOCK_ORDER)
    assert spec["shuffle_modules"] == ["avp"]


def test_present_items_reorders_modules_without_shuffle():
    items = [
        {"code": "DISC-01", "module": "disc"},
        {"code": "AVP-001", "module": "avp"},
        {"code": "AVP-002", "module": "avp"},
        {"code": "SJT-01", "module": "sjt"},
    ]
    shown = present_items(items, shuffle=False)
    assert [i["module"] for i in shown] == ["avp", "avp", "sjt", "disc"]
    assert [i["code"] for i in shown] == ["AVP-001", "AVP-002", "SJT-01", "DISC-01"]


def test_present_items_shuffles_only_avp_deterministically():
    items = [{"code": f"AVP-{i:03d}", "module": "avp"} for i in range(1, 9)]
    items += [{"code": "SJT-01", "module": "sjt"}, {"code": "DISC-01", "module": "disc"}]
    a = [i["code"] for i in present_items(items, seed=42)]
    b = [i["code"] for i in present_items(items, seed=42)]
    c = [i["code"] for i in present_items(items, seed=99)]
    assert a == b
    assert a != c
    assert a[-2:] == ["SJT-01", "DISC-01"]
    assert set(a[:8]) == {f"AVP-{i:03d}" for i in range(1, 9)}
    assert a[:8] != [f"AVP-{i:03d}" for i in range(1, 9)]


def test_mulberry32_stays_in_unit_interval():
    rng = mulberry32(1)
    values = [rng() for _ in range(50)]
    assert all(0 <= v < 1 for v in values)
