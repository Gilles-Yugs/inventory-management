"""
Tests for restocking order API endpoints and the forecast fields they rely on.
"""
import json
from datetime import datetime, timedelta

import pytest


class TestDemandForecastCostFields:
    """Forecast records must carry the data restocking orders are priced from."""

    def test_forecasts_include_cost_and_lead_time(self, client):
        """Test that every forecast has unit cost, supplier and lead time."""
        response = client.get("/api/demand")
        assert response.status_code == 200

        data = response.json()
        assert len(data) > 0

        for forecast in data:
            assert isinstance(forecast["unit_cost"], (int, float))
            assert forecast["unit_cost"] > 0
            assert isinstance(forecast["supplier_name"], str)
            assert forecast["supplier_name"]
            assert isinstance(forecast["lead_time_days"], int)
            assert forecast["lead_time_days"] > 0


class TestRestockingOrderEndpoints:
    """Test suite for restocking order endpoints."""

    def _forecast(self, client, sku):
        forecasts = client.get("/api/demand").json()
        return next(f for f in forecasts if f["item_sku"] == sku)

    def test_get_restocking_orders_empty(self, client, isolated_restocking):
        """Test listing orders when none have been submitted."""
        response = client.get("/api/restocking-orders")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_restocking_order(self, client, isolated_restocking):
        """Test submitting a valid order."""
        forecast = self._forecast(client, "WDG-001")
        payload = {"budget": 5000, "items": [{"sku": "WDG-001", "quantity": 100}]}

        response = client.post("/api/restocking-orders", json=payload)
        assert response.status_code == 201

        order = response.json()
        assert order["status"] == "Submitted"
        assert order["order_number"].startswith("RST-")
        assert order["budget"] == 5000
        assert order["lead_time_days"] == forecast["lead_time_days"]
        assert abs(order["total_cost"] - 100 * forecast["unit_cost"]) < 0.01

        item = order["items"][0]
        assert item["sku"] == "WDG-001"
        assert item["quantity"] == 100
        assert item["supplier_name"] == forecast["supplier_name"]
        assert abs(item["line_total"] - 100 * forecast["unit_cost"]) < 0.01

    def test_order_lead_time_is_longest_item(self, client, isolated_restocking):
        """Test that the order lead time is the slowest item's lead time."""
        fast = self._forecast(client, "FLT-405")
        slow = self._forecast(client, "CTL-330")
        assert slow["lead_time_days"] > fast["lead_time_days"]

        payload = {
            "budget": 10000,
            "items": [{"sku": "FLT-405", "quantity": 10}, {"sku": "CTL-330", "quantity": 1}],
        }
        response = client.post("/api/restocking-orders", json=payload)
        assert response.status_code == 201
        assert response.json()["lead_time_days"] == slow["lead_time_days"]

    def test_expected_delivery_matches_lead_time(self, client, isolated_restocking):
        """Test that expected delivery is submitted date plus lead time."""
        payload = {"budget": 5000, "items": [{"sku": "GSK-203", "quantity": 10}]}
        order = client.post("/api/restocking-orders", json=payload).json()

        submitted = datetime.fromisoformat(order["submitted_date"])
        expected = datetime.fromisoformat(order["expected_delivery"])
        assert expected - submitted == timedelta(days=order["lead_time_days"])

    def test_submitted_order_appears_in_list_newest_first(self, client, isolated_restocking):
        """Test that submitted orders are listed, newest first."""
        first = client.post(
            "/api/restocking-orders",
            json={"budget": 1000, "items": [{"sku": "GSK-203", "quantity": 5}]},
        ).json()
        second = client.post(
            "/api/restocking-orders",
            json={"budget": 1000, "items": [{"sku": "FLT-405", "quantity": 5}]},
        ).json()
        assert first["id"] != second["id"]
        assert first["order_number"] != second["order_number"]

        response = client.get("/api/restocking-orders")
        assert response.status_code == 200
        ids = [o["id"] for o in response.json()]
        assert ids == [second["id"], first["id"]]

    def test_order_is_persisted_to_file(self, client, isolated_restocking, tmp_path):
        """Test that a submitted order is written to the JSON file."""
        payload = {"budget": 1000, "items": [{"sku": "GSK-203", "quantity": 5}]}
        order = client.post("/api/restocking-orders", json=payload).json()

        saved = json.loads((tmp_path / "restocking_orders.json").read_text())
        assert [o["id"] for o in saved] == [order["id"]]

    def test_client_supplied_price_is_ignored(self, client, isolated_restocking):
        """Test that the server prices the order from forecast data."""
        forecast = self._forecast(client, "WDG-001")
        payload = {
            "budget": 5000,
            "items": [{"sku": "WDG-001", "quantity": 10, "unit_cost": 0.01, "lead_time_days": 1}],
        }
        order = client.post("/api/restocking-orders", json=payload).json()

        assert order["items"][0]["unit_cost"] == forecast["unit_cost"]
        assert order["items"][0]["lead_time_days"] == forecast["lead_time_days"]

    def test_order_exactly_at_budget_is_accepted(self, client, isolated_restocking):
        """Test that a total equal to the budget is allowed."""
        forecast = self._forecast(client, "GSK-203")
        total = round(10 * forecast["unit_cost"], 2)

        response = client.post(
            "/api/restocking-orders",
            json={"budget": total, "items": [{"sku": "GSK-203", "quantity": 10}]},
        )
        assert response.status_code == 201

    def test_order_over_budget_rejected(self, client, isolated_restocking):
        """Test that a total above the budget is rejected and not stored."""
        response = client.post(
            "/api/restocking-orders",
            json={"budget": 10, "items": [{"sku": "WDG-001", "quantity": 100}]},
        )
        assert response.status_code == 400
        assert "budget" in response.json()["detail"].lower()
        assert client.get("/api/restocking-orders").json() == []

    def test_unknown_sku_rejected(self, client, isolated_restocking):
        """Test that a SKU outside the demand forecast is rejected."""
        response = client.post(
            "/api/restocking-orders",
            json={"budget": 1000, "items": [{"sku": "NOPE-999", "quantity": 1}]},
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_duplicate_sku_rejected(self, client, isolated_restocking):
        """Test that the same SKU cannot appear twice."""
        response = client.post(
            "/api/restocking-orders",
            json={
                "budget": 1000,
                "items": [{"sku": "GSK-203", "quantity": 1}, {"sku": "GSK-203", "quantity": 2}],
            },
        )
        assert response.status_code == 400
        assert "duplicate" in response.json()["detail"].lower()

    def test_empty_items_rejected(self, client, isolated_restocking):
        """Test that an order with no items fails validation."""
        response = client.post("/api/restocking-orders", json={"budget": 1000, "items": []})
        assert response.status_code == 422

    @pytest.mark.parametrize("quantity", [0, -5])
    def test_non_positive_quantity_rejected(self, client, isolated_restocking, quantity):
        """Test that zero or negative quantities fail validation."""
        response = client.post(
            "/api/restocking-orders",
            json={"budget": 1000, "items": [{"sku": "GSK-203", "quantity": quantity}]},
        )
        assert response.status_code == 422

    def test_negative_budget_rejected(self, client, isolated_restocking):
        """Test that a negative budget fails validation."""
        response = client.post(
            "/api/restocking-orders",
            json={"budget": -1, "items": [{"sku": "GSK-203", "quantity": 1}]},
        )
        assert response.status_code == 422
