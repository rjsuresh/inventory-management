"""
Tests for restocking API endpoints (recommendations and order submission).
"""
import pytest


class TestRestockRecommendationsEndpoint:
    """Test suite for the restock recommendations endpoint."""

    def test_get_recommendations_zero_budget(self, client):
        """Test that a zero budget yields no recommendations."""
        response = client.get("/api/restocking/recommendations?budget=0")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_get_recommendations_negative_budget(self, client):
        """Test that a negative budget is rejected."""
        response = client.get("/api/restocking/recommendations?budget=-1")
        assert response.status_code == 400

        data = response.json()
        assert "detail" in data

    def test_get_recommendations_large_budget_structure(self, client):
        """Test that recommendations have the expected structure."""
        response = client.get("/api/restocking/recommendations?budget=1000000")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        first = data[0]
        assert "sku" in first
        assert "item_name" in first
        assert "category" in first
        assert "warehouse" in first
        assert "trend" in first
        assert "current_demand" in first
        assert "forecasted_demand" in first
        assert "unit_cost" in first
        assert "recommended_quantity" in first
        assert "estimated_cost" in first
        assert "lead_time_days" in first

    def test_recommendations_within_budget(self, client):
        """Test that the total estimated cost never exceeds the given budget."""
        budget = 5000
        response = client.get(f"/api/restocking/recommendations?budget={budget}")
        data = response.json()

        total_cost = sum(item["estimated_cost"] for item in data)
        assert total_cost <= budget + 0.01

    def test_recommendations_have_positive_quantities(self, client):
        """Test that every recommended item has a positive quantity and cost."""
        response = client.get("/api/restocking/recommendations?budget=1000000")
        data = response.json()

        for item in data:
            assert item["recommended_quantity"] > 0
            assert item["estimated_cost"] > 0
            assert item["lead_time_days"] > 0

    def test_recommendations_trend_values(self, client):
        """Test that recommended items have valid trend values."""
        response = client.get("/api/restocking/recommendations?budget=1000000")
        data = response.json()

        valid_trends = ["increasing", "stable", "decreasing"]
        for item in data:
            assert item["trend"].lower() in valid_trends

    def test_recommendations_prioritize_increasing_trend(self, client):
        """Test that increasing-trend items are recommended before decreasing-trend items."""
        response = client.get("/api/restocking/recommendations?budget=1000000")
        data = response.json()

        trend_rank = {"increasing": 0, "stable": 1, "decreasing": 2}
        ranks = [trend_rank[item["trend"].lower()] for item in data]

        # The recommendation order should be non-decreasing in trend rank
        assert ranks == sorted(ranks)

    def test_recommendations_small_budget_fewer_items(self, client):
        """Test that a smaller budget yields no more items than a larger budget."""
        small_response = client.get("/api/restocking/recommendations?budget=100")
        large_response = client.get("/api/restocking/recommendations?budget=1000000")

        small_data = small_response.json()
        large_data = large_response.json()

        assert len(small_data) <= len(large_data)


class TestRestockOrderSubmission:
    """Test suite for submitting restocking orders."""

    def _get_sample_items(self, client):
        """Helper to fetch a couple of recommended items to submit as an order."""
        response = client.get("/api/restocking/recommendations?budget=5000")
        recommendations = response.json()
        return [
            {
                "sku": item["sku"],
                "item_name": item["item_name"],
                "category": item["category"],
                "warehouse": item["warehouse"],
                "quantity": item["recommended_quantity"],
                "unit_cost": item["unit_cost"]
            }
            for item in recommendations
        ]

    def test_submit_restock_order_empty_items(self, client):
        """Test that submitting an order with no items is rejected."""
        response = client.post("/api/restocking/orders", json={"items": [], "budget": 5000})
        assert response.status_code == 400

        data = response.json()
        assert "detail" in data

    def test_submit_restock_order_success(self, client):
        """Test submitting a valid restocking order."""
        items = self._get_sample_items(client)
        assert len(items) > 0

        response = client.post("/api/restocking/orders", json={"items": items, "budget": 5000})
        assert response.status_code == 200

        order = response.json()
        assert order["status"] == "Submitted"
        assert order["customer"] == "Internal Restocking"
        assert "order_number" in order
        assert "lead_time_days" in order
        assert order["lead_time_days"] > 0
        assert "expected_delivery" in order
        assert "T" in order["expected_delivery"]

    def test_submit_restock_order_total_value_calculation(self, client):
        """Test that the submitted order's total value matches the sum of its line items."""
        items = self._get_sample_items(client)

        response = client.post("/api/restocking/orders", json={"items": items, "budget": 5000})
        order = response.json()

        expected_total = sum(item["quantity"] * item["unit_cost"] for item in items)
        assert abs(order["total_value"] - expected_total) < 0.01

    def test_submit_restock_order_items_structure(self, client):
        """Test that the created order's items reflect the submitted line items."""
        items = self._get_sample_items(client)

        response = client.post("/api/restocking/orders", json={"items": items, "budget": 5000})
        order = response.json()

        assert isinstance(order["items"], list)
        assert len(order["items"]) == len(items)
        for order_item in order["items"]:
            assert "sku" in order_item
            assert "name" in order_item
            assert "quantity" in order_item
            assert "unit_price" in order_item

    def test_submitted_order_appears_in_orders_list(self, client):
        """Test that a submitted restocking order shows up via GET /api/orders."""
        items = self._get_sample_items(client)

        create_response = client.post("/api/restocking/orders", json={"items": items, "budget": 5000})
        created_order = create_response.json()

        orders_response = client.get("/api/orders")
        assert orders_response.status_code == 200
        all_orders = orders_response.json()

        matching = [o for o in all_orders if o["id"] == created_order["id"]]
        assert len(matching) == 1
        assert matching[0]["status"] == "Submitted"
