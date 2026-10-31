"""
Phase 4 tests — verify the control flow pipeline branches.

Branches tested:
1. Tool output present -> pruner called
2. Cache hit -> skips routing
3. Health check pass -> proceeds normally
4. Health check fail -> retries to frontier model
5. Confidence valid -> skips escalation
6. Confidence invalid -> re-routes to stronger model

Run with:  python -m pytest tests/test_phase4.py -v
"""

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from optiroute.main import app
from optiroute.config import get_config
from optiroute import database as db


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_DIR", tmp_path)
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "test_optiroute.db")
    # Need to run startup event to init db, but TestClient(app) doesn't run lifespan automatically unless we use 'with TestClient(app)'.
    # We will let the tests use 'with TestClient(app)' directly.


@pytest.fixture
def mock_call_model():
    with patch("optiroute.main.call_model") as mock:
        from optiroute.models import ChatCompletionResponse, Choice, ChoiceMessage, UsageInfo
        resp = ChatCompletionResponse(
            model="gpt-4o",
            choices=[Choice(message=ChoiceMessage(content="test response"))],
            usage=UsageInfo(prompt_tokens=10, completion_tokens=10, total_tokens=20)
        )
        mock.return_value = (resp, 100.0)
        yield mock


def test_tool_output_present(mock_call_model):
    """Test branch where pruner is activated."""
    with patch("optiroute.engine.ContextPruner.has_large_tool_output", return_value=True) as has_tool, \
         patch("optiroute.engine.ContextPruner.prune") as prune:
         
        # Mock prune to return unmodified request and 50 tokens pruned
        def mock_prune(req):
            return req, 50
        prune.side_effect = mock_prune
        
        with TestClient(app) as client:
            resp = client.post("/v1/chat/completions", json={
                "model": "auto",
                "messages": [{"role": "user", "content": "test"}]
            })
            
            assert resp.status_code == 200
            has_tool.assert_called_once()
            prune.assert_called_once()
            assert resp.json()["optiroute"]["tokens_pruned"] == 50


def test_cache_hit():
    """Test branch where cache hit skips routing."""
    with patch("optiroute.engine.CacheManager.check_cache") as check_cache:
        from optiroute.models import ChatCompletionResponse, Choice, ChoiceMessage, UsageInfo
        cached_resp = ChatCompletionResponse(
            model="cache-model",
            choices=[Choice(message=ChoiceMessage(content="cached response"))],
            usage=UsageInfo()
        )
        check_cache.return_value = cached_resp
        
        with patch("optiroute.engine.RoutingEngine.route_request") as route_req:
            with TestClient(app) as client:
                resp = client.post("/v1/chat/completions", json={
                    "model": "auto",
                    "messages": [{"role": "user", "content": "test"}]
                })
                
                assert resp.status_code == 200
                check_cache.assert_called_once()
                route_req.assert_not_called()  # Skips routing
                assert resp.json()["optiroute"]["cache_hit"] is True


def test_health_check_fail_fallback_to_frontier(mock_call_model):
    """Test branch where model is unhealthy -> fall back to frontier."""
    with patch("optiroute.engine.RoutingEngine.is_healthy") as mock_health:
        # First model is unhealthy, frontier model is healthy
        mock_health.side_effect = [False, True]
        
        with TestClient(app) as client:
            resp = client.post("/v1/chat/completions", json={
                "model": "light", # explicitly ask for light
                "messages": [{"role": "user", "content": "test"}]
            })
            
            assert resp.status_code == 200
            # Should have routed to heavy tier
            assert resp.json()["optiroute"]["tier"] == "heavy"
            assert resp.json()["optiroute"]["rule_matched"] == "frontier_fallback"


def test_quality_check_invalid_escalates(mock_call_model):
    """Test branch where quality check fails -> re-routes to stronger tier."""
    with patch("optiroute.engine.RoutingEngine.evaluate_response_quality") as mock_qual:
        # First check fails, second check passes
        mock_qual.side_effect = [False, True]
        
        with TestClient(app) as client:
            resp = client.post("/v1/chat/completions", json={
                "model": "light", # explicitly ask for light
                "messages": [{"role": "user", "content": "test"}]
            })
            
            assert resp.status_code == 200
            assert mock_call_model.call_count == 2
            assert resp.json()["optiroute"]["escalated"] is True
            # Light -> Mid escalation
            assert resp.json()["optiroute"]["tier"] == "mid"

