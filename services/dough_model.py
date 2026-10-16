"""
Dough HQ simulation model (placeholder until real Little Caesars dough inputs arrive).

One deterministic plan per store, date, and hour drives every Dough HQ endpoint
(inventory, schedule, recommendations, alerts, KPIs) so the numbers always agree.

Lifecycle: dough is mixed early morning, held in the walk-in (cold_hold, usable
up to day 3), pulled to temper, then ready for slap-out. Ready dough left out
too long overproofs and becomes waste. Pulls happen FIFO (oldest dough first).

Tunable inputs live in DOUGH_SPECS and PULLS; swap them for real store standards.
"""

from dataclasses import dataclass, field
from typing import Dict, List
import zlib

# Daily balls needed per store at store_factor 1.0 (matches jdub_demo.lce_store_ops volumes)
DOUGH_SPECS = {
    "Large Classic": {"daily_need": 440, "temper_min": 180, "popularity": 0.45},
    "Crazy Bread": {"daily_need": 140, "temper_min": 120, "popularity": 0.10},
    "Deep Dish": {"daily_need": 48, "temper_min": 200, "popularity": 0.20},
    "Thin Crust": {"daily_need": 28, "temper_min": 150, "popularity": 0.25},
}

# Share of daily demand by hour (lunch 11-13, dinner rush 16-19)
HOURLY_SHARE = {10: 0.02, 11: 0.12, 12: 0.16, 13: 0.11, 14: 0.06, 15: 0.06, 16: 0.09,
                17: 0.16, 18: 0.13, 19: 0.05, 20: 0.025, 21: 0.01, 22: 0.005}

# Pull-to-temper waves: (hour, share of daily need, purpose). The dinner pull is timed
# so the slowest dough (Deep Dish, 200 min) is ready by the 16:00 ramp.
PULLS = [(7.5, 0.57, "lunch"), (12.5, 0.43, "dinner"), (17.0, 0.07, "late night")]
MIX_HOUR = 6.5
LUNCH_START, DINNER_START = 11, 16


def _u(*parts) -> float:
    """Stable uniform in [0, 1) from the inputs (same across processes and workers)."""
    return (zlib.crc32("|".join(str(p) for p in parts).encode()) % 100000) / 100000.0


def _consumed_by(need: float, hour: float) -> float:
    """Balls consumed from opening up to the given (fractional) hour."""
    total = 0.0
    for h, share in HOURLY_SHARE.items():
        if hour >= h + 1:
            total += share
        elif hour > h:
            total += share * (hour - h)
    return need * total


@dataclass
class DoughTypePlan:
    dough_type: str
    temper_min: int
    popularity: float
    daily_need: int
    day3_on_hand: int
    day2_on_hand: int
    mixed_today: int
    pulls: List[Dict] = field(default_factory=list)  # {hour, qty, purpose}
    stages: List[Dict] = field(default_factory=list)  # {stage, quantity, age_days, temper_elapsed, hours_until_stale}
    ready: int = 0
    tempering: int = 0
    dinner_need: int = 0
    dinner_supply: int = 0
    projected_waste: int = 0


def store_factor(store_id: int) -> float:
    return 0.85 + (store_id * 37 % 110) / 275.0  # ~0.85-1.25, matches the SQL generator spread


def dough_plan(store_id: int, date: str, hour: float) -> List[DoughTypePlan]:
    sf = store_factor(store_id)
    # Some stores consistently under-pull for dinner, some over-mix (waste)
    pull_bias = 0.78 + 0.28 * _u("pull", store_id)          # 0.78-1.06
    overmix = 1.00 + 0.05 * _u("mix", store_id, date)       # 0-5% over need
    plans = []
    for name, spec in DOUGH_SPECS.items():
        need = round(spec["daily_need"] * sf * (0.93 + 0.14 * _u("need", store_id, date, name)))
        day3 = round(need * (0.02 + 0.03 * _u("d3", store_id, date, name))) if _u("d3x", store_id, name) > 0.5 else 0
        day2 = round(need * (0.18 + 0.12 * _u("d2", store_id, date, name)))
        mixed = max(0, round(need * overmix) - day2 - day3)
        p = DoughTypePlan(name, spec["temper_min"], spec["popularity"], need, day3, day2, mixed)

        for ph, share, purpose in PULLS:
            qty = round(need * share * (pull_bias if purpose == "dinner" else 1.0))
            p.pulls.append({"hour": ph, "qty": qty, "purpose": purpose})

        # Walk-in layers in the order crews actually pull: day 2, then today's mix.
        # Day-3 dough tends to get skipped (the FIFO miss Dough HQ flags), so it is pulled last.
        layers = [[1, day2], [0, mixed if hour >= MIX_HOUR else 0], [2, day3]]
        pulled = tempered = 0
        temper_rows = []
        for pull in p.pulls:
            if hour < pull["hour"]:
                continue
            remaining = pull["qty"]
            for layer in layers:
                take = min(layer[1], remaining)
                layer[1] -= take
                remaining -= take
            got = pull["qty"] - remaining
            pulled += got
            elapsed = int((hour - pull["hour"]) * 60)
            if elapsed >= spec["temper_min"]:
                tempered += got
            else:
                temper_rows.append({"quantity": got, "elapsed": elapsed})

        consumed = min(tempered, round(_consumed_by(need, hour)))
        ready = max(0, tempered - consumed)
        # Ready dough sitting after 21:00 starts to overproof
        overproofed = round(ready * 0.5) if hour >= 21 else 0
        ready -= overproofed

        for age, qty in layers:
            if qty > 0:
                p.stages.append({"stage": "cold_hold" if hour >= MIX_HOUR + 0.5 or age > 0 else "mixed",
                                 "quantity": qty, "age_days": age, "temper_elapsed": 0,
                                 "hours_until_stale": round(max(0.0, (3 - age) * 24 - hour), 1)})
        for row in temper_rows:
            p.stages.append({"stage": "tempering", "quantity": row["quantity"], "age_days": 0,
                             "temper_elapsed": row["elapsed"], "hours_until_stale": 6.0})
        if ready > 0:
            p.stages.append({"stage": "ready", "quantity": ready, "age_days": 0,
                             "temper_elapsed": spec["temper_min"], "hours_until_stale": round(max(0.5, 22 - hour), 1)})
        if overproofed > 0:
            p.stages.append({"stage": "overproofed", "quantity": overproofed, "age_days": 0,
                             "temper_elapsed": spec["temper_min"], "hours_until_stale": 0.0})

        p.ready, p.tempering = ready, sum(r["quantity"] for r in temper_rows)
        # Dinner coverage: everything pulled by the dinner wave vs demand through 20:00
        dinner_pull = next(x for x in p.pulls if x["purpose"] == "dinner")
        lunch_pull = next(x for x in p.pulls if x["purpose"] == "lunch")
        p.dinner_need = round(_consumed_by(need, 20) - _consumed_by(need, DINNER_START))
        lunch_leftover = max(0, lunch_pull["qty"] - round(_consumed_by(need, DINNER_START)))
        p.dinner_supply = dinner_pull["qty"] + lunch_leftover
        # Waste = day-3 dough still in the walk-in (expires at close) plus expected overproofing,
        # which grows with over-mixing. Leftover day-1 dough rolls forward as tomorrow's day 2.
        day3_left = next(q for age, q in layers if age == 2)
        p.projected_waste = day3_left + round(need * (0.012 + 0.4 * (overmix - 1.0)))
        plans.append(p)
    return plans


def summary(store_id: int, date: str, hour: float) -> Dict:
    plans = dough_plan(store_id, date, hour)
    need_total = sum(p.daily_need for p in plans)
    dinner_need = sum(p.dinner_need for p in plans)
    dinner_supply = sum(p.dinner_supply for p in plans)
    if hour < LUNCH_START:
        upcoming = round(sum(_consumed_by(p.daily_need, DINNER_START) - _consumed_by(p.daily_need, LUNCH_START) for p in plans))
        supply = sum(next(x["qty"] for x in p.pulls if x["purpose"] == "lunch") for p in plans)
        coverage = supply / upcoming * 100 if upcoming else 100
    else:
        upcoming, coverage = dinner_need, (dinner_supply / dinner_need * 100 if dinner_need else 100)
    return {
        "dough_ready_balls": sum(p.ready for p in plans),
        "forecast_need_balls": upcoming,
        "rush_coverage_pct": round(min(coverage, 125.0), 1),
        "projected_waste_pct": round(sum(p.projected_waste for p in plans) / need_total * 100, 1),
        "day3_at_risk_balls": sum(s["quantity"] for p in plans for s in p.stages if s["age_days"] >= 2),
    }


def fmt_hour(h: float) -> str:
    total = int(round(h * 12)) * 5  # nearest 5 minutes
    hh, mm = divmod(total, 60)
    suffix = "AM" if hh < 12 else "PM"
    return f"{(hh - 1) % 12 + 1}:{mm:02d} {suffix}"
