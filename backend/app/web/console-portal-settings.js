(() => {
  const DEFAULTS = {
    theme: "nebula",
    density: "comfortable",
    motion: "system",
    descriptions: "on",
  };

  const KEYS = {
    theme: "seldrune.portal.theme",
    density: "seldrune.portal.density",
    motion: "seldrune.portal.motion",
    descriptions: "seldrune.portal.descriptions",
  };

  function readPreference(name) {
    return localStorage.getItem(KEYS[name]) || DEFAULTS[name];
  }

  function applyPreferences() {
    const root = document.documentElement;
    root.dataset.portalTheme = readPreference("theme");
    root.dataset.portalDensity = readPreference("density");
    root.dataset.portalMotion = readPreference("motion");
    root.dataset.portalDescriptions = readPreference("descriptions");
  }

  function persist(name, value) {
    localStorage.setItem(KEYS[name], value);
    applyPreferences();
  }

  function initSettings() {
    applyPreferences();

    const host = document.getElementById("portal-settings-content");
    if (!host || host.dataset.initialized === "true") return;
    host.dataset.initialized = "true";

    host.innerHTML = `
      <div class="portal-settings-grid">
        <label class="portal-setting-card">
          <span>Visual atmosphere</span>
          <small>Choose the portal surface without changing application behavior.</small>
          <select id="portal-theme-setting">
            <option value="nebula">Nebula</option>
            <option value="aurora">Aurora</option>
            <option value="void">Void</option>
          </select>
        </label>

        <label class="portal-setting-card">
          <span>Interface density</span>
          <small>Comfortable favors presentation; compact fits more controls on screen.</small>
          <select id="portal-density-setting">
            <option value="comfortable">Comfortable</option>
            <option value="compact">Compact</option>
          </select>
        </label>

        <label class="portal-setting-card">
          <span>Motion</span>
          <small>Respect system preference, keep full motion, or reduce all portal animation.</small>
          <select id="portal-motion-setting">
            <option value="system">Follow device</option>
            <option value="full">Full</option>
            <option value="reduced">Reduced</option>
          </select>
        </label>

        <article class="portal-setting-card">
          <span>Fixed landing page</span>
          <small>Every fresh Owner Console load opens Home for predictable navigation.</small>
          <strong>Home · Locked</strong>
        </article>

        <label class="portal-setting-card portal-setting-toggle">
          <div>
            <span>Workspace descriptions</span>
            <small>Show explanatory text below each portal heading.</small>
          </div>
          <input id="portal-descriptions-setting" type="checkbox">
        </label>

        <article class="portal-setting-card">
          <span>Engineering boundary</span>
          <small>
            Internal version/evolution contracts remain backend-only. They are not part of
            normal owner navigation and do not determine portal layout.
          </small>
          <strong>Owner portal mode · Active</strong>
        </article>

        <article class="portal-setting-card portal-links-card">
          <span>Advanced portals</span>
          <small>Open focused operational views without crowding the main workspace tabs.</small>
          <div class="portal-link-grid">
            <a href="/console-assets/executive-brief.html">Executive brief</a>
            <a href="/console-assets/command-monitor.html">Command monitor</a>
            <a href="/console-assets/organization-board.html">Organization board</a>
            <a href="/console-assets/aetherion.html">Aetherion lab</a>
          </div>
        </article>
      </div>

      <div class="portal-settings-actions">
        <button id="portal-settings-save" type="button">Save portal settings</button>
        <button id="portal-settings-reset" type="button" class="ghost">
          Reset portal settings
        </button>
      </div>
      <p id="portal-settings-status" class="policy-status">
        Preferences are stored in this browser only.
      </p>`;

    const theme = document.getElementById("portal-theme-setting");
    const density = document.getElementById("portal-density-setting");
    const motion = document.getElementById("portal-motion-setting");
    const descriptions = document.getElementById("portal-descriptions-setting");
    const status = document.getElementById("portal-settings-status");

    const syncControls = () => {
      theme.value = readPreference("theme");
      density.value = readPreference("density");
      motion.value = readPreference("motion");
      descriptions.checked = readPreference("descriptions") === "on";
    };
    syncControls();

    [theme, density, motion].forEach(control => {
      control.addEventListener("change", () => {
        const name = control === theme
          ? "theme"
          : control === density
            ? "density"
            : "motion";
        persist(name, control.value);
      });
    });

    descriptions.addEventListener("change", () => {
      persist("descriptions", descriptions.checked ? "on" : "off");
    });

    document.getElementById("portal-settings-save")?.addEventListener("click", () => {
      persist("theme", theme.value);
      persist("density", density.value);
      persist("motion", motion.value);
      persist("descriptions", descriptions.checked ? "on" : "off");
      status.textContent = "Portal settings saved for this browser.";
    });

    document.getElementById("portal-settings-reset")?.addEventListener("click", () => {
      Object.values(KEYS).forEach(key => localStorage.removeItem(key));
      applyPreferences();
      syncControls();
      status.textContent = "Portal settings reset to defaults.";
    });
  }

  applyPreferences();

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initSettings, {once: true});
  } else {
    initSettings();
  }
  document.addEventListener("seldrune:portal-ready", initSettings);
})();