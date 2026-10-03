(() => {
  const WORKSPACES = [
    ["home", "HOME", "⌂"],
    ["operator", "AI CHAT", "✦"],
    ["outputs", "OUTPUTS", "▣"],
    ["coding", "CODING LAB", "⌘"],
    ["operations", "WORKSPACE", "□"],
    ["media", "MEDIA", "◉"],
    ["intelligence", "SYSTEM", "⚙"],
    ["connections", "CONNECT", "↗"],
    ["sense", "SENSE", "◉"],
    ["contact", "CONTACT", "✉"],
  ];

  const PRIMARY_WORKSPACES = new Set([
    "home", "operator", "media", "connections", "contact",
  ]);

  const DESCRIPTIONS = {
    home: "Seldrune command nexus for AI, saved outputs, coding, missions, and system health.",
    operator: "One conversational Seldrune AI for questions, creation, and supported actions.",
    outputs: "Browse and download files Seldrune created in this browser.",
    coding: "Build source with connected coding agents, CI, and preview tools.",
    operations: "Track Seldrune self-development, agent work, and verified execution.",
    media: "Seldrune Media camera, microphone, face and voice transformation workspace.",
    intelligence: "Agents, owner decisions, budgets, execution evidence, and system policies.",
    connections: "Connect verified AI, code, email, and deployment services; manage creation tools in one place.",
    sense: "System health, provider status, and owner continuity preferences.",
    contact: "Contact Seldrune or report a portal issue.",
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
        <div class="cosmic-brand-mark" aria-hidden="true"><span>SE</span></div>
        <div>
          <strong>SELDRUNE</strong>
          <small>AETHELION INTELLIGENCE FOUNDRY</small>
        </div>
      </div>
      <nav class="cosmic-tabs owner-portal-tabs" role="tablist"
           aria-label="Seldrune workspaces" aria-orientation="horizontal"></nav>
      <div class="owner-portal-actions">
        <button type="button" id="portal-back-button" class="owner-back-button ghost"
                aria-label="Go to previous Seldrune page" hidden>← Back</button>
        <button type="button" class="owner-command-button"
                data-open-portal="operator">Ask Seldrune</button>
        <div class="cosmic-runtime-pill" id="portal-runtime-pill">
          <strong id="portal-runtime-state">● CHECKING</strong>
          <small id="cosmic-runtime-model">Seldrune runtime</small>
        </div>
      </div>`;
    main.prepend(bar);

    const tabList = bar.querySelector(".owner-portal-tabs");
    const moreTabs = document.createElement("details");
    moreTabs.className = "owner-portal-more-tabs";
    moreTabs.innerHTML = '<summary>More</summary><div class="owner-portal-more-menu" aria-label="More workspaces"></div>';
    bar.insertBefore(moreTabs, bar.querySelector(".owner-portal-actions"));
    const moreTabList = moreTabs.querySelector(".owner-portal-more-menu");
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
      button.id = `portal-tab-${id}`;
      button.setAttribute("aria-controls", `portal-panel-${id}`);
      button.innerHTML =
        `<span class="cosmic-tab-icon">${icon}</span>` +
        `<span class="cosmic-tab-label">${label}</span>`;
      (PRIMARY_WORKSPACES.has(id) ? tabList : moreTabList).append(button);

      const panel = document.createElement("section");
      panel.id = `portal-panel-${id}`;
      panel.className = "cosmic-tab-panel owner-portal-panel";
      panel.dataset.portalPanel = id;
      panel.setAttribute("role", "tabpanel");
      panel.setAttribute("aria-labelledby", button.id);
      panel.tabIndex = 0;
      panel.innerHTML = `
        <div class="cosmic-page-heading owner-portal-heading">
          <div>
            <p>SELDRUNE STI COMMAND NEXUS</p>
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
    home.dataset.portalScene = "true";
    home.innerHTML = `
      <div class="owner-home-intro">
        <span>SELDRUNE · OWNER PORTAL</span>
        <h2>Your workspace, without the clutter.</h2>
        <p>Chat with Seldrune, create media, manage connections, and review work from one simple navigation bar.</p>
      </div>
      <div class="owner-home-actions" aria-label="Quick actions">
        <button class="portal-quick-card" type="button" data-open-portal="operator">
          <span class="portal-quick-icon">✦</span>
          <span><strong>AI CHAT</strong><small>Questions and text responses</small></span><b>→</b>
        </button>
        <button class="portal-quick-card" type="button" data-open-portal="media">
          <span class="portal-quick-icon">◉</span>
          <span><strong>MEDIA</strong><small>Audio, video, and live studio</small></span><b>→</b>
        </button>
        <button class="portal-quick-card" type="button" data-open-portal="connections">
          <span class="portal-quick-icon">↗</span>
          <span><strong>CONNECTIONS</strong><small>Providers and integrations</small></span><b>→</b>
        </button>
        <button class="portal-quick-card" type="button" data-open-portal="contact">
          <span class="portal-quick-icon">✉</span>
          <span><strong>CONTACT</strong><small>Get help or report an issue</small></span><b>→</b>
        </button>
      </div>
      <div class="owner-home-status" role="status">
        <span><strong id="portal-runtime-inline">Runtime checking</strong></span>
        <span><strong id="portal-attention-value">Checking</strong> · <small id="portal-attention-detail">Owner attention</small></span>
      </div>`;
    panels.get("home")?.querySelector(".owner-portal-heading")?.after(home);

    move("#overview", "home");
    move("#seldrune-gpt", "operator");
    // The universal AI is the single request composer; remove the older duplicate
    // owner-command form after its legacy event handler has been registered.
    document.querySelector("#command")?.remove();

    move("#cognitive-mission", "operations");
    move("#sti-runtime", "operations");
    move("#action-inbox", "intelligence");
    move("#commands", "operations");

    move("#face-v01-mission", "media");
    move("#liveshift-mission", "media");
    move("#face-external-test", "media");

    const mediaDiagnostics = document.createElement("details");
    mediaDiagnostics.className = "media-advanced-details";
    mediaDiagnostics.innerHTML = "<summary>Live transformation status and advanced diagnostics</summary>";
    ["#face-v01-mission", "#liveshift-mission", "#face-external-test"].forEach(selector => {
      const section = grid("media")?.querySelector(selector);
      if (section) mediaDiagnostics.append(section);
    });
    grid("media")?.append(mediaDiagnostics);

    const mediaForge = document.querySelector("#seldrune-gpt .gpt-creation-forge");
    if (mediaForge) {
      const mediaForgeHost = document.createElement("section");
      mediaForgeHost.id = "media-creation-host";
      mediaForgeHost.className = "panel media-create-panel";
      mediaForgeHost.append(mediaForge);
      grid("media")?.prepend(mediaForgeHost);
    }

    const mediaStudio = document.createElement("section");
    mediaStudio.id = "seldrune-media-live-studio";
    mediaStudio.className = "panel media-live-studio";
    mediaStudio.setAttribute("aria-labelledby", "media-live-studio-title");
    mediaStudio.style.gridColumn = "1 / -1";
    mediaStudio.innerHTML = `
      <div class="section-head">
        <div>
          <p class="eyebrow">SELDRUNE MEDIA · LIVE TRANSFORMATION</p>
          <h2 id="media-live-studio-title">Camera &amp; microphone studio</h2>
          <p>Capture from a phone camera and microphone, then route authorized profiles through the configured LiveShell GPU session.</p>
        </div>
        <a class="ghost" href="/liveshell/mobile">Open full studio ↗</a>
      </div>
      <p class="media-live-studio-note">Face and voice profile approval, a connected GPU worker, and the persistent AI transformed indicator are required for a live session.</p>
      <div class="media-live-studio-frame"></div>`;
    const mediaStudioFrame = document.createElement("iframe");
    mediaStudioFrame.title = "Seldrune LiveShell camera and microphone transformation studio";
    mediaStudioFrame.src = "/liveshell/mobile";
    mediaStudioFrame.loading = "lazy";
    mediaStudioFrame.allow = "camera; microphone; autoplay";
    mediaStudioFrame.referrerPolicy = "same-origin";
    mediaStudioFrame.style.cssText =
      "display:block;width:100%;height:1420px;border:0;background:#080b14;";
    const mediaStudioFrameWrap = mediaStudio.querySelector(".media-live-studio-frame");
    if (mediaStudioFrameWrap) {
      mediaStudioFrameWrap.style.cssText =
        "overflow:hidden;border:1px solid rgba(84,220,255,.24);border-radius:16px;background:#080b14;";
      mediaStudioFrameWrap.append(mediaStudioFrame);
    }
    const resizeMediaStudioFrame = () => {
      mediaStudioFrame.style.height =
        window.matchMedia("(max-width: 920px)").matches ? "2180px" : "1420px";
    };
    resizeMediaStudioFrame();
    window.addEventListener("resize", resizeMediaStudioFrame, {passive: true});
    const liveMediaDetails = document.createElement("details");
    liveMediaDetails.className = "media-advanced-details";
    liveMediaDetails.innerHTML = "<summary>Open live camera and microphone studio</summary>";
    liveMediaDetails.append(mediaStudio);
    grid("media")?.append(liveMediaDetails);


    move(".agent-observatory", "intelligence");
    move(".incident-center", "intelligence");
    move(".audit-center", "intelligence");
    move("#evidence-truth", "intelligence");
    move("#tool-control", "connections");

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
    grid("intelligence")?.append(portalSettings);
    move(".treasury", "intelligence");
    move(".governance-policy", "intelligence");

    const outputLibrary = document.createElement("section");
    outputLibrary.id = "seldrune-output-library";
    outputLibrary.className = "panel output-library";
    outputLibrary.setAttribute("aria-labelledby", "seldrune-output-title");
    outputLibrary.innerHTML = `
      <div class="output-library-head">
        <div>
          <p class="eyebrow">SELDRUNE OUTPUT VAULT</p>
          <h2 id="seldrune-output-title">Your created files</h2>
          <p>Generated text, edited documents, and verified build receipts appear here.</p>
        </div>
        <span class="output-storage-note">Saved in this browser</span>
      </div>
      <div class="output-library-controls">
        <label class="output-search">Search outputs
          <input id="seldrune-output-search" type="search" autocomplete="off"
                 placeholder="Find a file or project…">
        </label>
        <div class="output-filters" role="group" aria-label="Filter output files">
          <button type="button" data-output-filter="all" aria-pressed="true">All</button>
          <button type="button" data-output-filter="app">Apps</button>
          <button type="button" data-output-filter="game">Games</button>
          <button type="button" data-output-filter="song">Songs</button>
          <button type="button" data-output-filter="video">Videos</button>
          <button type="button" data-output-filter="visual">Images & 3D</button>
          <button type="button" data-output-filter="document">Documents</button>
          <button type="button" data-output-filter="build">Builds</button>
        </div>
      </div>
      <p id="seldrune-output-status" class="output-library-status" role="status">
        Loading saved outputs…
      </p>
      <div id="seldrune-output-list" class="output-list" role="list"
           aria-live="polite" aria-relevant="additions removals text"></div>`;
    grid("outputs")?.append(outputLibrary);

    const codingLab = document.createElement("section");
    codingLab.id = "seldrune-coding-lab";
    codingLab.className = "panel coding-lab";
    codingLab.setAttribute("aria-labelledby", "coding-lab-title");
    codingLab.innerHTML = `
      <div class="coding-lab-hero">
        <div>
          <p class="eyebrow">SELDRUNE RAPIDBUILD LOOP · CODING LAB</p>
          <h2 id="coding-lab-title">From brief to verified build</h2>
          <p>Give Seldrune a build goal. Connected coding tools can create a branch, write code,
             run checks, and return a preview or deployment receipt.</p>
        </div>
        <button type="button" class="ghost" data-open-portal="operator">Ask Seldrune AI</button>
      </div>
      <ol class="coding-lab-stages" aria-label="RapidBuild workflow">
        <li><span>01</span><strong>Plan</strong><small>Scope the change</small></li>
        <li><span>02</span><strong>Build</strong><small>Use connected agents</small></li>
        <li><span>03</span><strong>Verify</strong><small>Read actual CI results</small></li>
        <li><span>04</span><strong>Preview</strong><small>Show provider receipts</small></li>
      </ol>
      <div id="coding-lab-provider-status" class="coding-provider-grid" aria-live="polite">
        <div class="coding-provider-card" data-provider="github"><strong>GitHub</strong><span>Checking tools…</span></div>
        <div class="coding-provider-card" data-provider="circleci"><strong>CircleCI</strong><span>Checking tools…</span></div>
        <div class="coding-provider-card" data-provider="railway"><strong>Railway</strong><span>Checking tools…</span></div>
      </div>
      <form id="coding-lab-form" class="coding-lab-form">
        <label>Repository or project <span>Optional</span>
          <input id="coding-lab-repository" type="text" maxlength="240"
                 autocomplete="off" placeholder="owner/repository or project name">
        </label>
        <label>What should Seldrune build?
          <textarea id="coding-lab-brief" minlength="5" maxlength="6800" required
                    placeholder="Describe the app, game, feature, or fix. Include the behavior you expect."></textarea>
        </label>
        <div class="coding-lab-actions">
          <p id="coding-lab-status" role="status">Builds use configured tools and report the actual result.</p>
          <button type="submit" id="coding-lab-submit">Start build <span>→</span></button>
        </div>
      </form>
      <div id="coding-lab-run-list" class="coding-lab-run-list" aria-live="polite"></div>`;
    grid("coding")?.append(codingLab);

    const footer = document.createElement("footer");
    footer.className = "cosmic-footer owner-portal-footer";
    footer.innerHTML =
      "<span>SELDRUNE · OWNER PORTAL</span>" +
      '<span><a href="/mail">Contact by email</a> · <a href="https://github.com/seldrune-platform/seldrune-platform/issues/new" target="_blank" rel="noopener noreferrer">Report an issue</a></span>';
    root.after(footer);

    const contactPanel = document.createElement("section");
    contactPanel.id = "seldrune-contact-panel";
    contactPanel.className = "panel";
    contactPanel.setAttribute("aria-labelledby", "seldrune-contact-title");
    contactPanel.innerHTML = `
      <p class="eyebrow">CONTACT SELDRUNE</p>
      <h2 id="seldrune-contact-title">How can we help?</h2>
      <p>Use Seldrune Mail to send a message, or report a portal problem through the project issue tracker.</p>
      <div class="contact-options">
        <a class="contact-option" href="/mail">
          <strong>Open Seldrune Mail →</strong>
          <span>Compose and send through a connected email provider.</span>
        </a>
        <a class="contact-option" href="https://github.com/seldrune-platform/seldrune-platform/issues/new" target="_blank" rel="noopener noreferrer">
          <strong>Report a portal issue →</strong>
          <span>Open a new issue with the Seldrune project.</span>
        </a>
        <a class="contact-option" id="seldrune-contact-email-link" href="#" hidden>
          <strong>Email Seldrune →</strong>
          <span id="seldrune-contact-email-address"></span>
        </a>
      </div>
      <p id="seldrune-contact-note" class="policy-status" role="status"></p>`;
    grid("contact")?.append(contactPanel);
    const contactEmail = document.querySelector('meta[name="seldrune-contact-email"]')?.content?.trim() || "";
    const contactEmailLink = contactPanel.querySelector("#seldrune-contact-email-link");
    const contactEmailNote = contactPanel.querySelector("#seldrune-contact-note");
    const emailLooksValid = contactEmail.includes("@") && contactEmail.lastIndexOf(".") > contactEmail.indexOf("@");
    if (emailLooksValid) {
      contactEmailLink.href = "mailto:" + contactEmail;
      contactEmailLink.hidden = false;
      contactPanel.querySelector("#seldrune-contact-email-address").textContent = contactEmail;
      contactEmailNote.textContent = "Direct support email is configured.";
    } else {
      contactEmailNote.textContent = "Direct support email is not configured for this portal yet.";
    }

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
      document.dispatchEvent(new CustomEvent("seldrune:workspace-change", {detail: {workspace: id}}));

      document.querySelectorAll(".owner-portal-tab").forEach(button => {
        const active = button.dataset.portalTab === id;
        button.setAttribute("aria-selected", String(active));
        button.tabIndex = active ? 0 : -1;
      });
      panels.forEach((panel, panelId) => {
        panel.classList.toggle("active", panelId === id);
        panel.hidden = panelId !== id;
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

    const activateTabFromClick = event => {
      const button = event.target.closest("[data-portal-tab]");
      if (!button) return;
      activate(button.dataset.portalTab, {historyMode: "push"});
      moreTabs.open = false;
    };
    tabList.addEventListener("click", activateTabFromClick);
    moreTabList.addEventListener("click", activateTabFromClick);

    tabList.addEventListener("keydown", event => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      const buttons = [...tabList.querySelectorAll(".owner-portal-tab")];
      const current = buttons.indexOf(document.activeElement);
      if (event.key === "Home" || event.key === "End") {
        const next = event.key === "Home" ? buttons[0] : buttons.at(-1);
        next?.focus();
        if (next) activate(next.dataset.portalTab, {historyMode: "push"});
        event.preventDefault();
        return;
      }
      const delta = event.key === "ArrowRight" ? 1 : -1;
      const next = buttons[(current + delta + buttons.length) % buttons.length];
      next?.focus();
      if (next) activate(next.dataset.portalTab, {historyMode: "push"});
      event.preventDefault();
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
        detail.textContent = "Seldrune is actively executing an owner request.";
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
