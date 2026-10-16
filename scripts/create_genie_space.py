"""
Build the create payload for the DoughSight IQ Genie space (jdub_demo.lce_store_ops).

Usage: python3 scripts/create_genie_space.py > /tmp/doughsight_genie.json
       databricks api post /api/2.0/genie/spaces --profile DEFAULT --json @/tmp/doughsight_genie.json
"""

import json
import os
import sys

sys.path.insert(0, os.path.expanduser(
    "~/.vibe/marketplace/plugins/fe-internal-tools/skills/genie-rooms/resources"))
from genie_space_builder import GenieSpaceBuilder  # noqa: E402

S = "jdub_demo.lce_store_ops"

INSTRUCTIONS = """You answer questions about Little Caesars store operations for 25 Metro Detroit stores (store_id 1-25).
- Orders live in pos_transactions (one row per order) and pos_line_items (one row per item). Revenue = SUM(order_total); food sales = SUM(food_subtotal).
- channel values: walk_in (Hot-N-Ready counter), pizza_portal (app or online pickup from the heated Pizza Portal), delivery (DoorDash), phone. Say "Pizza Portal" and "Hot-N-Ready walk-in" in answers.
- Dayparts by order_hour: lunch = 11-13, afternoon = 14-15, dinner rush = 16-19, late night = 20-22.
- Dough: dough_prep_log has one row per store, prep_date, dough_type (Large Classic, Thin Crust, Deep Dish, Crazy Bread). Waste % = SUM(balls_wasted) / SUM(balls_mixed). A stockout day has rush_stockout_flag = true; balls_short is the shortfall.
- menu_items.dough_type maps each pizza or bread to the dough it uses (NULL for wings, dips, sauce, drinks).
- local_events lists Detroit Tigers, Red Wings, Pistons, and Lions home games. Join on event_date = order_date or prep_date to compare event days with non-event days.
- labor_schedule is hourly; is_forecast = true rows are next week's plan. Labor % = labor_cost / revenue for the same store and date.
- Data runs through 2026-10-01. "Last week" means the 7 days ending on the latest order_date.
- Always name stores by stores.name, not only the id."""

QUESTIONS = [
    "Which stores had the highest dough waste % in the last 30 days?",
    "What share of orders came through the Pizza Portal by store last month?",
    "How do dinner rush sales on Red Wings home game days compare to other days at Detroit stores?",
    "Which stores had the most dough stockout days this year, and for which dough type?",
    "Show revenue by daypart for Detroit Woodward Ave over the last 4 weeks",
    "What are the top 10 menu items by revenue this quarter?",
    "Compare average order value by channel",
    "Which stores have the highest labor cost as a percent of revenue in the last 30 days?",
    "Weekly revenue trend for all stores over the last 12 weeks",
    "How many Deep Dish dough balls did each store use last week?",
]

b = GenieSpaceBuilder(
    title="DoughSight IQ: Little Caesars Store Ops",
    description="Little Caesars Metro Detroit store operations: orders, channels, dough prep and waste, labor, inventory, and Detroit sports events (synthetic demo data).",
    warehouse_id="0168e23e24e6ae10",
)
b.set_instructions(INSTRUCTIONS)
for t in ["dough_prep_log", "employees", "ingredients", "inventory_levels", "labor_schedule",
          "local_events", "menu_items", "pos_line_items", "pos_transactions", "stores"]:
    b.add_table(f"{S}.{t}")
b.add_example_sql(
    title="Dough waste % by store, last 30 days",
    sql=(f"SELECT s.name, ROUND(100.0 * SUM(d.balls_wasted) / SUM(d.balls_mixed), 1) AS waste_pct "
         f"FROM {S}.dough_prep_log d JOIN {S}.stores s USING (store_id) "
         f"WHERE d.prep_date > (SELECT MAX(prep_date) FROM {S}.dough_prep_log) - INTERVAL 30 DAYS "
         f"GROUP BY s.name ORDER BY waste_pct DESC"),
)
b.add_example_sql(
    title="Dinner rush revenue on event vs non-event days",
    sql=(f"SELECT CASE WHEN e.event_date IS NULL THEN 'no home game' ELSE 'home game' END AS day_type, "
         f"ROUND(SUM(t.order_total) / COUNT(DISTINCT t.store_id, t.order_date), 2) AS dinner_rev_per_store_day "
         f"FROM {S}.pos_transactions t LEFT JOIN (SELECT DISTINCT event_date FROM {S}.local_events) e "
         f"ON e.event_date = t.order_date WHERE t.order_hour BETWEEN 16 AND 19 GROUP BY 1"),
)

b.validate()
ss = b.to_dict()
for path in (("instructions", "example_question_sqls"), ("instructions", "text_instructions")):
    lst = ss.get(path[0], {}).get(path[1])
    if lst:
        lst.sort(key=lambda x: x["id"])
ss.setdefault("config", {})["sample_questions"] = [
    {"id": f"01f1000000000000{i:016x}", "question": [q]} for i, q in enumerate(QUESTIONS, 1)]
print(json.dumps({
    "title": "DoughSight IQ: Little Caesars Store Ops",
    "description": "Little Caesars Metro Detroit store operations: orders, channels, dough prep and waste, labor, inventory, and Detroit sports events (synthetic demo data).",
    "warehouse_id": "0168e23e24e6ae10",
    "parent_path": "/Workspace/Users/jonathan.whiteley@databricks.com",
    "serialized_space": json.dumps(ss),
}))
