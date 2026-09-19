from services.supreme.capabilities import ALIEN_CAPABILITIES, CapabilityState, capability


def test_capabilities_have_unique_keys_and_metrics():
    keys = [item.key for item in ALIEN_CAPABILITIES]
    assert len(keys) == len(set(keys))
    assert all(item.metric for item in ALIEN_CAPABILITIES)


def test_research_targets_are_not_predeclared_as_verified():
    assert all(item.state is CapabilityState.CONCEPT for item in ALIEN_CAPABILITIES)


def test_capability_lookup():
    item = capability("proof_mesh")
    assert item.metric == "verified_error_escape_rate"
