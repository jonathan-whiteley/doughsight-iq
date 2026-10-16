"""
Model Serving Client for Databricks ML endpoints.

Makes direct REST API calls to model serving endpoints for:
- Demand forecasting
- Labor optimization
- Inventory prediction
- Dough prep and temper schedule optimization

The feature engineering here matches the training notebooks:
- 02_train_demand_forecast_model.py
- 03_train_labor_optimization_model.py
- 04_train_inventory_prediction_model.py
- 05_train_dough_scheduler_model.py

This module calls the actual Databricks Model Serving REST API:
https://docs.databricks.com/en/machine-learning/model-serving/
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from databricks.sdk import WorkspaceClient

logger = logging.getLogger(__name__)


class ModelServingClient:
    """
    Client for calling Databricks Model Serving endpoints via REST API.
    
    Uses the /serving-endpoints/{endpoint}/invocations API directly.
    """

    def __init__(self):
        """Initialize with Databricks configuration."""
        self._client: Optional[WorkspaceClient] = None
        self._initialized = False

    def _ensure_client(self):
        """Ensure WorkspaceClient is initialized."""
        if self._client is None:
            # WorkspaceClient automatically handles authentication in Databricks Apps
            # via OAuth/service principal - no need to extract tokens manually
            self._client = WorkspaceClient()
            logger.info(f"WorkspaceClient initialized for host: {self._client.config.host}")
            logger.info(f"Auth type: {self._client.config.auth_type}")
            self._initialized = True

    @property
    def client(self) -> WorkspaceClient:
        """Lazy initialization of WorkspaceClient."""
        self._ensure_client()
        return self._client

    def _call_endpoint_sync(self, endpoint_name: str, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Call a model serving endpoint using the SDK (sync version).
        
        Uses WorkspaceClient's serving_endpoints API which handles auth automatically.
        """
        self._ensure_client()
        
        logger.info(f"Calling model endpoint via SDK: {endpoint_name}")
        logger.debug(f"Number of records: {len(records)}")
        
        try:
            # Use the SDK's serving endpoints API - handles auth automatically
            response = self._client.serving_endpoints.query(
                name=endpoint_name,
                dataframe_records=records
            )
            
            # Convert response to dict format expected by callers
            result = {"predictions": response.predictions if response.predictions else []}
            logger.info(f"Model endpoint {endpoint_name} returned successfully")
            return result
            
        except Exception as e:
            logger.error(f"Model serving call failed for {endpoint_name}: {e}")
            raise

    async def predict_async(
        self,
        endpoint_name: str,
        features: Dict[str, List[Any]],
    ) -> Dict[str, Any]:
        """
        Call a model serving endpoint with features (async version).

        Args:
            endpoint_name: Name of the model serving endpoint
            features: Dictionary of feature columns and values
                      e.g., {"store_id": [1], "hour": [12], "temp": [72.5]}

        Returns:
            Model predictions as dictionary
        """
        # Convert columnar format to row format
        records = []
        if features:
            num_records = len(list(features.values())[0])
            for i in range(num_records):
                record = {k: v[i] for k, v in features.items()}
                records.append(record)
        
        logger.info(f"Calling model endpoint: {endpoint_name}")
        logger.debug(f"Payload features: {list(features.keys())}")
        
        # Run sync SDK call in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None, 
                self._call_endpoint_sync, 
                endpoint_name, 
                records
            )
            return result
        except Exception as e:
            logger.error(f"Model serving call failed for {endpoint_name}: {e}")
            raise

    def predict_sync(
        self,
        endpoint_name: str,
        features: Dict[str, List[Any]],
    ) -> Dict[str, Any]:
        """
        Call a model serving endpoint with features (sync version).
        
        For use in non-async contexts.
        """
        # Convert columnar format to row format
        records = []
        if features:
            num_records = len(list(features.values())[0])
            for i in range(num_records):
                record = {k: v[i] for k, v in features.items()}
                records.append(record)
        
        logger.info(f"Calling model endpoint (sync): {endpoint_name}")
        return self._call_endpoint_sync(endpoint_name, records)

    # =========================================================================
    # DEMAND FORECAST MODEL
    # Features expected by notebook 02_train_demand_forecast_model.py:
    # - day_of_week, day_of_month, month, week_of_year, quarter
    # - is_weekend, is_month_start, is_month_end
    # - txn_lag_1, txn_lag_2, txn_lag_7, txn_lag_14
    # - revenue_lag_1, revenue_lag_7
    # - txn_rolling_7d_avg, txn_rolling_7d_std, txn_rolling_14d_avg
    # - revenue_rolling_7d_avg
    # - txn_wow_change
    # - store_id
    # =========================================================================
    
    async def predict_demand(
        self,
        store_id: int,
        date: str,
        base_transactions: int = 100,  # Base daily transactions for lag calculations
        base_revenue: float = 1200.0,  # Base daily revenue
    ) -> Dict[str, Any]:
        """
        Predict demand for a store for a specific date.
        
        Computes all required temporal and lag features from the date.
        
        Args:
            store_id: Store identifier
            date: Target date string (YYYY-MM-DD)
            base_transactions: Baseline transaction count for lag feature estimation
            base_revenue: Baseline revenue for lag feature estimation
        
        Returns:
            Model predictions (transaction count)
        """
        from config.settings import settings
        
        # Parse date
        dt = datetime.strptime(date, "%Y-%m-%d")
        
        # Temporal features
        day_of_week = dt.isoweekday()  # Monday=1, Sunday=7
        day_of_month = dt.day
        month = dt.month
        week_of_year = dt.isocalendar()[1]
        quarter = (month - 1) // 3 + 1
        is_weekend = 1 if day_of_week in [6, 7] else 0
        is_month_start = 1 if day_of_month <= 3 else 0
        is_month_end = 1 if day_of_month >= 28 else 0
        
        # Lag features - using estimated values based on day patterns
        # In production, these would come from actual historical queries
        day_factor = 1.0
        if day_of_week in [6, 7]:  # Weekend
            day_factor = 0.8
        elif day_of_week == 5:  # Friday
            day_factor = 1.15
        
        txn_lag_1 = int(base_transactions * day_factor * 0.95)  # Yesterday
        txn_lag_2 = int(base_transactions * day_factor * 0.93)  # 2 days ago
        txn_lag_7 = int(base_transactions * day_factor)  # Same day last week
        txn_lag_14 = int(base_transactions * day_factor * 0.98)  # 2 weeks ago
        
        revenue_lag_1 = base_revenue * day_factor * 0.95
        revenue_lag_7 = base_revenue * day_factor
        
        # Rolling averages (simulated)
        txn_rolling_7d_avg = base_transactions * 0.92
        txn_rolling_7d_std = base_transactions * 0.15
        txn_rolling_14d_avg = base_transactions * 0.90
        revenue_rolling_7d_avg = base_revenue * 0.92
        
        # Week-over-week change
        txn_wow_change = (txn_lag_1 - txn_lag_7) / max(txn_lag_7, 1)
        
        features = {
            "day_of_week": [day_of_week],
            "day_of_month": [day_of_month],
            "month": [month],
            "week_of_year": [week_of_year],
            "quarter": [quarter],
            "is_weekend": [is_weekend],
            "is_month_start": [is_month_start],
            "is_month_end": [is_month_end],
            "txn_lag_1": [txn_lag_1],
            "txn_lag_2": [txn_lag_2],
            "txn_lag_7": [txn_lag_7],
            "txn_lag_14": [txn_lag_14],
            "revenue_lag_1": [revenue_lag_1],
            "revenue_lag_7": [revenue_lag_7],
            "txn_rolling_7d_avg": [txn_rolling_7d_avg],
            "txn_rolling_7d_std": [txn_rolling_7d_std],
            "txn_rolling_14d_avg": [txn_rolling_14d_avg],
            "revenue_rolling_7d_avg": [revenue_rolling_7d_avg],
            "txn_wow_change": [txn_wow_change],
            "store_id": [store_id],
        }

        return await self.predict_async(settings.demand_forecast_endpoint, features)

    # =========================================================================
    # LABOR OPTIMIZER MODEL
    # Features expected by notebook 03_train_labor_optimization_model.py:
    # - hour, day_of_week, is_weekend, month
    # - is_breakfast, is_lunch, is_dinner
    # - transactions, revenue, avg_ticket
    # - txn_prev_hour, txn_same_hour_yesterday, txn_same_hour_last_week
    # - txn_hourly_avg_7d
    # - store_id
    # =========================================================================
    
    async def predict_labor(
        self,
        store_id: int,
        date: str,
        hour: int,
        forecasted_transactions: int,
        avg_ticket: float = 12.50,
    ) -> Dict[str, Any]:
        """
        Get optimal staffing recommendation for a specific hour.
        
        The model predicts a 0-indexed staff level (0-6), which should be
        adjusted by +2 to get actual staff count (2-8).
        
        Args:
            store_id: Store identifier
            date: Target date string (YYYY-MM-DD)
            hour: Hour of day (0-23)
            forecasted_transactions: Expected transactions for this hour
            avg_ticket: Average ticket size
        
        Returns:
            Model prediction (0-indexed staff level, add 2 for actual count)
        """
        from config.settings import settings
        
        # Parse date
        dt = datetime.strptime(date, "%Y-%m-%d")
        
        # Temporal features
        day_of_week = dt.isoweekday()
        month = dt.month
        is_weekend = 1 if day_of_week in [6, 7] else 0
        
        # Daypart features
        is_breakfast = 1 if 6 <= hour < 10 else 0
        is_lunch = 1 if 11 <= hour < 14 else 0
        is_dinner = 1 if 17 <= hour < 20 else 0
        
        # Traffic/revenue features
        transactions = forecasted_transactions
        revenue = transactions * avg_ticket
        
        # Lag features (simulated - would come from historical data)
        txn_prev_hour = int(transactions * 0.8)  # Previous hour typically lower
        txn_same_hour_yesterday = int(transactions * 0.95)
        txn_same_hour_last_week = int(transactions * 0.98)
        txn_hourly_avg_7d = transactions * 0.92
        
        features = {
            "hour": [hour],
            "day_of_week": [day_of_week],
            "is_weekend": [is_weekend],
            "month": [month],
            "is_breakfast": [is_breakfast],
            "is_lunch": [is_lunch],
            "is_dinner": [is_dinner],
            "transactions": [transactions],
            "revenue": [revenue],
            "avg_ticket": [avg_ticket],
            "txn_prev_hour": [txn_prev_hour],
            "txn_same_hour_yesterday": [txn_same_hour_yesterday],
            "txn_same_hour_last_week": [txn_same_hour_last_week],
            "txn_hourly_avg_7d": [txn_hourly_avg_7d],
            "store_id": [store_id],
        }

        return await self.predict_async(settings.labor_optimizer_endpoint, features)

    # =========================================================================
    # INVENTORY PREDICTOR MODEL
    # Features expected by notebook 04_train_inventory_prediction_model.py:
    # - store_id, ingredient_id, par_level, category_encoded, cost_per_unit
    # - qty_on_hand, days_supply, stock_ratio, below_par, critical_level
    # - daily_usage_rate
    # =========================================================================
    
    # Category encoding from notebook
    CATEGORY_ENCODING = {
        "protein": 1,
        "vegetable": 2,
        "cheese": 3,
        "dough": 4,
        "sauce": 5,
        "other": 6
    }
    
    async def predict_inventory(
        self,
        store_id: int,
        ingredient_id: int,
        current_stock: float,
        par_level: float,
        category: str = "other",
        cost_per_unit: float = 5.0,
    ) -> Dict[str, Any]:
        """
        Predict suggested order quantity for an ingredient.
        
        Args:
            store_id: Store identifier
            ingredient_id: Ingredient identifier
            current_stock: Current quantity on hand
            par_level: Target stock level
            category: Ingredient category (protein, vegetable, cheese, dough, sauce, packaging, other)
            cost_per_unit: Cost per unit
        
        Returns:
            Model prediction (suggested_order_qty)
        """
        from config.settings import settings
        
        # Compute derived features (matching notebook logic)
        daily_usage_rate = par_level / 3  # Standard turnover assumption
        days_supply = current_stock / daily_usage_rate if daily_usage_rate > 0 else 0
        stock_ratio = current_stock / par_level if par_level > 0 else 0
        below_par = 1 if current_stock < par_level else 0
        critical_level = 1 if days_supply < 2 else 0
        category_encoded = self.CATEGORY_ENCODING.get(category.lower(), 6)
        
        features = {
            "store_id": [store_id],
            "ingredient_id": [ingredient_id],
            "par_level": [float(par_level)],
            "category_encoded": [category_encoded],
            "cost_per_unit": [float(cost_per_unit)],
            "qty_on_hand": [float(current_stock)],
            "days_supply": [float(days_supply)],
            "stock_ratio": [float(stock_ratio)],
            "below_par": [below_par],
            "critical_level": [critical_level],
            "daily_usage_rate": [float(daily_usage_rate)],
        }

        return await self.predict_async(settings.inventory_predictor_endpoint, features)

    # =========================================================================
    # DOUGH SCHEDULER MODEL
    # Features expected by notebook 05_train_dough_scheduler_model.py:
    # - store_id, hour, day_of_week, is_weekend
    # - traffic, traffic_per_hour_normalized
    # - daypart_encoded, daypart_factor
    # - is_rush_hour
    # - dough_id, temper_time_min, max_age_hours, popularity
    # - temper_complexity, freshness_urgency
    # =========================================================================

    # Dough types from notebook
    DOUGH_TYPES = {
        "large_classic": {"id": 1, "temper_time": 180, "max_age_hours": 72, "popularity": 0.45},
        "thin_crust": {"id": 2, "temper_time": 150, "max_age_hours": 60, "popularity": 0.25},
        "deep_dish": {"id": 3, "temper_time": 200, "max_age_hours": 48, "popularity": 0.20},
        "crazy_bread": {"id": 4, "temper_time": 120, "max_age_hours": 36, "popularity": 0.10},
    }

    async def predict_dough_schedule(
        self,
        store_id: int,
        date: str,
        hour: int,
        dough_type: str,
        forecasted_traffic: int,
        max_traffic: int = 50,  # For normalization
    ) -> Dict[str, Any]:
        """
        Predict optimal dough prep and temper schedule for a specific dough type and hour.

        Args:
            store_id: Store identifier
            date: Target date (YYYY-MM-DD)
            hour: Hour of day (6-21)
            dough_type: One of large_classic, thin_crust, deep_dish, crazy_bread
            forecasted_traffic: Expected transaction count for this hour
            max_traffic: Maximum expected traffic for normalization

        Returns:
            Model prediction (optimal_quantity - dough balls to have ready)
        """
        from config.settings import settings

        # Parse date
        dt = datetime.strptime(date, "%Y-%m-%d")
        day_of_week = dt.isoweekday()
        is_weekend = 1 if day_of_week in [6, 7] else 0

        # Daypart features
        if 6 <= hour < 10:
            daypart_encoded = 1  # breakfast
            daypart_factor = 0.15
        elif 10 <= hour < 14:
            daypart_encoded = 2  # lunch
            daypart_factor = 0.35
        elif 14 <= hour < 17:
            daypart_encoded = 3  # afternoon
            daypart_factor = 0.20
        elif 17 <= hour < 21:
            daypart_encoded = 4  # dinner
            daypart_factor = 0.25
        else:
            daypart_encoded = 5  # closing
            daypart_factor = 0.05

        # Rush hour indicator
        is_rush_hour = 1 if (11 <= hour <= 13) or (17 <= hour <= 19) else 0

        # Traffic normalization
        traffic_per_hour_normalized = forecasted_traffic / max(max_traffic, 1)

        # Dough type properties
        dough_props = self.DOUGH_TYPES.get(dough_type.lower(), self.DOUGH_TYPES["large_classic"])
        dough_id = dough_props["id"]
        temper_time_min = dough_props["temper_time"]
        max_age_hours = dough_props["max_age_hours"]
        popularity = dough_props["popularity"]

        # Derived dough features
        temper_complexity = temper_time_min / 200  # Normalized to max 200 min
        freshness_urgency = 1 / max(max_age_hours, 1)

        features = {
            "store_id": [store_id],
            "hour": [hour],
            "day_of_week": [day_of_week],
            "is_weekend": [is_weekend],
            "traffic": [forecasted_traffic],
            "traffic_per_hour_normalized": [traffic_per_hour_normalized],
            "daypart_encoded": [daypart_encoded],
            "daypart_factor": [daypart_factor],
            "is_rush_hour": [is_rush_hour],
            "dough_id": [dough_id],
            "temper_time_min": [temper_time_min],
            "max_age_hours": [max_age_hours],
            "popularity": [popularity],
            "temper_complexity": [temper_complexity],
            "freshness_urgency": [freshness_urgency],
        }

        return await self.predict_async(settings.dough_scheduler_endpoint, features)

    async def check_endpoint_health(self, endpoint_name: str) -> Dict[str, Any]:
        """
        Check if a model serving endpoint is healthy and ready.
        
        Returns:
            {"name": str, "state": str, "ready": bool}
        """
        try:
            endpoints = self.client.serving_endpoints.list()
            for ep in endpoints:
                if ep.name == endpoint_name:
                    state = ep.state.ready if ep.state else "UNKNOWN"
                    return {
                        "name": endpoint_name,
                        "state": str(state),
                        "ready": str(state) == "READY",
                    }
            return {"name": endpoint_name, "state": "NOT_FOUND", "ready": False}
        except Exception as e:
            logger.error(f"Failed to check endpoint health: {e}")
            return {"name": endpoint_name, "state": "ERROR", "ready": False, "error": str(e)}

    def list_endpoints(self) -> List[str]:
        """List all available model serving endpoints."""
        try:
            endpoints = self.client.serving_endpoints.list()
            return [ep.name for ep in endpoints]
        except Exception as e:
            logger.error(f"Failed to list endpoints: {e}")
            return []


# Singleton instance
model_client = ModelServingClient()
