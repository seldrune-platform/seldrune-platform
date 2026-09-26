(() => {
  let dashboard;
  let memoryDirty = false;
  let refreshTimer;

  function mount() {
    const host = document.querySelector("#portal-panel-sense .owner-portal-grid");
    if (!host || document.querySelector("#system-sense-dashboard")) return;
    dashboard = document.createElement("section");
    dashboard.id = "system-sense-dashboard";
    dashboard.className = "system-sense-dashboard";
    dashboard.innerHTML = `
      <div class="system-sense-status">
        <div>
          <strong id="sense-monitor-state">SENSE STARTING</strong>
          <small id="sense-sampled-at">Waiting for the first system snapshot.</small>
        </div>
        <strong id="sense-health" class="system-sense-health" data-state="unknown">UNKNOWN</strong>
      </div>
      <p id="sense-system-message" role="status" aria-live="polite"></p>
      <div class="sense-metric-grid">
        <article class="sense-metric">
          <span>Active agents</span><strong id="sense-agents">—</strong><small id="sense-agents-detail">Waiting for system data.</small>
        </article>
        <article class="sense-metric">
          <span>Open tasks</span><strong id="sense-tasks">—</strong><small id="sense-tasks-detail">Waiting for system data.</small>
        </article>
        <article class="sense-metric">
          <span>Open security events</span><strong id="sense-security">—</strong><small id="sense-security-detail">No snapshot yet.</small>
        </article>
        <article class="sense-metric">
          <span>Life worker cycles</span><strong id="sense-cycles">—</strong><small id="sense-worker-detail">Worker state is unknown.</small>
        </article>
      </div>
      <div class="sense-detail-grid">
        <section class="sense-provider-panel">
          <p class="eyebrow">MODEL CONNECTIONS</p>
          <h2>Provider configuration</h2>
          <div id="sense-provider-list" class="sense-provider-list"></div>
          <small>Configured means a key or endpoint is present. Seldrune checks a provider when you send a request; it does not poll providers or run hidden models in the background.</small>
        </section>
        <section class="sense-owner-memory">
          <p class="eyebrow">OWNER CONTINUITY</p>
          <h2 id="sense-owner-heading">Preferences for this owner</h2>
          <p>Save context you want Seldrune to remember between chats. You control and can clear it.</p>
          <label for="sense-owner-preferences">Saved preferences</label>
          <textarea id="sense-owner-preferences" maxlength="4000"
            placeholder="For example: keep updates concise, focus on the Seldrune Coding Lab, and show verification results."></textarea>
          <div class="sense-owner-memory-foot">
            <small>Saved in Seldrune. Included as context when you chat with a selected model provider. To clear it, empty the field and save.</small>
            <button id="sense-owner-save" type="button">Save preferences</button>
          </div>
          <p id="sense-owner-message" role="status" aria-live="polite"></p>
        </section>
      </div>`;
    host.append(dashboard);

    dashboard.querySelector("#sense-owner-preferences")
      .addEventListener("input", () => { memoryDirty = true; });
    dashboard.querySelector("#sense-owner-save")
      .addEventListener("click", saveOwnerContinuity);
  }

  function setText(id, value) {
    const element = dashboard?.querySelector("#" + id);
    if (element) element.textContent = String(value);
  }

  function renderProviders(providers) {
    const list = dashboard?.querySelector("#sense-provider-list");
    if (!list) return;
    list.replaceChildren();
    providers.forEach(provider => {
      const row = document.createElement("div");
      row.className = "sense-provider-item";
      const label = document.createElement("strong");
      label.textContent = provider.label;
      const status = document.createElement("span");
      status.className = provider.configured
        ? "sense-provider-configured"
        : "sense-provider-needed";
      status.textContent = provider.configured
        ? "Configured · checked on request"
        : "Needs " + (provider.configuration_hint || "server setup");
      const model = document.createElement("small");
      model.textContent = provider.model || "Model is selected by Seldrune";
      row.append(label, status, model);
      list.append(row);
    });
    if (!providers.length) {
      const empty = document.createElement("small");
      empty.textContent = "No provider status is available.";
      list.append(empty);
    }
  }

  function renderSnapshot(snapshot) {
    const health = snapshot.system?.health || "unknown";
    const healthBadge = dashboard.querySelector("#sense-health");
    healthBadge.dataset.state = health;
    healthBadge.textContent = health.toUpperCase();

    const worker = snapshot.life_worker || {};
    const interval = worker.sample_interval_seconds || "—";
    setText(
      "sense-monitor-state",
      worker.alive
        ? "ALWAYS-ON SENSE · sampling every " + interval + " seconds"
        : "SENSE MONITOR · " + String(worker.status || "unknown").toUpperCase(),
    );
    setText(
      "sense-sampled-at",
      "Snapshot " + new Date(snapshot.sampled_at).toLocaleTimeString(),
    );
    setText("sense-agents", snapshot.agents?.active ?? 0);
    setText("sense-agents-detail", (snapshot.agents?.total ?? 0) + " registered in this organization");
    setText("sense-tasks", snapshot.tasks?.open ?? 0);
    setText("sense-tasks-detail", (snapshot.tasks?.failed ?? 0) + " failed tasks");
    setText("sense-security", snapshot.security_events?.open ?? 0);
    const severity = snapshot.security_events?.by_severity || {};
    setText(
      "sense-security-detail",
      Object.entries(severity).map(([name, count]) => name + ": " + count).join(" · ")
        || "No open security events",
    );
    setText("sense-cycles", worker.cycle_count ?? 0);
    setText(
      "sense-worker-detail",
      worker.alive
        ? "Last pulse " + (worker.age_seconds ?? "—") + "s ago"
        : "No fresh running heartbeat",
    );
    const owner = snapshot.owner || {};
    if (owner.display_name) {
      setText("sense-owner-heading", "Preferences for " + owner.display_name);
    }
    renderProviders(snapshot.model_providers || []);
    setText(
      "sense-system-message",
      "Monitoring database-backed agent, task, security-event, worker, and provider-configuration signals for this organization.",
    );
  }

  async function refreshSystem() {
    if (!dashboard) return;
    try {
      const snapshot = await api("/sense/system");
      renderSnapshot(snapshot);
    } catch (error) {
      setText("sense-system-message", "System snapshot unavailable: " + error.message);
    }
  }

  async function loadOwnerContinuity() {
    if (!dashboard || memoryDirty) return;
    try {
      const state = await api("/sense/owner-continuity");
      dashboard.querySelector("#sense-owner-preferences").value = state.content || "";
      setText("sense-owner-message", state.saved
        ? "Owner preferences are saved."
        : "No preferences saved yet.");
    } catch (error) {
      setText("sense-owner-message", "Could not load owner preferences: " + error.message);
    }
  }

  async function saveOwnerContinuity() {
    if (!dashboard) return;
    const button = dashboard.querySelector("#sense-owner-save");
    button.disabled = true;
    setText("sense-owner-message", "Saving owner preferences…");
    try {
      const result = await api("/sense/owner-continuity", {
        method: "PUT",
        body: JSON.stringify({
          content: dashboard.querySelector("#sense-owner-preferences").value,
        }),
      });
      memoryDirty = false;
      dashboard.querySelector("#sense-owner-preferences").value = result.content || "";
      setText("sense-owner-message", result.saved
        ? "Preferences saved for this owner account."
        : "Owner preferences cleared.");
      await refreshSystem();
    } catch (error) {
      setText("sense-owner-message", "Could not save preferences: " + error.message);
    } finally {
      button.disabled = false;
    }
  }

  async function start() {
    mount();
    await Promise.all([refreshSystem(), loadOwnerContinuity()]);
    if (!refreshTimer) {
      refreshTimer = window.setInterval(() => {
        if (!document.hidden) refreshSystem();
      }, 15000);
    }
  }

  document.addEventListener("seldrune:portal-ready", mount);
  document.addEventListener("seldrune:console-ready", start);
  document.addEventListener("seldrune:workspace-change", event => {
    if (event.detail?.workspace === "sense") refreshSystem();
  });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) refreshSystem();
  });
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount, {once: true});
  } else {
    mount();
  }
})();