"""
Tests for the report endpoints (quarterly performance and monthly trends).
"""
import pytest


class TestQuarterlyReports:
    """Test suite for /api/reports/quarterly."""

    def test_get_quarterly_reports(self, client):
        """Test getting quarterly reports without filters."""
        response = client.get("/api/reports/quarterly")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        for quarter in data:
            assert quarter["quarter"].startswith("Q")
            assert quarter["total_orders"] > 0
            assert 0 <= quarter["fulfillment_rate"] <= 100
            assert abs(quarter["avg_order_value"] - quarter["total_revenue"] / quarter["total_orders"]) < 0.01

    def test_quarterly_reports_sorted(self, client):
        """Test that quarters are returned in order."""
        data = client.get("/api/reports/quarterly").json()
        labels = [q["quarter"] for q in data]
        assert labels == sorted(labels)

    def test_quarterly_totals_match_orders(self, client):
        """Test that every order is counted in exactly one quarter."""
        orders = client.get("/api/orders").json()
        data = client.get("/api/reports/quarterly").json()
        assert sum(q["total_orders"] for q in data) == len(orders)

    def test_quarterly_filter_by_warehouse(self, client):
        """Test that the warehouse filter limits the orders counted."""
        orders = client.get("/api/orders?warehouse=Tokyo").json()
        data = client.get("/api/reports/quarterly?warehouse=Tokyo").json()

        assert sum(q["total_orders"] for q in data) == len(orders)
        all_orders = client.get("/api/orders").json()
        assert len(orders) < len(all_orders)

    def test_quarterly_filter_by_category(self, client):
        """Test that the category filter limits the orders counted."""
        orders = client.get("/api/orders?category=Sensors").json()
        data = client.get("/api/reports/quarterly?category=Sensors").json()
        assert sum(q["total_orders"] for q in data) == len(orders)

    def test_quarterly_filter_by_status(self, client):
        """Test that filtering to delivered orders gives a 100% fulfillment rate."""
        data = client.get("/api/reports/quarterly?status=Delivered").json()
        assert len(data) > 0
        for quarter in data:
            assert quarter["fulfillment_rate"] == 100

    def test_quarterly_filter_by_month(self, client):
        """Test that a single month only produces its own quarter."""
        data = client.get("/api/reports/quarterly?month=2025-03").json()
        assert [q["quarter"] for q in data] == ["Q1-2025"]

        orders = client.get("/api/orders?month=2025-03").json()
        assert data[0]["total_orders"] == len(orders)

    def test_quarterly_filter_by_quarter(self, client):
        """Test that a quarter value is accepted as the period filter."""
        data = client.get("/api/reports/quarterly?month=Q2-2025").json()
        assert [q["quarter"] for q in data] == ["Q2-2025"]

    def test_quarterly_all_means_no_filter(self, client):
        """Test that 'all' behaves like no filter."""
        unfiltered = client.get("/api/reports/quarterly").json()
        with_all = client.get(
            "/api/reports/quarterly?warehouse=all&category=all&status=all&month=all"
        ).json()
        assert with_all == unfiltered

    def test_quarterly_no_matching_orders(self, client):
        """Test that filters matching nothing return an empty list."""
        response = client.get("/api/reports/quarterly?warehouse=Atlantis")
        assert response.status_code == 200
        assert response.json() == []


class TestMonthlyTrends:
    """Test suite for /api/reports/monthly-trends."""

    def test_get_monthly_trends(self, client):
        """Test getting monthly trends without filters."""
        response = client.get("/api/reports/monthly-trends")
        assert response.status_code == 200

        data = response.json()
        assert len(data) > 0
        for month in data:
            assert len(month["month"]) == 7
            assert month["order_count"] > 0
            assert month["delivered_count"] <= month["order_count"]

        months = [m["month"] for m in data]
        assert months == sorted(months)

    def test_monthly_totals_match_orders(self, client):
        """Test that monthly counts add up to the number of orders."""
        orders = client.get("/api/orders").json()
        data = client.get("/api/reports/monthly-trends").json()
        assert sum(m["order_count"] for m in data) == len(orders)

    def test_monthly_filter_by_warehouse(self, client):
        """Test that the warehouse filter limits the orders counted."""
        orders = client.get("/api/orders?warehouse=London").json()
        data = client.get("/api/reports/monthly-trends?warehouse=London").json()
        assert sum(m["order_count"] for m in data) == len(orders)

    def test_monthly_filter_by_month(self, client):
        """Test that a single month filter returns only that month."""
        data = client.get("/api/reports/monthly-trends?month=2025-05").json()
        assert [m["month"] for m in data] == ["2025-05"]

    def test_monthly_filter_by_quarter(self, client):
        """Test that a quarter filter returns only that quarter's months."""
        data = client.get("/api/reports/monthly-trends?month=Q1-2025").json()
        assert [m["month"] for m in data] == ["2025-01", "2025-02", "2025-03"]

    def test_monthly_revenue_matches_orders(self, client):
        """Test that filtered revenue equals the sum of the matching orders."""
        orders = client.get("/api/orders?status=Shipped").json()
        data = client.get("/api/reports/monthly-trends?status=Shipped").json()

        expected = sum(o["total_value"] for o in orders)
        assert abs(sum(m["revenue"] for m in data) - expected) < 0.01

    def test_monthly_no_matching_orders(self, client):
        """Test that filters matching nothing return an empty list."""
        data = client.get("/api/reports/monthly-trends?category=Nothing").json()
        assert data == []
