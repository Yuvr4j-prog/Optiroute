"""
Phase 0 tests — verify the basic pass-through proxy works.

These tests validate:
1. Config loading and validation
2. Router produces correct decisions for different model/tier inputs
3. End-to-end request round-trip (requires OPENAI_API_KEY in environment)

Run with:  python -m pytest tests/ -v
Or:        python tests/test_phase0.py  (for the live round-trip test)
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Ensure the project root is on the path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from optiroute.config import load_config, AppConfig
from optiroute.models import ChatCompletionRequest, ChatMessage
from optiroute.engine import RoutingEngine


def test_config_loads():
    """Config file loads and validates successfully."""
    config = load_config()
    assert isinstance(config, AppConfig)
    assert "light" in config.tiers
    assert "mid" in config.tiers
    assert "heavy" in config.tiers
    print("✓ Config loads successfully")
    print(f"  Tiers: {list(config.tiers.keys())}")
    for name, tier in config.tiers.items():
        print(f"  {name}: {[m.id for m in tier.models]}")


def test_tier_order():
    """Tier escalation order is light → mid → heavy."""
    config = load_config()
    assert config.tier_order == ["light", "mid", "heavy"]
    assert config.next_tier("light") == "mid"
    assert config.next_tier("mid") == "heavy"
    assert config.next_tier("heavy") is None
    print("✓ Tier order and escalation path correct")


def test_router_default():
    """model='auto' routes to the default tier (light)."""
    config = load_config()
    req = ChatCompletionRequest(
        model="auto",
        messages=[ChatMessage(role="user", content="Hello")],
    )
    router = RoutingEngine(config); model, decision = router.route_request(req)
    assert decision.selected_tier == "light"
    assert model.id == "gpt-4o-mini"
    assert "default_tier" in decision.rule_matched
    print(f"✓ model='auto' → tier={decision.selected_tier}, model={model.id}")


def test_router_explicit_tier():
    """model='heavy' routes to the heavy tier."""
    config = load_config()
    req = ChatCompletionRequest(
        model="heavy",
        messages=[ChatMessage(role="user", content="Explain quantum gravity")],
    )
    router = RoutingEngine(config); model, decision = router.route_request(req)
    assert decision.selected_tier == "heavy"
    assert model.id == "gpt-4.1"
    print(f"✓ model='heavy' → tier={decision.selected_tier}, model={model.id}")


def test_router_explicit_model():
    """model='gpt-4o' routes directly to that model."""
    config = load_config()
    req = ChatCompletionRequest(
        model="gpt-4o",
        messages=[ChatMessage(role="user", content="Hello")],
    )
    router = RoutingEngine(config); model, decision = router.route_request(req)
    assert model.id == "gpt-4o"
    assert decision.selected_tier == "mid"
    assert "explicit_model" in decision.rule_matched
    print(f"✓ model='gpt-4o' → tier={decision.selected_tier}, model={model.id}")


def test_router_tier_override():
    """tier_override field forces a specific tier."""
    config = load_config()
    req = ChatCompletionRequest(
        model="auto",
        messages=[ChatMessage(role="user", content="Hello")],
        tier_override="heavy",
    )
    router = RoutingEngine(config); model, decision = router.route_request(req)
    assert decision.selected_tier == "heavy"
    assert "tier_override" in decision.rule_matched
    print(f"✓ tier_override='heavy' → tier={decision.selected_tier}, model={model.id}")


async def test_live_round_trip():
    """
    End-to-end test: send a real request through the proxy to OpenAI.
    Requires OPENAI_API_KEY to be set.
    """
    if not os.environ.get("OPENAI_API_KEY"):
        print("⚠ Skipping live round-trip test (OPENAI_API_KEY not set)")
        return

    from optiroute.proxy import call_model
    from optiroute.engine import ObservabilityEngine

    config = load_config()
    req = ChatCompletionRequest(
        model="auto",
        messages=[ChatMessage(role="user", content="Say 'OptiRoute works!' and nothing else.")],
        max_tokens=20,
    )

    model_config, decision = route_request(req, config)
    print(f"\n--- Live Round-Trip Test ---")
    print(f"  Routing: tier={decision.selected_tier}, model={model_config.id}")

    response, latency_ms = await call_model(model_config, req)
    obs = ObservabilityEngine(); cost = obs.estimate_cost(model_config, response.usage)

    content = response.choices[0].message.content if response.choices else "(no content)"
    print(f"  Response: {content}")
    print(f"  Tokens: {response.usage.total_tokens}")
    print(f"  Cost: ${cost:.6f}")
    print(f"  Latency: {latency_ms:.0f}ms")
    print(f"✓ Live round-trip successful!")


def main():
    """Run all Phase 0 tests."""
    print("=" * 60)
    print("OptiRoute — Phase 0 Tests")
    print("=" * 60)

    # Unit tests (no API key needed)
    test_config_loads()
    test_tier_order()
    test_router_default()
    test_router_explicit_tier()
    test_router_explicit_model()
    test_router_tier_override()

    # Live test (needs API key)
    print()
    asyncio.run(test_live_round_trip())

    print()
    print("=" * 60)
    print("All Phase 0 tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    main()

