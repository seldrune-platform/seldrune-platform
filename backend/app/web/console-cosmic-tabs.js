(() => {
  const WORKSPACES = [
    ["home", "Home", "⌂"],
    ["operator", "GPT", "✦"],
    ["operations", "Work", "⌘"],
    ["media", "Media", "◉"],
    ["intelligence", "Insights", "⬡"],
    ["tools", "Tools", "⌁"],
    ["settings", "Settings", "⚙"],
  ];

  const DESCRIPTIONS = {
    home: "Your simple launch point for Seldrune.",
    operator: "Chat, upload files, edit PDFs, and issue owner orders.",
    operations: "See active work, approvals, and execution progress.",
    media: "Open Seldrune Face and LiveShift controls.",
    intelligence: "Review evidence, incidents, agents, and audit signals.",
    tools: "Connect providers, manage credentials, and run tools.",
    settings: "Portal appearance, limits, treasury, and owner controls.",
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
        <button type="button" id="portal-back-button" class="owner-back-button ghost"
                aria-label="Go to previous Seldrune page" hidden>← Back</button>
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
    home.className = "owner-portal-home portal-depth-scene";
    home.dataset.portalScene = "true";
    home.innerHTML = `
      <div class="neural-grid-layer" aria-hidden="true">
        <i></i><i></i><i></i><i></i><i></i><i></i>
      </div>

      <button class="portal-quick-card portal-quick-gpt" type="button"
              data-open-portal="operator" data-depth="1.05">
        <span class="portal-quick-icon">✦</span>
        <span><strong>GPT</strong><small>Chat with Seldrune</small></span>
        <b>→</b>
      </button>

      <button class="portal-quick-card portal-quick-orders" type="button"
              data-open-portal="operator" data-focus-target="#command" data-depth=".8">
        <span class="portal-quick-icon">⌘</span>
        <span><strong>Orders</strong><small>Run executive work</small></span>
        <b>→</b>
      </button>

      <article class="portal-gateway-card" data-depth="1.35">
        <div class="portal-gateway-copy">
          <span>SELDRUNE OWNER PORTAL</span>
          <h2>Enter Seldrune</h2>
          <p>One intelligent gateway to chat, work, tools, files, media, and evidence.</p>
        </div>
        <button class="portal-gateway" type="button" data-open-portal="operator"
                aria-label="Enter Seldrune GPT">
          <span class="portal-aura"></span>
          <span class="portal-ring portal-ring-outer"></span>
          <span class="portal-ring portal-ring-mid"></span>
          <span class="portal-ring portal-ring-inner"></span>
          <span class="portal-fractal">
            <i></i><i></i><i></i><i></i><i></i><i></i>
          </span>
          <span class="portal-core">
            <b>STI</b>
            <small>ENTER</small>
          </span>
          <span class="portal-particles" aria-hidden="true"></span>
        </button>
        <div class="portal-live-strip">
          <span><i></i><strong id="portal-runtime-inline">Runtime checking</strong></span>
          <span><strong id="portal-attention-value">Checking</strong><small id="portal-attention-detail">Owner attention</small></span>
        </div>
      </article>

      <button class="portal-quick-card portal-quick-tools" type="button"
              data-open-portal="tools" data-depth=".9">
        <span class="portal-quick-icon">⌁</span>
        <span><strong>Tools</strong><small>Connect & manage</small></span>
        <b>→</b>
      </button>

      <button class="portal-quick-card portal-quick-files" type="button"
              data-open-portal="operator" data-focus-target="#seldrune-gpt-dropzone"
              data-depth="1.1">
        <span class="portal-quick-icon">▣</span>
        <span><strong>Files & PDF</strong><small>Upload, read, edit</small></span>
        <b>→</b>
      </button>

      <article class="portal-status-card" data-depth=".55">
        <span>System</span>
        <strong id="portal-tools-value">Governed</strong>
        <small>Provider actions stay receipt-backed and credential-aware.</small>
        <button type="button" class="ghost" data-open-portal="operations">View work</button>
      </article>`;
    panels.get("home")?.querySelector(".owner-portal-heading")?.after(home);

    const particleRoot = home.querySelector(".portal-particles");
    if (particleRoot) {
      for (let index = 0; index < 22; index += 1) {
        const particle = document.createElement("i");
        particle.style.setProperty("--particle-index", String(index));
        particle.style.setProperty("--particle-angle", `${(index * 16.36).toFixed(2)}deg`);
        particle.style.setProperty("--particle-duration", `${(7 + index * .18).toFixed(2)}s`);
        particle.style.setProperty("--particle-scale", (0.65 + index / 44).toFixed(2));
        particle.style.setProperty("--particle-opacity", (0.25 + index / 40).toFixed(2));
        particleRoot.append(particle);
      }
    }

    const scene = home;
    const gateway = home.querySelector(".portal-gateway");
    const motionReduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!motionReduced) {
      scene.addEventListener("pointermove", event => {
        const bounds = scene.getBoundingClientRect();
        const x = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width));
        const y = Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height));
        scene.style.setProperty("--cursor-x", `${(x * 100).toFixed(2)}%`);
        scene.style.setProperty("--cursor-y", `${(y * 100).toFixed(2)}%`);
        scene.style.setProperty("--cursor-shift-x", `${((x - .5) * 16).toFixed(2)}px`);
        scene.style.setProperty("--cursor-shift-y", `${((y - .5) * 12).toFixed(2)}px`);
        scene.style.setProperty("--portal-tilt-x", `${((.5 - y) * 8).toFixed(2)}deg`);
        scene.style.setProperty("--portal-tilt-y", `${((x - .5) * 10).toFixed(2)}deg`);
        scene.querySelectorAll("[data-depth]").forEach(node => {
          const depth = Number(node.dataset.depth || 1);
          const dx = (x - .5) * 16 * depth;
          const dy = (y - .5) * 12 * depth;
          node.style.setProperty("--depth-x", `${dx.toFixed(2)}px`);
          node.style.setProperty("--depth-y", `${dy.toFixed(2)}px`);
        });
      });
      scene.addEventListener("pointerleave", () => {
        scene.style.setProperty("--cursor-shift-x", "0px");
        scene.style.setProperty("--cursor-shift-y", "0px");
        scene.style.setProperty("--portal-tilt-x", "0deg");
        scene.style.setProperty("--portal-tilt-y", "0deg");
        scene.querySelectorAll("[data-depth]").forEach(node => {
          node.style.setProperty("--depth-x", "0px");
          node.style.setProperty("--depth-y", "0px");
        });
      });
    }
    gateway?.addEventListener("focus", () => scene.classList.add("portal-keyboard-focus"));
    gateway?.addEventListener("blur", () => scene.classList.remove("portal-keyboard-focus"));

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

    let currentWorkspace = "home";
    let portalHistoryDepth = 0;
    const backButton = document.getElementById("portal-back-button");

    function syncBackButton() {
      if (!backButton) return;
      const canGoBackInsidePortal = portalHistoryDepth > 0 && currentWorkspace !== "home";
      backButton.hidden = !canGoBackInsidePortal;
    }

    function activate(id, options = {}) {
      const {
        historyMode = "push",
        scroll = true,
      } = options;
      if (!panels.has(id)) id = "home";
      const changed = currentWorkspace !== id;
      currentWorkspace = id;

      document.querySelectorAll(".owner-portal-tab").forEach(button => {
        const active = button.dataset.portalTab === id;
        button.setAttribute("aria-selected", String(active));
        button.tabIndex = active ? 0 : -1;
      });
      panels.forEach((panel, panelId) => {
        panel.classList.toggle("active", panelId === id);
      });

      if (changed && historyMode === "push") {
        portalHistoryDepth += 1;
        history.pushState(
          {seldrunePortal: true, workspace: id, depth: portalHistoryDepth},
          "",
          `#${id}`,
        );
      } else if (historyMode === "replace") {
        history.replaceState(
          {seldrunePortal: true, workspace: id, depth: portalHistoryDepth},
          "",
          id === "home"
            ? location.pathname + location.search
            : `#${id}`,
        );
      }

      syncBackButton();

      if (id === "operator") {
        requestAnimationFrame(() => {
          document.getElementById("seldrune-gpt-input")?.focus();
        });
      }
      if (scroll) {
        window.scrollTo({
          top: 0,
          behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
            ? "auto"
            : "smooth",
        });
      }
    }

    tabList.addEventListener("click", event => {
      const button = event.target.closest("[data-portal-tab]");
      if (button) activate(button.dataset.portalTab, {historyMode: "push"});
    });

    tabList.addEventListener("keydown", event => {
      if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
      const buttons = [...tabList.querySelectorAll(".owner-portal-tab")];
      const current = buttons.indexOf(document.activeElement);
      const delta = event.key === "ArrowRight" ? 1 : -1;
      const next = buttons[(current + delta + buttons.length) % buttons.length];
      next?.focus();
      if (next) activate(next.dataset.portalTab, {historyMode: "push"});
    });

    document.addEventListener("click", event => {
      const trigger = event.target.closest("[data-open-portal]");
      if (!trigger) return;
      activate(trigger.dataset.openPortal, {historyMode: "push"});
      const focusTarget = trigger.dataset.focusTarget;
      if (focusTarget) {
        requestAnimationFrame(() => {
          const target = document.querySelector(focusTarget);
          target?.scrollIntoView({behavior: "smooth", block: "center"});
          target?.focus?.({preventScroll: true});
        });
      }
    });

    backButton?.addEventListener("click", () => {
      if (portalHistoryDepth > 0) history.back();
      else activate("home", {historyMode: "replace"});
    });

    window.addEventListener("popstate", event => {
      const state = event.state;
      if (state?.seldrunePortal && panels.has(state.workspace)) {
        portalHistoryDepth = Math.max(0, Number(state.depth) || 0);
        activate(state.workspace, {historyMode: "none", scroll: false});
        return;
      }

      const requested = location.hash.slice(1);
      if (panels.has(requested)) {
        portalHistoryDepth = Math.max(0, portalHistoryDepth - 1);
        activate(requested, {historyMode: "none", scroll: false});
        return;
      }

      portalHistoryDepth = 0;
      activate("home", {historyMode: "replace", scroll: false});
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
      const inline = document.getElementById("portal-runtime-inline");
      if (inline) {
        inline.textContent = degraded
          ? "Runtime attention"
          : ready
            ? "Runtime online"
            : "Runtime checking";
      }
    };
    if (runtime) {
      new MutationObserver(syncRuntime).observe(runtime, {
        attributes: true,
        childList: true,
        subtree: true,
      });
    }
    syncRuntime();

    // A fresh Owner Console session always starts from Home, then each workspace
    // navigation creates real browser history so Back returns through Seldrune
    // instead of immediately leaving the console.
    portalHistoryDepth = 0;
    history.replaceState(
      {seldrunePortal: true, workspace: "home", depth: 0},
      "",
      location.pathname + location.search,
    );
    activate("home", {historyMode: "none", scroll: false});

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