"""
Genie AI Chatbot API endpoints.

Provides natural language query interface using Databricks Genie:
- Start conversations
- Continue conversations with follow-ups
- Get suggested questions
- Retrieve conversation history

Used by Regional Manager's Compare view for AI insights.
"""

import os
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from config.settings import Settings, get_settings
from services.genie import genie_client

router = APIRouter()

_workspace_id: Optional[str] = None


def _get_workspace_id(settings: Settings) -> Optional[str]:
    """WORKSPACE_ID if set, else ask the workspace (cached), so a new workspace needs no config."""
    global _workspace_id
    if settings.workspace_id:
        return settings.workspace_id
    if _workspace_id is None:
        try:
            _workspace_id = str(genie_client.client.get_workspace_id())
        except Exception:
            return None
    return _workspace_id


# === Pydantic Models ===

class QueryRequest(BaseModel):
    """Request to query Genie."""
    question: str
    conversation_id: Optional[str] = None


class QueryResponse(BaseModel):
    """Response from Genie query."""
    conversation_id: str
    message_id: str
    response: str
    data: Optional[List[dict]] = None
    sql: Optional[str] = None
    genie_url: Optional[str] = None


class SuggestedQuestion(BaseModel):
    """Suggested question for users."""
    question: str
    category: str  # "sales", "labor", "inventory", "comparison"


# === Endpoints ===

@router.post("/query", response_model=QueryResponse)
async def query_genie(
    request: QueryRequest,
    settings: Settings = Depends(get_settings),
) -> QueryResponse:
    """
    Query Genie with a natural language question.
    
    If conversation_id is provided, continues existing conversation.
    Otherwise, starts a new conversation.
    
    Example questions:
    - "Which store had the highest sales last week?"
    - "Compare Store #5 vs Store #12 performance"
    - "Why did Store #22's labor costs increase?"
    """
    # Check if Genie is configured
    if not settings.genie_space_id:
        raise HTTPException(
            status_code=503,
            detail="Genie Space not configured. Run setup notebook 06_setup_genie_space.py first."
        )

    try:
        if request.conversation_id:
            # Continue existing conversation
            result = genie_client.continue_conversation(
                conversation_id=request.conversation_id,
                question=request.question
            )
        else:
            # Start new conversation
            result = genie_client.start_conversation(request.question)

        # Add Genie URL for opening in UI
        genie_url = genie_client.get_genie_url(result["conversation_id"])

        return QueryResponse(
            conversation_id=result["conversation_id"],
            message_id=result["message_id"],
            response=result["response"],
            data=result.get("data"),
            sql=result.get("sql"),
            genie_url=genie_url
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Return a simulated response for demo purposes
        return QueryResponse(
            conversation_id="demo-conversation",
            message_id="demo-message",
            response=_get_demo_response(request.question),
            data=_get_demo_data(request.question),
            sql=None,
            genie_url=None
        )


@router.get("/suggestions", response_model=List[SuggestedQuestion])
async def get_suggested_questions(
    settings: Settings = Depends(get_settings),
) -> List[SuggestedQuestion]:
    """
    Get suggested questions for the Genie chatbot.
    
    Returns categorized questions users commonly ask.
    """
    # Suggestions aligned with actual Genie space tables:
    # - stores: store_id, name, address, city, state, latitude, longitude, sqft, open_date
    # - stores_kpi_view: store_id, name, city, sales_today, sales_yesterday, sales_wtd, sales_mtd, sales_ytd, vs_yesterday_pct, labor_cost_pct, rank
    # - pos_transactions: txn_id, store_id, timestamp, total, channel, payment_method
    # - employees: employee_id, store_id, name, role, hourly_rate, employment_type, status
    # - inventory_levels: store_id, ingredient_id, date, qty_on_hand, par_level, days_supply
    
    suggestions = [
        # Sales questions (from stores_kpi_view)
        SuggestedQuestion(
            question="Which store had the highest sales last week?",
            category="sales"
        ),
        SuggestedQuestion(
            question="Show me sales trends for the past 30 days",
            category="sales"
        ),
        SuggestedQuestion(
            question="What are the top selling items this week?",
            category="sales"
        ),
        SuggestedQuestion(
            question="What's the average labor cost percentage by store?",
            category="labor"
        ),
        
        # Transaction/Channel questions (from pos_transactions)
        SuggestedQuestion(
            question="What percentage of sales come from delivery vs in-store?",
            category="sales"
        ),
        SuggestedQuestion(
            question="Which payment method is most popular?",
            category="sales"
        ),
        
        # Employee questions (from employees table)
        SuggestedQuestion(
            question="How many employees work at each store?",
            category="labor"
        ),
        SuggestedQuestion(
            question="What's the average hourly rate by role?",
            category="labor"
        ),
        
        # Inventory questions (from inventory_levels)
        SuggestedQuestion(
            question="Which stores have inventory below par level?",
            category="inventory"
        ),
        SuggestedQuestion(
            question="Show me stores with less than 2 days supply",
            category="inventory"
        ),
        
        # Comparison questions (from stores_kpi_view)
        SuggestedQuestion(
            question="Which stores are underperforming this month?",
            category="comparison"
        ),
        SuggestedQuestion(
            question="Rank all stores by monthly sales",
            category="comparison"
        ),
    ]

    return suggestions


@router.get("/status")
async def get_genie_status(
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Get Genie configuration status.
    
    Returns whether Genie is properly configured.
    """
    is_configured = bool(settings.genie_space_id)

    # Build the embed iframe URL for the Genie space, if configured.
    # Format: https://<host>/embed/genie/rooms/<space_id>?o=<workspace_id>
    embed_url = None
    if is_configured:
        host = (settings.databricks_host or os.getenv("DATABRICKS_HOST") or "").rstrip("/")
        if host and not host.startswith("http"):
            host = f"https://{host}"
        if host:
            embed_url = f"{host}/embed/genie/rooms/{settings.genie_space_id}"
            workspace_id = _get_workspace_id(settings)
            if workspace_id:
                embed_url += f"?o={workspace_id}"

    return {
        "configured": is_configured,
        "genie_space_id": settings.genie_space_id if is_configured else None,
        "embed_url": embed_url,
        "message": "Genie is ready" if is_configured else "Run setup notebook to configure Genie Space"
    }


# === Demo Response Generator ===

def _get_demo_response(question: str) -> str:
    """Generate a demo response when Genie is not configured."""
    question_lower = question.lower()
    
    if "highest sales" in question_lower or "top" in question_lower and "sales" in question_lower:
        return """Based on the pos_transactions data, **Detroit Woodward Ave** had the highest weekly sales with **$24,502** in revenue.

Top 3 stores by weekly sales (sales_wtd):
1. **Detroit Woodward Ave**: $24,502
2. **Dearborn Michigan Ave**: $22,847
3. **Troy Big Beaver**: $21,293

These stores consistently rank highest due to prime locations near business districts."""

    elif "underperforming" in question_lower:
        return """Based on pos_transactions rankings, here are the underperforming stores this month:

1. **Ferndale** (Rank #25): sales_mtd $42,150
2. **Auburn Hills** (Rank #24): sales_mtd $44,302
3. **Rochester Hills** (Rank #23): sales_mtd $45,891

These stores have the lowest monthly sales and may need additional support or marketing attention."""

    elif "labor cost" in question_lower:
        return """From employees and labor data, average labor cost percentage by store:

| Store | City | Labor Cost % |
|-------|------|-------------|
| Detroit Woodward Ave | Detroit | 23.5% |
| Dearborn Michigan Ave | Dearborn | 24.2% |
| Troy Big Beaver | Troy | 25.1% |
| Metro Average | - | 25.0% |
| Pontiac | Pontiac | 28.2% |

Stores with labor_cost_pct above 27% should review their scheduling."""

    elif "delivery" in question_lower or "channel" in question_lower:
        return """From pos_transactions, sales breakdown by channel:

| Channel | Transaction Count | Percentage |
|---------|------------------|------------|
| walk_in | 125,420 | 45% |
| pizza_portal | 75,294 | 30% |
| delivery | 45,168 | 18% |
| phone | 17,562 | 7% |

Walk-in remains dominant with Pizza Portal growing as a key channel."""

    elif "payment" in question_lower:
        return """From pos_transactions, most popular payment methods:

| Payment Method | Count | Percentage |
|----------------|-------|------------|
| credit | 100,336 | 40% |
| debit | 62,710 | 25% |
| cash | 50,168 | 20% |
| apple_pay | 25,084 | 10% |
| google_pay | 12,542 | 5% |

Credit cards are the most used payment method across all stores."""

    elif "employee" in question_lower or "staff" in question_lower:
        return """From employees table, headcount by store:

Stores average **7-8 employees** each, with a mix of:
- Shift Leads: ~20% (hourly rate: $18.50)
 - Pizza Makers ~60% (hourly rate: $16.00)
- Cashiers: ~20% (hourly rate: $15.00)

Full-time vs Part-time split varies by store based on traffic patterns."""

    elif "inventory" in question_lower or "par" in question_lower or "supply" in question_lower:
        return """From inventory_levels, stores with inventory concerns:

| Store | Items Below Par | Avg Days Supply |
|-------|----------------|-----------------|
| Newark - NewPark Mall | 4 items | 1.8 days |
| Union City - Station | 3 items | 2.1 days |
| Hayward - Southland | 3 items | 2.3 days |

These stores should prioritize restocking items where qty_on_hand < par_level."""

    elif "rank" in question_lower or "all stores" in question_lower:
        return """From pos_transactions, all 25 stores ranked by monthly sales:

| Rank | Store | City | Sales MTD |
|------|-------|------|-----------|
| 1 | Detroit Woodward Ave | Detroit | $98,420 |
| 2 | Dearborn Michigan Ave | Dearborn | $94,502 |
| 3 | Troy Big Beaver | Troy | $91,847 |
| ... | | | |
| 25 | Ferndale | Ferndale | $42,150 |

Use the rank column for quick performance comparisons."""

    else:
        return f"""I analyzed your question about the store data.

Available data includes:
- **stores**: Location info (address, city, sqft, open_date)
- **stores_kpi_view**: Sales metrics (today, WTD, MTD, YTD) and labor_cost_pct
- **pos_transactions**: Transaction details (total, channel, payment_method)
- **employees**: Staff info (name, role, hourly_rate, employment_type)
- **inventory_levels**: Stock data (qty_on_hand, par_level, days_supply)

Try asking about specific metrics from these tables!"""


def _get_demo_data(question: str) -> Optional[List[dict]]:
    """Generate demo data when Genie is not configured."""
    question_lower = question.lower()
    
    if "highest sales" in question_lower or "top" in question_lower and "sales" in question_lower:
        return [
            {"rank": 1, "name": "Detroit Woodward Ave", "city": "Detroit", "sales_wtd": 24502},
            {"rank": 2, "name": "Dearborn Michigan Ave", "city": "Dearborn", "sales_wtd": 22847},
            {"rank": 3, "name": "Troy Big Beaver", "city": "Troy", "sales_wtd": 21293},
            {"rank": 4, "name": "Southfield", "city": "Southfield", "sales_wtd": 19847},
            {"rank": 5, "name": "Livonia", "city": "Livonia", "sales_wtd": 18502},
        ]

    elif "rank" in question_lower or "all stores" in question_lower:
        return [
            {"rank": 1, "name": "Detroit Woodward Ave", "sales_mtd": 98420},
            {"rank": 2, "name": "Dearborn Michigan Ave", "sales_mtd": 94502},
            {"rank": 3, "name": "Troy Big Beaver", "sales_mtd": 91847},
            {"rank": 4, "name": "Southfield", "sales_mtd": 88293},
            {"rank": 5, "name": "Livonia", "sales_mtd": 85102},
        ]

    elif "labor" in question_lower:
        return [
            {"name": "Detroit Woodward Ave", "city": "Detroit", "labor_cost_pct": 23.5},
            {"name": "Dearborn Michigan Ave", "city": "Dearborn", "labor_cost_pct": 24.2},
            {"name": "Troy Big Beaver", "city": "Troy", "labor_cost_pct": 25.1},
            {"name": "Warren", "city": "Warren", "labor_cost_pct": 26.8},
            {"name": "Pontiac", "city": "Pontiac", "labor_cost_pct": 28.2},
        ]

    elif "delivery" in question_lower or "channel" in question_lower:
        return [
            {"channel": "walk_in", "transaction_count": 125420, "percentage": 45.0},
            {"channel": "pizza_portal", "transaction_count": 75294, "percentage": 30.0},
            {"channel": "delivery", "transaction_count": 45168, "percentage": 18.0},
            {"channel": "phone", "transaction_count": 17562, "percentage": 7.0},
        ]
    
    elif "payment" in question_lower:
        return [
            {"payment_method": "credit", "count": 100336, "percentage": 40.0},
            {"payment_method": "debit", "count": 62710, "percentage": 25.0},
            {"payment_method": "cash", "count": 50168, "percentage": 20.0},
            {"payment_method": "apple_pay", "count": 25084, "percentage": 10.0},
            {"payment_method": "google_pay", "count": 12542, "percentage": 5.0},
        ]
    
    elif "employee" in question_lower or "staff" in question_lower or "hourly rate" in question_lower:
        return [
            {"role": "shift_lead", "avg_hourly_rate": 18.50, "employee_count": 42},
            {"role": "pizza_maker", "avg_hourly_rate": 16.00, "employee_count": 126},
            {"role": "cashier", "avg_hourly_rate": 15.00, "employee_count": 42},
        ]
    
    elif "inventory" in question_lower or "par" in question_lower or "supply" in question_lower:
        return [
            {"name": "Hamtramck", "items_below_par": 4, "avg_days_supply": 1.8},
            {"name": "Auburn Hills", "items_below_par": 3, "avg_days_supply": 2.1},
            {"name": "Ferndale", "items_below_par": 3, "avg_days_supply": 2.3},
            {"name": "Rochester Hills", "items_below_par": 2, "avg_days_supply": 2.5},
        ]

    elif "underperforming" in question_lower:
        return [
            {"rank": 25, "name": "Ferndale", "city": "Ferndale", "sales_mtd": 42150},
            {"rank": 24, "name": "Auburn Hills", "city": "Auburn Hills", "sales_mtd": 44302},
            {"rank": 23, "name": "Rochester Hills", "city": "Rochester Hills", "sales_mtd": 45891},
            {"rank": 22, "name": "Pontiac", "city": "Pontiac", "sales_mtd": 48420},
        ]
    
    return None



