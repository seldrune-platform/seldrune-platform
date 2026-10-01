from backend.app.api.routes.mcp_bridge import TOOLS


def test_mcp_catalog_exposes_seldrune_agents_and_astra_bridge() -> None:
    tools = {tool["name"]: tool for tool in TOOLS}

    assert "list_seldrune_agents" in tools
    assert "ask_seldrune_ai" in tools

    agent_tool = tools["list_seldrune_agents"]
    assert agent_tool["annotations"]["readOnlyHint"] is True
    assert agent_tool["annotations"]["idempotentHint"] is True

    astra_tool = tools["ask_seldrune_ai"]
    assert astra_tool["annotations"]["readOnlyHint"] is False
    assert astra_tool["annotations"]["destructiveHint"] is False
    assert astra_tool["annotations"]["idempotentHint"] is False
    assert astra_tool["inputSchema"]["required"] == ["organization_id", "message"]
