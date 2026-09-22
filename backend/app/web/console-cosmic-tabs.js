(() => {
  const WORKSPACES = [
    ["home", "Home", "⌂"],
    ["operator", "Operator", "✦"],
    ["operations", "Operations", "⌘"],
    ["media", "Media", "◉"],
    ["intelligence", "Intelligence", "⬡"],
    ["tools", "Tools", "⌁"],
    ["settings", "Settings", "⚙"],
  ];

  const DESCRIPTIONS = {
    home: "Owner-level state, priorities, and shortcuts without engineering noise.",
    operator: "Talk to Seldrune, issue governed orders, and create new missions.",
    operations: "Execution runtime, approvals, active work, and delivery evidence.",
    media: "Seldrune Face, LiveShift, and authorized real-time media controls.",
    intelligence: "Agent evidence, incidents, governance history, and truth signals.",
    tools: "External providers, credentials, action receipts, and tool execution.",
    settings: "Portal experience, treasury, governance limits, and owner controls.",
  };

  function initOwnerPortal() {
    const view = document.querySelector("#console-view");
    const main = view?.querySelector("main");
    if (!view || !main || document.querySelector(".owner-portal-bar")) return;

    document.body.classList.add("cosmic-console", "owner-portal");
    document.documentElement.dataset.portalReady = "true";

    const bar = document.createElement("header");
    bar.className = "cosmic-command-bar owner-portal-bar";
    bar.innerHTML = `
      <div class="cosmic-brand owner-portal-brand">
        <div class="cosmic-brand-mark" aria-hidden="true"><span>⌁</span></div>
        <div>
          <strong>SELDRUNE</strong>
          <small>OWNER PORTAL</small>
        </div>
      </div>
      <nav class="cosmic-tabs owner-portal-tabs" role="tablist"
           aria-label="Seldrune owner workspaces"></nav>
      <div class="owner-portal-actions">
        <button type="button" class="owner-command-button"
                data-open-portal="operator">New order</button>
        <div class="cosmic-runtime-pill" id="portal-runtime-pill">
          <strong id="portal-runtime-state">● CHECKING</strong>
          <small id="cosmic-runtime-model">Seldrune runtime</small>
        </div>
      </div>`;
    main.prepend(bar);

    const tabList = bar.querySelector(".owner-portal-tabs");
    const root = document.createElement("div");
    root.id = "owner-portal-root";
    root.className = "owner-portal-root";
    bar.after(root);

    const panels = new Map();
    WORKSPACES.forEach(([id, label, icon]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "cosmic-tab owner-portal-tab";
      button.dataset.portalTab = id;
      button.setAttribute("role", "tab");
      button.setAttribute("aria-controls", `portal-panel-${id}`);
      button.innerHTML =
        `<span class="cosmic-tab-icon">${icon}</span>` +
        `<span class="cosmic-tab-label">${label}</span>`;
      tabList.append(button);

      const panel = document.createElement("section");
      panel.id = `portal-panel-${id}`;
      panel.className = "cosmic-tab-panel owner-portal-panel";
      panel.dataset.portalPanel = id;
      panel.setAttribute("role", "tabpanel");
      panel.innerHTML = `
        <div class="cosmic-page-heading owner-portal-heading">
          <div>
            <p>SELDRUNE OWNER WORKSPACE</p>
            <h1>${label}</h1>
          </div>
          <small>${DESCRIPTIONS[id]}</small>
        </div>
        <div class="cosmic-panel-grid owner-portal-grid"></div>`;
      root.append(panel);
      panels.set(id, panel);
    });

    const grid = id => panels.get(id)?.querySelector(".owner-portal-grid");
    const move = (selector, id) => {
      const node = document.querySelector(selector);
      const target = grid(id);
      if (node && target) target.append(node);
    };

    const home = document.createElement("section");
    home.className = "owner-portal-home";
    home.innerHTML = `
      <article class="owner-hero-card owner-hero-primary">
        <div class="owner-hero-copy">
          <span class="owner-hero-kicker">OWNER COMMAND CENTER</span>
          <h2>One portal. Every Seldrune operation.</h2>
          <p>
            Run the organization from outcome-focused workspaces while engineering
            versions, internal milestones, and implementation detail remain behind
            the backend boundary.
          </p>
          <div class="owner-hero-actions">
            <button type="button" data-open-portal="operator">Speak to Seldrune</button>
            <button type="button" class="ghost" data-open-portal="operations">
              View operations
            </button>
          </div>
        </div>
        <div class="owner-reactor" aria-hidden="true">
          <i></i><i></i><i></i><b>STI</b>
        </div>
      </article>
      <article class="owner-signal-card">
        <span>OWNER ATTENTION</span>
        <strong id="portal-attention-value">Checking</strong>
        <small id="portal-attention-detail">
          Reading approvals, incidents, and active execution.
        </small>
        <button type="button" class="ghost" data-open-portal="operations">
          Open operations
        </button>
      </article>
      <article class="owner-signal-card">
        <span>ACTION FABRIC</span>
        <strong id="portal-tools-value">Governed</strong>
        <small>
          Provider actions require real tools and receipts. Missing integrations fail closed.
        </small>
        <button type="button" class="ghost" data-open-portal="tools">
          Open tools
        </button>
      </article>`;
    panels.get("home")?.querySelector(".owner-portal-heading")?.after(home);

    move("#overview", "home");
    move("#seldrune-gpt", "operator");
    move("#command", "operator");

    move("#sti-runtime", "operations");
    move("#action-inbox", "operations");
    move("#commands", "operations");

    move("#face-v01-mission", "media");
    move("#liveshift-mission", "media");
    move("#face-external-test", "media");

    move(".agent-observatory", "intelligence");
    move(".incident-center", "intelligence");
    move(".audit-center", "intelligence");
    move("#evidence-truth", "intelligence");

    move("#tool-control", "tools");

    const portalSettings = document.createElement("section");
    portalSettings.id = "portal-settings";
    portalSettings.className = "panel portal-settings-host";
    portalSettings.innerHTML = `
      <div class="section-head">
        <div>
          <p class="eyebrow">PORTAL SETTINGS</p>
          <h2>Owner portal experience</h2>
          <p>Personalize navigation and presentation without changing backend execution policy.</p>
        </div>
      </div>
      <div id="portal-settings-content">
        <div class="empty">Loading portal preferences…</div>
      </div>`;
    grid("settings")?.append(portalSettings);
    move(".treasury", "settings");
    move(".governance-policy", "settings");

    const footer = document.createElement("footer");
    footer.className = "cosmic-footer owner-portal-footer";
    footer.innerHTML =
      "<span>SELDRUNE · OWNER PORTAL</span>" +
      "<span>Execution truth · governed actions · evidence first</span>";
    root.after(footer);

    const preferenceKey = "seldrune.portal.defaultWorkspace";

    function activate(id, updateHash = true) {
      if (!panels.has(id)) id = "home";
      document.querySelectorAll(".owner-portal-tab").forEach(button => {
        const active = button.dataset.portalTab === id;
        button.setAttribute("aria-selected", String(active));
        button.tabIndex = active ? 0 : -1;
      });
      panels.forEach((panel, panelId) => {
        panel.classList.toggle("active", panelId === id);
      });
      if (updateHash) history.replaceState(null, "", `#${id}`);
      localStorage.setItem("seldrune.portal.lastWorkspace", id);
      if (id === "operator") {
        requestAnimationFrame(() => {
          document.getElementById("seldrune-gpt-input")?.focus();
        });
      }
      window.scrollTo({
        top: 0,
        behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "auto"
          : "smooth",
      });
    }

    tabList.addEventListener("click", event => {
      const button = event.target.closest("[data-portal-tab]");
      if (button) activate(button.dataset.portalTab);
    });

    tabList.addEventListener("keydown", event => {
      if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
      const buttons = [...tabList.querySelectorAll(".owner-portal-tab")];
      const current = buttons.indexOf(document.activeElement);
      const delta = event.key === "ArrowRight" ? 1 : -1;
      const next = buttons[(current + delta + buttons.length) % buttons.length];
      next?.focus();
      if (next) activate(next.dataset.portalTab);
    });

    document.addEventListener("click", event => {
      const trigger = event.target.closest("[data-open-portal]");
      if (trigger) activate(trigger.dataset.openPortal);
    });

    window.addEventListener("hashchange", () => {
      const requested = location.hash.slice(1);
      if (panels.has(requested)) activate(requested, false);
    });

    const readNumber = id => {
      const text = document.getElementById(id)?.textContent || "";
      const value = Number(text.replace(/[^0-9.-]/g, ""));
      return Number.isFinite(value) ? Math.max(0, value) : 0;
    };

    const syncOwnerSignals = () => {
      const approvals = readNumber("pending") + readNumber("action-approvals");
      const critical = readNumber("incident-critical");
      const running = readNumber("sti-running");
      const value = document.getElementById("portal-attention-value");
      const detail = document.getElementById("portal-attention-detail");
      if (!value || !detail) return;
      if (critical > 0) {
        value.textContent = `${critical} critical`;
        detail.textContent = "Production incidents need owner attention.";
      } else if (approvals > 0) {
        value.textContent = `${approvals} decisions`;
        detail.textContent = "Approvals or reviews are waiting for you.";
      } else if (running > 0) {
        value.textContent = `${running} running`;
        detail.textContent = "Seldrune is actively executing governed work.";
      } else {
        value.textContent = "Clear";
        detail.textContent = "No measured owner intervention is currently required.";
      }
    };

    const signalObserver = new MutationObserver(syncOwnerSignals);
    ["pending", "action-approvals", "incident-critical", "sti-running"].forEach(id => {
      const node = document.getElementById(id);
      if (node) {
        signalObserver.observe(node, {
          childList: true,
          subtree: true,
          characterData: true,
        });
      }
    });
    syncOwnerSignals();

    const runtime = document.getElementById("runtime-status");
    const runtimeState = document.getElementById("portal-runtime-state");
    const runtimeModel = document.getElementById("cosmic-runtime-model");
    const syncRuntime = () => {
      if (!runtime || !runtimeState || !runtimeModel) return;
      const ready = runtime.classList.contains("runtime-ready");
      const degraded = runtime.classList.contains("runtime-degraded");
      runtimeState.textContent = degraded
        ? "● ATTENTION"
        : ready
          ? "● ONLINE"
          : "● CHECKING";
      runtimeState.dataset.state = degraded ? "degraded" : ready ? "ready" : "checking";
      runtimeModel.textContent =
        document.getElementById("runtime-version")?.textContent || "Seldrune runtime";
    };
    if (runtime) {
      new MutationObserver(syncRuntime).observe(runtime, {
        attributes: true,
        childList: true,
        subtree: true,
      });
    }
    syncRuntime();

    const requested = location.hash.slice(1);
    const preferred = localStorage.getItem(preferenceKey);
    const last = localStorage.getItem("seldrune.portal.lastWorkspace");
    const initial = panels.has(requested)
      ? requested
      : panels.has(preferred)
        ? preferred
        : panels.has(last)
          ? last
          : "home";
    activate(initial, false);

    window.seldrunePortal = {
      activate,
      workspaces: WORKSPACES.map(([id, label]) => ({id, label})),
    };
    document.dispatchEvent(new CustomEvent("seldrune:portal-ready"));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initOwnerPortal, {once: true});
  } else {
    initOwnerPortal();
  }
  document.addEventListener("seldrune:console-ready", initOwnerPortal);
})();