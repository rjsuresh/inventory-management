from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel
from uuid import uuid4
from datetime import datetime, timedelta
from mock_data import inventory_items, orders, demand_forecasts, backlog_items, spending_summary, monthly_spending, category_spending, recent_transactions, purchase_orders

app = FastAPI(title="Factory Inventory Management System")

# Quarter mapping for date filtering
QUARTER_MAP = {
    'Q1-2025': ['2025-01', '2025-02', '2025-03'],
    'Q2-2025': ['2025-04', '2025-05', '2025-06'],
    'Q3-2025': ['2025-07', '2025-08', '2025-09'],
    'Q4-2025': ['2025-10', '2025-11', '2025-12']
}

# Simulated per-category supplier lead times (no real supplier data exists in this demo)
CATEGORY_LEAD_TIME_DAYS = {
    "Circuit Boards": 10,
    "Sensors": 7,
    "Actuators": 12,
    "Controllers": 9,
    "Power Supplies": 14
}
DEFAULT_LEAD_TIME_DAYS = 10
TREND_RANK = {"increasing": 0, "stable": 1, "decreasing": 2}

def filter_by_month(items: list, month: Optional[str]) -> list:
    """Filter items by month/quarter based on order_date field"""
    if not month or month == 'all':
        return items

    if month.startswith('Q'):
        # Handle quarters
        if month in QUARTER_MAP:
            months = QUARTER_MAP[month]
            return [item for item in items if any(m in item.get('order_date', '') for m in months)]
    else:
        # Direct month match
        return [item for item in items if month in item.get('order_date', '')]

    return items

def apply_filters(items: list, warehouse: Optional[str] = None, category: Optional[str] = None,
                 status: Optional[str] = None) -> list:
    """Apply common filters to a list of items"""
    filtered = items

    if warehouse and warehouse != 'all':
        filtered = [item for item in filtered if item.get('warehouse') == warehouse]

    if category and category != 'all':
        filtered = [item for item in filtered if item.get('category', '').lower() == category.lower()]

    if status and status != 'all':
        filtered = [item for item in filtered if item.get('status', '').lower() == status.lower()]

    return filtered

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data models
class InventoryItem(BaseModel):
    id: str
    sku: str
    name: str
    category: str
    warehouse: str
    quantity_on_hand: int
    reorder_point: int
    unit_cost: float
    location: str
    last_updated: str

class Order(BaseModel):
    id: str
    order_number: str
    customer: str
    items: List[dict]
    status: str
    order_date: str
    expected_delivery: str
    total_value: float
    actual_delivery: Optional[str] = None
    warehouse: Optional[str] = None
    category: Optional[str] = None
    lead_time_days: Optional[int] = None

class DemandForecast(BaseModel):
    id: str
    item_sku: str
    item_name: str
    current_demand: int
    forecasted_demand: int
    trend: str
    period: str

class BacklogItem(BaseModel):
    id: str
    order_id: str
    item_sku: str
    item_name: str
    quantity_needed: int
    quantity_available: int
    days_delayed: int
    priority: str
    has_purchase_order: Optional[bool] = False

class PurchaseOrder(BaseModel):
    id: str
    backlog_item_id: str
    supplier_name: str
    quantity: int
    unit_cost: float
    expected_delivery_date: str
    status: str
    created_date: str
    notes: Optional[str] = None

class CreatePurchaseOrderRequest(BaseModel):
    backlog_item_id: str
    supplier_name: str
    quantity: int
    unit_cost: float
    expected_delivery_date: str
    notes: Optional[str] = None

class RestockRecommendation(BaseModel):
    sku: str
    item_name: str
    category: str
    warehouse: str
    trend: str
    current_demand: int
    forecasted_demand: int
    unit_cost: float
    recommended_quantity: int
    estimated_cost: float
    lead_time_days: int

class RestockOrderItem(BaseModel):
    sku: str
    item_name: str
    category: str
    warehouse: str
    quantity: int
    unit_cost: float

class CreateRestockOrderRequest(BaseModel):
    items: List[RestockOrderItem]
    budget: float

# API endpoints
@app.get("/")
def root():
    return {"message": "Factory Inventory Management System API", "version": "1.0.0"}

@app.get("/api/inventory", response_model=List[InventoryItem])
def get_inventory(
    warehouse: Optional[str] = None,
    category: Optional[str] = None
):
    """Get all inventory items with optional filtering"""
    return apply_filters(inventory_items, warehouse, category)

@app.get("/api/inventory/{item_id}", response_model=InventoryItem)
def get_inventory_item(item_id: str):
    """Get a specific inventory item"""
    item = next((item for item in inventory_items if item["id"] == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@app.get("/api/orders", response_model=List[Order])
def get_orders(
    warehouse: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    month: Optional[str] = None
):
    """Get all orders with optional filtering"""
    filtered_orders = apply_filters(orders, warehouse, category, status)
    filtered_orders = filter_by_month(filtered_orders, month)
    return filtered_orders

@app.get("/api/orders/{order_id}", response_model=Order)
def get_order(order_id: str):
    """Get a specific order"""
    order = next((order for order in orders if order["id"] == order_id), None)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@app.get("/api/demand", response_model=List[DemandForecast])
def get_demand_forecasts():
    """Get demand forecasts"""
    return demand_forecasts

@app.get("/api/backlog", response_model=List[BacklogItem])
def get_backlog():
    """Get backlog items with purchase order status"""
    # Add has_purchase_order flag to each backlog item
    result = []
    for item in backlog_items:
        item_dict = dict(item)
        # Check if this backlog item has a purchase order
        has_po = any(po["backlog_item_id"] == item["id"] for po in purchase_orders)
        item_dict["has_purchase_order"] = has_po
        result.append(item_dict)
    return result

@app.get("/api/dashboard/summary")
def get_dashboard_summary(
    warehouse: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    month: Optional[str] = None
):
    """Get summary statistics for dashboard with optional filtering"""
    # Filter inventory
    filtered_inventory = apply_filters(inventory_items, warehouse, category)

    # Filter orders
    filtered_orders = apply_filters(orders, warehouse, category, status)
    filtered_orders = filter_by_month(filtered_orders, month)

    total_inventory_value = sum(item["quantity_on_hand"] * item["unit_cost"] for item in filtered_inventory)
    low_stock_items = len([item for item in filtered_inventory if item["quantity_on_hand"] <= item["reorder_point"]])
    pending_orders = len([order for order in filtered_orders if order["status"] in ["Processing", "Backordered"]])
    total_backlog_items = len(backlog_items)

    return {
        "total_inventory_value": round(total_inventory_value, 2),
        "low_stock_items": low_stock_items,
        "pending_orders": pending_orders,
        "total_backlog_items": total_backlog_items,
        "total_orders_value": sum(order["total_value"] for order in filtered_orders)
    }

def build_restock_recommendations(budget: float) -> List[dict]:
    """Greedily recommend restock items by demand trend/growth within a budget"""
    inventory_by_sku = {item["sku"]: item for item in inventory_items}
    inventory_by_name = {item["name"].lower(): item for item in inventory_items}

    candidates = []
    for forecast in demand_forecasts:
        item = inventory_by_sku.get(forecast["item_sku"]) or inventory_by_name.get(forecast["item_name"].lower())
        if not item:
            continue

        demand_gap = forecast["forecasted_demand"] - forecast["current_demand"]
        recommended_quantity = max(demand_gap, round(forecast["current_demand"] * 0.1), 10)
        lead_time_days = CATEGORY_LEAD_TIME_DAYS.get(item["category"], DEFAULT_LEAD_TIME_DAYS)

        candidates.append({
            "sku": item["sku"],
            "item_name": forecast["item_name"],
            "category": item["category"],
            "warehouse": item["warehouse"],
            "trend": forecast["trend"],
            "current_demand": forecast["current_demand"],
            "forecasted_demand": forecast["forecasted_demand"],
            "unit_cost": item["unit_cost"],
            "recommended_quantity": recommended_quantity,
            "lead_time_days": lead_time_days,
            "_demand_gap": demand_gap
        })

    candidates.sort(key=lambda c: (TREND_RANK.get(c["trend"], 99), -c["_demand_gap"]))

    recommendations = []
    remaining_budget = budget
    for candidate in candidates:
        if remaining_budget <= 0:
            break

        full_cost = round(candidate["recommended_quantity"] * candidate["unit_cost"], 2)
        if full_cost <= remaining_budget:
            quantity = candidate["recommended_quantity"]
        elif candidate["unit_cost"] > 0:
            quantity = int(remaining_budget // candidate["unit_cost"])
        else:
            quantity = 0

        if quantity <= 0:
            continue

        estimated_cost = round(quantity * candidate["unit_cost"], 2)
        remaining_budget -= estimated_cost

        recommendations.append({
            "sku": candidate["sku"],
            "item_name": candidate["item_name"],
            "category": candidate["category"],
            "warehouse": candidate["warehouse"],
            "trend": candidate["trend"],
            "current_demand": candidate["current_demand"],
            "forecasted_demand": candidate["forecasted_demand"],
            "unit_cost": candidate["unit_cost"],
            "recommended_quantity": quantity,
            "estimated_cost": estimated_cost,
            "lead_time_days": candidate["lead_time_days"]
        })

    return recommendations

@app.get("/api/restocking/recommendations", response_model=List[RestockRecommendation])
def get_restock_recommendations(budget: float):
    """Recommend items to restock based on demand trend/growth within a budget"""
    if budget < 0:
        raise HTTPException(status_code=400, detail="Budget must be non-negative")
    return build_restock_recommendations(budget)

@app.post("/api/restocking/orders", response_model=Order)
def create_restock_order(request: CreateRestockOrderRequest):
    """Submit a restocking order built from recommended items"""
    if not request.items:
        raise HTTPException(status_code=400, detail="At least one item is required")

    lead_time_days = max(
        CATEGORY_LEAD_TIME_DAYS.get(item.category, DEFAULT_LEAD_TIME_DAYS)
        for item in request.items
    )
    now = datetime.now()
    categories = {item.category for item in request.items}
    warehouses = {item.warehouse for item in request.items}

    new_order = {
        "id": str(uuid4()),
        "order_number": f"RESTOCK-{uuid4().hex[:8].upper()}",
        "customer": "Internal Restocking",
        "items": [
            {
                "sku": item.sku,
                "name": item.item_name,
                "quantity": item.quantity,
                "unit_price": item.unit_cost
            }
            for item in request.items
        ],
        "status": "Submitted",
        "order_date": now.isoformat(),
        "expected_delivery": (now + timedelta(days=lead_time_days)).isoformat(),
        "total_value": round(sum(item.quantity * item.unit_cost for item in request.items), 2),
        "actual_delivery": None,
        "warehouse": next(iter(warehouses)) if len(warehouses) == 1 else "Multiple",
        "category": next(iter(categories)) if len(categories) == 1 else "Multiple",
        "lead_time_days": lead_time_days
    }

    orders.append(new_order)
    return new_order

@app.get("/api/spending/summary")
def get_spending_summary():
    """Get spending summary statistics"""
    return spending_summary

@app.get("/api/spending/monthly")
def get_monthly_spending():
    """Get monthly spending breakdown"""
    return monthly_spending

@app.get("/api/spending/categories")
def get_category_spending():
    """Get spending by category"""
    return category_spending

@app.get("/api/spending/transactions")
def get_recent_transactions():
    """Get recent transactions"""
    return recent_transactions

@app.get("/api/reports/quarterly")
def get_quarterly_reports():
    """Get quarterly performance reports"""
    # Calculate quarterly statistics from orders
    quarters = {}

    for order in orders:
        order_date = order.get('order_date', '')
        # Determine quarter
        if '2025-01' in order_date or '2025-02' in order_date or '2025-03' in order_date:
            quarter = 'Q1-2025'
        elif '2025-04' in order_date or '2025-05' in order_date or '2025-06' in order_date:
            quarter = 'Q2-2025'
        elif '2025-07' in order_date or '2025-08' in order_date or '2025-09' in order_date:
            quarter = 'Q3-2025'
        elif '2025-10' in order_date or '2025-11' in order_date or '2025-12' in order_date:
            quarter = 'Q4-2025'
        else:
            continue

        if quarter not in quarters:
            quarters[quarter] = {
                'quarter': quarter,
                'total_orders': 0,
                'total_revenue': 0,
                'delivered_orders': 0,
                'avg_order_value': 0
            }

        quarters[quarter]['total_orders'] += 1
        quarters[quarter]['total_revenue'] += order.get('total_value', 0)
        if order.get('status') == 'Delivered':
            quarters[quarter]['delivered_orders'] += 1

    # Calculate averages and fulfillment rate
    result = []
    for q, data in quarters.items():
        if data['total_orders'] > 0:
            data['avg_order_value'] = round(data['total_revenue'] / data['total_orders'], 2)
            data['fulfillment_rate'] = round((data['delivered_orders'] / data['total_orders']) * 100, 1)
        result.append(data)

    # Sort by quarter
    result.sort(key=lambda x: x['quarter'])
    return result

@app.get("/api/reports/monthly-trends")
def get_monthly_trends():
    """Get month-over-month trends"""
    months = {}

    for order in orders:
        order_date = order.get('order_date', '')
        if not order_date:
            continue

        # Extract month (format: YYYY-MM-DD)
        month = order_date[:7]  # Gets YYYY-MM

        if month not in months:
            months[month] = {
                'month': month,
                'order_count': 0,
                'revenue': 0,
                'delivered_count': 0
            }

        months[month]['order_count'] += 1
        months[month]['revenue'] += order.get('total_value', 0)
        if order.get('status') == 'Delivered':
            months[month]['delivered_count'] += 1

    # Convert to list and sort
    result = list(months.values())
    result.sort(key=lambda x: x['month'])
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
