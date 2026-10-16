# Little Caesars Store Ops (StoreSight IQ reskin) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Adapt the StoreSight IQ Databricks App (Subway store-ops demo) into a Little Caesars store-operations app with LC branding, LC sample data, and a **Dough HQ** tab replacing Bread Baker, deployed as a new app on the DEFAULT workspace.

**Architecture:** Same as StoreSight: FastAPI + React, ~90% of KPIs simulated in `services/demo_data.py`, embedded Genie is the real-data path. We keep the Subway tab structure (Operations, Forecast, Labor, Inventory, *Dough HQ*, Genie; regional Map + Compare) and generate a fresh LC dataset for Genie.

**Prior art:** an earlier StoreSight reskin following the same pattern.

## Global Constraints

- **Project dir:** `~/Desktop/Projects/lce-store-ops` (git repo; baseline commit = untouched StoreSight copy).
- **Product name (decided 2026-10-01):** `DoughSight IQ`. Centralize it: frontend `src/brand.ts` exports `PRODUCT_NAME`, `BRAND_NAME = 'Little Caesars'`; backend reads `APP_TITLE` from `config/settings.py`. A rename must be a 2-file change.
- **App name (Databricks Apps slug):** `doughsight-iq`.
- **Workspace / profile:** DEFAULT (`fe-vm-jdub-vm-serverless`), `--profile DEFAULT`. Org id `66306676349647`. Warehouse `0168e23e24e6ae10`.
- **Unity Catalog:** `jdub_demo.lce_store_ops` (NEW schema). Never write to `jdub_demo.little_caesars` (other demos depend on it) or anything `ioc_sandbox`.
- **Store ids:** integers 1-25, same in app and tables.
- **Writing style:** no em dashes or en dashes anywhere (copy, comments, data). Colons, semicolons, commas, parentheses. Hyphens for ranges only.
- **No ML serving endpoints, no Lakebase** (app degrades gracefully as StoreSight does).
- **Testing reality:** no unit-test suite. Verification = backend boots + `curl` smoke tests, `npm run build` clean, browser screenshots.
- **Commits:** each task commits only its own paths (`git add <paths>`); if `index.lock` exists, wait and retry. End messages with `Co-authored-by: Isaac <no-reply@databricks.com>`.

## Domain model (Little Caesars)

**Region:** Metro Detroit (LC HQ is Detroit). 25 stores, e.g. Detroit Woodward Ave (District Detroit), Detroit Midtown, Dearborn Michigan Ave, Royal Oak Main St, Troy Big Beaver, Southfield, Livonia, Warren, Sterling Heights, Novi, Ann Arbor State St, Ypsilanti, Canton, Westland, Farmington Hills, Rochester Hills, Pontiac, Clinton Twp, St Clair Shores, Grosse Pointe, Taylor, Wyandotte, Hamtramck, Ferndale, Auburn Hills. Use real city centroids (small jitter), plausible street addresses, phone area codes 313/248/586/734.

**Menu:** Hot-N-Ready Classic (pepperoni, cheese), ExtraMostBestest, Detroit-Style Deep!Deep! Dish, Thin Crust, 3 Meat Treat, Ultimate Supreme, Veggie, Crazy Puffs, Crazy Bread, Italian Cheese Bread, Crazy Sauce, Caesar Wings (Buffalo, BBQ, Garlic Parmesan, Oven Roasted), Caesar Dips, 2L soda.

**Inventory ingredients (categories):** dough (Large Classic dough balls, Thin crust dough, Deep Dish dough, Crazy Bread dough), cheese (mozzarella/muenster blend, parmesan), protein (pepperoni, Italian sausage, bacon, ham, chicken wings raw), vegetable (green peppers, onions, mushrooms, black olives, banana peppers, jalapenos, pineapple), sauce (pizza sauce, Crazy Sauce cups, wing sauces, butter garlic), packaging (large pizza boxes, deep dish boxes, wing boats, Crazy Bread bags), other (2L soda, cornmeal, flour 50lb bags).

**Channels:** `walk_in` (Hot-N-Ready counter), `pizza_portal` (app/online pickup from the heated Pizza Portal), `delivery` (DoorDash), `phone`. Typical split ~45/30/18/7.

**Day shape:** open 10:30-23:00. Lunch peak 11-13, big dinner peak 16-19 (Hot-N-Ready rush, 17-18 highest). Avg ticket $13-17, 260-380 orders/day per store.

**Dough HQ (placeholder logic; Jonathan will supply real inputs later):** LC dough is made fresh in-store daily, held in the walk-in cooler, and must **temper** (warm to room temp, roughly 2-3 hrs) before slap-out. Model per store per day:
- Dough types: Large Classic, Thin Crust (pressed), Deep Dish (pan-proofed), Crazy Bread.
- Lifecycle stages: `mixed` -> `cold_hold` (walk-in, usable up to ~3 days, track age day 1/2/3) -> `tempering` -> `ready` (slap-out window ~4-6 hrs) -> `overproofed`/`expired` (waste).
- Outputs: dough on hand by stage and age, today's prep schedule (mix batches + pull-to-temper times keyed to the 11:00 and 16:00 rushes), ML recommendations ("Pull 4 trays Large Classic to temper by 13:30 for dinner rush", "Mix 2 extra batches tomorrow: Lions home game"), alerts (day-3 dough at risk, under-tempered for rush, waste trend), KPIs (dough balls ready vs forecast need, projected waste %, rush coverage %).
- Keep this logic isolated in `api/dough.py` + `get_dough_inventory()` in `demo_data.py` so real inputs slot in without touching other tabs.

## Tasks

### Task 1: LC dataset + Genie space (independent)
- [ ] Copy `notebooks/01_generate_data_and_streaming.py` to `notebooks/lce_01_generate_data.py`; rewrite for the LC domain above. Target `jdub_demo.lce_store_ops` (`CREATE SCHEMA IF NOT EXISTS`, no `CREATE CATALOG`). Tables: `stores`, `menu_items`, `pos_transactions` (365 days, channel + hour shape above), `pos_line_items`, `employees`, `labor_schedule`, `ingredients`, `inventory_levels`, plus NEW `dough_prep_log` (store_id, date, dough_type, balls_mixed, balls_used, balls_wasted, avg_temper_minutes, rush_stockout_flag). Drop all streaming/Lakebase sections.
- [ ] Run on serverless via `databricks jobs submit --profile DEFAULT` (no cluster spec; upload notebook to workspace first). Verify row counts.
- [ ] Add table + column comments. Create Genie space via `POST /api/2.0/genie/spaces` (fe-internal-tools `genie-rooms` skill), title "Little Caesars Store Ops", warehouse above, LC instructions and 8-10 sample questions (no benchmarks). Record the space id in `docs/superpowers/plans/DEPLOY_NOTES.md`.
- [ ] Commit `notebooks/lce_01_generate_data.py` and the deploy notes.

### Task 2: Backend reskin
- [ ] `services/demo_data.py`: LC stores, ingredients, hourly pattern, channels, ticket/volume ranges; replace bread generator with `get_dough_inventory()` (dataclass `DoughItem`). Region phone/manager names realistic.
- [ ] `api/bread.py` -> `api/dough.py` (router prefix `/api/dough`): endpoints `inventory`, `schedule`, `recommendations`, `optimize`, `alerts`, plus `summary` (KPIs). Same per-store, client-hour behaviour as bread. Update `api/__init__.py`, `api/state.py` (`/state/dough-schedule/...`).
- [ ] `api/inventory.py`, `operations.py`, `forecast.py`, `labor.py`, `stores.py`: LC copy, ingredient lists, channels, Detroit events context (Lions/Tigers/Red Wings/Pistons home games drive demand; LC owns the Red Wings and Tigers, a great demo hook).
- [ ] `config/settings.py`, `main.py`, `app.yaml`: catalog/schema `jdub_demo`/`lce_store_ops`, endpoint names `lce-*`, `APP_TITLE`. Keep `valueFrom` keys `sql_warehouse`, `genie_space`.
- [ ] Verify: boot uvicorn locally, curl every router; no "subway"/"bread"/"sandwich" left in `api/ services/ config/ main.py app.yaml` (`grep -rni`).
- [ ] Commit backend paths only.

### Task 3: Frontend reskin + Dough HQ page (after Task 2)
- [ ] Fetch the REAL Little Caesars logo (e.g. Wikimedia Commons SVG/PNG) into `frontend/public/`; never redraw it. Derive palette from it (LC orange ~#FF6600 family, black, white). Tailwind `lc` color namespace replaces `subway`; update `index.css`, `Button`, `Card`, charts, MapView RGB arrays, Login, layouts, favicon, `index.html` title.
- [ ] `src/brand.ts` with product/brand constants; use everywhere product name appears.
- [ ] `pages/store/Bread.tsx` -> `pages/store/DoughHQ.tsx`, route `dough`, nav label "Dough HQ". Cards: Dough on Hand (stage + age), Today's Prep and Temper Schedule, ML Dough Recommendations (add to schedule), Dough Alerts, KPI strip (ready vs need, rush coverage, projected waste). Update `api/client.ts` and `StoreLayout` prefetch/state.
- [ ] All Subway copy -> LC (channels, ingredients, "Subway App" -> "Pizza Portal", persona descriptions, Genie iframe title).
- [ ] Verify: `npm run build` clean; grep frontend/src for subway/bread/sandwich/footlong = none; run app locally and screenshot every tab.
- [ ] Commit frontend paths only.

### Task 4: Deploy + verify (controller)
- [ ] `databricks apps create doughsight-iq`; `apps update --json` with resources `sql_warehouse` (CAN_USE) + `genie_space` (CAN_RUN); grant app SP CAN_RUN on Genie space ACL and SELECT on the schema.
- [ ] `databricks sync --full . /Workspace/Users/<me>/apps/doughsight-iq`, `apps deploy --source-code-path`.
- [ ] Browser check every tab + Genie; save memory `reference_lce_store_ops_deploy`.
