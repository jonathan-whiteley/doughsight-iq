# DoughSight IQ deploy notes

- Workspace: DEFAULT (fe-vm-jdub-vm-serverless), org id 66306676349647, warehouse 0168e23e24e6ae10
- Schema: `jdub_demo.lce_store_ops` (synthetic, regenerate with `.venv/bin/python scripts/generate_lce_data.py`; pure SQL on the warehouse, ~5 min)
- Genie space: `01f1bdac47ea1655a766a731ee857f2a` ("DoughSight IQ: Little Caesars Store Ops"), built by `scripts/create_genie_space.py`
- App: `doughsight-iq`

## Tables (2026-10-01 build)

| Table | Rows | Notes |
|---|---|---|
| stores | 25 | Matches `services/demo_data.py` DEMO_STORES |
| menu_items | 17 | `dough_type` maps items to dough |
| ingredients | 30 | Matches LC_INGREDIENTS |
| local_events | 214 | Tigers, Red Wings, Pistons, Lions home games |
| employees | 361 | |
| pos_transactions | 2,540,199 | 365 days, ~278 orders/store/day, AOV ~$20, channel 45/30/18/7 |
| pos_line_items | 6,351,092 | |
| dough_prep_log | 36,500 | ~3.3% waste, stockouts on event nights |
| labor_schedule | 30,658 | last 90 days hourly + next 7 forecast |
| inventory_levels | 22,500 | last 30 days daily |
