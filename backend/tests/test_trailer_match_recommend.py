"""Unit tests for Trailer Match Assistant recommendation logic and delivery CTA emphasis."""

import pytest

from app.services.trailer_match_recommend import (
    TrailerKind,
    TrailerMatchInput,
    compute_delivery_cta_emphasis,
    estimate_trips,
    recommend_trailer,
)


def _inp(
    *,
    year=2020,
    make="Ford",
    model="F-150",
    trim=None,
    tow_package="unknown",
    brake="unknown",
    experience="first_time",
    load="mulch",
    amount="y1",
) -> TrailerMatchInput:
    return TrailerMatchInput(
        year=year,
        make=make,
        model=model,
        trim_or_engine=trim,
        tow_package=tow_package,  # type: ignore[arg-type]
        brake_controller=brake,  # type: ignore[arg-type]
        towing_experience=experience,  # type: ignore[arg-type]
        load_type=load,  # type: ignore[arg-type]
        estimated_amount=amount,  # type: ignore[arg-type]
    )


# --- Required scenarios (product spec) ---


def test_scenario_problem_f150_no_tow_first_time_three_yards_heavy():
    """2002 F-150, incomplete vehicle, no tow package, first time, ~3 cy dense load → multi-load 10′ 7k."""
    r = recommend_trailer(
        _inp(
            year=2002,
            make="Ford",
            model="F-150",
            trim=None,
            tow_package="no",
            brake="unknown",
            experience="first_time",
            load="gravel",
            amount="y3",
        )
    )
    assert r.mode == "multi_load"
    assert r.recommended_trailer == TrailerKind.ten_seven
    assert r.trailer_for_load == TrailerKind.twelve_twelve
    assert r.estimated_trips in (2, 3)
    assert r.vehicle_fit == "low"
    assert r.driver_fit in ("low", "medium")
    assert r.overall_confidence != "high"
    joined = " ".join(r.warnings).lower()
    assert "towing capacity" in joined or "verify" in joined


def test_scenario_strong_truck_gravel_three_yards_single_twelve_twelve():
    r = recommend_trailer(
        _inp(
            year=2022,
            make="Ford",
            model="F-250",
            trim="6.7L",
            tow_package="yes",
            brake="yes",
            experience="experienced",
            load="gravel",
            amount="y3",
        )
    )
    assert r.mode == "single_trailer"
    assert r.recommended_trailer == TrailerKind.twelve_twelve
    assert r.vehicle_fit in ("high", "medium")
    assert r.overall_confidence in ("medium", "high")


def test_scenario_unknown_brake_half_ton_topsoil_three_yards():
    r = recommend_trailer(
        _inp(
            experience="some",
            model="F-150",
            load="topsoil",
            amount="y3",
            brake="unknown",
            tow_package="yes",
            trim="5.0L",
        )
    )
    assert any("brake" in w.lower() for w in r.warnings)
    assert r.overall_confidence != "high"
    assert r.recommended_trailer in (TrailerKind.twelve_ten, TrailerKind.twelve_twelve)


def test_scenario_light_mulch_two_yards_incomplete_vehicle_not_twelve_twelve():
    r = recommend_trailer(
        _inp(
            model="F-150",
            tow_package="unknown",
            experience="first_time",
            load="mulch",
            amount="y2",
            trim=None,
        )
    )
    assert r.recommended_trailer != TrailerKind.twelve_twelve
    assert r.overall_confidence != "high"


def test_scenario_first_time_heavy_two_plus_yards_prefers_multi_or_contact():
    r = recommend_trailer(
        _inp(
            experience="first_time",
            model="F-150",
            load="gravel",
            amount="y2",
            tow_package="unknown",
            brake="unknown",
        )
    )
    assert r.mode == "multi_load"
    assert r.recommended_trailer == TrailerKind.ten_seven


# --- estimate_trips ---


@pytest.mark.parametrize(
    ("load", "amount", "want"),
    [
        ("gravel", "y3", 3),
        ("topsoil", "y3", 3),
        ("construction", "y4", 4),
        ("gravel", "y2", 2),
    ],
)
def test_estimate_trips_examples(load, amount, want):
    assert estimate_trips(load, amount, TrailerKind.ten_seven) == want  # type: ignore[arg-type]


# --- Regression / edge ---


def test_first_time_half_ton_one_yard_mulch_recommends_10_7k():
    r = recommend_trailer(_inp(experience="first_time", model="F-150", load="mulch", amount="y1"))
    assert r.recommended_trailer == TrailerKind.ten_seven


def test_half_ton_three_yards_mulch_some_experience_recommends_12_10k():
    r = recommend_trailer(_inp(experience="some", model="Silverado 1500", load="mulch", amount="y3"))
    assert r.recommended_trailer == TrailerKind.twelve_ten


def test_half_ton_three_yards_gravel_risky_setup_multi_load_not_twelve_twelve_primary():
    r = recommend_trailer(
        _inp(experience="first_time", model="F-150", load="gravel", amount="y3", tow_package="unknown")
    )
    assert r.mode == "multi_load"
    assert r.recommended_trailer == TrailerKind.ten_seven
    assert r.trailer_for_load == TrailerKind.twelve_twelve


def test_three_quarter_ton_four_yards_topsoil_recommends_12_12k():
    r = recommend_trailer(_inp(experience="experienced", model="F-250", load="topsoil", amount="y4"))
    assert r.recommended_trailer == TrailerKind.twelve_twelve


def test_four_yards_gravel_tacoma_recommends_12_12k():
    r = recommend_trailer(_inp(make="Toyota", model="Tacoma", load="gravel", amount="y4", experience="some"))
    assert r.recommended_trailer == TrailerKind.twelve_twelve


def test_unknown_brake_controller_warns_for_12_10k():
    r = recommend_trailer(_inp(experience="some", model="F-150", load="mulch", amount="y2", brake="unknown"))
    assert r.recommended_trailer == TrailerKind.twelve_ten
    assert any("brake" in w.lower() for w in r.warnings)


def test_other_load_contact_required():
    r = recommend_trailer(_inp(load="other", amount="y2", experience="experienced"))
    assert r.mode == "contact_required"
    assert r.recommended_trailer is None
    assert r.overall_confidence == "low"
    assert r.follow_up_cta == "ask_confirm"


def test_household_first_time_one_vs_three_yards():
    a = recommend_trailer(_inp(load="household", amount="y1", experience="first_time"))
    assert a.recommended_trailer == TrailerKind.ten_seven
    b = recommend_trailer(_inp(load="household", amount="y3", experience="first_time"))
    assert b.recommended_trailer == TrailerKind.twelve_ten


def test_construction_two_plus_yards_heavy_option():
    r = recommend_trailer(_inp(load="construction", amount="y2", experience="experienced", model="F-150"))
    assert r.recommended_trailer == TrailerKind.twelve_twelve
    assert any("construction" in w.lower() for w in r.warnings)


def test_unsure_amount_mulch_low_confidence():
    r = recommend_trailer(_inp(load="mulch", amount="unsure", experience="first_time"))
    assert r.overall_confidence == "low"
    assert r.recommended_trailer == TrailerKind.twelve_ten
    assert r.follow_up_cta == "ask_confirm"


def test_delivery_not_in_recommendation_input_identical_results():
    base = dict(make="Chevrolet", model="Colorado", experience="experienced", load="mulch", amount="y2")
    a = recommend_trailer(_inp(**base))
    b = recommend_trailer(_inp(**base))
    assert a.recommended_trailer == b.recommended_trailer
    assert a.alternative_trailer == b.alternative_trailer


def test_first_time_12_10k_delivery_cta_emphasized():
    inp = _inp(experience="first_time", model="F-150", load="mulch", amount="y3", brake="yes", tow_package="yes")
    res = recommend_trailer(inp)
    assert res.recommended_trailer == TrailerKind.twelve_ten
    meta = compute_delivery_cta_emphasis(inp, res)
    assert meta.delivery_cta_shown is True
    assert meta.delivery_cta_reason and "first-time" in meta.delivery_cta_reason.lower()


def test_heavy_material_delivery_cta_emphasized():
    inp = _inp(load="gravel", amount="y2", experience="experienced", model="F-150", brake="yes", tow_package="yes")
    res = recommend_trailer(inp)
    meta = compute_delivery_cta_emphasis(inp, res)
    assert meta.delivery_cta_shown is True
    assert "dense" in (meta.delivery_cta_reason or "").lower()


def test_brake_unknown_12k_recommendation_delivery_cta_emphasized():
    inp = _inp(load="gravel", amount="y3", experience="some", model="F-150", brake="unknown", tow_package="yes")
    res = recommend_trailer(inp)
    assert res.recommended_trailer == TrailerKind.twelve_twelve
    meta = compute_delivery_cta_emphasis(inp, res)
    assert meta.delivery_cta_shown is True
    assert "brake" in (meta.delivery_cta_reason or "").lower()


def test_multi_load_includes_ctas():
    r = recommend_trailer(
        _inp(year=2002, tow_package="no", experience="first_time", load="topsoil", amount="y3", trim=None)
    )
    assert r.mode == "multi_load"
    assert "Book" in r.ctas[0]
    assert "Ask us to confirm" in r.ctas[1]
