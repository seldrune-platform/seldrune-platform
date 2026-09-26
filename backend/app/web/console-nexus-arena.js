(() => {
  let observatory = null;
  let refreshing = false;
  let pointerBound = false;

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function mountDuel() {
    const card = document.querySelector(".portal-gateway-card");
    if (!card || card.querySelector(".nexus-duel-scene")) return;
    card.classList.add("nexus-duel-host");

    const scene = document.createElement("div");
    scene.className = "nexus-duel-scene";
    scene.setAttribute("aria-hidden", "true");
    const image = document.createElement("img");
    image.src = "/console-assets/nexus-alien-predator.svg";
    image.alt = "";
    image.loading = "eager";
    image.decoding = "async";
    scene.append(image);

    const alien = node("div", "nexus-duel-label nexus-duel-label-alien");
    alien.append(node("span", "", "Alien signal"));
    alien.append(node("small", "", "BIO-MECHANICAL ENTITY"));
    const hunter = node("div", "nexus-duel-label nexus-duel-label-hunter");
    hunter.append(node("span", "", "Predator lock"));
    hunter.append(node("small", "", "ARMORED HUNTER"));
    scene.append(alien, hunter);
    card.prepend(scene);

    const copy = card.querySelector(".portal-gateway-copy");
    if (copy) {
      const kicker = copy.querySelector("span");
      const heading = copy.querySelector("h2");
      const description = copy.querySelector("p");
      if (kicker) kicker.textContent = "XENOMORPH × HUNTER · 3D HOLOSCAPE";
      if (heading) heading.textContent = "We merge worlds.";
      if (description) {
        description.textContent = "A bright 3D alien-versus-hunter scene anchors the Seldrune command nexus.";
      }
    }

    if (!pointerBound && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      pointerBound = true;
      card.addEventListener("pointermove", event => {
        const bounds = card.getBoundingClientRect();
        const x = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width));
        const y = Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height));
        scene.style.setProperty("--nexus-drift-x", ((x - 0.5) * -10).toFixed(1) + "px");
        scene.style.setProperty("--nexus-drift-y", ((y - 0.5) * -7).toFixed(1) + "px");
      });
      card.addEventListener("pointerleave", () => {
        scene.style.setProperty("--nexus-drift-x", "0px");
        scene.style.setProperty("--nexus-drift-y", "0px");
      });
    }
  }

  function mountObservatory() {
    if (observatory) return;
    const panel = document.querySelector("#portal-panel-home");
    const home = panel?.querySelector(".owner-portal-home");
    if (!panel || !home) return;

    observatory = document.createElement("section");
    observatory.id = "nexus-observatory";
    observatory.className = "panel nexus-observatory";
    observatory.setAttribute("aria-labelledby", "nexus-observatory-title");
    observatory.innerHTML = [
      '<div class="nexus-observatory-header"><div>',
      '<p class="eyebrow">SURPRISE SYSTEMS LAYER · LIVE TELEMETRY</p>',
      '<h2 id="nexus-observatory-title">Seldrune Pulse Observatory</h2>',
      '<p>A live readout of the agent fabric and STI runtime, with the next useful workspace one tap away.</p>',
      '</div><span id="nexus-observatory-status" class="nexus-observatory-status" data-state="checking">SIGNAL CHECKING</span></div>',
      '<div class="nexus-observatory-grid">',
      '<article class="nexus-observatory-metric signal-metric"><small>Signal interpretation</small><strong id="nexus-observatory-signal">Reading measured status…</strong></article>',
      '<article class="nexus-observatory-metric"><small>Active agents</small><strong id="nexus-observatory-agents">—</strong></article>',
      '<article class="nexus-observatory-metric"><small>Tasks in flight</small><strong id="nexus-observatory-running">—</strong></article>',
      '<article class="nexus-observatory-metric"><small>Waiting tasks</small><strong id="nexus-observatory-waiting">—</strong></article>',
      '<article class="nexus-observatory-metric"><small>Verified runs</small><strong id="nexus-observatory-verified">—</strong></article>',
      '</div><div class="nexus-observatory-foot"><p id="nexus-observatory-source">Source: Seldrune task ledger and measured STI telemetry.</p>',
      '<button id="nexus-observatory-next" type="button" class="ghost" data-open-portal="intelligence">Inspect agent signal</button>',
      '<button id="nexus-observatory-refresh" type="button" class="ghost">Rescan</button></div>',
    ].join("");
    home.after(observatory);
    observatory.querySelector("#nexus-observatory-refresh").addEventListener("click", () => {
      void refreshPulse();
    });
  }

  function readMetric(id) {
    const text = document.getElementById(id)?.textContent || "";
    const match = text.match(/-?\d+(?:\.\d+)?/);
    return match ? Number(match[0]) : null;
  }

  async function refreshPulse() {
    if (
      refreshing ||
      !observatory ||
      typeof api !== "function" ||
      typeof state === "undefined" ||
      !state.org
    ) return;
    refreshing = true;
    const button = observatory.querySelector("#nexus-observatory-refresh");
    if (button) button.disabled = true;
    try {
      const results = await Promise.all([api("/agents"), api("/tasks")]);
      const agents = Array.isArray(results[0]) ? results[0] : [];
      const tasks = Array.isArray(results[1]) ? results[1] : [];
      const activeAgents = agents.filter(item => item.status === "active").length;
      const runningTasks = tasks.filter(item => item.status === "running").length;
      const waitingTasks = tasks.filter(item => item.status === "queued" || item.status === "assigned").length;
      const failedTasks = tasks.filter(item => item.status === "failed").length;
      const verifiedRuns = readMetric("sti-verified");

      observatory.querySelector("#nexus-observatory-agents").textContent = String(activeAgents);
      observatory.querySelector("#nexus-observatory-running").textContent = String(runningTasks);
      observatory.querySelector("#nexus-observatory-waiting").textContent = String(waitingTasks);
      observatory.querySelector("#nexus-observatory-verified").textContent =
        verifiedRuns === null ? "—" : String(verifiedRuns);

      const runtime = document.querySelector("#runtime-status");
      const degraded = Boolean(runtime?.classList.contains("runtime-degraded"));
      const ready = Boolean(runtime?.classList.contains("runtime-ready"));
      const status = observatory.querySelector("#nexus-observatory-status");
      const signal = observatory.querySelector("#nexus-observatory-signal");
      const next = observatory.querySelector("#nexus-observatory-next");

      if (degraded || failedTasks > 0) {
        status.dataset.state = "attention";
        status.textContent = "ATTENTION SIGNAL";
        signal.textContent = failedTasks
          ? failedTasks + " failed task" + (failedTasks === 1 ? "" : "s") + " need review"
          : "Runtime reports a degraded state";
        next.textContent = "Investigate in Intel";
        next.dataset.openPortal = "intelligence";
      } else if (runningTasks > 0 || waitingTasks > 0) {
        status.dataset.state = "active";
        status.textContent = "MISSION SIGNAL";
        signal.textContent = runningTasks + " running · " + waitingTasks + " waiting";
        next.textContent = "Open agent missions";
        next.dataset.openPortal = "intelligence";
      } else if (ready && activeAgents > 0) {
        status.dataset.state = "stable";
        status.textContent = "SYSTEM RESONANCE";
        signal.textContent = activeAgents + " agent" + (activeAgents === 1 ? "" : "s") + " ready · no tasks waiting";
        next.textContent = "Plan the next mission";
        next.dataset.openPortal = "operator";
      } else if (ready) {
        status.dataset.state = "checking";
        status.textContent = "CONFIGURATION NEEDED";
        signal.textContent = "STI runtime ready · no active agent is configured";
        next.textContent = "Review system tools";
        next.dataset.openPortal = "intelligence";
      } else {
        status.dataset.state = "checking";
        status.textContent = "SIGNAL CHECKING";
        signal.textContent = "Runtime readiness is not confirmed yet";
        next.textContent = "Inspect runtime";
        next.dataset.openPortal = "operations";
      }
      const timestamp = new Date().toLocaleTimeString();
      observatory.querySelector("#nexus-observatory-source").textContent =
        "Source: Seldrune agent/task ledger + STI telemetry · rescanned " + timestamp + ".";
    } catch (error) {
      const status = observatory.querySelector("#nexus-observatory-status");
      status.dataset.state = "attention";
      status.textContent = "SIGNAL UNAVAILABLE";
      observatory.querySelector("#nexus-observatory-signal").textContent =
        "Live agent data unavailable: " + error.message;
      observatory.querySelector("#nexus-observatory-source").textContent =
        "No system state was inferred from missing data. Try Rescan after checking the console session.";
    } finally {
      refreshing = false;
      if (button) button.disabled = false;
    }
  }

  function mount() {
    mountDuel();
    mountObservatory();
  }

  document.addEventListener("seldrune:portal-ready", () => {
    mount();
    void refreshPulse();
  });
  document.addEventListener("seldrune:console-ready", () => {
    mount();
    void refreshPulse();
  });
  document.addEventListener("seldrune:refresh", () => {
    void refreshPulse();
  });
  document.addEventListener("seldrune:workspace-change", event => {
    if (event.detail?.workspace === "home") void refreshPulse();
  });

  if (document.querySelector(".portal-gateway-card")) mount();
  window.setInterval(() => {
    if (document.querySelector("#portal-panel-home.active") && !document.hidden) {
      void refreshPulse();
    }
  }, 30000);
})();
