from pathlib import Path


def _live_gateway_service() -> str:
    render_config = Path("render.yaml").read_text(encoding="utf-8")
    marker = "    name: seldrune-live-gateway\n"
    assert marker in render_config
    service = render_config.split(marker, maxsplit=1)[1]
    return service.split("\ndatabases:", maxsplit=1)[0]


def test_live_gateway_render_health_check_uses_strict_readiness() -> None:
    service = _live_gateway_service()

    assert "    healthCheckPath: /readyz\n" in service
    assert "    healthCheckPath: /healthz\n" not in service
