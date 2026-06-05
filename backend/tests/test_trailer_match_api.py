"""API tests for Trailer Match delivery quote tracking."""


def test_delivery_quote_click_sets_flag(client, db_store):
    rid = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
    db_store["trailer_match_requests"] = [
        {
            "id": rid,
            "delivery_quote_clicked": False,
        }
    ]
    res = client.post(f"/trailer-match/requests/{rid}/delivery-quote-click")
    assert res.status_code == 200
    assert res.json() == {"ok": True}
    row = db_store["trailer_match_requests"][0]
    assert row.get("delivery_quote_clicked") is True


def test_delivery_quote_click_404_unknown_id(client, db_store):
    db_store["trailer_match_requests"] = []
    res = client.post("/trailer-match/requests/b1eebc99-9c0b-4ef8-bb6d-6bb9bd380a22/delivery-quote-click")
    assert res.status_code == 404


def test_assistant_persists_delivery_cta_fields(client, db_store):
    """POST /trailer-match/assistant stores delivery CTA emphasis flags."""
    body = {
        "year": 2021,
        "make": "Ford",
        "model": "F-150",
        "trim_or_engine": None,
        "tow_package": "unknown",
        "brake_controller": "unknown",
        "towing_experience": "first_time",
        "load_type": "mulch",
        "estimated_amount": "y1",
        "session_id": "sess-test",
    }
    res = client.post("/trailer-match/assistant", json=body)
    assert res.status_code == 201
    j = res.json()
    assert j["mode"] == "single_trailer"
    assert j["recommended"] is not None
    assert j["job_fit"] in ("low", "medium", "high")
    assert j["vehicle_fit"] in ("low", "medium", "high")
    assert j["driver_fit"] in ("low", "medium", "high")
    assert j["overall_confidence"] in ("low", "medium", "high")
    assert j["confidence"] == j["overall_confidence"]
    assert isinstance(j["ctas"], list)
    assert j["follow_up_cta"] in ("book", "ask_confirm")
    assert "delivery_cta_emphasized" in j
    rows = db_store.get("trailer_match_requests") or []
    assert len(rows) == 1
    row = rows[0]
    assert "delivery_cta_shown" in row
    assert "delivery_quote_clicked" in row
    assert row.get("delivery_quote_clicked") is False
    assert row.get("mode") == "single_trailer"
    assert row.get("job_fit") in ("low", "medium", "high")