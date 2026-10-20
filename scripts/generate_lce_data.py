"""
Generate the DoughSight IQ (Little Caesars) demo dataset in jdub_demo.lce_store_ops.

Runs entirely as SQL on a warehouse (no cluster needed). Store and ingredient
masters come from services/demo_data.py so the app and the Genie data always agree.

Usage: python3 scripts/generate_lce_data.py [--profile DEFAULT] [--warehouse 0168e23e24e6ae10]
                                           [--catalog jdub_demo] [--schema lce_store_ops]
Needs only the Databricks CLI and Python 3 (standard library). Drops and recreates the demo tables.
"""

import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from services.demo_data import DEMO_STORES, LC_INGREDIENTS  # noqa: E402

SCHEMA = "jdub_demo.lce_store_ops"
END_DATE = "2026-10-01"
DAYS = 365

COUNTY = {
    "Detroit": "Wayne", "Dearborn": "Wayne", "Livonia": "Wayne", "Canton": "Wayne", "Westland": "Wayne",
    "Taylor": "Wayne", "Wyandotte": "Wayne", "Hamtramck": "Wayne", "Grosse Pointe": "Wayne",
    "Royal Oak": "Oakland", "Troy": "Oakland", "Southfield": "Oakland", "Novi": "Oakland",
    "Farmington Hills": "Oakland", "Rochester Hills": "Oakland", "Pontiac": "Oakland",
    "Ferndale": "Oakland", "Auburn Hills": "Oakland",
    "Warren": "Macomb", "Sterling Heights": "Macomb", "Clinton Township": "Macomb",
    "Clinton Twp": "Macomb", "St Clair Shores": "Macomb", "St. Clair Shores": "Macomb",
    "Ann Arbor": "Washtenaw", "Ypsilanti": "Washtenaw",
}

# item_id, name, category, dough_type (or NULL), price, food_cost, weight (relative order share)
MENU = [
    (1, "Classic Pepperoni (Hot-N-Ready)", "pizza", "Large Classic", 6.49, 2.30, 30),
    (2, "Classic Cheese (Hot-N-Ready)", "pizza", "Large Classic", 5.99, 2.05, 12),
    (3, "ExtraMostBestest Pepperoni", "pizza", "Large Classic", 7.49, 2.75, 9),
    (4, "3 Meat Treat", "pizza", "Large Classic", 10.99, 3.80, 5),
    (5, "Ultimate Supreme", "pizza", "Large Classic", 10.99, 3.90, 4),
    (6, "Veggie", "pizza", "Large Classic", 9.99, 3.20, 2),
    (7, "Detroit-Style Deep!Deep! Dish Pepperoni", "pizza", "Deep Dish", 12.99, 4.40, 7),
    (8, "Thin Crust Pepperoni", "pizza", "Thin Crust", 8.99, 2.90, 4),
    (9, "Crazy Puffs (4pc)", "side", "Crazy Bread", 4.49, 1.30, 3),
    (10, "Crazy Bread (8pc)", "side", "Crazy Bread", 3.99, 0.95, 18),
    (11, "Italian Cheese Bread", "side", "Large Classic", 5.99, 1.70, 4),
    (12, "Crazy Sauce", "side", None, 1.29, 0.25, 14),
    (13, "Caesar Wings Buffalo (8pc)", "wings", None, 8.49, 3.60, 5),
    (14, "Caesar Wings BBQ (8pc)", "wings", None, 8.49, 3.60, 3),
    (15, "Caesar Wings Garlic Parmesan (8pc)", "wings", None, 8.49, 3.70, 3),
    (16, "Caesar Dip Ranch", "side", None, 0.99, 0.20, 5),
    (17, "Pepsi 2 Liter", "beverage", None, 3.49, 1.10, 9),
]


def sql_str(v):
    if v is None:
        return "NULL"
    if isinstance(v, str):
        return "'" + v.replace("'", "''") + "'"
    return str(v)


def values(rows):
    return ",\n".join("(" + ", ".join(sql_str(v) for v in r) + ")" for r in rows)


def run(sql, profile, warehouse, label):
    body = {"warehouse_id": warehouse, "statement": sql, "wait_timeout": "50s", "on_wait_timeout": "CONTINUE"}
    out = subprocess.run(["databricks", "api", "post", "/api/2.0/sql/statements", "--profile", profile,
                          "--json", json.dumps(body)], capture_output=True, text=True, check=True)
    d = json.loads(out.stdout)
    sid = d["statement_id"]
    while d["status"]["state"] in ("PENDING", "RUNNING"):
        time.sleep(5)
        out = subprocess.run(["databricks", "api", "get", f"/api/2.0/sql/statements/{sid}", "--profile", profile],
                             capture_output=True, text=True, check=True)
        d = json.loads(out.stdout)
    state = d["status"]["state"]
    if state != "SUCCEEDED":
        raise RuntimeError(f"{label}: {state} {d['status'].get('error', {}).get('message', '')}")
    print(f"ok  {label}")
    return d


def statements():
    stores = [(s["store_id"], s["name"], s["address"], s["city"], "MI", COUNTY.get(s["city"], "Wayne"),
               s["lat"], s["lng"], s["sqft"], s["open_date"], s.get("manager_name"), s.get("phone"))
              for s in DEMO_STORES]
    ingredients = [(i["id"], i["name"], i["category"], i["unit"], i["par"], i["cost_per_unit"]) for i in LC_INGREDIENTS]

    yield "schema", f"CREATE SCHEMA IF NOT EXISTS {SCHEMA} COMMENT 'Little Caesars store operations demo data for DoughSight IQ (synthetic, Metro Detroit)'"

    for t in ["pos_line_items", "pos_transactions", "labor_schedule", "inventory_levels", "dough_prep_log",
              "employees", "local_events", "menu_items", "ingredients", "stores", "pos_transactions_stream"]:
        yield f"drop {t}", f"DROP TABLE IF EXISTS {SCHEMA}.{t}"

    yield "stores", f"""
CREATE TABLE {SCHEMA}.stores (
  store_id INT COMMENT 'Store id 1-25 (matches the app store picker)',
  name STRING COMMENT 'Store name, e.g. Detroit Woodward Ave',
  address STRING, city STRING, state STRING,
  county STRING COMMENT 'Metro Detroit county: Wayne, Oakland, Macomb, Washtenaw',
  latitude DOUBLE, longitude DOUBLE,
  sqft INT, open_date DATE,
  manager_name STRING, phone STRING
) COMMENT 'Little Caesars stores in Metro Detroit (25 locations)'"""
    yield "stores insert", f"INSERT INTO {SCHEMA}.stores SELECT col1, col2, col3, col4, col5, col6, col7, col8, col9, CAST(col10 AS DATE), col11, col12 FROM VALUES {values(stores)}"

    yield "menu_items", f"""
CREATE TABLE {SCHEMA}.menu_items COMMENT 'Little Caesars menu items. dough_type links pizzas and breads to the dough they consume.' AS
SELECT col1 AS item_id, col2 AS item_name, col3 AS category, col4 AS dough_type,
       CAST(col5 AS DECIMAL(6,2)) AS price, CAST(col6 AS DECIMAL(6,2)) AS food_cost, col7 AS order_weight
FROM VALUES {values(MENU)}"""

    yield "ingredients", f"""
CREATE TABLE {SCHEMA}.ingredients COMMENT 'Ingredient and supply master (dough, cheese, protein, vegetable, sauce, packaging, other)' AS
SELECT col1 AS ingredient_id, col2 AS name, col3 AS category, col4 AS unit, col5 AS par_level, CAST(col6 AS DECIMAL(8,2)) AS cost_per_unit
FROM VALUES {values(ingredients)}"""

    # Detroit home games: Tigers (Apr-Sep, roughly every other day), Red Wings and Pistons (Oct-Apr, ~1 in 4 days),
    # Lions (Sundays Sep-Jan, alternating weeks). All downtown, so Detroit stores get the biggest lift.
    yield "local_events", f"""
CREATE TABLE {SCHEMA}.local_events COMMENT 'Detroit pro sports home games (synthetic schedule). Drive dinner-rush demand, strongest at Detroit stores.' AS
WITH d AS (SELECT explode(sequence(date_sub(DATE'{END_DATE}', {DAYS - 1}), date_add(DATE'{END_DATE}', 14))) AS event_date)
SELECT event_date, 'Detroit Tigers' AS team, 'MLB' AS league, 'Comerica Park' AS venue, CAST(28000 + abs(hash(event_date, 't')) % 14000 AS INT) AS attendance
FROM d WHERE month(event_date) BETWEEN 4 AND 9 AND abs(hash(event_date, 'tigers')) % 2 = 0
UNION ALL
SELECT event_date, 'Detroit Red Wings', 'NHL', 'Little Caesars Arena', CAST(17500 + abs(hash(event_date, 'r')) % 2000 AS INT)
FROM d WHERE (month(event_date) >= 10 OR month(event_date) <= 4) AND abs(hash(event_date, 'wings')) % 4 = 0
UNION ALL
SELECT event_date, 'Detroit Pistons', 'NBA', 'Little Caesars Arena', CAST(16000 + abs(hash(event_date, 'p')) % 4000 AS INT)
FROM d WHERE (month(event_date) >= 10 OR month(event_date) <= 4) AND abs(hash(event_date, 'pistons')) % 4 = 1
UNION ALL
SELECT event_date, 'Detroit Lions', 'NFL', 'Ford Field', CAST(64000 + abs(hash(event_date, 'l')) % 1500 AS INT)
FROM d WHERE dayofweek(event_date) = 1 AND (month(event_date) >= 9 OR month(event_date) = 1) AND weekofyear(event_date) % 2 = 0"""

    yield "employees", f"""
CREATE TABLE {SCHEMA}.employees COMMENT 'Store crew roster. Roles: Store Manager, Shift Leader, Pizza Maker, Crew Member, Cashier, Delivery Coordinator.' AS
WITH e AS (
  SELECT s.store_id, n FROM {SCHEMA}.stores s
  LATERAL VIEW explode(sequence(1, 12 + s.store_id % 6)) x AS n
)
SELECT CAST(store_id * 100 + n AS INT) AS employee_id, store_id,
  element_at(array('Jordan','Taylor','Marcus','Aaliyah','Chris','Destiny','Tyler','Jasmine','Andre','Sofia','Kevin','Brianna','Luis','Imani','Ethan','Nadia','Darius','Hannah'), (store_id * 7 + n) % 18 + 1)
  || ' ' || element_at(array('Johnson','Williams','Brown','Jackson','Davis','Hassan','Kowalski','Nguyen','Garcia','Moore','Haddad','Wilson','Thomas','Lewis','Robinson'), (store_id * 3 + n * 5) % 15 + 1) AS name,
  CASE WHEN n = 1 THEN 'Store Manager' WHEN n <= 3 THEN 'Shift Leader' WHEN n <= 7 THEN 'Pizza Maker'
       WHEN n <= 10 THEN 'Crew Member' WHEN n <= 12 THEN 'Cashier' ELSE 'Delivery Coordinator' END AS role,
  CAST(CASE WHEN n = 1 THEN 21.50 WHEN n <= 3 THEN 16.75 ELSE 13.25 + (n % 4) * 0.50 END AS DECIMAL(6,2)) AS hourly_rate,
  CASE WHEN n <= 4 THEN 'full_time' ELSE 'part_time' END AS employment_type,
  date_sub(DATE'{END_DATE}', CAST(30 + abs(hash(store_id, n)) % 1500 AS INT)) AS hire_date
FROM e"""

    # Orders: per store-day volume with weekday, Friday, event, and store-size effects; hour from the LC day curve.
    yield "pos_transactions", f"""
CREATE TABLE {SCHEMA}.pos_transactions
COMMENT 'Order headers, one row per order, 365 days. channel: walk_in (Hot-N-Ready counter), pizza_portal (app pickup), delivery (DoorDash), phone.'
AS
WITH days AS (SELECT explode(sequence(date_sub(DATE'{END_DATE}', {DAYS - 1}), DATE'{END_DATE}')) AS order_date),
ev AS (SELECT event_date, max(attendance) AS attendance FROM {SCHEMA}.local_events GROUP BY event_date),
sd AS (
  SELECT s.store_id, s.city, d.order_date,
    CAST(
      (230 + (s.store_id * 37) % 110) * (s.sqft / 1800.0)
      * CASE dayofweek(d.order_date) WHEN 6 THEN 1.28 WHEN 7 THEN 1.15 WHEN 1 THEN 1.05 WHEN 2 THEN 0.88 ELSE 0.95 END
      * CASE WHEN ev.event_date IS NOT NULL AND s.city IN ('Detroit','Hamtramck','Ferndale','Dearborn') THEN 1.30
             WHEN ev.event_date IS NOT NULL THEN 1.10 ELSE 1.0 END
      * (1 + 0.04 * sin(dayofyear(d.order_date) / 58.0))
      * (0.92 + (abs(hash(s.store_id, d.order_date)) % 1000) / 6250.0)
    AS INT) AS n_orders
  FROM {SCHEMA}.stores s CROSS JOIN days d LEFT JOIN ev ON ev.event_date = d.order_date
),
o AS (
  SELECT store_id, order_date, seq, (abs(hash(store_id, order_date, seq, 'h')) % 1000000) / 1000000.0 AS r1,
         (abs(hash(store_id, order_date, seq, 'c')) % 1000000) / 1000000.0 AS r2, (abs(hash(store_id, order_date, seq, 'p')) % 1000000) / 1000000.0 AS r3
  FROM sd LATERAL VIEW explode(sequence(1, n_orders)) x AS seq
)
SELECT
  CAST(store_id AS BIGINT) * 100000000 + CAST(date_format(order_date, 'yyMMdd') AS BIGINT) * 1000 + seq AS order_id,
  store_id, order_date,
  CAST(CASE WHEN r1 < 0.02 THEN 10 WHEN r1 < 0.14 THEN 11 WHEN r1 < 0.30 THEN 12 WHEN r1 < 0.41 THEN 13
       WHEN r1 < 0.47 THEN 14 WHEN r1 < 0.53 THEN 15 WHEN r1 < 0.62 THEN 16 WHEN r1 < 0.78 THEN 17
       WHEN r1 < 0.91 THEN 18 WHEN r1 < 0.96 THEN 19 WHEN r1 < 0.985 THEN 20 WHEN r1 < 0.995 THEN 21 ELSE 22 END AS INT) AS order_hour,
  CASE WHEN r2 < 0.45 THEN 'walk_in' WHEN r2 < 0.75 THEN 'pizza_portal' WHEN r2 < 0.93 THEN 'delivery' ELSE 'phone' END AS channel,
  CASE WHEN r3 < 0.58 THEN 'card' WHEN r3 < 0.80 THEN 'cash' WHEN r3 < 0.97 THEN 'app_wallet' ELSE 'gift_card' END AS payment_method,
  CAST(1 + floor(r3 * 1000 % 4) AS INT) AS item_count
FROM o"""

    yield "pos_line_items", f"""
CREATE TABLE {SCHEMA}.pos_line_items COMMENT 'Order line items. Join to menu_items on item_id; menu_items.dough_type maps pizzas and breads to dough consumption.' AS
WITH c AS (SELECT item_id, price, sum(order_weight) OVER (ORDER BY item_id) / sum(order_weight) OVER () AS cum FROM {SCHEMA}.menu_items),
w AS (SELECT item_id, price, coalesce(lag(cum) OVER (ORDER BY item_id), 0.0) AS lo, cum FROM c),
li AS (
  SELECT t.order_id, t.store_id, t.order_date, t.order_hour, t.channel, line_no,
         (abs(hash(t.order_id, line_no, 'i')) % 1000000) / 1000000.0 AS r, (abs(hash(t.order_id, line_no, 'q')) % 1000000) / 1000000.0 AS rq
  FROM {SCHEMA}.pos_transactions t LATERAL VIEW explode(sequence(1, t.item_count)) x AS line_no
)
SELECT li.order_id, line_no, li.store_id, li.order_date, li.order_hour, li.channel,
       w.item_id, CAST(CASE WHEN rq < 0.78 THEN 1 WHEN rq < 0.95 THEN 2 ELSE 3 END AS INT) AS quantity,
       w.price AS unit_price,
       CAST(w.price * CASE WHEN rq < 0.78 THEN 1 WHEN rq < 0.95 THEN 2 ELSE 3 END AS DECIMAL(8,2)) AS line_total
FROM li JOIN w ON li.r >= w.lo AND li.r < w.cum"""

    yield "order totals", f"""
CREATE OR REPLACE TABLE {SCHEMA}.pos_transactions
COMMENT 'Order headers, one row per order, 365 days. channel: walk_in (Hot-N-Ready counter), pizza_portal (app pickup), delivery (DoorDash), phone. order_total includes a delivery fee for delivery orders.'
AS SELECT t.order_id, t.store_id, t.order_date, t.order_hour,
  timestamp_seconds(unix_timestamp(CAST(t.order_date AS TIMESTAMP)) + t.order_hour * 3600 + abs(hash(t.order_id)) % 3600) AS order_ts,
  t.channel, t.payment_method, t.item_count,
  CAST(l.subtotal + CASE WHEN t.channel = 'delivery' THEN 3.99 ELSE 0 END AS DECIMAL(8,2)) AS order_total,
  CAST(l.subtotal AS DECIMAL(8,2)) AS food_subtotal
FROM {SCHEMA}.pos_transactions t JOIN (SELECT order_id, sum(line_total) AS subtotal FROM {SCHEMA}.pos_line_items GROUP BY order_id) l USING (order_id)"""

    # Dough: one dough ball per pizza or bread unit sold. Mixed = forecast need with misforecast noise;
    # waste from over-mixing, stockouts when an event night outruns the mix.
    yield "dough_prep_log", f"""
CREATE TABLE {SCHEMA}.dough_prep_log COMMENT 'Daily dough prep by store and dough type: balls mixed, used, wasted; temper time; dinner-rush stockout flag. Waste is driven by over-mixing; stockouts by event nights.' AS
WITH used AS (
  SELECT l.store_id, l.order_date AS prep_date, m.dough_type, sum(l.quantity) AS balls_used
  FROM {SCHEMA}.pos_line_items l JOIN {SCHEMA}.menu_items m USING (item_id)
  WHERE m.dough_type IS NOT NULL GROUP BY 1, 2, 3
),
ev AS (SELECT DISTINCT event_date FROM {SCHEMA}.local_events),
j AS (
  SELECT u.*, ev.event_date IS NOT NULL AS event_day,
    (abs(hash(u.store_id, u.prep_date, u.dough_type)) % 1000) / 1000.0 AS r,
    1.0 + (u.store_id % 5) * 0.012 AS store_bias
  FROM used u LEFT JOIN ev ON ev.event_date = u.prep_date
),
m AS (
  SELECT *, CAST(round(balls_used * CASE WHEN event_day THEN 0.97 + r * 0.08 ELSE store_bias + r * 0.06 END) AS INT) AS mixed
  FROM j
)
SELECT store_id, prep_date, dough_type,
  greatest(mixed, 0) AS balls_mixed,
  least(balls_used, mixed) AS balls_used,
  greatest(mixed - balls_used, 0) AS balls_wasted,
  CAST(CASE dough_type WHEN 'Large Classic' THEN 180 WHEN 'Thin Crust' THEN 150 WHEN 'Deep Dish' THEN 200 ELSE 120 END
       + (r - 0.5) * 40 AS INT) AS avg_temper_minutes,
  mixed < balls_used AS rush_stockout_flag,
  greatest(balls_used - mixed, 0) AS balls_short
FROM m"""

    yield "labor_schedule", f"""
CREATE TABLE {SCHEMA}.labor_schedule COMMENT 'Hourly staffing by store, last 90 days plus next 7. labor_cost = actual_staff * blended rate.' AS
WITH h AS (
  SELECT store_id, order_date AS work_date, order_hour AS hour, count(*) AS orders
  FROM {SCHEMA}.pos_transactions WHERE order_date > date_sub(DATE'{END_DATE}', 90) GROUP BY 1, 2, 3
),
fut AS (
  SELECT store_id, date_add(work_date, 7) AS work_date, hour, orders FROM h WHERE work_date > date_sub(DATE'{END_DATE}', 7)
),
a AS (SELECT *, false AS is_forecast FROM h UNION ALL SELECT *, true FROM fut)
SELECT store_id, work_date, hour, orders AS orders_actual_or_forecast,
  CAST(greatest(2, ceil(orders / 9.0) + 1) AS INT) AS scheduled_staff,
  CASE WHEN is_forecast THEN NULL ELSE CAST(greatest(2, ceil(orders / 9.0) + 1 + CASE WHEN abs(hash(store_id, work_date, hour)) % 10 = 0 THEN -1 WHEN abs(hash(store_id, work_date, hour)) % 10 = 1 THEN 1 ELSE 0 END) AS INT) END AS actual_staff,
  CAST(greatest(2, ceil(orders / 9.0) + 1) * 14.60 AS DECIMAL(8,2)) AS labor_cost,
  is_forecast
FROM a"""

    yield "inventory_levels", f"""
CREATE TABLE {SCHEMA}.inventory_levels COMMENT 'Daily end-of-day on-hand by store and ingredient, last 30 days.' AS
WITH d AS (SELECT explode(sequence(date_sub(DATE'{END_DATE}', 29), DATE'{END_DATE}')) AS snapshot_date)
SELECT s.store_id, i.ingredient_id, d.snapshot_date,
  CAST(i.par_level * (0.25 + (abs(hash(s.store_id, i.ingredient_id, d.snapshot_date)) % 1000) / 1000.0 * 1.05) AS DECIMAL(10,1)) AS qty_on_hand,
  i.par_level,
  CAST(3 * (0.25 + (abs(hash(s.store_id, i.ingredient_id, d.snapshot_date)) % 1000) / 1000.0 * 1.05) AS DECIMAL(6,1)) AS days_supply
FROM {SCHEMA}.stores s CROSS JOIN {SCHEMA}.ingredients i CROSS JOIN d"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="DEFAULT")
    ap.add_argument("--warehouse", default="0168e23e24e6ae10")
    ap.add_argument("--catalog", default="jdub_demo")
    ap.add_argument("--schema", default="lce_store_ops")
    a = ap.parse_args()
    global SCHEMA
    SCHEMA = f"{a.catalog}.{a.schema}"
    for label, sql in statements():
        run(sql, a.profile, a.warehouse, label)


if __name__ == "__main__":
    main()
