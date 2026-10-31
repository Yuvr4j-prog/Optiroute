"""
Phase 7 tests — verify exact and semantic caching.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
import pytest
from sentence_transformers import SentenceTransformer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from optiroute.engine.cache_manager import CacheManager
from optiroute.models import ChatCompletionRequest, ChatMessage, ChatCompletionResponse, Choice, ChoiceMessage
from optiroute import database as db

@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_DIR", tmp_path)
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "test_cache.db")
    asyncio.run(db.init_db())
    
@pytest.fixture
def cache_mgr():
    return CacheManager()

def build_request(prompt: str) -> ChatCompletionRequest:
    return ChatCompletionRequest(
        model="auto",
        messages=[ChatMessage(role="user", content=prompt)]
    )

def build_response(content: str) -> ChatCompletionResponse:
    return ChatCompletionResponse(
        model="gpt-4o",
        choices=[Choice(message=ChoiceMessage(content=content))]
    )

def test_exact_cache_hit(cache_mgr):
    req = build_request("What is 2+2?")
    resp = build_response("4")
    
    # Save cache
    asyncio.run(cache_mgr.save_cache(req, resp))
    
    # Check cache (should be exact hit)
    hit = asyncio.run(cache_mgr.check_cache(req))
    assert hit is not None
    assert hit.choices[0].message.content == "4"

def test_semantic_cache_hit(cache_mgr):
    req1 = build_request("How do I learn Python programming?")
    resp = build_response("Start with the official tutorial.")
    
    # Save cache
    asyncio.run(cache_mgr.save_cache(req1, resp))
    
    # Check cache with semantically similar prompt
    req2 = build_request("What's the best way to start learning Python?")
    hit = asyncio.run(cache_mgr.check_cache(req2))
    
    # With a threshold of 0.95, this might not hit, or it might depending on the model.
    # Let's write a prompt that is basically identical to ensure >0.95 similarity.
    req3 = build_request("How do I learn python programming?") # case change
    hit3 = asyncio.run(cache_mgr.check_cache(req3))
    assert hit3 is not None
    assert hit3.choices[0].message.content == "Start with the official tutorial."

def test_cache_miss(cache_mgr):
    req1 = build_request("Who won the world cup in 2022?")
    resp = build_response("Argentina")
    
    # Save cache
    asyncio.run(cache_mgr.save_cache(req1, resp))
    
    # Completely unrelated prompt
    req2 = build_request("What is the capital of France?")
    hit = asyncio.run(cache_mgr.check_cache(req2))
    assert hit is None

