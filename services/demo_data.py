"""
Shared Demo Data Service.

Provides consistent demo data across all API endpoints.
Uses seeded random generation based on store_id and date to ensure:
- Same sales/revenue numbers across Operations, Forecast views
- Consistent inventory levels across Inventory display and ML suggestions
- Matching % vs forecast calculations
- Stable dough inventory across Dough HQ tab and recommendations

This is the SINGLE SOURCE OF TRUTH for all demo data.
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import random
import logging

logger = logging.getLogger(__name__)

# === Data Classes ===

@dataclass
class DailySalesData:
    """Daily sales metrics for a store."""
    date: str
    total_sales: float
    total_transactions: int
    avg_ticket: float
    vs_yesterday_pct: float
    vs_forecast_pct: float
    forecast_sales: float
    forecast_transactions: int
    
    # Hourly breakdown
    hourly_sales: Dict[int, float] = field(default_factory=dict)
    hourly_transactions: Dict[int, int] = field(default_factory=dict)
    
    # Channel breakdown
    channel_breakdown: Dict[str, float] = field(default_factory=dict)


@dataclass 
class InventoryItem:
    """Single inventory item state."""
    id: int
    name: str
    category: str
    unit: str
    par_level: float
    current_stock: float
    days_supply: float
    status: str  # "good", "low", "critical", "overstocked"
    cost_per_unit: float


@dataclass
class DoughItem:
    """Single dough type inventory state."""
    dough_type: str
    quantity: int
    stage: str  # "mixed", "cold_hold", "tempering", "ready", "overproofed"
    age_days: int
    hours_until_stale: float
    temper_minutes_elapsed: int
    popularity: float


# === Constants (imported from original files) ===

LC_INGREDIENTS = [
    {"id": 1, "name": "Pepperoni", "category": "protein", "unit": "lbs", "par": 12, "cost_per_unit": 11.50},
    {"id": 2, "name": "Italian Sausage", "category": "protein", "unit": "lbs", "par": 10, "cost_per_unit": 8.00},
    {"id": 3, "name": "Bacon", "category": "protein", "unit": "lbs", "par": 8, "cost_per_unit": 12.00},
    {"id": 4, "name": "Ham", "category": "protein", "unit": "lbs", "par": 9, "cost_per_unit": 9.50},
    {"id": 5, "name": "Chicken Wings Raw", "category": "protein", "unit": "lbs", "par": 15, "cost_per_unit": 7.50},
    {"id": 10, "name": "Green Peppers", "category": "vegetable", "unit": "lbs", "par": 12, "cost_per_unit": 2.00},
    {"id": 11, "name": "Onions", "category": "vegetable", "unit": "lbs", "par": 15, "cost_per_unit": 1.50},
    {"id": 12, "name": "Mushrooms", "category": "vegetable", "unit": "lbs", "par": 10, "cost_per_unit": 3.00},
    {"id": 13, "name": "Black Olives", "category": "vegetable", "unit": "lbs", "par": 8, "cost_per_unit": 4.00},
    {"id": 14, "name": "Banana Peppers", "category": "vegetable", "unit": "lbs", "par": 6, "cost_per_unit": 3.50},
    {"id": 15, "name": "Jalapenos", "category": "vegetable", "unit": "lbs", "par": 6, "cost_per_unit": 3.00},
    {"id": 16, "name": "Pineapple", "category": "vegetable", "unit": "lbs", "par": 5, "cost_per_unit": 4.50},
    {"id": 20, "name": "Mozzarella/Muenster Blend", "category": "cheese", "unit": "lbs", "par": 20, "cost_per_unit": 6.00},
    {"id": 21, "name": "Parmesan", "category": "cheese", "unit": "lbs", "par": 8, "cost_per_unit": 7.00},
    {"id": 30, "name": "Pizza Sauce", "category": "sauce", "unit": "oz", "par": 160, "cost_per_unit": 0.03},
    {"id": 31, "name": "Crazy Sauce Cups", "category": "sauce", "unit": "units", "par": 96, "cost_per_unit": 0.15},
    {"id": 32, "name": "Wing Sauce Buffalo", "category": "sauce", "unit": "oz", "par": 64, "cost_per_unit": 0.08},
    {"id": 33, "name": "Wing Sauce BBQ", "category": "sauce", "unit": "oz", "par": 48, "cost_per_unit": 0.08},
    {"id": 34, "name": "Butter Garlic", "category": "sauce", "unit": "oz", "par": 64, "cost_per_unit": 0.06},
    {"id": 40, "name": "Large Classic Dough Balls", "category": "dough", "unit": "units", "par": 60, "cost_per_unit": 0.80},
    {"id": 41, "name": "Thin Crust Dough", "category": "dough", "unit": "units", "par": 40, "cost_per_unit": 0.70},
    {"id": 42, "name": "Deep Dish Dough", "category": "dough", "unit": "units", "par": 30, "cost_per_unit": 0.85},
    {"id": 43, "name": "Crazy Bread Dough", "category": "dough", "unit": "units", "par": 25, "cost_per_unit": 0.65},
    {"id": 50, "name": "Large Pizza Boxes", "category": "packaging", "unit": "units", "par": 200, "cost_per_unit": 0.35},
    {"id": 51, "name": "Deep Dish Boxes", "category": "packaging", "unit": "units", "par": 150, "cost_per_unit": 0.40},
    {"id": 52, "name": "Wing Boats", "category": "packaging", "unit": "units", "par": 100, "cost_per_unit": 0.25},
    {"id": 53, "name": "Crazy Bread Bags", "category": "packaging", "unit": "units", "par": 100, "cost_per_unit": 0.10},
    {"id": 60, "name": "2L Soda", "category": "other", "unit": "units", "par": 48, "cost_per_unit": 2.00},
    {"id": 61, "name": "Cornmeal", "category": "other", "unit": "lbs", "par": 10, "cost_per_unit": 0.50},
    {"id": 62, "name": "Flour 50lb Bags", "category": "other", "unit": "units", "par": 5, "cost_per_unit": 15.00},
]

DOUGH_TYPES = [
    {"id": 1, "name": "Large Classic", "temper_minutes": 180, "max_age_hours": 72, "popularity": 0.45},
    {"id": 2, "name": "Thin Crust", "temper_minutes": 150, "max_age_hours": 60, "popularity": 0.25},
    {"id": 3, "name": "Deep Dish", "temper_minutes": 200, "max_age_hours": 48, "popularity": 0.20},
    {"id": 4, "name": "Crazy Bread", "temper_minutes": 120, "max_age_hours": 36, "popularity": 0.10},
]

# Little Caesars hourly traffic patterns (% of daily traffic by hour)
# Open 10:30-23:00, lunch peak 11-13, dinner rush 16-19 (17-18 highest)
HOURLY_TRAFFIC_PATTERN = {
    10: 0.02, 11: 0.12, 12: 0.18, 13: 0.14,   # Lunch peak
    14: 0.08, 15: 0.07, 16: 0.08,   # Afternoon
    17: 0.16, 18: 0.15, 19: 0.12, 20: 0.06, 21: 0.02,  # Dinner rush (17-18 highest)
}


# === Store Data Constants ===

DEMO_STORES = [
    {"store_id": 1, "name": "Detroit Woodward Ave", "address": "101 Woodward Ave", "city": "Detroit", "lat": 42.3314, "lng": -83.0458, "sqft": 1800, "open_date": "2015-03-15", "manager_name": "Maria Rodriguez", "phone": "(313) 555-0101"},
    {"store_id": 2, "name": "Detroit Midtown", "address": "4520 Cass Ave", "city": "Detroit", "lat": 42.3412, "lng": -83.0637, "sqft": 1600, "open_date": "2016-06-20", "manager_name": "James Wilson", "phone": "(313) 555-0102"},
    {"store_id": 3, "name": "Dearborn Michigan Ave", "address": "22850 Michigan Ave", "city": "Dearborn", "lat": 42.3182, "lng": -83.1863, "sqft": 2200, "open_date": "2014-01-10", "manager_name": "Ahmed Hassan", "phone": "(313) 555-0103"},
    {"store_id": 4, "name": "Royal Oak Main St", "address": "105 S Main St", "city": "Royal Oak", "lat": 42.4889, "lng": -83.1448, "sqft": 1500, "open_date": "2017-08-05", "manager_name": "Sarah Johnson", "phone": "(248) 555-0104"},
    {"store_id": 5, "name": "Troy Big Beaver", "address": "2900 W Big Beaver Rd", "city": "Troy", "lat": 42.6100, "lng": -83.2089, "sqft": 1900, "open_date": "2015-11-12", "manager_name": "Michael Chen", "phone": "(248) 555-0105"},
    {"store_id": 6, "name": "Southfield", "address": "29111 Civic Center Dr", "city": "Southfield", "lat": 42.4783, "lng": -83.2818, "sqft": 2000, "open_date": "2013-04-22", "manager_name": "Patricia Davis", "phone": "(248) 555-0106"},
    {"store_id": 7, "name": "Livonia", "address": "36000 W 7 Mile Rd", "city": "Livonia", "lat": 42.4748, "lng": -83.3793, "sqft": 1700, "open_date": "2016-02-28", "manager_name": "David Thompson", "phone": "(734) 555-0107"},
    {"store_id": 8, "name": "Warren", "address": "26400 Van Dyke Ave", "city": "Warren", "lat": 42.5286, "lng": -83.0152, "sqft": 1650, "open_date": "2015-09-14", "manager_name": "Lisa Martinez", "phone": "(586) 555-0108"},
    {"store_id": 9, "name": "Sterling Heights", "address": "12800 Hall Rd", "city": "Sterling Heights", "lat": 42.7842, "lng": -83.0203, "sqft": 1550, "open_date": "2017-01-08", "manager_name": "Kevin Anderson", "phone": "(586) 555-0109"},
    {"store_id": 10, "name": "Novi", "address": "25550 Novi Rd", "city": "Novi", "lat": 42.4726, "lng": -83.4809, "sqft": 1800, "open_date": "2014-07-19", "manager_name": "Jennifer Brown", "phone": "(248) 555-0110"},
    {"store_id": 11, "name": "Ann Arbor State St", "address": "214 State St", "city": "Ann Arbor", "lat": 42.2794, "lng": -83.7460, "sqft": 1400, "open_date": "2016-05-30", "manager_name": "Robert Garcia", "phone": "(734) 555-0111"},
    {"store_id": 12, "name": "Ypsilanti", "address": "1150 Washtenaw Ave", "city": "Ypsilanti", "lat": 42.2390, "lng": -83.6101, "sqft": 1750, "open_date": "2015-03-25", "manager_name": "Elizabeth White", "phone": "(734) 555-0112"},
    {"store_id": 13, "name": "Canton", "address": "44300 Ford Rd", "city": "Canton", "lat": 42.3066, "lng": -83.3686, "sqft": 1500, "open_date": "2017-06-15", "manager_name": "Christopher Lee", "phone": "(734) 555-0113"},
    {"store_id": 14, "name": "Westland", "address": "7777 N Wayne Rd", "city": "Westland", "lat": 42.3243, "lng": -83.4117, "sqft": 1850, "open_date": "2014-11-08", "manager_name": "Amanda Taylor", "phone": "(734) 555-0114"},
    {"store_id": 15, "name": "Farmington Hills", "address": "32555 Thirteen Mile Rd", "city": "Farmington Hills", "lat": 42.5384, "lng": -83.3101, "sqft": 1450, "open_date": "2016-04-12", "manager_name": "Daniel Clark", "phone": "(248) 555-0115"},
    {"store_id": 16, "name": "Rochester Hills", "address": "320 S Main St", "city": "Rochester Hills", "lat": 42.6614, "lng": -83.1386, "sqft": 1350, "open_date": "2015-08-22", "manager_name": "Nancy King", "phone": "(248) 555-0116"},
    {"store_id": 17, "name": "Pontiac", "address": "585 University Dr", "city": "Pontiac", "lat": 42.6387, "lng": -83.2936, "sqft": 1600, "open_date": "2017-02-18", "manager_name": "Mark Vincent", "phone": "(248) 555-0117"},
    {"store_id": 18, "name": "Clinton Twp", "address": "42000 Garfield Rd", "city": "Clinton Twp", "lat": 42.6018, "lng": -82.9211, "sqft": 1550, "open_date": "2016-10-05", "manager_name": "Samantha Lewis", "phone": "(586) 555-0118"},
    {"store_id": 19, "name": "St Clair Shores", "address": "23500 Jefferson Ave", "city": "St Clair Shores", "lat": 42.4898, "lng": -82.8704, "sqft": 2100, "open_date": "2013-12-01", "manager_name": "Thomas Walker", "phone": "(586) 555-0119"},
    {"store_id": 20, "name": "Grosse Pointe", "address": "16100 Mack Ave", "city": "Grosse Pointe", "lat": 42.4169, "lng": -82.8919, "sqft": 1700, "open_date": "2015-05-17", "manager_name": "Dorothy Hall", "phone": "(313) 555-0120"},
    {"store_id": 21, "name": "Taylor", "address": "12900 Inkster Rd", "city": "Taylor", "lat": 42.2725, "lng": -83.2712, "sqft": 1900, "open_date": "2014-09-28", "manager_name": "Ronald Scott", "phone": "(734) 555-0121"},
    {"store_id": 22, "name": "Wyandotte", "address": "2000 Biddle Ave", "city": "Wyandotte", "lat": 42.2107, "lng": -83.1574, "sqft": 1650, "open_date": "2016-07-14", "manager_name": "Barbara Green", "phone": "(734) 555-0122"},
    {"store_id": 23, "name": "Hamtramck", "address": "3700 Conant St", "city": "Hamtramck", "lat": 42.3844, "lng": -83.0720, "sqft": 1500, "open_date": "2017-03-22", "manager_name": "George Young", "phone": "(313) 555-0123"},
    {"store_id": 24, "name": "Ferndale", "address": "1400 W 9 Mile Rd", "city": "Ferndale", "lat": 42.4531, "lng": -83.1348, "sqft": 1800, "open_date": "2015-01-30", "manager_name": "Margaret Hernandez", "phone": "(248) 555-0124"},
    {"store_id": 25, "name": "Auburn Hills", "address": "3200 Joslyn Rd", "city": "Auburn Hills", "lat": 42.6631, "lng": -83.2408, "sqft": 1400, "open_date": "2016-11-20", "manager_name": "Steven Murphy", "phone": "(248) 555-0125"},
]


# === Cache Storage ===

# Cache structure: {cache_key: (timestamp, data)}
_sales_cache: Dict[str, tuple] = {}
_inventory_cache: Dict[str, tuple] = {}
_dough_cache: Dict[str, tuple] = {}
_store_kpis_cache: Dict[str, tuple] = {}

CACHE_TTL_SECONDS = 300  # 5 minutes


def _get_cache_key(store_id: int, date: str) -> str:
    """Generate cache key for store+date combination."""
    return f"{store_id}_{date}"


def _is_cache_valid(cache: Dict, key: str) -> bool:
    """Check if cache entry is still valid."""
    if key not in cache:
        return False
    timestamp, _ = cache[key]
    return (datetime.now() - timestamp).total_seconds() < CACHE_TTL_SECONDS


# === Sales Data Generation ===

def get_daily_sales(store_id: int, date: str, current_hour: Optional[int] = None) -> DailySalesData:
    """
    Get consistent daily sales data for a store.
    
    Uses seeded random for deterministic results within the cache period.
    """
    cache_key = _get_cache_key(store_id, date)
    
    if _is_cache_valid(_sales_cache, cache_key):
        _, data = _sales_cache[cache_key]
        return data
    
    # Generate new data with seeded random
    seed = hash(f"{store_id}_{date}") % (2**32)
    rng = random.Random(seed)
    
    # Parse date
    date_obj = datetime.strptime(date, "%Y-%m-%d")
    is_weekend = date_obj.weekday() >= 5
    
    # Base daily metrics for Little Caesars (260-380 orders/day, avg $13-17/ticket)
    store_factor = 0.85 + (store_id % 10) * 0.03  # Store performance varies 0.85-1.15x

    if is_weekend:
        base_transactions = int(320 * store_factor * rng.uniform(0.9, 1.1))
    else:
        base_transactions = int(300 * store_factor * rng.uniform(0.85, 1.05))

    avg_ticket = rng.uniform(13.00, 17.00)
    total_sales = base_transactions * avg_ticket
    
    # Forecast (slightly different from actual)
    forecast_transactions = int(base_transactions * rng.uniform(0.92, 1.08))
    forecast_sales = forecast_transactions * avg_ticket
    
    # Calculate % vs forecast
    vs_forecast_pct = ((total_sales - forecast_sales) / forecast_sales) * 100
    
    # Yesterday's comparison (consistent with yesterday's data)
    yesterday_seed = hash(f"{store_id}_{(date_obj - timedelta(days=1)).strftime('%Y-%m-%d')}") % (2**32)
    yesterday_rng = random.Random(yesterday_seed)
    yesterday_transactions = int(base_transactions * yesterday_rng.uniform(0.85, 1.15))
    yesterday_sales = yesterday_transactions * avg_ticket
    vs_yesterday_pct = ((total_sales - yesterday_sales) / yesterday_sales) * 100
    
    # Generate hourly breakdown
    hourly_sales = {}
    hourly_transactions = {}
    
    for hour in range(6, 22):
        hour_pct = HOURLY_TRAFFIC_PATTERN.get(hour, 0.05)
        hourly_transactions[hour] = int(base_transactions * hour_pct * rng.uniform(0.85, 1.15))
        hourly_sales[hour] = hourly_transactions[hour] * avg_ticket * rng.uniform(0.95, 1.05)
    
    # Channel breakdown for Little Caesars: walk_in/pizza_portal/delivery/phone (~45/30/18/7)
    walk_in_pct = rng.uniform(0.43, 0.47)
    pizza_portal_pct = rng.uniform(0.28, 0.32)
    delivery_pct = rng.uniform(0.16, 0.20)
    phone_pct = 1 - walk_in_pct - pizza_portal_pct - delivery_pct

    channel_breakdown = {
        "walk_in": walk_in_pct,
        "pizza_portal": pizza_portal_pct,
        "delivery": delivery_pct,
        "phone": phone_pct,
    }
    
    data = DailySalesData(
        date=date,
        total_sales=round(total_sales, 2),
        total_transactions=base_transactions,
        avg_ticket=round(avg_ticket, 2),
        vs_yesterday_pct=round(vs_yesterday_pct, 1),
        vs_forecast_pct=round(vs_forecast_pct, 1),
        forecast_sales=round(forecast_sales, 2),
        forecast_transactions=forecast_transactions,
        hourly_sales=hourly_sales,
        hourly_transactions=hourly_transactions,
        channel_breakdown=channel_breakdown,
    )
    
    _sales_cache[cache_key] = (datetime.now(), data)
    logger.debug(f"Generated sales data for store {store_id} on {date}: ${total_sales:.2f}")
    
    return data


def get_sales_up_to_hour(store_id: int, date: str, current_hour: int) -> dict:
    """
    Get accumulated sales up to a specific hour.
    
    Used by Operations page to show "sales today" based on time of day.
    """
    daily = get_daily_sales(store_id, date, current_hour)
    
    # Sum up sales and transactions up to current hour
    sales_so_far = sum(
        daily.hourly_sales.get(h, 0) 
        for h in range(6, min(current_hour + 1, 22))
    )
    transactions_so_far = sum(
        daily.hourly_transactions.get(h, 0)
        for h in range(6, min(current_hour + 1, 22))
    )
    
    return {
        "sales_today": round(sales_so_far, 2),
        "transactions_today": transactions_so_far,
        "vs_yesterday_pct": daily.vs_yesterday_pct,
        "vs_forecast_pct": daily.vs_forecast_pct,
        "current_hour_sales": daily.hourly_sales.get(current_hour, 0),
        "channel_breakdown": daily.channel_breakdown,
        "forecast_sales": daily.forecast_sales,
    }


# === Inventory Data Generation ===

def get_inventory_levels(store_id: int, date: str) -> List[InventoryItem]:
    """
    Get consistent inventory levels for a store.

    Same levels used for display AND ML model inputs.
    """
    cache_key = _get_cache_key(store_id, date)

    if _is_cache_valid(_inventory_cache, cache_key):
        _, data = _inventory_cache[cache_key]
        return data

    # Generate with seeded random
    seed = hash(f"inv_{store_id}_{date}") % (2**32)
    rng = random.Random(seed)

    inventory = []

    for ing in LC_INGREDIENTS:
        # Generate stock level (varies 20% to 130% of par)
        stock_pct = rng.uniform(0.2, 1.3)
        current_stock = round(ing["par"] * stock_pct, 1)
        days_supply = round(current_stock / (ing["par"] / 3), 1)  # Assuming 3-day par
        
        # Determine status
        if days_supply < 1:
            status = "critical"
        elif days_supply < 2:
            status = "low"
        elif days_supply > 5:
            status = "overstocked"
        else:
            status = "good"
        
        inventory.append(InventoryItem(
            id=ing["id"],
            name=ing["name"],
            category=ing["category"],
            unit=ing["unit"],
            par_level=ing["par"],
            current_stock=current_stock,
            days_supply=days_supply,
            status=status,
            cost_per_unit=ing["cost_per_unit"],
        ))
    
    _inventory_cache[cache_key] = (datetime.now(), inventory)
    logger.debug(f"Generated inventory data for store {store_id} on {date}")
    
    return inventory


def get_inventory_summary(store_id: int, date: str) -> dict:
    """Get inventory summary stats - uses same data as get_inventory_levels."""
    inventory = get_inventory_levels(store_id, date)
    
    items_good = sum(1 for i in inventory if i.status == "good")
    items_low = sum(1 for i in inventory if i.status == "low")
    items_critical = sum(1 for i in inventory if i.status == "critical")
    items_overstocked = sum(1 for i in inventory if i.status == "overstocked")
    
    total_value = sum(i.current_stock * i.cost_per_unit for i in inventory)
    
    return {
        "total_items": len(inventory),
        "items_good": items_good,
        "items_low": items_low,
        "items_critical": items_critical,
        "items_overstocked": items_overstocked,
        "total_inventory_value": round(total_value, 2),
    }


def get_items_needing_order(store_id: int, date: str) -> List[InventoryItem]:
    """Get items that need to be ordered (low/critical) - from same data source."""
    inventory = get_inventory_levels(store_id, date)
    return [i for i in inventory if i.status in ("low", "critical") or i.days_supply < 3]


# === Dough Inventory Generation ===

def get_dough_inventory(store_id: int, date: str, current_hour: float) -> List[DoughItem]:
    """
    Dough on hand by type, lifecycle stage, and age (one row per stage/age).

    Driven by services/dough_model.py so Dough HQ inventory, schedule,
    recommendations, alerts, and KPIs always agree.
    """
    from services.dough_model import dough_plan

    items = []
    for plan in dough_plan(store_id, date, current_hour):
        for s in plan.stages:
            items.append(DoughItem(
                dough_type=plan.dough_type,
                quantity=s["quantity"],
                stage=s["stage"],
                age_days=s["age_days"],
                hours_until_stale=s["hours_until_stale"],
                temper_minutes_elapsed=s["temper_elapsed"],
                popularity=plan.popularity,
            ))
    return items


# === Helper Functions ===

def clear_cache():
    """Clear all cached data (useful for testing)."""
    global _sales_cache, _inventory_cache, _dough_cache, _store_kpis_cache
    _sales_cache = {}
    _inventory_cache = {}
    _dough_cache = {}
    _store_kpis_cache = {}
    logger.info("Demo data cache cleared")


def get_forecast_for_date(store_id: int, date: str) -> dict:
    """Get forecast data - consistent with actual sales."""
    sales = get_daily_sales(store_id, date)
    return {
        "predicted_transactions": sales.forecast_transactions,
        "predicted_revenue": sales.forecast_sales,
        "actual_transactions": sales.total_transactions,
        "actual_revenue": sales.total_sales,
        "vs_forecast_pct": sales.vs_forecast_pct,
    }


# === Store KPI Data Generation (Regional Manager Views) ===

@dataclass
class StoreKPI:
    """KPI data for a single store."""
    store_id: int
    name: str
    city: str
    address: str
    latitude: float
    longitude: float
    sqft: int
    open_date: str
    sales_today: float
    sales_wtd: float
    sales_mtd: float
    sales_ytd: float
    vs_forecast_pct: float
    labor_cost_pct: float
    rank: int
    trend: str  # "up", "down", "flat"
    staff_count: int
    manager_name: str
    phone: str


def get_all_store_kpis(date: str) -> List[StoreKPI]:
    """
    Get consistent KPI data for all stores.
    
    Uses seeded random based on date to ensure all stores have
    consistent data throughout the day.
    """
    cache_key = f"store_kpis_{date}"
    
    if _is_cache_valid(_store_kpis_cache, cache_key):
        _, data = _store_kpis_cache[cache_key]
        return data
    
    # Generate with seeded random for entire region
    seed = hash(f"region_kpis_{date}") % (2**32)
    rng = random.Random(seed)
    
    store_kpis = []
    
    # First, generate raw metrics for all stores
    raw_metrics = []
    for store in DEMO_STORES:
        store_id = store["store_id"]
        
        # Store-specific seed for consistent individual store data
        store_seed = hash(f"store_{store_id}_{date}") % (2**32)
        store_rng = random.Random(store_seed)
        
        # Base performance varies by store (some stores perform better)
        # Using sqft as a factor (larger stores = more sales potential)
        sqft = store.get("sqft", 1600)
        size_factor = sqft / 1600  # Normalize to avg sqft
        
        # Performance factor (deterministic per store)
        perf_factor = 0.7 + (store_id % 10) * 0.06  # 0.7 to 1.24
        
        # Daily sales
        base_daily = 2500 * size_factor * perf_factor
        sales_today = base_daily * store_rng.uniform(0.85, 1.15)
        
        # Weekly (5 days worth roughly)
        sales_wtd = sales_today * store_rng.uniform(4.5, 5.5)
        
        # Monthly
        sales_mtd = sales_today * store_rng.uniform(18, 22)
        
        # Yearly
        sales_ytd = sales_mtd * store_rng.uniform(10, 12)
        
        # Forecast comparison (consistent with individual store data)
        daily_data = get_daily_sales(store_id, date)
        vs_forecast_pct = daily_data.vs_forecast_pct
        
        # Labor cost (varies by store efficiency)
        labor_cost_pct = store_rng.uniform(22, 32)
        
        # Trend based on yesterday comparison
        vs_yesterday = daily_data.vs_yesterday_pct
        if vs_yesterday > 3:
            trend = "up"
        elif vs_yesterday < -3:
            trend = "down"
        else:
            trend = "flat"
        
        # Staff count (based on store size)
        staff_count = int(sqft / 300) + store_rng.randint(0, 2)
        
        raw_metrics.append({
            "store": store,
            "sales_today": sales_today,
            "sales_wtd": sales_wtd,
            "sales_mtd": sales_mtd,
            "sales_ytd": sales_ytd,
            "vs_forecast_pct": vs_forecast_pct,
            "labor_cost_pct": labor_cost_pct,
            "trend": trend,
            "staff_count": staff_count,
        })
    
    # Sort by monthly sales to determine rank
    raw_metrics.sort(key=lambda x: x["sales_mtd"], reverse=True)
    
    # Build final KPI objects with ranks
    for rank, metrics in enumerate(raw_metrics, 1):
        store = metrics["store"]
        store_id = store["store_id"]
        
        store_kpis.append(StoreKPI(
            store_id=store_id,
            name=store["name"],
            city=store["city"],
            address=store["address"],
            latitude=store["lat"],
            longitude=store["lng"],
            sqft=store.get("sqft", 1600),
            open_date=store.get("open_date", "2020-01-01"),
            sales_today=round(metrics["sales_today"], 2),
            sales_wtd=round(metrics["sales_wtd"], 2),
            sales_mtd=round(metrics["sales_mtd"], 2),
            sales_ytd=round(metrics["sales_ytd"], 2),
            vs_forecast_pct=round(metrics["vs_forecast_pct"], 1),
            labor_cost_pct=round(metrics["labor_cost_pct"], 1),
            rank=rank,
            trend=metrics["trend"],
            staff_count=metrics["staff_count"],
            manager_name=store.get("manager_name", f"Manager {store_id}"),
            phone=store.get("phone", f"(313) 555-{1000 + store_id:04d}"),
        ))
    
    # Sort by store_id for consistent ordering
    store_kpis.sort(key=lambda x: x.store_id)
    
    _store_kpis_cache[cache_key] = (datetime.now(), store_kpis)
    logger.debug(f"Generated KPIs for {len(store_kpis)} stores on {date}")
    
    return store_kpis


def get_store_kpi(store_id: int, date: str) -> Optional[StoreKPI]:
    """Get KPI for a single store - consistent with get_all_store_kpis."""
    all_kpis = get_all_store_kpis(date)
    return next((k for k in all_kpis if k.store_id == store_id), None)


def get_store_rankings(date: str) -> List[StoreKPI]:
    """Get stores sorted by rank (best performers first)."""
    all_kpis = get_all_store_kpis(date)
    return sorted(all_kpis, key=lambda x: x.rank)


# Singleton-style accessor for consistency
demo_data = type('DemoDataService', (), {
    'get_daily_sales': staticmethod(get_daily_sales),
    'get_sales_up_to_hour': staticmethod(get_sales_up_to_hour),
    'get_inventory_levels': staticmethod(get_inventory_levels),
    'get_inventory_summary': staticmethod(get_inventory_summary),
    'get_items_needing_order': staticmethod(get_items_needing_order),
    'get_dough_inventory': staticmethod(get_dough_inventory),
    'get_forecast_for_date': staticmethod(get_forecast_for_date),
    'get_all_store_kpis': staticmethod(get_all_store_kpis),
    'get_store_kpi': staticmethod(get_store_kpi),
    'get_store_rankings': staticmethod(get_store_rankings),
    'clear_cache': staticmethod(clear_cache),
    'LC_INGREDIENTS': LC_INGREDIENTS,
    'DOUGH_TYPES': DOUGH_TYPES,
    'HOURLY_TRAFFIC_PATTERN': HOURLY_TRAFFIC_PATTERN,
    'DEMO_STORES': DEMO_STORES,
})()

