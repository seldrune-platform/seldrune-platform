from backend.app.api.routes.status import _release_provenance


def test_release_provenance_prefers_seldrune(monkeypatch):
    monkeypatch.setattr(
        "backend.app.api.routes.status.settings.release_sha",
        "release-123",
    )
    monkeypatch.setenv("RENDER_GIT_COMMIT", "render-456")
    assert _release_provenance() == {
        "sha": "release-123",
        "source": "seldrune",
    }


def test_release_provenance_uses_render_commit(monkeypatch):
    monkeypatch.setattr(
        "backend.app.api.routes.status.settings.release_sha",
        None,
    )
    monkeypatch.setenv("RENDER_GIT_COMMIT", "render-456")
    assert _release_provenance() == {
        "sha": "render-456",
        "source": "render",
    }
