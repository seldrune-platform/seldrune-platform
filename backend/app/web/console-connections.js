(() => {
  let host;
  let requestPromise = null;
  let modelProviders = [];
  let externalProviders = [];
  let loadedAt = 0;

  const MODEL_PROVIDERS = new Set(["openai", "gemini", "anthropic"]);
  const INTEGRATIONS = {
    openai: {
      label: "OpenAI",
      kind: "model",
      help: "Use an OpenAI API key. Billing is managed by OpenAI; an account password or ChatGPT subscription is not an API key.",
    },
    gemini: {
      label: "Google Gemini",
      kind: "model",
      help: "Use a Google Gemini API key. Billing is managed by Google; never paste your Google account password.",
    },
    anthropic: {
      label: "Anthropic",
      kind: "model",
      help: "Use an Anthropic API key. Billing is managed by Anthropic; never paste your account password.",
    },
    github: {
      label: "GitHub",
      kind: "external",
      help: "Use a fine-grained GitHub token or GitHub App credential with only the repository permissions you need.",
    },
    gmail: {
      label: "Gmail",
      kind: "external",
      help: "Use a Google OAuth access token with the Gmail scope, not your Gmail password. Tokens may expire.",
    },
    render: {
      label: "Render",
      kind: "external",
      help: "Use a Render API key with the smallest access scope required.",
    },
  };

  function isConnectionsActive() {
    return Boolean(document.querySelector("#portal-panel-connections.active"));
  }

  function createPanel() {
    if (!host || host.querySelector("#integration-center")) return;
    const panel = document.createElement("section");
    panel.id = "integration-center";
    panel.className = "panel integration-center";
    panel.innerHTML =
      '<div class="integration-center-head"><div>' +
        '<p class="eyebrow">SELDRUNE CONNECTION CENTER</p>' +
        '<h2>Integrations</h2>' +
        '<p>One place for verified AI, code, email, and deployment connections. Seldrune stores supported credentials in the encrypted organization vault and shows only provider status.</p>' +
      '</div><button id="integration-refresh" type="button" class="ghost">Refresh status</button></div>' +
      '<div class="integration-section-head"><div><p class="eyebrow">EXTERNAL SERVICES</p><h3>Connected providers</h3></div><span id="integration-count" class="integration-count">Checking</span></div>' +
      '<div id="integration-list" class="integration-list" aria-live="polite"><div class="empty">Loading supported providers…</div></div>' +
      '<form id="integration-credential-form" class="integration-form">' +
        '<div><p class="eyebrow">ONE SECURE ADAPTOR</p><h3>Connect or rotate a credential</h3></div>' +
        '<label>Service<select id="integration-provider" required>' +
          '<optgroup label="AI model providers"><option value="openai">OpenAI API</option><option value="gemini">Google Gemini API</option><option value="anthropic">Anthropic API</option></optgroup>' +
          '<optgroup label="Code, email, and deploy"><option value="github">GitHub</option><option value="gmail">Gmail</option><option value="render">Render</option></optgroup>' +
        '</select></label>' +
        '<label>Credential<input id="integration-key" type="password" required minlength="8" maxlength="20000" autocomplete="new-password" spellcheck="false" placeholder="Paste a provider API key or token"></label>' +
        '<div class="integration-form-actions"><button id="integration-save" type="submit">Verify and connect</button><button id="integration-toggle" type="button" class="ghost">Show</button></div>' +
        '<p id="integration-key-message" role="status" aria-live="polite">Seldrune makes a read-only model-list request before saving AI keys. Do not enter your account password. Credentials are encrypted in the organization vault and never shown again.</p>' +
      '</form>' +
      '<section class="integration-capabilities" aria-labelledby="integration-capabilities-title">' +
        '<div><p class="eyebrow">BUILT-IN CREATION WORKSPACES</p><h3 id="integration-capabilities-title">Open a studio</h3></div>' +
        '<div class="integration-capability-grid">' +
          '<button class="integration-capability" type="button" data-open-portal="operator"><span><strong>AI creation</strong><small>Prompts, projects, and supported actions</small></span><b>→</b></button>' +
          '<button class="integration-capability" type="button" data-open-portal="coding"><span><strong>Coding Lab</strong><small>Build, test, and inspect connected CI</small></span><b>→</b></button>' +
          '<button class="integration-capability" type="button" data-open-portal="media"><span><strong>Media Studio</strong><small>Face and LiveShift workflows</small></span><b>→</b></button>' +
          '<button class="integration-capability" type="button" data-open-portal="outputs"><span><strong>Output library</strong><small>Find and download created files</small></span><b>→</b></button>' +
        '</div>' +
      '</section>' +
      '<p class="integration-center-note">Creation workspaces use the providers connected above and the tools available in this deployment. A provider is shown as ready only when Seldrune reports usable access; unsupported media rendering is not marked as installed.</p>';
    host.prepend(panel);

    panel.querySelector("#integration-refresh").addEventListener("click", () => refreshStatus(true));
    panel.querySelector("#integration-credential-form").addEventListener("submit", saveCredential);
    panel.querySelector("#integration-provider").addEventListener("change", updateCredentialHelp);
    panel.querySelector("#integration-toggle").addEventListener("click", toggleCredentialVisibility);
    panel.querySelector("#integration-list").addEventListener("click", handleProviderAction);
  }

  function mount() {
    host = document.querySelector("#portal-panel-connections .owner-portal-grid");
    if (!host) return;
    createPanel();
  }

  function updateCredentialHelp() {
    const provider = document.querySelector("#integration-provider")?.value;
    const config = INTEGRATIONS[provider];
    const message = document.querySelector("#integration-key-message");
    const input = document.querySelector("#integration-key");
    if (message && config) {
      message.textContent = config.help + " Seldrune verifies access before encrypting the credential.";
    }
    if (input && config) {
      input.placeholder = config.kind === "model" ? "Paste the provider API key" : "Paste the provider token or API key";
    }
  }

  function makeState(text, state) {
    const badge = document.createElement("span");
    badge.className = "integration-state is-" + state;
    badge.textContent = text;
    return badge;
  }

  function makeProviderCard(provider, kind) {
    const card = document.createElement("article");
    card.className = "integration-card";

    const head = document.createElement("div");
    head.className = "integration-card-head";
    const name = document.createElement("strong");
    name.textContent = provider.label || INTEGRATIONS[provider.provider]?.label || provider.provider;
    const configured = kind === "model"
      ? Boolean(provider.configured)
      : Boolean(provider.secret_available);
    const ready = kind === "model"
      ? configured
      : Boolean(provider.ready);
    const state = ready
      ? makeState(kind === "model" ? "Connected" : "Ready", "ready")
      : configured
        ? makeState("Connected · setup incomplete", "partial")
        : makeState("Not connected", "missing");
    head.append(name, state);
    card.append(head);

    const detail = document.createElement("p");
    if (kind === "model") {
      detail.textContent =
        (provider.model ? "Model: " + provider.model + ". " : "") +
        (provider.text_only ? "Text chat." : "Model capabilities depend on the selected provider.");
    } else {
      const actions = provider.actions || [];
      const readyActions = actions.filter(action => action.ready).length;
      detail.textContent = provider.secret_available
        ? readyActions + "/" + actions.length + " supported actions ready."
        : actions.length + " supported actions available after connecting.";
    }
    card.append(detail);

    if (kind === "external" && Array.isArray(provider.actions) && provider.actions.length) {
      const capabilities = document.createElement("details");
      const summary = document.createElement("summary");
      summary.textContent = "Supported actions";
      const list = document.createElement("ul");
      provider.actions.forEach(action => {
        const item = document.createElement("li");
        item.textContent = action.name || action.action_name;
        list.append(item);
      });
      capabilities.append(summary, list);
      card.append(capabilities);
    }

    const actions = document.createElement("div");
    actions.className = "integration-card-actions";
    const connect = document.createElement("button");
    connect.type = "button";
    connect.dataset.integrationConnect = provider.provider;
    const vaultManaged = kind === "model"
      ? provider.source === "vault"
      : Boolean(provider.reference_id);
    connect.textContent = vaultManaged
      ? "Replace key"
      : configured
        ? "Add vault key"
        : "Connect";
    actions.append(connect);

    if (vaultManaged) {
      const disconnect = document.createElement("button");
      disconnect.type = "button";
      disconnect.className = "ghost";
      if (kind === "model") disconnect.dataset.disconnectModel = provider.provider;
      else disconnect.dataset.disconnectIntegration = provider.provider;
      disconnect.textContent = "Disconnect";
      actions.append(disconnect);
    }
    card.append(actions);
    return card;
  }

  function renderProviders() {
    const list = document.querySelector("#integration-list");
    const count = document.querySelector("#integration-count");
    if (!list) return;
    list.replaceChildren();

    let visible = 0;
    modelProviders.filter(item => MODEL_PROVIDERS.has(item.provider)).forEach(provider => {
      list.append(makeProviderCard(provider, "model"));
      visible += 1;
    });
    externalProviders.forEach(provider => {
      list.append(makeProviderCard(provider, "external"));
      visible += 1;
    });
    if (count) count.textContent = visible + " supported";
    if (!visible) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = "No supported providers were returned.";
      list.append(empty);
    }
  }

  async function refreshStatus(force = false) {
    const list = document.querySelector("#integration-list");
    if (!list) return;
    if (requestPromise) return requestPromise;
    if (!force && Date.now() - loadedAt < 30000 && (modelProviders.length || externalProviders.length)) {
      renderProviders();
      return;
    }

    requestPromise = (async () => {
      list.innerHTML = '<div class="empty">Checking connected providers…</div>';
      try {
        let toolStatus;
        if (window.seldruneTools?.refresh) {
          await window.seldruneTools.refresh();
          toolStatus = window.seldruneTools.getStatus?.();
        } else {
          toolStatus = await api("/tool-bootstrap/status");
        }
        const modelStatus = await api("/model-provider-connections");
        modelProviders = modelStatus.providers || [];
        externalProviders = toolStatus?.providers || [];
        loadedAt = Date.now();
        renderProviders();
      } catch (error) {
        list.replaceChildren();
        const empty = document.createElement("div");
        empty.className = "empty";
        empty.textContent = "Connection status unavailable: " + error.message;
        list.append(empty);
      }
    })();
    try {
      await requestPromise;
    } finally {
      requestPromise = null;
    }
  }

  function selectProvider(provider) {
    const select = document.querySelector("#integration-provider");
    const input = document.querySelector("#integration-key");
    select.value = provider;
    updateCredentialHelp();
    document.querySelector("#integration-credential-form")
      ?.scrollIntoView({behavior: "smooth", block: "center"});
    input?.focus({preventScroll: true});
  }

  async function handleProviderAction(event) {
    const connect = event.target.closest("[data-integration-connect]");
    if (connect) {
      selectProvider(connect.dataset.integrationConnect);
      return;
    }

    const modelDisconnect = event.target.closest("[data-disconnect-model]");
    const externalDisconnect = event.target.closest("[data-disconnect-integration]");
    if (!modelDisconnect && !externalDisconnect) return;
    const provider = (modelDisconnect || externalDisconnect).dataset.disconnectModel
      || (modelDisconnect || externalDisconnect).dataset.disconnectIntegration;
    if (!window.confirm("Disconnect " + provider + " from the Seldrune vault? This does not revoke the provider credential.")) return;

    const button = modelDisconnect || externalDisconnect;
    button.disabled = true;
    try {
      if (modelDisconnect) {
        await api("/model-provider-connections/" + encodeURIComponent(provider), {method: "DELETE"});
      } else {
        await api("/tool-bootstrap/credentials/" + encodeURIComponent(provider), {method: "DELETE"});
        await window.seldruneTools?.refresh();
      }
      const message = document.querySelector("#integration-key-message");
      if (message) message.textContent = provider + " disconnected from Seldrune.";
      loadedAt = 0;
      await refreshStatus(true);
    } catch (error) {
      button.disabled = false;
      const message = document.querySelector("#integration-key-message");
      if (message) message.textContent = "Could not disconnect: " + error.message;
    }
  }

  async function saveCredential(event) {
    event.preventDefault();
    const provider = document.querySelector("#integration-provider")?.value;
    const input = document.querySelector("#integration-key");
    const button = document.querySelector("#integration-save");
    const message = document.querySelector("#integration-key-message");
    const secret = input?.value || "";
    if (!provider || !INTEGRATIONS[provider] || !secret) return;

    button.disabled = true;
    message.textContent = "Verifying " + INTEGRATIONS[provider].label + " access…";
    try {
      if (MODEL_PROVIDERS.has(provider)) {
        await api("/model-provider-connections/" + encodeURIComponent(provider), {
          method: "POST",
          body: JSON.stringify({secret_value: secret}),
        });
      } else {
        await api("/tool-bootstrap/credentials/verified", {
          method: "POST",
          body: JSON.stringify({provider, secret_value: secret}),
        });
      }
      input.value = "";
      input.type = "password";
      document.querySelector("#integration-toggle").textContent = "Show";
      message.textContent = INTEGRATIONS[provider].label + " verified and connected. The credential is encrypted in Seldrune.";
      loadedAt = 0;
      if (!MODEL_PROVIDERS.has(provider)) await window.seldruneTools?.refresh();
      await refreshStatus(true);
    } catch (error) {
      message.textContent = "Credential not saved: " + error.message;
    } finally {
      if (input) input.value = "";
      input.type = "password";
      document.querySelector("#integration-toggle").textContent = "Show";
      button.disabled = false;
    }
  }

  function toggleCredentialVisibility(event) {
    const input = document.querySelector("#integration-key");
    if (!input) return;
    const reveal = input.type === "password";
    input.type = reveal ? "text" : "password";
    event.currentTarget.textContent = reveal ? "Hide" : "Show";
  }

  document.addEventListener("seldrune:portal-ready", mount);
  document.addEventListener("seldrune:console-ready", () => {
    mount();
    if (isConnectionsActive()) void refreshStatus();
  });
  document.addEventListener("seldrune:workspace-change", event => {
    if (event.detail?.workspace === "connections") void refreshStatus();
  });
  document.addEventListener("seldrune:tool-status-updated", () => {
    const snapshot = window.seldruneTools?.getStatus?.();
    externalProviders = snapshot?.providers || externalProviders;
    if (isConnectionsActive()) renderProviders();
  });
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount, {once: true});
  } else {
    mount();
  }
})();
