"""
Dough HQ API endpoints.

Provides ML-optimized dough scheduling for Little Caesars:
- Current dough inventory by lifecycle stage and age
- Optimal temper and prep schedule by time of day
- Real-time adjustments based on demand

Uses the lce-dough-scheduler model serving endpoint (fallback to demo data).
Accounts for dough temper times and lifecycle stages (mixed, cold_hold, tempering, ready, overproofed).
"""

from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
import logging
from config.settings import Settings, get_settings
from services.model_serving import model_client

logger = logging.getLogger(__name__)

router = APIRouter()


def get_client_adjusted_time(request: Request) -> datetime:
    """Get current time adjusted to client's local timezone using X-Client-Local-Hour header."""
    server_now = datetime.now()
    server_hour = server_now.hour

    client_hour = None
    header_value = request.headers.get("X-Client-Local-Hour") if request else None
    if header_value:
        try:
            client_hour = int(header_value)
        except ValueError:
            pass

    if client_hour is not None:
        hour_offset = client_hour - server_hour
        return server_now + timedelta(hours=hour_offset)

    return server_now


# === Dough Types with Properties ===

DOUGH_TYPES = [
    {
        "id": 1,
        "name": "Large Classic",
        "temper_minutes": 180,
        "max_age_hours": 72,
        "popularity": 0.45,
        "description": "Hot-N-Ready Large Classic pizza dough"
    },
    {
        "id": 2,
        "name": "Thin Crust",
        "temper_minutes": 150,
        "max_age_hours": 60,
        "popularity": 0.25,
        "description": "Pressed thin crust pizza dough"
    },
    {
        "id": 3,
        "name": "Deep Dish",
        "temper_minutes": 200,
        "max_age_hours": 48,
        "popularity": 0.20,
        "description": "Pan-proofed deep dish pizza dough"
    },
    {
        "id": 4,
        "name": "Crazy Bread",
        "temper_minutes": 120,
        "max_age_hours": 36,
        "popularity": 0.10,
        "description": "Crazy Bread dough for garlic bread"
    },
]


# === Pydantic Models ===

class DoughInventory(BaseModel):
    """Current dough inventory item."""
    dough_type: str
    quantity: int
    stage: str  # "mixed", "cold_hold", "tempering", "ready", "overproofed"
    age_days: int
    hours_until_stale: float
    temper_minutes_elapsed: int


class PrepTask(BaseModel):
    """Single dough prep or temper task."""
    id: int
    dough_type: str
    quantity: int
    action: str  # "mix", "pull_to_temper", "slice", "slap_out"
    scheduled_time: str
    ready_time: str
    status: str  # "pending", "in_progress", "complete"
    priority: str  # "high", "medium", "low"


class DoughSchedule(BaseModel):
    """Full dough prep and temper schedule for a day."""
    store_id: int
    date: str
    tasks: List[PrepTask]
    total_dough_balls: int
    next_task: Optional[PrepTask]


class DoughRecommendation(BaseModel):
    """ML recommendation for dough prep and tempering."""
    dough_type: str
    recommended_quantity: int
    suggested_action: str  # "Mix X balls", "Pull X to temper"
    suggested_time: str
    reason: str
    confidence: float


class DoughKPI(BaseModel):
    """Key performance indicators for dough management."""
    dough_ready_balls: int
    forecast_need_balls: int
    rush_coverage_pct: float
    projected_waste_pct: float
    day3_at_risk_balls: int


def _frac_hour(dt: datetime) -> float:
    return dt.hour + dt.minute / 60.0


# === Endpoints ===

@router.get("/inventory/{store_id}")
async def get_dough_inventory_endpoint(
    request: Request,
    store_id: int,
    settings: Settings = Depends(get_settings),
) -> List[DoughInventory]:
    """
    Get current dough inventory for a store.

    Uses shared demo_data service for consistent levels.
    Shows quantity, lifecycle stage, and age for each dough type.
    Uses client's local time for accurate stage determination.
    """
    from services.demo_data import demo_data

    client_now = get_client_adjusted_time(request)
    current_hour = _frac_hour(client_now)
    date_str = client_now.strftime("%Y-%m-%d")

    # Get consistent dough inventory from shared service
    dough_items = demo_data.get_dough_inventory(store_id, date_str, current_hour)

    inventory = []
    for item in dough_items:
        inventory.append(DoughInventory(
            dough_type=item.dough_type,
            quantity=item.quantity,
            stage=item.stage,
            age_days=item.age_days,
            hours_until_stale=item.hours_until_stale,
            temper_minutes_elapsed=item.temper_minutes_elapsed,
        ))

    return inventory



@router.get("/schedule/{store_id}")
async def get_dough_schedule(
    request: Request,
    store_id: int,
    date: Optional[str] = Query(None),
    settings: Settings = Depends(get_settings),
) -> DoughSchedule:
    """
    Today's mix and pull-to-temper schedule, from the same plan as inventory and KPIs.
    Status is relative to the client's local time.
    """
    from services.dough_model import dough_plan, fmt_hour, MIX_HOUR

    client_now = get_client_adjusted_time(request)
    target_date = date or client_now.strftime("%Y-%m-%d")
    now_h = _frac_hour(client_now) if date is None else -1

    tasks: List[PrepTask] = []
    for plan in dough_plan(store_id, target_date, 23.5):
        rows = [("mix", MIX_HOUR, plan.mixed_today, 15, "medium")]
        for pull in plan.pulls:
            prio = "high" if pull["purpose"] == "dinner" else ("medium" if pull["purpose"] == "lunch" else "low")
            rows.append(("pull_to_temper", pull["hour"], pull["qty"], plan.temper_min, prio))
        for action, h, qty, minutes, prio in rows:
            if qty <= 0:
                continue
            done_h = h + minutes / 60.0
            status = "complete" if now_h >= done_h else ("in_progress" if now_h >= h else "pending")
            tasks.append(PrepTask(
                id=len(tasks) + 1, dough_type=plan.dough_type, quantity=qty, action=action,
                scheduled_time=fmt_hour(h), ready_time=fmt_hour(done_h), status=status, priority=prio,
            ))

    order = {"mix": 0, "pull_to_temper": 1}
    tasks.sort(key=lambda t: (datetime.strptime(t.scheduled_time, "%I:%M %p"), order[t.action]))
    for i, t in enumerate(tasks, 1):
        t.id = i
    next_task = next((t for t in tasks if t.status == "pending"), None)
    return DoughSchedule(store_id=store_id, date=target_date, tasks=tasks,
                         total_dough_balls=sum(t.quantity for t in tasks if t.action == "mix"),
                         next_task=next_task)


@router.get("/recommendations/{store_id}")
async def get_dough_recommendations(
    request: Request,
    store_id: int,
    settings: Settings = Depends(get_settings),
) -> List[DoughRecommendation]:
    """
    Dough actions for the next rush and tomorrow's mix, consistent with the KPI strip.
    """
    from services.dough_model import dough_plan, fmt_hour, _u, DINNER_START

    client_now = get_client_adjusted_time(request)
    h = _frac_hour(client_now)
    date_str = client_now.strftime("%Y-%m-%d")
    recs: List[DoughRecommendation] = []

    for plan in dough_plan(store_id, date_str, h):
        conf = round(0.84 + 0.12 * _u("conf", store_id, date_str, plan.dough_type), 2)
        gap = plan.dinner_need - plan.dinner_supply
        latest_pull = DINNER_START - plan.temper_min / 60.0
        if h < DINNER_START + 2 and gap > 0:
            when = fmt_hour(max(h + 0.25, latest_pull)) if h < latest_pull + 1 else "now"
            recs.append(DoughRecommendation(
                dough_type=plan.dough_type, recommended_quantity=int(gap * 1.05) + 1,
                suggested_action=f"Pull {int(gap * 1.05) + 1} extra balls to temper",
                suggested_time=when,
                reason=(f"Dinner rush forecast needs {plan.dinner_need} {plan.dough_type} balls; "
                        f"planned pulls cover {plan.dinner_supply}. Temper takes {plan.temper_min} min."),
                confidence=conf,
            ))
        day3 = sum(s["quantity"] for s in plan.stages if s["age_days"] >= 2)
        if day3 >= 3:
            recs.append(DoughRecommendation(
                dough_type=plan.dough_type, recommended_quantity=day3,
                suggested_action=f"Use {day3} day-3 balls first",
                suggested_time=fmt_hour(max(h + 0.25, 12.5)) if h < 12.5 else "now",
                reason="Day-3 dough expires at close. Put it in the next pull so it sells instead of becoming waste.",
                confidence=conf,
            ))
        over = plan.projected_waste - sum(s["quantity"] for s in plan.stages if s["age_days"] >= 2)
        if over >= 4:
            tomorrow_mix = max(0, plan.mixed_today - over)
            recs.append(DoughRecommendation(
                dough_type=plan.dough_type, recommended_quantity=tomorrow_mix,
                suggested_action=f"Mix {tomorrow_mix} balls tomorrow ({over} fewer)",
                suggested_time="6:30 AM",
                reason=f"About {over} {plan.dough_type} balls are projected to overproof today; trimming tomorrow's mix cuts waste.",
                confidence=round(conf - 0.05, 2),
            ))

    recs.sort(key=lambda r: (r.suggested_action.startswith("Mix"), -r.recommended_quantity))
    return recs


@router.post("/optimize/{store_id}")
async def optimize_dough_schedule(
    store_id: int,
    date: str,
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Generate ML-optimized dough prep and temper schedule for a day.

    Calls the dough scheduler model serving endpoint.
    """
    import random
    import logging

    logger = logging.getLogger(__name__)

    # Get current inventory from shared service
    from services.demo_data import demo_data
    # Use noon as a reference hour for optimization
    dough_items = demo_data.get_dough_inventory(store_id, date, 12)
    current_inv = {d.dough_type: d.quantity for d in dough_items}

    # Get hourly traffic forecast
    hourly_traffic = [random.randint(5, 45) for _ in range(24)]

    # Prep times to generate schedule for
    prep_times_config = [
        (8, "08:00 AM", "Morning mix"),
        (10, "10:30 AM", "Pull for lunch"),
        (15, "03:00 PM", "Afternoon mix"),
        (16, "04:30 PM", "Pull for dinner"),
    ]

    try:
        optimized_schedule = []

        for prep_hour, time_str, _ in prep_times_config:
            traffic = hourly_traffic[prep_hour] if prep_hour < len(hourly_traffic) else 25

            for dough in DOUGH_TYPES[:3]:  # Top 3 doughs
                result = await model_client.predict_dough_schedule(
                    store_id=store_id,
                    date=date,
                    hour=prep_hour,
                    dough_type=dough["name"],
                    forecasted_traffic=traffic,
                    max_traffic=50,
                )

                predictions = result.get("predictions", [])
                if predictions and len(predictions) > 0:
                    raw_qty = predictions[0] if isinstance(predictions[0], (int, float)) else 20
                    # Scale up based on traffic and popularity
                    scaled_qty = raw_qty * (1 + traffic / 50) * (1 + dough["popularity"])
                    qty = int(max(5, min(60, scaled_qty)))

                    optimized_schedule.append({
                        "time": time_str,
                        "dough_type": dough["name"],
                        "quantity": qty,
                        "action": "mix" if prep_hour in [8, 15] else "pull_to_temper"
                    })

        logger.info(f"Dough schedule optimized via model serving for {date}")

        return {
            "store_id": store_id,
            "date": date,
            "optimized_schedule": optimized_schedule,
            "total_dough_balls": sum(s["quantity"] for s in optimized_schedule),
            "model_status": "active"
        }

    except Exception as e:
        logger.warning(f"Dough model unavailable, using fallback: {e}")
        # Return simulated optimized schedule
        schedule = [
            {"time": "08:00 AM", "dough_type": "Large Classic", "quantity": 30, "action": "mix"},
            {"time": "08:00 AM", "dough_type": "Thin Crust", "quantity": 15, "action": "mix"},
            {"time": "10:30 AM", "dough_type": "Large Classic", "quantity": 40, "action": "pull_to_temper"},
            {"time": "10:30 AM", "dough_type": "Thin Crust", "quantity": 20, "action": "pull_to_temper"},
            {"time": "10:30 AM", "dough_type": "Deep Dish", "quantity": 15, "action": "pull_to_temper"},
            {"time": "03:00 PM", "dough_type": "Large Classic", "quantity": 30, "action": "mix"},
            {"time": "03:00 PM", "dough_type": "Crazy Bread", "quantity": 10, "action": "mix"},
            {"time": "04:30 PM", "dough_type": "Large Classic", "quantity": 35, "action": "pull_to_temper"},
            {"time": "04:30 PM", "dough_type": "Thin Crust", "quantity": 18, "action": "pull_to_temper"},
            {"time": "04:30 PM", "dough_type": "Deep Dish", "quantity": 12, "action": "pull_to_temper"},
        ]

        return {
            "store_id": store_id,
            "date": date,
            "optimized_schedule": schedule,
            "total_dough_balls": sum(s["quantity"] for s in schedule),
            "estimated_waste_reduction": f"{random.randint(10, 25)}%",
            "model_status": "simulated"
        }



@router.get("/alerts/{store_id}")
async def get_dough_alerts(
    request: Request,
    store_id: int,
    settings: Settings = Depends(get_settings),
) -> List[dict]:
    """Dough alerts: dinner shortfall, day-3 dough, tempering progress, overproofing."""
    from services.dough_model import dough_plan, DINNER_START

    client_now = get_client_adjusted_time(request)
    h = _frac_hour(client_now)
    alerts: List[dict] = []
    for plan in dough_plan(store_id, client_now.strftime("%Y-%m-%d"), h):
        gap = plan.dinner_need - plan.dinner_supply
        if gap > 0 and h < DINNER_START + 3:
            alerts.append({"type": "rush_shortfall", "severity": "critical" if gap > plan.dinner_need * 0.1 else "warning",
                           "dough_type": plan.dough_type,
                           "message": f"Dinner rush short about {gap} {plan.dough_type} balls at current pull plan",
                           "action": f"Pull {gap + 1} more to temper"})
        for s in plan.stages:
            if s["age_days"] >= 2 and s["quantity"] >= 3:
                alerts.append({"type": "aging", "severity": "warning", "dough_type": plan.dough_type,
                               "message": f"{s['quantity']} {plan.dough_type} balls on day 3 in the walk-in",
                               "action": "Use first in the next pull"})
            if s["stage"] == "overproofed":
                alerts.append({"type": "waste", "severity": "critical", "dough_type": plan.dough_type,
                               "message": f"{s['quantity']} {plan.dough_type} balls overproofed",
                               "action": "Log as waste"})
            if s["stage"] == "tempering":
                left = plan.temper_min - s["temper_elapsed"]
                alerts.append({"type": "tempering", "severity": "info", "dough_type": plan.dough_type,
                               "message": f"{s['quantity']} {plan.dough_type} balls tempering, ready in {left} min",
                               "action": "Hold slap-out until tempered"})
    rank = {"critical": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda a: rank[a["severity"]])
    return alerts


@router.get("/summary/{store_id}")
async def get_dough_summary(
    request: Request,
    store_id: int,
    settings: Settings = Depends(get_settings),
) -> DoughKPI:
    """Dough KPIs for the next rush (lunch before 11:00, otherwise dinner)."""
    from services.dough_model import summary

    client_now = get_client_adjusted_time(request)
    return DoughKPI(**summary(store_id, client_now.strftime("%Y-%m-%d"), _frac_hour(client_now)))
