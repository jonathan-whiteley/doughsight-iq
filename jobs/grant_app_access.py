# Databricks notebook source
# MAGIC %md
# MAGIC ## Give the app read access
# MAGIC `USE CATALOG`, `USE SCHEMA` and `SELECT` on the demo schema for the app's service principal. Genie `CAN_RUN` is set by the bundle itself (`resources/doughsight.genie_space.yml`).

# COMMAND ----------

import time
from databricks.sdk import WorkspaceClient

p = {k: dbutils.widgets.get(k) for k in ["catalog", "schema", "warehouse_id", "app_name"]}
w = WorkspaceClient()
sp = w.apps.get(p["app_name"]).service_principal_client_id
print(f"App {p['app_name']} service principal: {sp}")


def run_sql(sql):
    d = w.api_client.do("POST", "/api/2.0/sql/statements",
                        body={"warehouse_id": p["warehouse_id"], "statement": sql, "wait_timeout": "50s"})
    while d["status"]["state"] in ("PENDING", "RUNNING"):
        time.sleep(5)
        d = w.api_client.do("GET", f"/api/2.0/sql/statements/{d['statement_id']}")
    if d["status"]["state"] != "SUCCEEDED":
        raise RuntimeError(d["status"].get("error", {}).get("message", d["status"]["state"])[:300])


grants = [f"GRANT USE CATALOG ON CATALOG `{p['catalog']}` TO `{sp}`",
          f"GRANT USE SCHEMA, SELECT ON SCHEMA `{p['catalog']}`.`{p['schema']}` TO `{sp}`"]
for_owner = []
for g in grants:
    try:
        run_sql(g)
        print(f"✅ {g}")
    except RuntimeError as e:
        for_owner.append(g)
        print(f"⚠️  Couldn't run: {g}\n    {e}")
if for_owner:
    print("\n👉 Ask your schema owner (or anyone with MANAGE on it) to run:\n\n" + ";\n".join(for_owner) + ";\n")
    print("The app deploys either way, but it can't read the data until these are granted.")
