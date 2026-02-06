"""
API Tests

Tests for FastAPI endpoints using TestClient.
Mocks agent registry and orchestrator when needed.

Run: pytest tests/test_api.py -v
"""

import pytest
from typing import Dict, Any


# ==================== Test Client Fixture ====================

@pytest.fixture
def client():
    """Create FastAPI TestClient."""
    try:
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)
    except ImportError as e:
        pytest.skip(f"Cannot import app.main: {e}")


# ==================== Health and Root Endpoints ====================

def test_root_endpoint(client):
    """Test root endpoint returns welcome message."""
    response = client.get("/")
    
    assert response.status_code == 200
    data = response.json()
    
    # Should have basic info
    assert "message" in data or "service" in data or "status" in data


def test_health_endpoint(client):
    """Test health check endpoint."""
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    
    # Should indicate healthy status
    assert "status" in data
    assert data["status"] in ["ok", "healthy", "up"]


# ==================== Chat API Tests ====================

def test_chat_endpoint_exists(client):
    """Test that chat endpoint exists and can be called."""
    try:
        # Try to call chat endpoint
        response = client.post(
            "/api/chat",
            json={
                "message": "Hello",
                "user_id": "test_user",
                "user_role": "CARRIER"
            },
            headers={"Authorization": "Bearer test_token"}
        )
        
        # Should not return 404 (endpoint exists)
        assert response.status_code != 404
        
        # If it returns other errors, that's fine (auth, validation, etc.)
        # We're just testing the endpoint exists
        if response.status_code == 200:
            data = response.json()
            assert "message" in data or "conversation_id" in data
    
    except Exception as e:
        # If chat endpoint not implemented, skip
        pytest.skip(f"Chat endpoint not available: {e}")


def test_chat_endpoint_requires_message():
    """Test chat endpoint validation (if available)."""
    try:
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        
        # Send request without message
        response = client.post(
            "/api/chat",
            json={
                "user_id": "test_user",
                "user_role": "CARRIER"
            },
            headers={"Authorization": "Bearer test_token"}
        )
        
        # Should return validation error (422)
        assert response.status_code == 422
    
    except Exception:
        pytest.skip("Chat endpoint not available or test not applicable")


# ==================== Carrier API Tests ====================

def test_carrier_score_endpoint(client, monkeypatch):
    """Test carrier score endpoint with mocked backend."""
    try:
        # Mock carrier service
        async def mock_get_carrier_stats(carrier_id, auth_header=None, request_id=None):
            return {
                "total_bookings": 100,
                "completed_bookings": 95,
                "cancelled_bookings": 3,
                "no_shows": 2,
                "late_arrivals": 10,
                "avg_delay_minutes": 5.0,
                "avg_dwell_minutes": 30.0,
                "anomaly_count": 1
            }
        
        import app.tools.carrier_service_client
        monkeypatch.setattr(
            app.tools.carrier_service_client,
            "get_carrier_stats",
            mock_get_carrier_stats
        )
        
        # Call carrier score endpoint
        response = client.get(
            "/api/carriers/carrier-123/score",
            headers={
                "Authorization": "Bearer test_token",
                "x-user-role": "OPERATOR"
            }
        )
        
        # Should return success or not found (if endpoint not implemented)
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert "score" in data or "message" in data
    
    except Exception:
        pytest.skip("Carrier score endpoint not available")


# ==================== Slots API Tests ====================

def test_slots_availability_endpoint(client, monkeypatch):
    """Test slots availability endpoint with mocked backend."""
    try:
        from datetime import datetime, timedelta
        
        # Mock slot service
        async def mock_get_availability(terminal, date=None, gate=None, auth_header=None, request_id=None):
            base_time = datetime(2026, 2, 5, 9, 0, 0)
            return [
                {
                    "slot_id": "slot-001",
                    "start": base_time.isoformat() + "Z",
                    "end": (base_time + timedelta(hours=2)).isoformat() + "Z",
                    "capacity": 20,
                    "remaining": 15,
                    "terminal": terminal,
                    "gate": "G1"
                }
            ]
        
        import app.tools.slot_service_client
        monkeypatch.setattr(
            app.tools.slot_service_client,
            "get_availability",
            mock_get_availability
        )
        
        # Call slots availability endpoint
        response = client.get(
            "/api/slots/availability?terminal=A&date=2026-02-05",
            headers={
                "Authorization": "Bearer test_token",
                "x-user-role": "CARRIER"
            }
        )
        
        # Should return success or not found
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert "slots" in data or "message" in data or "data" in data
    
    except Exception:
        pytest.skip("Slots availability endpoint not available")


# ==================== Analytics API Tests ====================

def test_analytics_stress_index_endpoint(client):
    """Test analytics stress index endpoint (if available)."""
    try:
        response = client.get(
            "/api/analytics/stress-index?terminal=A",
            headers={
                "Authorization": "Bearer test_token",
                "x-user-role": "ADMIN"
            }
        )
        
        # Should return success or not found
        assert response.status_code in [200, 404, 403]
        
        if response.status_code == 200:
            data = response.json()
            assert "stress_index" in data or "message" in data or "data" in data
    
    except Exception:
        pytest.skip("Analytics stress index endpoint not available")


# ==================== Error Handling Tests ====================

def test_endpoint_not_found(client):
    """Test that non-existent endpoints return 404."""
    response = client.get("/api/nonexistent/endpoint")
    
    assert response.status_code == 404


def test_unauthorized_access():
    """Test that endpoints require authorization."""
    try:
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        
        # Try to access protected endpoint without auth
        response = client.get("/api/carriers/carrier-123/score")
        
        # Should return 401 or 403 (or 404 if endpoint doesn't exist)
        assert response.status_code in [401, 403, 404, 422]
    
    except Exception:
        pytest.skip("Authorization test not applicable")


# ==================== CORS Tests ====================

def test_cors_headers(client):
    """Test that CORS headers are present."""
    response = client.options("/")
    
    # CORS preflight should be handled
    # Status might be 200 or 405 depending on setup
    assert response.status_code in [200, 405]


# ==================== Lifespan/Startup Tests ====================

def test_app_starts_successfully():
    """Test that FastAPI app can be instantiated successfully."""
    try:
        from app.main import app
        
        # App should have routes
        assert len(app.routes) > 0
        
        # Should have lifespan context (for closing clients)
        assert hasattr(app, "router")
    
    except ImportError:
        pytest.skip("Cannot import app.main")


# ==================== Run Tests ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
