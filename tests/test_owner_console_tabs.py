from pathlib import Path
import re
import xml.etree.ElementTree as ET

WEB = Path("backend/app/web")


def test_owner_console_uses_single_owner_portal_shell():
    html = (WEB / "index.html").read_text()
    assert "/console-assets/console-cosmic-tabs.css" in html
    assert "/console-assets/console-cosmic-tabs.js" in html
    assert "/console-assets/console-agents.css" in html
    assert "/console-assets/console-agents.js" in html
    assert "/console-assets/console-portal.css" in html
    assert "/console-assets/console-portal-settings.js" in html
    assert "/console-assets/seldrune-gpt-studio.css" in html
    assert "/console-assets/console-clean.css" in html
    assert "/console-assets/console-nexus-arena.css" not in html
    assert "/console-assets/console-nexus-arena.js" not in html
    assert "/console-assets/console-connections.js" in html

    # Engineering/version presentation layers stay out of the normal owner portal.
    assert "/console-assets/console-xenobiotic.css" not in html
    assert "/console-assets/console-xenobiotic.js" not in html
    assert "/console-assets/console-v100.css" not in html
    assert "/console-assets/console-v100.js" not in html
    assert "/console-assets/console-tabs.css" not in html
    assert "/console-assets/console-tabs.js" not in html


def test_gpt_operator_remains_truth_gated_and_multimodal():
    html = (WEB / "index.html").read_text()
    assert 'id="seldrune-gpt-execute"' not in html
    assert "Run with Seldrune" not in html
    assert "Send to Seldrune" in html
    assert "confirmation-gated" in html
    assert 'id="seldrune-gpt-model"' in html
    assert 'id="seldrune-gpt-files"' in html
    assert 'id="seldrune-gpt-dropzone"' in html
    assert 'id="seldrune-gpt-attachments"' in html
    assert 'id="seldrune-gpt-mode"' in html
    assert 'id="seldrune-gpt-capabilities"' in html
    assert 'id="seldrune-gpt-open-tools"' in html
    assert "Seldrune AI · text chat" in html
    assert "Chat replies are text." in html


def test_creation_forge_routes_typed_projects_through_the_cognitive_operator():
    html = (WEB / "index.html").read_text()
    script = (WEB / "seldrune-gpt.js").read_text()
    styles = (WEB / "seldrune-gpt-studio.css").read_text()

    for mode in ("song", "video"):
        assert f'data-creation-mode="{mode}"' in html
        assert f"    {mode}: {{" in script
    for hidden_mode in ("app", "game", "visual"):
        assert f'data-creation-mode="{hidden_mode}"' not in html
    for mode in ("app", "game", "visual"):
        assert f"    {mode}: {{" in script
    assert 'id="seldrune-gpt-creation-status"' in html
    assert "buildCreativeOrder(request)" in script
    assert '/console-assets/seldrune-media.js' in script
    assert 'data-default="true"' in script
    assert "authenticated Seldrune origin" in script
    assert "never silently use raw device media as a fallback" in script
    assert "When building or cloning a camera or microphone app" in script
    assert "order: buildCreativeOrder(request)" in script
    assert "cannot render audio" in script
    assert "cannot render video" in script
    assert "no rendered media file was produced" in script
    assert ".gpt-creation-forge" in styles


def test_creation_forge_app_intent_precedes_media_keyword_classification():
    script = (WEB / "seldrune-gpt.js").read_text()
    classifier = script.split(
        "function classifyOutputKind(request, mode = creationMode) {", 1
    )[1].split("\n  function titleFromRequest", 1)[0]
    game = classifier.index(r"/\b(game|playable|gameplay|level design)\b/.test(text)")
    app_intent = classifier.index("if (appIntent) return 'app';")
    song = classifier.index(r"/\b(song|music|lyrics|soundtrack|audio)\b/.test(text)")
    video = classifier.index(r"/\b(video|film|movie|clip|storyboard)\b/.test(text)")
    visual = classifier.index(
        r"/\b(image|illustration|picture|visual|poster|artwork|3d scene|3d model)\b/.test(text)"
    )
    assert game < app_intent < song
    assert app_intent < video
    assert app_intent < visual

    media_pattern = re.search(
        r"const mediaForExistingApp = /(.+)/\.test\(text\);", classifier
    )
    app_pattern = re.search(
        r"const appIntent = /(.*)/\.test\(text\) && !mediaForExistingApp;", classifier
    )
    assert media_pattern and app_pattern
    media_for_app = re.compile(media_pattern.group(1), re.IGNORECASE)
    app_terms = re.compile(app_pattern.group(1), re.IGNORECASE)
    def is_app_intent(value):
        return bool(app_terms.search(value) and not media_for_app.search(value))

    assert is_app_intent("Build a video chat app")
    assert not is_app_intent("Create a promotional video for my app")
    assert not is_app_intent("Write a video script")



def test_portal_controller_defines_owner_workspaces_and_fixed_home():
    js = (WEB / "console-cosmic-tabs.js").read_text()
    for workspace in (
        "home",
        "operator",
        "outputs",
        "coding",
        "operations",
        "media",
        "intelligence",
        "settings",
        "connections",
        "sense",
    ):
        assert f'["{workspace}",' in js
    assert "AETHELION INTELLIGENCE FOUNDRY" in js
    assert "seldrune:workspace-change" in js
    assert "portal-quick-orders" not in js
    assert "Ask Seldrune" in js
    for label in (
        "HOME", "AI CHAT", "OUTPUTS", "CODING LAB",
        "WORKSPACE", "MEDIA", "SYSTEM", "CONNECT", "SENSE", "CONTACT",
    ):
        assert label in js
    assert 'move("#seldrune-gpt", "operator")' in js
    assert 'move("#command", "operator")' not in js
    assert 'document.querySelector("#command")?.remove()' in js
    assert 'move("#cognitive-mission", "operations")' in js
    assert 'move("#sti-runtime", "operations")' in js
    assert 'move("#face-v01-mission", "media")' in js
    assert 'move("#tool-control", "connections")' in js
    assert 'grid("outputs")?.append(outputLibrary)' in js
    assert 'grid("coding")?.append(codingLab)' in js
    assert 'aria-labelledby", button.id' in js
    assert 'panel.hidden = panelId !== id' in js
    assert 'event.key === "Home"' in js
    assert 'portalSettings.id = "portal-settings"' in js
    assert 'grid("settings")?.append(portalSettings)' in js
    assert '["contact", "CONTACT", "✉"]' in js
    assert "PRIMARY_WORKSPACES" in js
    assert 'workspace: "home", depth: 0' in js
    assert 'activate("home", {historyMode: "none", scroll: false})' in js
    assert "seldrune.portal.lastWorkspace" not in js


def test_portal_settings_are_browser_scoped_and_home_is_locked():
    js = (WEB / "console-portal-settings.js").read_text()
    assert "seldrune.portal.theme" in js
    assert "seldrune.portal.density" in js
    assert "seldrune.portal.motion" in js
    assert "seldrune.portal.defaultWorkspace" not in js
    assert "Fixed landing page" in js
    assert "Home · Locked" in js
    assert "Preferences are stored in this browser only." in js


def test_owner_portal_hides_legacy_navigation_shell():
    css = (WEB / "console-portal.css").read_text()
    assert "body.owner-portal #console-view>aside" in css
    assert "display:none!important" in css
    assert "header:not(.owner-portal-bar)" in css
    assert "grid-template-columns:minmax(0,1fr)" in css


def test_portal_navigation_uses_browser_history_inside_console():
    js = (WEB / "console-cosmic-tabs.js").read_text()
    assert 'id="portal-back-button"' in js
    assert "history.pushState(" in js
    assert 'window.addEventListener("popstate"' in js
    assert 'workspace: "home", depth: 0' in js
    assert 'activate(state.workspace, {historyMode: "none", scroll: false})' in js
    assert 'backButton?.addEventListener("click"' in js
    assert "history.back()" in js
    assert 'window.addEventListener("hashchange"' not in js


def test_every_owner_workspace_uses_portal_visual_system():
    css = (WEB / "console-portal.css").read_text()
    for selector in (
        '#portal-panel-operator #seldrune-gpt',
        '#portal-panel-outputs #seldrune-output-library',
        '#portal-panel-coding #seldrune-coding-lab',
        '#portal-panel-operations #cognitive-mission',
        '#portal-panel-operations #sti-runtime',
        '#portal-panel-media #face-v01-mission',
        '#portal-panel-media #liveshift-mission',
        '#portal-panel-intelligence .agent-observatory',
        '#portal-panel-intelligence .audit-center',
        '#portal-panel-connections #tool-control',
        '#portal-panel-settings #portal-settings',
        '#portal-panel-intelligence .governance-policy',
        '#portal-panel-intelligence #action-inbox',
    ):
        assert selector in css
    assert "FULL WORKSPACE REDESIGN" in css
    assert ".owner-back-button" in css


def test_outputs_library_persists_downloadable_files_and_lab_is_provider_truthful():
    js = (WEB / "seldrune-gpt.js").read_text()
    portal = (WEB / "console-cosmic-tabs.js").read_text()
    assert "seldrune-output-library" in js
    assert "window.indexedDB.open('seldrune-output-library', 1)" in js
    assert "Download file" in js
    assert "seldrune:outputs-changed" in js
    assert "no rendered media file was produced" in js
    assert "Seldrune RapidBuild Loop" in js
    for provider in ("github", "circleci", "railway"):
        assert f'data-provider="{provider}"' in portal
    assert "Open verified run evidence" in js


def test_gpt_pdf_editor_is_single_ai_prompt_flow():
    html = (WEB / "index.html").read_text()
    script = (WEB / "seldrune-gpt.js").read_text()
    styles = (WEB / "seldrune-gpt-studio.css").read_text()

    assert 'id="seldrune-gpt-pdf-edit"' not in html
    assert "AI PDF Editor" in html
    assert "no coordinates or manual edit tools" in html
    assert "async function runAiPdfEdit" in script
    assert "pdfAttachments.length === 1 && attachments.length === 1" in script
    assert "await runAiPdfEdit(message, pdfAttachments[0])" in script
    assert "AI Edit PDF" in script
    assert ".gpt-mode-pill.active" in styles
    assert ".gpt-dropzone.ai-pdf-mode" in styles


def test_agent_workspace_executes_assigned_work_and_records_retries():
    html = (WEB / "index.html").read_text()
    script = (WEB / "console-agents.js").read_text()
    styles = (WEB / "console-agents.css").read_text()

    assert "/console-assets/console-agents.js" in html
    assert 'root.id = "agent-task-console";' in script
    assert 'api("/agents")' in script
    assert 'api("/tasks")' in script
    assert '"/execute"' in script
    assert '"/assign"' in script
    assert "retry_of_task_id" in script
    assert "MAX_VISIBLE_TASKS = 10" in script
    assert "agent-task-metrics" in styles
    assert "@media (max-width: 620px)" in styles


def test_nexus_duel_and_observatory_use_measured_system_data():
    svg = WEB / "nexus-alien-predator.svg"
    ET.parse(svg)

    script = (WEB / "console-nexus-arena.js").read_text()
    styles = (WEB / "console-nexus-arena.css").read_text()

    assert 'document.querySelector("#portal-panel-home")' in script
    assert 'api("/agents")' in script
    assert 'api("/tasks")' in script
    assert 'readMetric("sti-verified")' in script
    assert "nexus-alien-predator.svg" in script
    assert "failedTasks" in script
    assert "CONFIGURATION NEEDED" in script
    assert "No system state was inferred from missing data." in script
    assert "@media (max-width: 560px)" in styles
    assert "@media (prefers-reduced-motion: reduce)" in styles


def test_sense_console_is_owner_only_surface_and_provider_status_is_truthful():
    html = (WEB / "index.html").read_text()
    script = (WEB / "console-system-sense.js").read_text()
    styles = (WEB / "console-cosmic-tabs.css").read_text()

    assert "/console-assets/console-system-sense.js" in html
    assert 'id="seldrune-gpt-provider"' in html
    assert "#portal-panel-sense" in styles
    assert 'api("/sense/system")' in script
    assert 'api("/sense/owner-continuity")' in script
    assert "checked on request" in script
    assert "To clear it, empty the field and save." in script


def test_connections_workspace_unifies_verified_services_and_ai_keys():
    html = (WEB / "index.html").read_text()
    script = (WEB / "console-connections.js").read_text()
    styles = (WEB / "console-cosmic-tabs.css").read_text()
    portal = (WEB / "console-cosmic-tabs.js").read_text()

    assert "/console-assets/console-connections.js" in html
    assert "GitHub token or GitHub App credential" in script
    assert "Google OAuth access token" in script
    assert "Do not enter your account password." in script
    assert "SELDRUNE CONNECTION CENTER" in script
    assert "OpenAI API" in script
    assert "Google Gemini API" in script
    assert "Anthropic API" in script
    assert "read-only model-list request before saving" in script
    assert 'type="password"' in script
    assert "autocomplete" in script
    assert "secret_value: secret" in script
    assert "model-provider-connections" in script
    assert "Credentials are encrypted in the organization vault" in script
    assert 'data-open-portal="connections"' in portal
    assert "#portal-panel-connections .owner-portal-grid" in styles
    assert ".integration-list" in styles



def test_connections_is_one_lazy_workspace_with_creation_shortcuts():
    html = (WEB / "index.html").read_text()
    portal = (WEB / "console-cosmic-tabs.js").read_text()
    connections = (WEB / "console-connections.js").read_text()
    tools = (WEB / "console-tools.js").read_text()

    assert 'move("#tool-control", "connections")' in portal
    assert 'move("#tool-control", "intelligence")' not in portal
    assert "portal-quick-card portal-quick-tools" not in portal
    assert "provider-vault-card" not in html
    assert "integration-credential-form" in connections
    assert "/model-provider-connections/" in connections
    assert "/tool-bootstrap/credentials/verified" in connections
    for workspace in (
        'data-open-portal="operator"',
        'data-open-portal="coding"',
        'data-open-portal="media"',
        'data-open-portal="outputs"',
    ):
        assert workspace in connections
    assert "seldrune:workspace-change" in tools
    assert "seldrune:console-ready', loadToolControl" not in tools
    assert "setInterval" not in connections
    assert "visibilitychange" not in connections
