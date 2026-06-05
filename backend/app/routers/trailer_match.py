"""Public Trailer Match Assistant + admin listing."""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from app.deps import get_supabase_client, optional_customer_jwt_claims
from app.schemas import (
    TrailerMatchAssistantIn,
    TrailerMatchAssistantOut,
    TrailerMatchConfidence,
    TrailerMatchDeliveryQuoteClickOut,
    TrailerMatchFollowUp,
    TrailerMatchMode,
    TrailerMatchRequestAdminRow,
    TrailerMatchTier,
    TrailerMatchTrailerCard,
)
from app.services.trailer_match_recommend import (
    TrailerKind,
    TrailerMatchInput,
    compute_delivery_cta_emphasis,
    recommend_trailer,
    trailer_kind_public_label,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/trailer-match", tags=["trailer-match"])

LEGAL_DISCLAIMER = (
    "This assistant is a planning tool only—not a certified safety calculator. "
    "You are responsible for verifying your vehicle’s towing capacity, payload rating, "
    "hitch rating, brake controller requirements, and all applicable laws before towing."
)

ESTIMATE_DISCLAIMER = (
    "Material weights vary with moisture, compaction, and how the trailer is loaded. "
    "Treat every number here as a rough estimate, not a guarantee."
)

TRAILER_BLURB = {
    TrailerKind.ten_seven: "Smaller box, easier to swing in tight driveways; best when the load stays lighter.",
    TrailerKind.twelve_ten: "Our most popular 12′ dump—extra length for mulch and mixed jobs without jumping to the heaviest axle.",
    TrailerKind.twelve_twelve: "Heavy-duty 12′ option when dense material or bigger jobs need more payload breathing room.",
}


def _title_match_score(title: str, kind: TrailerKind) -> int:
    t = title.lower()
    if "dump" not in t and "trailer" not in t:
        return 0
    score = 0
    if kind == TrailerKind.ten_seven:
        if "10" in t:
            score += 2
        if "7k" in t or "7 k" in t or "7000" in t:
            score += 3
    elif kind == TrailerKind.twelve_ten:
        if "12" in t:
            score += 2
        if "10k" in t or "10 k" in t or "10000" in t:
            score += 3
        if "12k" in t and "10k" not in t:
            score -= 2
    elif kind == TrailerKind.twelve_twelve:
        if "12" in t:
            score += 2
        if ("12k" in t or "12 k" in t) and "10k" not in t:
            score += 3
        if "10k" in t:
            score -= 2
    return score


def resolve_catalog_item_for_trailer(client: Client, kind: TrailerKind) -> str | None:
    try:
        res = client.table("items").select("id,title,active").eq("active", True).execute()
    except Exception:
        log.exception("trailer_match catalog lookup failed")
        return None
    best: tuple[int, str] = (0, "")
    for row in res.data or []:
        title = str(row.get("title") or "")
        sc = _title_match_score(title, kind)
        if sc > best[0]:
            best = (sc, str(row.get("id") or ""))
    if best[0] >= 4 and best[1]:
        return best[1]
    return None


def _kind_to_schema_tier(k: TrailerKind) -> TrailerMatchTier:
    return TrailerMatchTier(k.value)


def _parse_uuid(request_id: str) -> str:
    try:
        return str(uuid.UUID(request_id.strip()))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request id.",
        ) from e


@router.post("/assistant", response_model=TrailerMatchAssistantOut, status_code=status.HTTP_201_CREATED)
def trailer_match_assistant(
    body: TrailerMatchAssistantIn,
    customer: Annotated[dict | None, Depends(optional_customer_jwt_claims)] = None,
    client: Client = Depends(get_supabase_client),
) -> TrailerMatchAssistantOut:
    inp = TrailerMatchInput(
        year=body.year,
        make=body.make,
        model=body.model,
        trim_or_engine=body.trim_or_engine,
        tow_package=body.tow_package.value,  # type: ignore[arg-type]
        brake_controller=body.brake_controller.value,  # type: ignore[arg-type]
        towing_experience=body.towing_experience.value,  # type: ignore[arg-type]
        load_type=body.load_type.value,  # type: ignore[arg-type]
        estimated_amount=body.estimated_amount.value,  # type: ignore[arg-type]
    )
    result = recommend_trailer(inp)
    delivery_meta = compute_delivery_cta_emphasis(inp, result)

    auth_sub: str | None = None
    if customer is not None:
        raw = customer.get("sub")
        auth_sub = str(raw).strip() if raw else None

    item_id = (
        resolve_catalog_item_for_trailer(client, result.recommended_trailer)
        if result.recommended_trailer
        else None
    )

    row = {
        "year": body.year,
        "make": body.make.strip(),
        "model": body.model.strip(),
        "trim_or_engine": (body.trim_or_engine or "").strip() or None,
        "tow_package": body.tow_package.value,
        "brake_controller": body.brake_controller.value,
        "towing_experience": body.towing_experience.value,
        "load_type": body.load_type.value,
        "estimated_amount": body.estimated_amount.value,
        "estimated_weight_min": result.estimated_weight_min_lbs,
        "estimated_weight_max": result.estimated_weight_max_lbs,
        "mode": result.mode,
        "trailer_for_load": result.trailer_for_load.value if result.trailer_for_load else None,
        "estimated_trips": result.estimated_trips,
        "job_fit": result.job_fit,
        "vehicle_fit": result.vehicle_fit,
        "driver_fit": result.driver_fit,
        "recommended_trailer_type": result.recommended_trailer.value if result.recommended_trailer else None,
        "alternative_trailer_type": result.alternative_trailer.value,
        "warnings": result.warnings,
        "reasons": result.reasons,
        "confidence": result.confidence,
        "cta_suggestion": result.follow_up_cta,
        "delivery_cta_shown": delivery_meta.delivery_cta_shown,
        "delivery_cta_reason": delivery_meta.delivery_cta_reason,
        "delivery_quote_clicked": False,
        "session_id": (body.session_id or "").strip() or None,
        "customer_auth0_sub": auth_sub,
        "recommended_catalog_item_id": item_id,
    }
    try:
        ins = client.table("trailer_match_requests").insert(row).execute()
    except Exception as exc:
        log.exception("trailer_match_requests insert failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not save your answers right now. Please try again in a moment.",
        ) from exc
    data = ins.data or []
    if not data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Insert failed")
    rid = str(data[0]["id"])

    rec = result.recommended_trailer
    alt = result.alternative_trailer
    rec_card = (
        TrailerMatchTrailerCard(
            type=_kind_to_schema_tier(rec),
            title=trailer_kind_public_label(rec),
            blurb=TRAILER_BLURB[rec],
        )
        if rec
        else None
    )
    tfl = result.trailer_for_load
    oc = TrailerMatchConfidence(result.overall_confidence)
    return TrailerMatchAssistantOut(
        id=rid,
        mode=TrailerMatchMode(result.mode),
        recommended=rec_card,
        trailer_for_load=_kind_to_schema_tier(tfl) if tfl else None,
        trailer_for_load_title=trailer_kind_public_label(tfl) if tfl else None,
        estimated_trips=result.estimated_trips,
        job_fit=TrailerMatchConfidence(result.job_fit),
        vehicle_fit=TrailerMatchConfidence(result.vehicle_fit),
        driver_fit=TrailerMatchConfidence(result.driver_fit),
        overall_confidence=oc,
        alternative=TrailerMatchTrailerCard(
            type=_kind_to_schema_tier(alt),
            title=trailer_kind_public_label(alt),
            blurb=TRAILER_BLURB[alt],
        ),
        estimated_weight_min_lbs=result.estimated_weight_min_lbs,
        estimated_weight_max_lbs=result.estimated_weight_max_lbs,
        confidence=oc,
        reasons=result.reasons,
        warnings=result.warnings,
        ctas=result.ctas,
        follow_up_cta=TrailerMatchFollowUp(result.follow_up_cta),
        delivery_cta_emphasized=delivery_meta.delivery_cta_shown,
        delivery_cta_reason=delivery_meta.delivery_cta_reason,
        recommended_catalog_item_id=item_id,
        legal_disclaimer=LEGAL_DISCLAIMER,
        estimate_disclaimer=ESTIMATE_DISCLAIMER,
    )


@router.post(
    "/requests/{request_id}/delivery-quote-click",
    response_model=TrailerMatchDeliveryQuoteClickOut,
    status_code=status.HTTP_200_OK,
)
def trailer_match_delivery_quote_click(
    request_id: str,
    client: Client = Depends(get_supabase_client),
) -> TrailerMatchDeliveryQuoteClickOut:
    rid = _parse_uuid(request_id)
    try:
        res = (
            client.table("trailer_match_requests")
            .update({"delivery_quote_clicked": True})
            .eq("id", rid)
            .execute()
        )
    except Exception as exc:
        log.exception("trailer_match_requests delivery_quote_clicked update failed id=%s", rid)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not record that action. You can still email us from the link we opened.",
        ) from exc
    rows = getattr(res, "data", None) or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match request not found.")
    return TrailerMatchDeliveryQuoteClickOut(ok=True)
