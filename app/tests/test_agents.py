"""
Agent Tests

Tests for agent logic with mocked backend services.
Uses pytest monkeypatch to mock HTTP clients.

Run: pytest tests/test_agents.py -v
"""

import pytest
from datetime import datetime, timedelta
from typing import Dict, Any, Optional


# ==================== Fixtures ====================

@pytest.fixture
def context_base():
    """Base context for agent execution."""
    return {
        "trace_id": "trace123456",
        "auth_header": "Bearer test_token",
        "user_role": "OPERATOR",
        "user_id": "user123",
        "entities": {},
        "message": "Test message"
    }


@pytest.fixture
def mock_carrier_stats():
    """Mock carrier statistics response."""
    return {
        "total_bookings": 100,
        "completed_bookings": 95,
        "cancelled_bookings": 3,
        "no_shows": 2,
        "late_arrivals": 10,
        "avg_delay_minutes": 5.0,
        "avg_dwell_minutes": 30.0,
        "anomaly_count": 1,
        "last_activity_at": "2026-02-04T10:00:00Z"
    }


@pytest.fixture
def mock_slot_availability():
    """Mock slot availability response."""
    base_time = datetime(2026, 2, 5, 9, 0, 0)
    
    return [
        {
            "slot_id": "slot-001",
            "start": base_time.isoformat() + "Z",
            "end": (base_time + timedelta(hours=2)).isoformat() + "Z",
            "capacity": 20,
            "remaining": 15,
            "terminal": "A",
            "gate": "G1"
        },
        {
            "slot_id": "slot-002",
            "start": (base_time + timedelta(hours=3)).isoformat() + "Z",
            "end": (base_time + timedelta(hours=5)).isoformat() + "Z",
            "capacity": 15,
            "remaining": 10,
            "terminal": "A",
            "gate": "G2"
        }
    ]


# ==================== BookingAgent Tests ====================

@pytest.mark.asyncio
async def test_booking_agent_success(context_base, monkeypatch):
    """Test BookingAgent with valid booking reference."""
    from app.agents.booking_agent import BookingAgent
    
    # Mock booking service response
    async def mock_get_booking_status(booking_ref, auth_header=None, request_id=None):
        return {
            "booking_ref": booking_ref,
            "status": "confirmed",
            "carrier_id": "carrier-123",
            "terminal": "A",
            "gate": "G1",
            "slot_start": "2026-02-05T09:00:00Z",
            "slot_end": "2026-02-05T11:00:00Z"
        }
    
    import app.tools.booking_service_client
    monkeypatch.setattr(
        app.tools.booking_service_client,
        "get_booking_status",
        mock_get_booking_status
    )
    
    # Execute agent
    context = {**context_base, "entities": {"booking_ref": "BK-123"}}
    agent = BookingAgent()
    result = await agent.execute(context)
    
    # Validate response structure
    assert "message" in result
    assert "data" in result
    assert "proofs" in result
    
    # Validate data contains booking info
    assert result["data"]["booking_ref"] == "BK-123"
    assert result["data"]["status"] == "confirmed"


@pytest.mark.asyncio
async def test_booking_agent_missing_booking_ref(context_base):
    """Test BookingAgent with missing booking_ref (validation error)."""
    from app.agents.booking_agent import BookingAgent
    
    # Execute agent without booking_ref
    context = {**context_base, "entities": {}}
    agent = BookingAgent()
    result = await agent.execute(context)
    
    # Should return validation error
    assert "message" in result
    assert "data" in result
    
    # Data should contain error information
    assert "error" in result["data"] or "error_type" in result["data"]


@pytest.mark.asyncio
async def test_booking_agent_missing_auth(context_base):
    """Test BookingAgent without auth_header (unauthorized error)."""
    from app.agents.booking_agent import BookingAgent
    
    # Execute agent without auth
    context = {
        **context_base,
        "auth_header": None,
        "entities": {"booking_ref": "BK-123"}
    }
    agent = BookingAgent()
    result = await agent.execute(context)
    
    # Should return unauthorized error
    assert "message" in result
    assert "data" in result
    
    # Should indicate auth error
    data = result["data"]
    assert "error" in data or "error_type" in data


# ==================== CarrierScoreAgent Tests ====================

@pytest.mark.asyncio
async def test_carrier_score_agent_success(context_base, mock_carrier_stats, monkeypatch):
    """Test CarrierScoreAgent with mocked carrier service."""
    from app.agents.carrier_score_agent import CarrierScoreAgent
    
    # Mock carrier service client
    async def mock_get_carrier_stats(carrier_id, auth_header=None, request_id=None):
        return mock_carrier_stats
    
    import app.tools.carrier_service_client
    monkeypatch.setattr(
        app.tools.carrier_service_client,
        "get_carrier_stats",
        mock_get_carrier_stats
    )
    
    # Execute agent
    context = {**context_base, "entities": {"carrier_id": "carrier-123"}}
    agent = CarrierScoreAgent()
    result = await agent.execute(context)
    
    # Validate response
    assert "message" in result
    assert "data" in result
    assert "proofs" in result
    
    # Validate score data
    data = result["data"]
    assert "carrier_id" in data
    assert "score" in data
    assert "tier" in data
    assert "confidence" in data
    
    # Score should be reasonable for good stats
    assert 0 <= data["score"] <= 100
    assert data["tier"] in ["A", "B", "C", "D"]


@pytest.mark.asyncio
async def test_carrier_score_agent_mvp_fallback(context_base, monkeypatch):
    """Test CarrierScoreAgent MVP fallback when carrier service returns 404."""
    from app.agents.carrier_score_agent import CarrierScoreAgent
    from fastapi import HTTPException
    
    # Mock carrier service to raise 404
    async def mock_get_carrier_stats_404(carrier_id, auth_header=None, request_id=None):
        raise HTTPException(status_code=404, detail="Carrier not found")
    
    # Mock booking service for fallback
    class MockAsyncClient:
        async def get(self, url, headers=None, params=None):
            class MockResponse:
                status_code = 200
                def json(self):
                    return {
                        "bookings": [
                            {"status": "completed"},
                            {"status": "completed"},
                            {"status": "cancelled"}
                        ]
                    }
                def raise_for_status(self):
                    pass
            return MockResponse()
        
        @property
        def is_closed(self):
            return False
    
    def mock_get_client():
        return MockAsyncClient()
    
    import app.tools.carrier_service_client
    import app.tools.booking_service_client
    
    monkeypatch.setattr(
        app.tools.carrier_service_client,
        "get_carrier_stats",
        mock_get_carrier_stats_404
    )
    monkeypatch.setattr(
        app.tools.booking_service_client,
        "get_client",
        mock_get_client
    )
    
    # Execute agent
    context = {**context_base, "entities": {"carrier_id": "carrier-123"}}
    agent = CarrierScoreAgent()
    result = await agent.execute(context)
    
    # Should still return a response (MVP fallback)
    assert "message" in result
    assert "data" in result
    
    # May include data_quality info
    if "data_quality" in result.get("proofs", {}):
        assert result["proofs"]["data_quality"] in ["mvp", "fallback"]


# ==================== SlotAgent Tests ====================

@pytest.mark.asyncio
async def test_slot_agent_availability(context_base, mock_slot_availability, monkeypatch):
    """Test SlotAgent availability request."""
    from app.agents.slot_agent import SlotAgent
    
    # Mock slot service
    async def mock_get_availability(terminal, date=None, gate=None, auth_header=None, request_id=None):
        return mock_slot_availability
    
    import app.tools.slot_service_client
    monkeypatch.setattr(
        app.tools.slot_service_client,
        "get_availability",
        mock_get_availability
    )
    
    # Execute agent for availability
    context = {
        **context_base,
        "entities": {
            "terminal": "A",
            "date": "2026-02-05",
            "intent": "check_availability"
        }
    }
    agent = SlotAgent()
    result = await agent.execute(context)
    
    # Validate response
    assert "message" in result
    assert "data" in result
    
    # Should have slot data
    data = result["data"]
    assert "terminal" in data or "slots" in data or "availability" in data


@pytest.mark.asyncio
async def test_slot_agent_recommendation(context_base, mock_slot_availability, mock_carrier_stats, monkeypatch):
    """Test SlotAgent recommendation request."""
    from app.agents.slot_agent import SlotAgent
    
    # Mock slot service
    async def mock_get_availability(terminal, date=None, gate=None, auth_header=None, request_id=None):
        return mock_slot_availability
    
    # Mock carrier service for score
    async def mock_get_carrier_stats(carrier_id, auth_header=None, request_id=None):
        return mock_carrier_stats
    
    import app.tools.slot_service_client
    import app.tools.carrier_service_client
    
    monkeypatch.setattr(
        app.tools.slot_service_client,
        "get_availability",
        mock_get_availability
    )
    monkeypatch.setattr(
        app.tools.carrier_service_client,
        "get_carrier_stats",
        mock_get_carrier_stats
    )
    
    # Execute agent for recommendations
    context = {
        **context_base,
        "entities": {
            "terminal": "A",
            "date": "2026-02-05",
            "carrier_id": "carrier-123",
            "intent": "recommend_slot"
        },
        "user_role": "CARRIER"
    }
    agent = SlotAgent()
    result = await agent.execute(context)
    
    # Validate response
    assert "message" in result
    assert "data" in result
    
    # Should have recommendations
    data = result["data"]
    assert "recommended" in data or "slots" in data


@pytest.mark.asyncio
async def test_slot_agent_service_unavailable(context_base, monkeypatch):
    """Test SlotAgent when slot service is unavailable."""
    from app.agents.slot_agent import SlotAgent
    from fastapi import HTTPException
    
    # Mock slot service to raise 503
    async def mock_get_availability_503(terminal, date=None, gate=None, auth_header=None, request_id=None):
        raise HTTPException(status_code=503, detail="Service unavailable")
    
    import app.tools.slot_service_client
    monkeypatch.setattr(
        app.tools.slot_service_client,
        "get_availability",
        mock_get_availability_503
    )
    
    # Execute agent
    context = {
        **context_base,
        "entities": {
            "terminal": "A",
            "date": "2026-02-05"
        }
    }
    agent = SlotAgent()
    result = await agent.execute(context)
    
    # Should return error response
    assert "message" in result
    assert "data" in result
    
    # Should indicate service error
    data = result["data"]
    assert "error" in data or "error_type" in data


# ==================== Run Tests ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
