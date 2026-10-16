# Databricks notebook source
# MAGIC %md
# MAGIC # DoughSight IQ: the production ML behind the app
# MAGIC
# MAGIC Three models feed three tabs of the DoughSight IQ store-ops app. Each one shows a different production ML capability on Databricks; all three are tracked in MLflow and governed in Unity Catalog.
# MAGIC
# MAGIC | App tab | Question it answers | Model | Capability it highlights | How the app consumes it |
# MAGIC |---|---|---|---|---|
# MAGIC | **Forecast** | How many orders will each store get each day next week? | LightGBM on **Feature Views** | Declarative features, point-in-time correct training, features packaged with the model | Nightly batch: `forecast_predictions` |
# MAGIC | **Labor** | How many crew should be on the line each hour? | **Custom MLflow PyFunc**: orders model plus staffing rules | Business logic shipped inside the model, so the endpoint answers in crew, not raw predictions | Real-time endpoint `doughsight-labor`, plus `labor_recommendations` |
# MAGIC | **Dough HQ** | How many dough balls should each store mix tomorrow? | **Champion vs challenger** (Ridge vs tuned XGBoost) | Compare on a business metric (waste vs stockouts), then promote with an alias | Real-time endpoint `doughsight-dough`, plus `dough_recommendations` |
# MAGIC
# MAGIC **Flow:** 1. Train with Feature Views, 2. Serve with Model Serving, 3. Govern with MLflow and Unity Catalog, 4. Monitor with inference tables and prediction tables.
# MAGIC
# MAGIC Data: `jdub_demo.lce_store_ops` (25 Metro Detroit stores, one year of POS orders, hourly labor, daily dough prep, and Tigers, Red Wings, Pistons, and Lions home games).

# COMMAND ----------

# MAGIC %pip install databricks-feature-engineering==0.16.1 lightgbm==4.5.0 xgboost==2.1.4 --quiet
# MAGIC %restart_python

# COMMAND ----------

import json
import os
import tempfile
from datetime import timedelta

import joblib
import lightgbm as lgb
import mlflow
import numpy as np
import pandas as pd
import sklearn
import xgboost as xgb
from databricks.feature_engineering import FeatureEngineeringClient
from databricks.feature_engineering.entities import (
    AggregationFunction, Avg, Count, DeltaTableSource, SlidingWindow,
)
from mlflow.models import infer_signature
from mlflow.tracking import MlflowClient
from pyspark.sql import functions as F
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

CATALOG, SCHEMA = "jdub_demo", "lce_store_ops"
FQ = f"{CATALOG}.{SCHEMA}"

FORECAST_MODEL = f"{FQ}.doughsight_forecast"
LABOR_MODEL = f"{FQ}.doughsight_labor"
DOUGH_MODEL = f"{FQ}.doughsight_dough"
LABOR_ENDPOINT, DOUGH_ENDPOINT = "doughsight-labor", "doughsight-dough"

ME = spark.sql("SELECT current_user()").first()[0]
EXPERIMENT = f"/Users/{ME}/doughsight-ml-demo/doughsight_ml_experiment"

mlflow.set_registry_uri("databricks-uc")
mlflow.set_experiment(EXPERIMENT)
client = MlflowClient(registry_uri="databricks-uc")
fe = FeatureEngineeringClient()

# The synthetic data ends on a fixed day; "tomorrow" is the day after it.
AS_OF = spark.sql(f"SELECT max(order_date) FROM {FQ}.pos_transactions").first()[0]
TOMORROW = AS_OF + timedelta(days=1)
print(f"Data runs through {AS_OF}; scoring for {TOMORROW} onward. Experiment: {EXPERIMENT}")

# COMMAND ----------

# MAGIC %md
# MAGIC Shared calendar context used by every model: day of week, weekend flag, and the home-game schedule. Games are published months ahead, so these are fair inputs for a forecast (no peeking at the future).

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE TEMP VIEW calendar AS
SELECT d AS ds,
       dayofweek(d) AS dow,
       CASE WHEN dayofweek(d) IN (1, 7) THEN 1 ELSE 0 END AS is_weekend,
       month(d) AS month,
       coalesce(e.n_events, 0) AS n_events,
       coalesce(e.max_attendance, 0) AS max_attendance
FROM (SELECT explode(sequence(DATE'2025-10-01', DATE_ADD(DATE'{AS_OF}', 14))) AS d)
LEFT JOIN (
  SELECT event_date, count(*) AS n_events, max(attendance) AS max_attendance
  FROM {FQ}.local_events GROUP BY event_date
) e ON e.event_date = d
""")
display(spark.sql("SELECT * FROM calendar WHERE n_events > 0 ORDER BY ds DESC LIMIT 5"))

# COMMAND ----------

# MAGIC %md
# MAGIC # 1. Train
# MAGIC ## 1a. Forecast tab: Feature Views + point-in-time training
# MAGIC
# MAGIC Instead of hand-writing window functions, we **declare** the features once: "orders per store over the last 7 and 28 days" and "average ticket over 28 days". Unity Catalog stores the definitions; Databricks computes them point-in-time for training and for scoring, so training and production can never drift apart.

# COMMAND ----------

pos_source = DeltaTableSource(catalog_name=CATALOG, schema_name=SCHEMA, table_name="pos_transactions")
# order_total is DECIMAL; expose a DOUBLE copy so the model sees the same numeric type in training and scoring.
TICKET_SQL = "*, CAST(order_total AS DOUBLE) AS order_total_usd"
ticket_source = DeltaTableSource(
    catalog_name=CATALOG, schema_name=SCHEMA, table_name="pos_transactions", transformation_sql=TICKET_SQL,
    dataframe_schema=spark.sql(f"SELECT {TICKET_SQL} FROM {FQ}.pos_transactions LIMIT 0").schema.json(),
)


def sliding(days):
    return SlidingWindow(window_duration=timedelta(days=days), slide_duration=timedelta(days=1))


def declare(name, function, source=pos_source):
    """Register a Feature View definition in UC; reuse it on reruns."""
    try:
        return fe.create_feature(
            source=source, function=function, entity=["store_id"], timeseries_column="order_ts",
            catalog_name=CATALOG, schema_name=SCHEMA, name=name,
        )
    except Exception as e:
        if "already exist" not in str(e).lower() and "AlreadyExists" not in type(e).__name__:
            raise
        return fe.get_feature(full_name=f"{FQ}.{name}")


FEATURES = [
    declare("doughsight_store_orders_7d", AggregationFunction(operator=Count(input="order_id"), time_window=sliding(7))),
    declare("doughsight_store_orders_28d", AggregationFunction(operator=Count(input="order_id"), time_window=sliding(28))),
    declare("doughsight_store_ticket_avg_28d", AggregationFunction(operator=Avg(input="order_total_usd"), time_window=sliding(28)),
            source=ticket_source),
]
print("Feature Views:", [f.name for f in FEATURES])

# COMMAND ----------

# MAGIC %md
# MAGIC **Labels:** one row per store per day, stamped at midnight. The point-in-time join only uses feature windows that closed at or before that timestamp, so a day's own orders can never leak into its features. The check below proves it against a hand-written query.

# COMMAND ----------

labels = spark.sql(f"""
SELECT t.store_id,
       CAST(t.order_date AS TIMESTAMP) AS order_ts,
       count(*) AS daily_orders,
       c.dow, c.is_weekend, c.month, c.n_events, c.max_attendance
FROM {FQ}.pos_transactions t
JOIN calendar c ON c.ds = t.order_date
WHERE t.order_date >= DATE_ADD((SELECT min(order_date) FROM {FQ}.pos_transactions), 28)
GROUP BY ALL
""")

SPLIT = "2026-08-01"  # time-based holdout: train on the past, test on the most recent two months
train_labels = labels.filter(f"order_ts < '{SPLIT}'")
test_labels = labels.filter(f"order_ts >= '{SPLIT}'")

ts_train = fe.create_training_set(
    df=train_labels, features=FEATURES, label="daily_orders", exclude_columns=["store_id", "order_ts"],
)

# Point-in-time check: the 7-day feature for store 1 on 2026-07-15 must equal orders from Jul 8 through Jul 14.
check = fe.create_training_set(
    df=train_labels.filter("store_id = 1 AND order_ts = '2026-07-15'"), features=FEATURES[:1], label="daily_orders",
).load_df().first()
expected = spark.sql(f"""
SELECT count(*) FROM {FQ}.pos_transactions
WHERE store_id = 1 AND order_ts >= '2026-07-08' AND order_ts < '2026-07-15'
""").first()[0]
print(f"Feature View value: {check['doughsight_store_orders_7d']}, hand-written SQL: {expected}")
assert check["doughsight_store_orders_7d"] == expected, "point-in-time window does not match"

train_pdf = ts_train.load_df().toPandas()
X_f, y_f = train_pdf.drop(columns=["daily_orders"]), train_pdf["daily_orders"]
print(f"Training rows: {len(train_pdf):,}; features: {list(X_f.columns)}")

# COMMAND ----------

with mlflow.start_run(run_name="forecast_lightgbm") as run:
    params = dict(n_estimators=400, learning_rate=0.05, num_leaves=31, min_child_samples=20, random_state=7, verbose=-1)
    forecast_model = lgb.LGBMRegressor(**params).fit(X_f, y_f)
    mlflow.log_params(params)
    mlflow.set_tags({"app_tab": "Forecast", "capability": "feature_views"})
    # fe.log_model packages the Feature View lineage with the model, so scoring only needs store_id + timestamp.
    fe.log_model(
        model=forecast_model, artifact_path="model", flavor=mlflow.lightgbm,
        training_set=ts_train, registered_model_name=FORECAST_MODEL,
    )
    forecast_run_id = run.info.run_id

forecast_version = max(
    (v for v in client.search_model_versions(f"name='{FORECAST_MODEL}'") if v.run_id == forecast_run_id),
    key=lambda v: int(v.version),
).version

# Evaluate on the holdout through the same scoring path production uses.
scored_test = fe.score_batch(
    model_uri=f"models:/{FORECAST_MODEL}/{forecast_version}", df=test_labels.drop("daily_orders"), result_type="double",
)
eval_pdf = (scored_test.join(test_labels.select("store_id", "order_ts", "daily_orders"), ["store_id", "order_ts"])
            .select("daily_orders", "prediction", "doughsight_store_orders_7d").toPandas())
mae = mean_absolute_error(eval_pdf.daily_orders, eval_pdf.prediction)
naive_mae = mean_absolute_error(eval_pdf.daily_orders, eval_pdf.doughsight_store_orders_7d / 7)
mape = float(np.mean(np.abs(eval_pdf.prediction - eval_pdf.daily_orders) / eval_pdf.daily_orders))
with mlflow.start_run(run_id=forecast_run_id):
    mlflow.log_metrics({"test_mae": mae, "test_mape": mape, "naive_7d_avg_mae": naive_mae})
client.set_registered_model_alias(FORECAST_MODEL, "champion", forecast_version)
print(f"Forecast v{forecast_version}: MAE {mae:.1f} orders/day ({mape:.1%} MAPE) vs naive 7-day average MAE {naive_mae:.1f}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1b. Labor tab: a custom PyFunc that answers in crew, not raw predictions
# MAGIC
# MAGIC A LightGBM model predicts orders for a store-hour. The staffing rules (orders one crew member can handle, minimum and maximum crew, wage) live **inside the model** as versioned config, so the endpoint returns `recommended_staff` and `labor_cost_estimate` directly and the rules are governed with the model.

# COMMAND ----------

labor_df = spark.sql(f"""
WITH h AS (
  SELECT store_id, work_date, hour, orders_actual_or_forecast AS orders, actual_staff, labor_cost
  FROM {FQ}.labor_schedule WHERE NOT is_forecast
), f AS (
  SELECT h.*, AVG(orders) OVER (PARTITION BY store_id, hour ORDER BY work_date
                                ROWS BETWEEN 28 PRECEDING AND 1 PRECEDING) AS store_hour_avg_orders_28d
  FROM h
)
SELECT f.*, c.dow, c.is_weekend, c.n_events, c.max_attendance
FROM f JOIN calendar c ON c.ds = f.work_date
WHERE store_hour_avg_orders_28d IS NOT NULL
""").toPandas()

LABOR_FEATURES = ["hour", "dow", "is_weekend", "n_events", "max_attendance", "store_hour_avg_orders_28d"]
INT_COLS = ["hour", "dow", "is_weekend", "n_events", "max_attendance"]
labor_df[INT_COLS] = labor_df[INT_COLS].astype("int64")
labor_df["store_hour_avg_orders_28d"] = labor_df["store_hour_avg_orders_28d"].astype("float64")

hourly_wage = float((labor_df.labor_cost / labor_df.actual_staff).mean())
STAFFING_RULES = {
    "features": LABOR_FEATURES,
    "orders_per_crew_hour": 5.0,  # target productivity; stores average about 4.8 today
    "min_crew": 2,
    "max_crew": 10,
    "hourly_wage": round(hourly_wage, 2),
}
LABOR_SPLIT = pd.Timestamp("2026-09-10").date()
lab_train, lab_test = labor_df[labor_df.work_date < LABOR_SPLIT], labor_df[labor_df.work_date >= LABOR_SPLIT]
orders_model = lgb.LGBMRegressor(n_estimators=300, learning_rate=0.05, random_state=7, verbose=-1)
orders_model.fit(lab_train[LABOR_FEATURES], lab_train.orders)
print(f"Staffing rules: {STAFFING_RULES}")


class LaborStaffingModel(mlflow.pyfunc.PythonModel):
    """Predict hourly orders, then turn them into a crew recommendation."""

    def load_context(self, context):
        self.orders_model = joblib.load(context.artifacts["orders_model"])
        with open(context.artifacts["staffing_rules"]) as f:
            self.rules = json.load(f)

    def predict(self, context, model_input, params=None):
        r = self.rules
        orders = np.clip(self.orders_model.predict(model_input[r["features"]]), 0, None)
        crew = np.clip(np.ceil(orders / r["orders_per_crew_hour"]), r["min_crew"], r["max_crew"]).astype("int64")
        return pd.DataFrame({
            "predicted_orders": orders.round(1),
            "recommended_staff": crew,
            "labor_cost_estimate": (crew * r["hourly_wage"]).round(2),
        })


artifact_dir = tempfile.mkdtemp()
joblib.dump(orders_model, os.path.join(artifact_dir, "orders_model.joblib"))
with open(os.path.join(artifact_dir, "staffing_rules.json"), "w") as f:
    json.dump(STAFFING_RULES, f)
artifacts = {"orders_model": os.path.join(artifact_dir, "orders_model.joblib"),
             "staffing_rules": os.path.join(artifact_dir, "staffing_rules.json")}

# Validate the wrapper locally before logging, exactly as serving will call it.
ctx = mlflow.pyfunc.PythonModelContext(artifacts=artifacts, model_config={})
staffing = LaborStaffingModel()
staffing.load_context(ctx)
test_out = staffing.predict(ctx, lab_test)
labor_mae = mean_absolute_error(lab_test.orders, test_out.predicted_orders)
crew_hours_scheduled = int(lab_test.actual_staff.sum())
crew_hours_recommended = int(test_out.recommended_staff.sum())

example_in = lab_test[LABOR_FEATURES].head(3)
with mlflow.start_run(run_name="labor_staffing_pyfunc") as run:
    mlflow.log_params({f"rule_{k}": v for k, v in STAFFING_RULES.items() if k != "features"})
    mlflow.log_metrics({"test_orders_mae": labor_mae, "crew_hours_scheduled": crew_hours_scheduled,
                        "crew_hours_recommended": crew_hours_recommended})
    mlflow.set_tags({"app_tab": "Labor", "capability": "custom_pyfunc"})
    labor_info = mlflow.pyfunc.log_model(
        artifact_path="model",
        python_model=LaborStaffingModel(),
        artifacts=artifacts,
        signature=infer_signature(example_in, staffing.predict(ctx, example_in)),
        input_example=example_in,
        pip_requirements=[f"mlflow=={mlflow.__version__}", f"lightgbm=={lgb.__version__}",
                          f"scikit-learn=={sklearn.__version__}", f"pandas=={pd.__version__}",
                          f"numpy=={np.__version__}", f"joblib=={joblib.__version__}"],
        registered_model_name=LABOR_MODEL,
    )
labor_version = labor_info.registered_model_version
client.set_registered_model_alias(LABOR_MODEL, "champion", labor_version)
print(f"Labor v{labor_version}: orders MAE {labor_mae:.2f}/hour; holdout crew-hours scheduled {crew_hours_scheduled:,} "
      f"vs recommended {crew_hours_recommended:,}")
display(pd.concat([example_in.reset_index(drop=True), staffing.predict(ctx, example_in)], axis=1))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1c. Dough HQ tab: champion vs challenger
# MAGIC
# MAGIC Target: true dough demand per store, day, and dough type (balls used plus balls short). The plan mixes the prediction plus a 5% buffer. We judge models the way an operator would: **waste** (dough mixed but thrown out) versus **shortfall** (customers who could not get a Hot-N-Ready), priced into one daily cost. A challenger only replaces the champion if it lowers that cost.

# COMMAND ----------

dough_df = spark.sql(f"""
WITH d AS (
  SELECT store_id, prep_date, dough_type, balls_mixed, balls_wasted, balls_short,
         balls_used + balls_short AS demand, CAST(rush_stockout_flag AS INT) AS stockout
  FROM {FQ}.dough_prep_log
), f AS (
  SELECT d.*,
    AVG(demand) OVER (PARTITION BY store_id, dough_type ORDER BY prep_date ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING) AS demand_7d_avg,
    AVG(demand) OVER (PARTITION BY store_id, dough_type, dayofweek(prep_date) ORDER BY prep_date
                      ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS demand_same_dow_4w,
    SUM(stockout) OVER (PARTITION BY store_id, dough_type ORDER BY prep_date ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING) AS stockouts_7d
  FROM d
)
SELECT f.*, c.dow, c.is_weekend, c.n_events, c.max_attendance
FROM f JOIN calendar c ON c.ds = f.prep_date
WHERE demand_same_dow_4w IS NOT NULL
""").toPandas()

DOUGH_NUM = ["dow", "is_weekend", "n_events", "max_attendance", "demand_7d_avg", "demand_same_dow_4w", "stockouts_7d"]
DOUGH_FEATURES = ["dough_type"] + DOUGH_NUM
dough_df[["dow", "is_weekend", "n_events", "max_attendance", "stockouts_7d"]] = \
    dough_df[["dow", "is_weekend", "n_events", "max_attendance", "stockouts_7d"]].astype("int64")
dough_df[["demand_7d_avg", "demand_same_dow_4w"]] = dough_df[["demand_7d_avg", "demand_same_dow_4w"]].astype("float64")

d_train_all = dough_df[dough_df.prep_date < pd.Timestamp(SPLIT).date()]
d_test = dough_df[dough_df.prep_date >= pd.Timestamp(SPLIT).date()]
VALID_START = pd.Timestamp("2026-07-01").date()  # tune on July, compare on the untouched Aug-Sep holdout
d_fit, d_valid = d_train_all[d_train_all.prep_date < VALID_START], d_train_all[d_train_all.prep_date >= VALID_START]

BUFFER, BALL_COST, LOST_MARGIN = 0.05, 0.65, 3.00  # assumptions: $ per wasted ball, $ margin per short ball


def business_eval(y_true, y_pred):
    mix = np.ceil(np.asarray(y_pred) * (1 + BUFFER))
    y = np.asarray(y_true)
    waste, short = np.clip(mix - y, 0, None).sum(), np.clip(y - mix, 0, None).sum()
    return {"waste_balls": float(waste), "short_balls": float(short),
            "stockout_rate": float((y > mix).mean()), "daily_cost_usd": float((waste * BALL_COST + short * LOST_MARGIN) / d_test.prep_date.nunique())}


def pipeline(regressor):
    pre = ColumnTransformer([("dough", OneHotEncoder(handle_unknown="ignore"), ["dough_type"])], remainder="passthrough")
    return Pipeline([("prep", pre), ("model", regressor)])


dough_example = d_test[DOUGH_FEATURES].head(3)


def log_dough(model, run_name, extra_params):
    with mlflow.start_run(run_name=run_name) as run:
        mlflow.log_params(extra_params)
        metrics = business_eval(d_test.demand, model.predict(d_test[DOUGH_FEATURES]))
        metrics["test_mae"] = mean_absolute_error(d_test.demand, model.predict(d_test[DOUGH_FEATURES]))
        mlflow.log_metrics(metrics)
        mlflow.set_tags({"app_tab": "Dough HQ", "capability": "champion_challenger"})
        info = mlflow.sklearn.log_model(
            model, artifact_path="model", input_example=dough_example,
            signature=infer_signature(dough_example, model.predict(dough_example)),
            registered_model_name=DOUGH_MODEL,
        )
    return info.registered_model_version, metrics


def current_champion():
    """The @champion version, if it takes today's feature set (a schema change means re-baselining)."""
    try:
        version = client.get_model_version_by_alias(DOUGH_MODEL, "champion").version
    except Exception:
        return None
    schema = mlflow.pyfunc.load_model(f"models:/{DOUGH_MODEL}/{version}").metadata.get_input_schema()
    return version if schema and schema.input_names() == DOUGH_FEATURES else None


champion_version = current_champion()
if champion_version:
    print(f"Existing champion: v{champion_version}")
else:
    baseline = pipeline(Ridge(alpha=1.0)).fit(d_train_all[DOUGH_FEATURES], d_train_all.demand)
    champion_version, _ = log_dough(baseline, "dough_baseline_ridge", {"model": "ridge", "alpha": 1.0})
    client.set_registered_model_alias(DOUGH_MODEL, "champion", champion_version)
    print(f"No compatible champion: registered the Ridge baseline as champion v{champion_version}")

# COMMAND ----------

# MAGIC %md
# MAGIC **Challenger:** XGBoost with a small random hyperparameter search. Every trial is a nested MLflow run, tuned on July, then compared with the champion on the August and September holdout neither model has seen.

# COMMAND ----------


rng = np.random.default_rng(7)
trials = [{"n_estimators": int(rng.integers(150, 500)), "max_depth": int(rng.integers(3, 9)),
           "learning_rate": float(np.round(10 ** rng.uniform(np.log10(0.02), np.log10(0.2)), 4)),
           "subsample": float(np.round(rng.uniform(0.7, 1.0), 2))} for _ in range(10)]

with mlflow.start_run(run_name="dough_xgb_sweep"):
    results = []
    for i, p in enumerate(trials):
        with mlflow.start_run(run_name=f"trial_{i}", nested=True):
            m = pipeline(xgb.XGBRegressor(random_state=7, **p)).fit(d_fit[DOUGH_FEATURES], d_fit.demand)
            mae_v = mean_absolute_error(d_valid.demand, m.predict(d_valid[DOUGH_FEATURES]))
            mlflow.log_params(p)
            mlflow.log_metric("valid_mae", mae_v)
            results.append((mae_v, p))
    best_params = min(results, key=lambda r: r[0])[1]
    mlflow.log_params({f"best_{k}": v for k, v in best_params.items()})

challenger = pipeline(xgb.XGBRegressor(random_state=7, **best_params)).fit(d_train_all[DOUGH_FEATURES], d_train_all.demand)
challenger_version, challenger_metrics = log_dough(challenger, "dough_challenger_xgb", {"model": "xgboost", **best_params})
client.set_registered_model_alias(DOUGH_MODEL, "challenger", challenger_version)

champion = mlflow.pyfunc.load_model(f"models:/{DOUGH_MODEL}/{champion_version}")
champion_metrics = business_eval(d_test.demand, champion.predict(d_test[DOUGH_FEATURES]))
champion_metrics["test_mae"] = mean_absolute_error(d_test.demand, champion.predict(d_test[DOUGH_FEATURES]))

comparison = pd.DataFrame({
    f"Champion v{champion_version}": champion_metrics,
    f"Challenger v{challenger_version} (XGBoost)": challenger_metrics,
}).T[["daily_cost_usd", "waste_balls", "short_balls", "stockout_rate", "test_mae"]]
display(comparison.round(3).reset_index().rename(columns={"index": "plan"}))

# COMMAND ----------

# MAGIC %md
# MAGIC *With production data, add a third row for the stores' actual mix (`balls_mixed`) so the business sees the model against today's process. This synthetic dataset derives the mix from true demand, so that row would not be a fair baseline here.*
# MAGIC
# MAGIC **Promotion:** one alias move. The app and the endpoint config always reference `@champion`; the old champion stays one step away as `@previous` for instant rollback.

# COMMAND ----------

if challenger_metrics["daily_cost_usd"] < champion_metrics["daily_cost_usd"]:
    client.set_registered_model_alias(DOUGH_MODEL, "previous", champion_version)
    client.set_registered_model_alias(DOUGH_MODEL, "champion", challenger_version)
    client.delete_registered_model_alias(DOUGH_MODEL, "challenger")
    decision = f"Promoted v{challenger_version}: saves ${champion_metrics['daily_cost_usd'] - challenger_metrics['daily_cost_usd']:,.0f}/day vs v{champion_version}"
else:
    decision = f"Kept champion v{champion_version}: challenger v{challenger_version} did not lower daily cost"
dough_version = client.get_model_version_by_alias(DOUGH_MODEL, "champion").version
print(decision)

# COMMAND ----------

# MAGIC %md
# MAGIC # 2. Serve
# MAGIC Labor and Dough HQ answer questions on demand ("how many crew at 6 PM?"), so they get **real-time endpoints**: serverless, scale to zero, pinned to the `@champion` version, with **AI Gateway inference tables** logging every request and response to Unity Catalog. The Forecast is a nightly job, so it is scored in **batch** (section 4). Serving it in real time is one more step: publish its Feature Views to a Lakebase online store.

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import (
    AiGatewayConfig, AiGatewayInferenceTableConfig, AiGatewayUsageTrackingConfig,
    EndpointCoreConfigInput, EndpointTag, ServedEntityInput,
)

w = WorkspaceClient()
existing = {e.name for e in w.serving_endpoints.list()}


def gateway(prefix):
    return dict(inference_table_config=AiGatewayInferenceTableConfig(catalog_name=CATALOG, schema_name=SCHEMA,
                                                                     table_name_prefix=prefix, enabled=True),
                usage_tracking_config=AiGatewayUsageTrackingConfig(enabled=True))


def deploy(name, model, version, tab):
    entity = ServedEntityInput(entity_name=model, entity_version=str(version), workload_size="Small", scale_to_zero_enabled=True)
    if name in existing:
        w.serving_endpoints.update_config(name=name, served_entities=[entity])
    else:
        w.serving_endpoints.create(
            name=name, config=EndpointCoreConfigInput(name=name, served_entities=[entity]),
            ai_gateway=AiGatewayConfig(**gateway(name.replace("-", "_"))),
            tags=[EndpointTag(key="doughsight_app", value="doughsight-iq"), EndpointTag(key="doughsight_tab", value=tab)],
        )
    return f"{name} -> {model} v{version}"


print(deploy(LABOR_ENDPOINT, LABOR_MODEL, labor_version, "Labor"))
print(deploy(DOUGH_ENDPOINT, DOUGH_MODEL, dough_version, "Dough HQ"))
for name in (LABOR_ENDPOINT, DOUGH_ENDPOINT):
    ep = w.serving_endpoints.wait_get_serving_endpoint_not_updating(name, timeout=timedelta(minutes=40))
    if name in existing:  # keep the inference table on for endpoints created by an earlier run
        w.serving_endpoints.put_ai_gateway(name=name, **gateway(name.replace("-", "_")))
    print(f"{name}: {ep.state.ready.value}, config {ep.state.config_update.value}")

# COMMAND ----------

# MAGIC %md
# MAGIC Live calls, exactly what the app would send: Saturday lunch at a store with a Red Wings home game, and tomorrow's Large Classic dough plan.

# COMMAND ----------

labor_request = [{"hour": 12, "dow": 7, "is_weekend": 1, "n_events": 1, "max_attendance": 19500, "store_hour_avg_orders_28d": 26.5},
                 {"hour": 15, "dow": 3, "is_weekend": 0, "n_events": 0, "max_attendance": 0, "store_hour_avg_orders_28d": 9.0}]
labor_response = w.serving_endpoints.query(name=LABOR_ENDPOINT, dataframe_records=labor_request).predictions
print("Labor endpoint:", labor_response)

dough_request = [{"dough_type": "Large Classic", "dow": 7, "is_weekend": 1, "n_events": 1, "max_attendance": 19500,
                  "demand_7d_avg": 210.0, "demand_same_dow_4w": 236.0, "stockouts_7d": 1}]
dough_response = w.serving_endpoints.query(name=DOUGH_ENDPOINT, dataframe_records=dough_request).predictions
print(f"Dough endpoint: demand {dough_response[0]:.0f} balls, mix {np.ceil(dough_response[0] * (1 + BUFFER)):.0f}")

# COMMAND ----------

# MAGIC %md
# MAGIC # 3. Govern
# MAGIC Every model lives in Unity Catalog next to the data it was trained on: versions, aliases, owners, descriptions, tags, permissions, and lineage from the source tables and Feature Views to the model.

# COMMAND ----------

descriptions = {
    FORECAST_MODEL: ("Daily orders per store, 7 days ahead. LightGBM on Feature Views (7d and 28d order counts, "
                     "28d average ticket) plus the home-game calendar. Scored nightly into forecast_predictions.", "Forecast"),
    LABOR_MODEL: ("Hourly crew recommendation. Custom PyFunc: LightGBM orders model plus staffing rules "
                  f"({STAFFING_RULES['orders_per_crew_hour']} orders per crew-hour, {STAFFING_RULES['min_crew']} to "
                  f"{STAFFING_RULES['max_crew']} crew). Served at {LABOR_ENDPOINT}.", "Labor"),
    DOUGH_MODEL: ("Daily dough demand per store and dough type. Champion/challenger on waste vs shortfall cost; "
                  f"@champion is served at {DOUGH_ENDPOINT}, @previous is the rollback.", "Dough HQ"),
}
def tag(set_fn, *args):
    """Apply a UC tag; workspace tag policies may restrict keys/values, which is governance working as intended."""
    try:
        set_fn(*args)
    except Exception as e:
        if "tag policy" not in str(e):
            raise
        print(f"Skipped tag {args[-2]}={args[-1]}: blocked by a workspace tag policy")


for model, (text, tab) in descriptions.items():
    client.update_registered_model(model, description=text)
    tag(client.set_registered_model_tag, model, "doughsight_app", "doughsight-iq")
    tag(client.set_registered_model_tag, model, "doughsight_tab", tab)
    tag(client.set_registered_model_tag, model, "doughsight_owner", "store-ops-data-science")

for model, version in [(FORECAST_MODEL, forecast_version), (LABOR_MODEL, labor_version), (DOUGH_MODEL, dough_version)]:
    tag(client.set_model_version_tag, model, str(version), "doughsight_validation", "passed_holdout")

rows = []
for model in descriptions:
    alias_by_version = {}
    aliases = client.get_registered_model(model).aliases  # {alias: version} in MLflow 2.x
    pairs = aliases.items() if isinstance(aliases, dict) else ((a.alias, a.version) for a in aliases)
    for alias, version in pairs:
        alias_by_version.setdefault(str(version), []).append(alias)
    for v in client.search_model_versions(f"name='{model}'"):
        rows.append({"model": model.split(".")[-1], "version": int(v.version), "run_id": v.run_id,
                     "aliases": ", ".join(alias_by_version.get(str(v.version), []))})
display(pd.DataFrame(rows).sort_values(["model", "version"], ascending=[True, False]).groupby("model").head(3))

host = w.config.host.rstrip("/")
print(f"Lineage (Feature Views -> model): {host}/explore/data/models/{CATALOG}/{SCHEMA}/doughsight_forecast")
print(f"Experiment: {host}/ml/experiments/{mlflow.get_experiment_by_name(EXPERIMENT).experiment_id}")

# COMMAND ----------

# MAGIC %md
# MAGIC Access is plain SQL on the model. Shown here, not run, so the demo does not change anyone's permissions:
# MAGIC ```sql
# MAGIC GRANT EXECUTE ON MODEL jdub_demo.lce_store_ops.doughsight_dough TO `store-ops-analysts`;
# MAGIC GRANT MANAGE  ON MODEL jdub_demo.lce_store_ops.doughsight_dough TO `ml-platform-admins`;
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC # 4. Monitor
# MAGIC ## Batch predictions the app reads
# MAGIC The app never calls a model to draw a chart; it reads these tables. Each row carries the model version that produced it.

# COMMAND ----------

stores = spark.table(f"{FQ}.stores").select("store_id")
future = (stores.crossJoin(spark.sql(f"SELECT ds, dow, is_weekend, month, n_events, max_attendance FROM calendar "
                                     f"WHERE ds BETWEEN DATE'{TOMORROW}' AND DATE_ADD(DATE'{TOMORROW}', 6)"))
          .withColumn("order_ts", F.col("ds").cast("timestamp")).drop("ds"))
forecast = (fe.score_batch(model_uri=f"models:/{FORECAST_MODEL}@champion", df=future, result_type="double")
            .select("store_id", F.col("order_ts").cast("date").alias("forecast_date"),
                    F.round("prediction").cast("int").alias("predicted_orders"),
                    F.lit(int(forecast_version)).alias("model_version"), F.current_timestamp().alias("scored_at")))
forecast.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{FQ}.forecast_predictions")

labor_inputs = spark.sql(f"""
SELECT s.store_id, h.hour, c.dow, c.is_weekend, c.n_events, c.max_attendance,
       AVG(l.orders_actual_or_forecast) AS store_hour_avg_orders_28d
FROM {FQ}.stores s
CROSS JOIN (SELECT explode(sequence(10, 22)) AS hour) h
JOIN calendar c ON c.ds = DATE'{TOMORROW}'
JOIN {FQ}.labor_schedule l ON l.store_id = s.store_id AND l.hour = h.hour AND NOT l.is_forecast
     AND l.work_date > DATE_SUB(DATE'{AS_OF}', 28)
GROUP BY ALL
""").toPandas()
labor_inputs[INT_COLS] = labor_inputs[INT_COLS].astype("int64")
labor_inputs["store_hour_avg_orders_28d"] = labor_inputs["store_hour_avg_orders_28d"].astype("float64")
labor_out = mlflow.pyfunc.load_model(f"models:/{LABOR_MODEL}@champion").predict(labor_inputs[LABOR_FEATURES])
labor_recs = pd.concat([labor_inputs[["store_id", "hour"]], labor_out], axis=1).assign(
    work_date=TOMORROW, model_version=int(labor_version))
spark.createDataFrame(labor_recs).withColumn("scored_at", F.current_timestamp()) \
    .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{FQ}.labor_recommendations")

dough_hist = dough_df.sort_values("prep_date")
latest = dough_hist.groupby(["store_id", "dough_type"]).tail(7)
dough_inputs = latest.groupby(["store_id", "dough_type"]).agg(
    demand_7d_avg=("demand", "mean"), stockouts_7d=("stockout", "sum")).reset_index()
same_dow = dough_hist[pd.to_datetime(dough_hist.prep_date).dt.dayofweek == pd.Timestamp(TOMORROW).dayofweek] \
    .groupby(["store_id", "dough_type"]).tail(4).groupby(["store_id", "dough_type"]).demand.mean().rename("demand_same_dow_4w")
cal_t = spark.sql(f"SELECT dow, is_weekend, n_events, max_attendance FROM calendar WHERE ds = DATE'{TOMORROW}'").toPandas().iloc[0]
dough_inputs = dough_inputs.merge(same_dow.reset_index(), on=["store_id", "dough_type"]).assign(**{k: int(cal_t[k]) for k in cal_t.index})
dough_inputs[["dow", "is_weekend", "n_events", "max_attendance", "stockouts_7d"]] = \
    dough_inputs[["dow", "is_weekend", "n_events", "max_attendance", "stockouts_7d"]].astype("int64")
demand = np.asarray(mlflow.pyfunc.load_model(f"models:/{DOUGH_MODEL}@champion").predict(dough_inputs[DOUGH_FEATURES]))
dough_recs = dough_inputs[["store_id", "dough_type"]].assign(
    prep_date=TOMORROW, predicted_demand=demand.round(1), balls_to_mix=np.ceil(demand * (1 + BUFFER)).astype(int),
    model_version=int(dough_version))
spark.createDataFrame(dough_recs).withColumn("scored_at", F.current_timestamp()) \
    .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{FQ}.dough_recommendations")

counts = {t: spark.table(f"{FQ}.{t}").count() for t in ["forecast_predictions", "labor_recommendations", "dough_recommendations"]}
print(counts)
display(spark.sql(f"SELECT * FROM {FQ}.dough_recommendations WHERE store_id = 1 ORDER BY dough_type"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Inference tables
# MAGIC Every endpoint call is captured in a Delta table in Unity Catalog (request, response, latency, caller), ready for drift checks, debugging, and audit. Rows land within about an hour of the call.

# COMMAND ----------

inference = {}
for name in (LABOR_ENDPOINT, DOUGH_ENDPOINT):
    table = f"{FQ}.{name.replace('-', '_')}_payload"
    try:
        inference[name] = spark.table(table).count()
        print(f"{table}: {inference[name]} logged requests")
    except Exception:
        inference[name] = "pending"
        print(f"{table}: not populated yet (first rows arrive within about an hour of the first call)")

# COMMAND ----------

# MAGIC %md
# MAGIC **Next steps for production:** schedule this notebook as a Lakeflow Job (retrain weekly, score nightly), add a Data Profiling monitor on the prediction and inference tables for drift alerts, and publish the Forecast Feature Views to a Lakebase online store to serve it in real time.

# COMMAND ----------

summary = {
    "forecast": {"version": forecast_version, "test_mae": round(mae, 2), "naive_mae": round(naive_mae, 2)},
    "labor": {"version": labor_version, "orders_mae": round(labor_mae, 2), "endpoint": LABOR_ENDPOINT,
              "live_response": labor_response},
    "dough": {"champion": dough_version, "decision": decision, "endpoint": DOUGH_ENDPOINT,
              "live_response": dough_response},
    "tables": counts, "inference_tables": inference,
}
dbutils.notebook.exit(json.dumps(summary, default=str))
