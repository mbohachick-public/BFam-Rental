"""
Trailer Match Assistant — planning guidance (not a certified safety calculator).

Balances material fit, tow-vehicle hints, and driver experience. Can recommend
multi-load plans on the 10′ 7k when a single larger trailer would fit the material
but not the towing profile.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Literal

# --- Enums / keys (API + DB use these string values) ---


class TrailerKind(str, Enum):
    ten_seven = "10_7k"
    twelve_ten = "12_10k"
    twelve_twelve = "12_12k"


TowPackage = Literal["yes", "no", "unknown"]
BrakeController = Literal["yes", "no", "unknown"]
TowingExperience = Literal["first_time", "some", "experienced"]
LoadType = Literal[
    "mulch",
    "topsoil",
    "gravel",
    "brush",
    "construction",
    "household",
    "other",
]
EstimatedAmount = Literal["y1", "y2", "y3", "y4", "y5plus", "unsure"]
FitLevel = Literal["low", "medium", "high"]
Confidence = FitLevel
FollowUpCta = Literal["book", "ask_confirm"]
RecommendationMode = Literal["single_trailer", "multi_load", "contact_required", "delivery_suggested"]

LB_PER_CY: dict[LoadType, tuple[int | None, int | None]] = {
    "mulch": (400, 800),
    "brush": (300, 700),
    "topsoil": (1800, 2400),
    "gravel": (2400, 3000),
    "construction": (1000, 2500),
    "household": (300, 1000),
    "other": (None, None),
}

COMFORT_PAYLOAD_LBS: dict[TrailerKind, int] = {
    TrailerKind.ten_seven: 4000,
    TrailerKind.twelve_ten: 7000,
    TrailerKind.twelve_twelve: 9500,
}

# Practical cubic yards per trip on a 10′ 7k for heavy materials (conservative planning).
CY_PER_TRIP_10_7K: dict[LoadType, float] = {
    "gravel": 1.25,
    "topsoil": 1.25,
    "construction": 1.15,
    "other": 1.2,
    "mulch": 1.5,
    "brush": 1.5,
    "household": 1.4,
}

TRAILER_DISPLAY: dict[TrailerKind, str] = {
    TrailerKind.ten_seven: "10′ 7k dump trailer",
    TrailerKind.twelve_ten: "12′ 10k dump trailer",
    TrailerKind.twelve_twelve: "12′ 12k dump trailer",
}

ORDER = (TrailerKind.ten_seven, TrailerKind.twelve_ten, TrailerKind.twelve_twelve)


def _rank(k: TrailerKind) -> int:
    return ORDER.index(k)


def _min_trailer(a: TrailerKind, b: TrailerKind) -> TrailerKind:
    return a if _rank(a) <= _rank(b) else b


def _max_trailer(a: TrailerKind, b: TrailerKind) -> TrailerKind:
    return a if _rank(a) >= _rank(b) else b


@dataclass(frozen=True)
class TrailerMatchInput:
    year: int
    make: str
    model: str
    trim_or_engine: str | None
    tow_package: TowPackage
    brake_controller: BrakeController
    towing_experience: TowingExperience
    load_type: LoadType
    estimated_amount: EstimatedAmount


@dataclass(frozen=True)
class RecommendationResult:
    mode: RecommendationMode
    recommended_trailer: TrailerKind | None
    trailer_for_load: TrailerKind | None
    estimated_trips: int | None
    job_fit: FitLevel
    vehicle_fit: FitLevel
    driver_fit: FitLevel
    overall_confidence: FitLevel
    estimated_weight_min_lbs: int | None
    estimated_weight_max_lbs: int | None
    reasons: list[str]
    warnings: list[str]
    ctas: list[str]
    follow_up_cta: FollowUpCta
    alternative_trailer: TrailerKind
    confidence: Confidence  # mirrors overall_confidence for API backward compatibility


@dataclass(frozen=True)
class DeliveryCtaEmphasis:
    delivery_cta_shown: bool
    delivery_cta_reason: str | None


def is_heavy_load(load: LoadType) -> bool:
    return load in ("gravel", "topsoil", "construction", "other")


def estimate_trips(load_type: LoadType, estimated_amount: EstimatedAmount, trailer_type: TrailerKind) -> int:
    """Conservative trip count for multi-load plans (10′ 7k oriented)."""
    if trailer_type != TrailerKind.ten_seven:
        return 1
    _, y_max = _yards_range(estimated_amount)
    if not is_heavy_load(load_type):
        return max(1, int(math.ceil(y_max / 2.0)))
    rate = CY_PER_TRIP_10_7K.get(load_type, 1.2)
    return max(1, int(math.ceil(y_max / rate)))


def _fit_ord(f: FitLevel) -> int:
    return {"low": 0, "medium": 1, "high": 2}[f]


def _fit_min(a: FitLevel, b: FitLevel, c: FitLevel) -> FitLevel:
    inv: dict[int, FitLevel] = {0: "low", 1: "medium", 2: "high"}
    return inv[min(_fit_ord(a), _fit_ord(b), _fit_ord(c))]


def _dec_fit(f: FitLevel) -> FitLevel:
    return {"high": "medium", "medium": "low", "low": "low"}[f]


def _vehicle_blob(inp: TrailerMatchInput) -> str:
    parts = [inp.make, inp.model, (inp.trim_or_engine or "")]
    return " ".join(p for p in parts if p).lower()


def infer_vehicle_tier(inp: TrailerMatchInput) -> Literal["heavy", "half", "unknown"]:
    s = _vehicle_blob(inp)
    heavy_markers = (
        "f-250",
        "f250",
        "f-350",
        "f350",
        "2500",
        "3500",
        "3500hd",
        "3/4",
        "one ton",
        "1 ton",
        "4500",
        "5500",
        "dually",
        "super duty",
        "2500hd",
    )
    if any(m in s for m in heavy_markers):
        return "heavy"
    half_markers = (
        "1500",
        "f-150",
        "f150",
        "tundra",
        "titan",
        "ram 1500",
        "tacoma",
        "ranger",
        "colorado",
        "canyon",
        "frontier",
        "ridgeline",
        "gladiator",
    )
    if any(m in s for m in half_markers):
        return "half"
    return "unknown"


def _yards_range(amount: EstimatedAmount) -> tuple[float, float]:
    if amount == "y1":
        return (1.0, 1.0)
    if amount == "y2":
        return (2.0, 2.0)
    if amount == "y3":
        return (3.0, 3.0)
    if amount == "y4":
        return (4.0, 4.0)
    if amount == "y5plus":
        return (5.0, 6.0)
    return (1.0, 3.0)


def _estimate_weight_range(
    load: LoadType, y_min: float, y_max: float
) -> tuple[int | None, int | None]:
    lo_cy, hi_cy = LB_PER_CY[load]
    if lo_cy is None or hi_cy is None:
        return (None, None)
    return (int(y_min * lo_cy), int(y_max * hi_cy))


def _min_trailer_for_weight(max_lb: int) -> TrailerKind:
    for kind in ORDER:
        if max_lb <= COMFORT_PAYLOAD_LBS[kind]:
            return kind
    return TrailerKind.twelve_twelve


def _material_trailer_for_load(
    inp: TrailerMatchInput,
    *,
    y_min: float,
    y_max: float,
    max_lb: int | None,
    vehicle: Literal["heavy", "half", "unknown"],
) -> TrailerKind:
    """Single-trip trailer sized from material + deck rules (not towing comfort)."""
    load = inp.load_type
    if max_lb is None:
        t = TrailerKind.twelve_ten
    else:
        t = _min_trailer_for_weight(max_lb)

    if load == "construction" and y_min >= 2.0:
        t = _max_trailer(t, TrailerKind.twelve_twelve)

    if load == "gravel" and y_max >= 3.0 and vehicle != "heavy":
        t = _max_trailer(t, TrailerKind.twelve_twelve)

    if max_lb is not None:
        if load == "mulch":
            if y_max >= 3.0:
                t = _max_trailer(t, TrailerKind.twelve_ten)
            elif y_max >= 2.0:
                t = _max_trailer(t, TrailerKind.twelve_ten)
        if load == "household" and y_max >= 3.0:
            t = _max_trailer(t, TrailerKind.twelve_ten)
        if vehicle == "heavy" and load == "topsoil" and y_max >= 4.0:
            t = _max_trailer(t, TrailerKind.twelve_twelve)

    return t


def _comfort_adjust_single_trailer(
    inp: TrailerMatchInput,
    base: TrailerKind,
    *,
    y_max: float,
    max_lb: int | None,
    vehicle: Literal["heavy", "half", "unknown"],
) -> TrailerKind:
    """Prefer smaller deck for first-time + very light jobs (same as prior product behavior)."""
    t = base
    load = inp.load_type
    exp = inp.towing_experience
    if max_lb is not None:
        if load == "mulch" and y_max >= 2.0 and exp != "first_time":
            t = _max_trailer(t, TrailerKind.twelve_ten)
        if (
            exp == "first_time"
            and vehicle != "heavy"
            and load in ("mulch", "brush", "household")
            and y_max <= 1.5
            and max_lb <= COMFORT_PAYLOAD_LBS[TrailerKind.ten_seven]
        ):
            t = TrailerKind.ten_seven
    return t


def _vehicle_fit(inp: TrailerMatchInput, for_trailer: TrailerKind) -> FitLevel:
    trim_missing = not (inp.trim_or_engine or "").strip()
    vf: FitLevel = "high"

    if trim_missing:
        vf = "medium"

    if inp.tow_package == "no":
        if is_heavy_load(inp.load_type):
            vf = "low"
        elif vf == "high":
            vf = "medium"
    elif inp.tow_package == "unknown":
        if vf == "high":
            vf = "medium"

    if inp.year <= 2010 and trim_missing:
        vf = _dec_fit(vf)

    if inp.brake_controller in ("no", "unknown") and for_trailer in (
        TrailerKind.twelve_ten,
        TrailerKind.twelve_twelve,
    ):
        if vf == "high":
            vf = "medium"
        elif vf == "medium" and inp.brake_controller == "no":
            vf = "low"

    return vf


def _driver_fit(inp: TrailerMatchInput, for_trailer: TrailerKind, *, y_max: float) -> FitLevel:
    exp = inp.towing_experience
    heavy = is_heavy_load(inp.load_type)
    if exp == "experienced":
        df: FitLevel = "high"
    elif exp == "some":
        df = "medium"
    else:
        df = "medium"
        if for_trailer in (TrailerKind.twelve_ten, TrailerKind.twelve_twelve):
            df = "medium"
        if heavy and y_max >= 2.0:
            df = "low"
        if for_trailer == TrailerKind.twelve_twelve and heavy:
            df = "low"
    return df


def _job_fit(
    load: LoadType,
    max_lb: int | None,
    trailer_for_load: TrailerKind,
    amount: EstimatedAmount,
) -> FitLevel:
    if load == "other" and max_lb is None:
        return "low"
    if amount == "unsure":
        return "low"
    if max_lb is None:
        return "medium"
    cap = COMFORT_PAYLOAD_LBS[trailer_for_load]
    if max_lb <= int(cap * 0.85):
        return "high"
    if max_lb <= cap:
        return "medium"
    return "low"


def _max_trailer_for_tow_profile(veh: FitLevel, drv: FitLevel) -> TrailerKind:
    v, d = _fit_ord(veh), _fit_ord(drv)
    if v == 0 and d == 0:
        return TrailerKind.ten_seven
    if min(v, d) == 0:
        return TrailerKind.twelve_ten
    return TrailerKind.twelve_twelve


def _pick_alternative(
    rec: TrailerKind | None,
    *,
    load: LoadType,
    max_lb: int | None,
    mode: RecommendationMode,
    trailer_for_load: TrailerKind,
) -> TrailerKind:
    if mode == "multi_load" and rec == TrailerKind.ten_seven and _rank(trailer_for_load) > _rank(rec):
        return trailer_for_load
    if rec is None:
        return TrailerKind.twelve_ten
    if rec == TrailerKind.ten_seven:
        return TrailerKind.twelve_ten
    if rec == TrailerKind.twelve_twelve:
        return TrailerKind.twelve_ten
    heavyish = load in ("gravel", "construction", "topsoil") or (max_lb is not None and max_lb > 5500)
    return TrailerKind.twelve_twelve if heavyish else TrailerKind.ten_seven


def _cta_strings(mode: RecommendationMode) -> list[str]:
    if mode == "contact_required":
        return ["Ask us to confirm", "Request delivery quote"]
    if mode == "multi_load":
        return ["Book 10′ trailer", "Ask us to confirm", "Request delivery quote"]
    return ["Book this trailer", "Ask us to confirm", "Request delivery quote"]


def compute_delivery_cta_emphasis(inp: TrailerMatchInput, result: RecommendationResult) -> DeliveryCtaEmphasis:
    parts: list[str] = []
    rec = result.recommended_trailer
    load = inp.load_type

    if result.mode == "delivery_suggested":
        parts.append("we capped trailer size for towing fit—delivery may be worth comparing")
    if inp.towing_experience == "first_time":
        parts.append("first-time tower")
    if inp.tow_package in ("no", "unknown"):
        parts.append("tow package not confirmed")
    if inp.brake_controller in ("no", "unknown"):
        parts.append("brake controller not confirmed")
    if rec in (TrailerKind.twelve_ten, TrailerKind.twelve_twelve):
        parts.append("larger 10k/12k GVWR dump trailer")
    if load in ("gravel", "topsoil", "construction", "other"):
        parts.append("dense or variable material")
    if inp.estimated_amount in ("y4", "y5plus", "unsure"):
        parts.append("large or uncertain volume")
    if result.overall_confidence == "low":
        parts.append("low overall confidence")
    if result.mode in ("multi_load", "delivery_suggested", "contact_required"):
        parts.append(f"mode:{result.mode}")

    if not parts:
        return DeliveryCtaEmphasis(delivery_cta_shown=False, delivery_cta_reason=None)
    reason = "; ".join(parts[:8])
    if len(parts) > 8:
        reason += "; …"
    return DeliveryCtaEmphasis(delivery_cta_shown=True, delivery_cta_reason=reason)


def recommend_trailer(inp: TrailerMatchInput) -> RecommendationResult:
    reasons: list[str] = []
    warnings: list[str] = []
    y_min, y_max = _yards_range(inp.estimated_amount)
    w_min, w_max = _estimate_weight_range(inp.load_type, y_min, y_max)
    vehicle = infer_vehicle_tier(inp)
    load = inp.load_type
    max_lb = w_max
    min_lb = w_min

    std_warns = [
        "Verify your vehicle’s towing capacity, payload rating, hitch rating, and brake controller requirements.",
        "Material weights are estimates and can vary significantly when wet.",
        "Do not exceed your vehicle, hitch, or trailer ratings.",
    ]

    trailer_for_load = _material_trailer_for_load(inp, y_min=y_min, y_max=y_max, max_lb=max_lb, vehicle=vehicle)
    trailer_comfort = _comfort_adjust_single_trailer(
        inp, trailer_for_load, y_max=y_max, max_lb=max_lb, vehicle=vehicle
    )

    vf_preview = _vehicle_fit(inp, trailer_for_load)
    df_preview = _driver_fit(inp, trailer_for_load, y_max=y_max)

    heavy_vol = is_heavy_load(load) and (
        inp.estimated_amount in ("y2", "y3", "y4", "y5plus") or (inp.estimated_amount == "unsure" and y_max >= 2.0)
    )

    mode: RecommendationMode = "single_trailer"
    recommended: TrailerKind | None = trailer_comfort
    trips: int | None = None
    t_load = trailer_for_load

    if load == "other" and max_lb is None:
        mode = "contact_required"
        recommended = None
        reasons.append(
            "We don’t have a reliable weight band for “other” loads—please contact us so we can recommend "
            "a trailer and plan safely."
        )
        warnings.extend(std_warns)
    elif heavy_vol and (vf_preview == "low" or df_preview == "low"):
        mode = "multi_load"
        recommended = TrailerKind.ten_seven
        trips = estimate_trips(load, inp.estimated_amount, TrailerKind.ten_seven)
        reasons.append("Recommended plan: 10′ 7k trailer with multiple smaller loads.")
        reasons.append(
            "The larger trailer may fit this material in fewer trips, but based on the vehicle and towing "
            "information provided, we recommend a smaller trailer and multiple lighter loads."
        )
        reasons.append("Smaller trailer is easier to maneuver for homeowner towing.")
        reasons.append("Heavy materials can exceed limits quickly.")
        if inp.tow_package in ("no", "unknown"):
            reasons.append("Your vehicle configuration is incomplete or does not indicate a tow package.")
        if inp.towing_experience == "first_time":
            reasons.append("First-time towing increases risk with heavier trailers.")
        reasons.append("Multiple smaller loads may be safer than one large load.")
        if trailer_for_load != TrailerKind.ten_seven:
            reasons.append(
                f"A {TRAILER_DISPLAY[trailer_for_load]} may fit the load in fewer trips, "
                "but we are not recommending it as your primary tow based on your answers."
            )
        warnings.extend(std_warns)
        if trailer_for_load in (TrailerKind.twelve_ten, TrailerKind.twelve_twelve):
            warnings.append(
                f"Larger dump trailers such as the {TRAILER_DISPLAY[trailer_for_load]} may match the material weight, "
                "but they may not be a good towing fit for the vehicle and experience described."
            )
    else:
        cap = _max_trailer_for_tow_profile(vf_preview, df_preview)
        recommended = _min_trailer(trailer_comfort, cap)
        if _rank(recommended) < _rank(trailer_for_load) and vf_preview == "low":
            mode = "delivery_suggested"
            reasons.append(
                "A larger trailer could reduce trips for this material, but your towing setup looks uncertain—"
                "we capped the recommendation and suggest asking about delivery or confirming details with us."
            )
        if max_lb is not None:
            reasons.append(
                f"Rough material weight about {min_lb or '—'}–{max_lb} lb informed trailer sizing."
            )
        else:
            reasons.append("Material-based trailer sizing uses your best-estimate answers.")

        if load == "construction" and y_min >= 2.0:
            warnings.append(
                "Construction debris weight varies a lot by what you’re tearing out—assume the upper end "
                "until you’ve seen the pile."
            )
        if load == "gravel" and y_max >= 3.0 and vehicle != "heavy":
            warnings.append(
                "Gravel can land near the top of the weight range—verify your truck, hitch, and brake setup "
                "before towing loaded."
            )
        if load in ("gravel", "topsoil") and y_max >= 4.0:
            warnings.append(
                "Material weight climbs quickly at four or more cubic yards—especially gravel or wet dirt/topsoil."
            )
        if max_lb is not None and max_lb > COMFORT_PAYLOAD_LBS[TrailerKind.twelve_twelve]:
            warnings.append(
                "Your estimated upper weight may exceed what we comfortably plan on a single trip even "
                "with our largest dump trailer—split the load or call us to confirm."
            )
        if inp.towing_experience == "first_time" and vehicle == "unknown" and load in ("gravel", "construction"):
            warnings.append(
                "We couldn’t tell your truck class from the description—double-check tow and payload limits."
            )
        if inp.brake_controller in ("no", "unknown") and recommended in (
            TrailerKind.twelve_ten,
            TrailerKind.twelve_twelve,
        ):
            warnings.append(
                "Trailers in the 10k and 12k GVWR range typically use electric brakes; towing loaded without "
                "a properly installed and working brake controller is unsafe and may be illegal where you live."
            )
        warnings.extend(std_warns)

    # --- Fits on final recommendation ---
    if recommended is None:
        job = _job_fit(load, max_lb, trailer_for_load, inp.estimated_amount)
        vehicle_f = "low"
        driver_f = "low"
        overall = "low"
    else:
        job = _job_fit(load, max_lb, trailer_for_load, inp.estimated_amount)
        vehicle_f = _vehicle_fit(inp, recommended)
        driver_f = _driver_fit(inp, recommended, y_max=y_max)
        if mode == "multi_load":
            job = _fit_min(job, "medium", "medium")
        overall = _fit_min(job, vehicle_f, driver_f)

    if recommended is None or load == "other":
        follow: FollowUpCta = "ask_confirm"
    elif mode == "multi_load":
        follow = "book"
    elif overall == "low":
        follow = "ask_confirm"
    else:
        follow = "book"

    ctas = _cta_strings(mode)

    alt = _pick_alternative(recommended, load=load, max_lb=max_lb, mode=mode, trailer_for_load=t_load)

    if recommended == TrailerKind.ten_seven and mode != "multi_load":
        reasons.append(
            "The 10′ 7k is our easiest-to-maneuver dump trailer and fits many smaller residential jobs."
        )
    elif recommended == TrailerKind.twelve_ten:
        reasons.append(
            "The 12′ 10k is our general-purpose sweet spot—extra length without jumping to the heaviest-duty axle."
        )
    elif recommended == TrailerKind.twelve_twelve:
        reasons.append(
            "The 12′ 12k is our heavy-duty 12′ option when payload margin really matters."
        )

    return RecommendationResult(
        mode=mode,
        recommended_trailer=recommended,
        trailer_for_load=t_load,
        estimated_trips=trips,
        job_fit=job,
        vehicle_fit=vehicle_f,
        driver_fit=driver_f,
        overall_confidence=overall,
        estimated_weight_min_lbs=min_lb,
        estimated_weight_max_lbs=max_lb,
        reasons=reasons,
        warnings=warnings,
        ctas=ctas,
        follow_up_cta=follow,
        alternative_trailer=alt,
        confidence=overall,
    )


def trailer_kind_public_label(kind: TrailerKind | str) -> str:
    if isinstance(kind, str):
        kind = TrailerKind(kind)
    return TRAILER_DISPLAY[kind]
