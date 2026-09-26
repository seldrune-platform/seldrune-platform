(() => {
  let host;
  let refreshTimer;

  function createPanel() {
    if (!host || host.querySelector("#model-provider-connection-panel")) return;
    const panel = document.createElement("section");
    panel.id = "model-provider-connection-panel";
    panel.className = "panel model-provider-connection-panel";
    panel.innerHTML =
      '<div class="connection-center-head"><div>' +
        '<p class="eyebrow">SELDRUNE CONNECTION CENTER</p>' +
        '<h2>AI providers</h2>' +
        '<p>Connect an API key once, verify it, and use that provider from Seldrune GPT. ' +
        'Keys are encrypted in the organization vault and never shown again.</p>' +
      '</div><button id="model-provider-refresh" type="button" class="ghost">Refresh status</button></div>' +
      '<div id="model-provider-connection-list" class="model-provider-connection-list" aria-live="polite">' +
        '<div class="empty">Loading AI connection status…</div>' +
      '</div>' +
      '<form id="model-provider-key-form" class="model-provider-key-form">' +
        '<div><p class="eyebrow">ADD OR ROTATE A KEY</p><h3>Connect an AI provider</h3></div>' +
        '<label>Provider<select id="model-provider-key-provider" required>' +
          '<option value="openai">OpenAI API</option>' +
          '<option value="gemini">Google Gemini API</option>' +
          '<option value="anthropic">Anthropic API</option>' +
        '</select></label>' +
        '<label>API key<input id="model-provider-key-value" type="password" required minlength="8" ' +
          'maxlength="20000" autocomplete="new-password" spellcheck="false" ' +
          'placeholder="Paste the provider API key"></label>' +
        '<div class="model-provider-key-actions">' +
          '<button id="model-provider-key-save" type="submit">Verify &amp; save encrypted key</button>' +
          '<button id="model-provider-key-toggle" type="button" class="ghost">Show</button>' +
        '</div>' +
        '<p id="model-provider-key-message" role="status" aria-live="polite">' +
          'Seldrune makes a read-only model-list request before saving. Do not enter your account password.' +
        '</p>' +
      '</form>' +
      '<p class="connection-center-note">API billing remains with each provider. A ChatGPT subscription password ' +
      'does not work as an API key. OpenAI, Gemini, and Anthropic connections in this release are for text chat; ' +
      'attachment support depends on the selected provider.</p>';
    host.prepend(panel);

    panel.querySelector("#model-provider-refresh")
      .addEventListener("click", refreshStatus);
    panel.querySelector("#model-provider-key-form")
      .addEventListener("submit", saveKey);
    panel.querySelector("#model-provider-key-toggle")
      .addEventListener("click", toggleKeyVisibility);
    panel.querySelector("#model-provider-connection-list")
      .addEventListener("click", handleProviderAction);
  }

  function mount() {
    host = document.querySelector("#portal-panel-connections .owner-portal-grid");
    if (!host) return;
    createPanel();
  }

  function renderProviders(providers) {
    const list = document.querySelector("#model-provider-connection-list");
    if (!list) return;
    list.replaceChildren();

    providers.forEach(provider => {
      const card = document.createElement("article");
      card.className = "model-provider-connection-card";
      card.dataset.configured = String(Boolean(provider.configured));

      const heading = document.createElement("div");
      heading.className = "model-provider-connection-heading";
      const title = document.createElement("strong");
      title.textContent = provider.label;
      const state = document.createElement("span");
      state.className = provider.configured
        ? "model-provider-state is-connected"
        : "model-provider-state is-disconnected";
      state.textContent = provider.configured
        ? (provider.source === "vault" ? "Connected · Seldrune Vault" : "Connected · server setting")
        : "Not connected";
      heading.append(title, state);

      const model = document.createElement("small");
      model.textContent = "Default model: " + (provider.model || "not selected");
      const capability = document.createElement("p");
      capability.textContent = provider.text_only
        ? "Text chat. Images and files are not available through this connection yet."
        : "Text and supported media chat.";

      const actions = document.createElement("div");
      actions.className = "model-provider-card-actions";
      const connect = document.createElement("button");
      connect.type = "button";
      connect.dataset.connectProvider = provider.provider;
      connect.textContent = provider.source === "vault"
        ? "Rotate key"
        : provider.configured
          ? "Add vault key"
          : "Connect";
      actions.append(connect);

      if (provider.source === "vault") {
        const disconnect = document.createElement("button");
        disconnect.type = "button";
        disconnect.className = "ghost";
        disconnect.dataset.disconnectProvider = provider.provider;
        disconnect.textContent = "Disconnect";
        actions.append(disconnect);
      }

      card.append(heading, model, capability, actions);
      list.append(card);
    });

    if (!providers.length) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = "No model providers are listed.";
      list.append(empty);
    }
  }

  async function refreshStatus() {
    const list = document.querySelector("#model-provider-connection-list");
    if (!list) return;
    try {
      const result = await api("/model-provider-connections");
      renderProviders(result.providers || []);
    } catch (error) {
      list.replaceChildren();
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = "Connection status unavailable: " + error.message;
      list.append(empty);
    }
  }

  function selectProvider(provider) {
    const select = document.querySelector("#model-provider-key-provider");
    const input = document.querySelector("#model-provider-key-value");
    const message = document.querySelector("#model-provider-key-message");
    if (select) select.value = provider;
    if (message) message.textContent =
      "Paste the " + provider + " API key. Seldrune will verify access before saving it.";
    document.querySelector("#model-provider-key-form")
      ?.scrollIntoView({behavior: "smooth", block: "center"});
    input?.focus({preventScroll: true});
  }

  async function handleProviderAction(event) {
    const connect = event.target.closest("[data-connect-provider]");
    if (connect) {
      selectProvider(connect.dataset.connectProvider);
      return;
    }
    const disconnect = event.target.closest("[data-disconnect-provider]");
    if (!disconnect) return;
    const provider = disconnect.dataset.disconnectProvider;
    if (!window.confirm(
      "Remove " + provider + " from the Seldrune vault? This does not revoke the key at the provider."
    )) return;

    disconnect.disabled = true;
    try {
      const result = await api(
        "/model-provider-connections/" + encodeURIComponent(provider),
        {method: "DELETE"}
      );
      const message = document.querySelector("#model-provider-key-message");
      if (message) message.textContent = result.detail || "Saved key removed.";
      await refreshStatus();
    } catch (error) {
      disconnect.disabled = false;
      const message = document.querySelector("#model-provider-key-message");
      if (message) message.textContent = "Could not disconnect: " + error.message;
    }
  }

  async function saveKey(event) {
    event.preventDefault();
    const select = document.querySelector("#model-provider-key-provider");
    const input = document.querySelector("#model-provider-key-value");
    const button = document.querySelector("#model-provider-key-save");
    const message = document.querySelector("#model-provider-key-message");
    const provider = select?.value;
    const secret = input?.value || "";
    if (!provider || !secret) return;

    button.disabled = true;
    message.textContent = "Verifying access, then saving the encrypted key…";
    try {
      const result = await api(
        "/model-provider-connections/" + encodeURIComponent(provider),
        {method: "POST", body: JSON.stringify({secret_value: secret})}
      );
      const verification = result.verification || {};
      const identity = verification.identity || {};
      const modelCount = identity.models_available;
      message.textContent = (verification.detail || "Provider access verified.")
        + (Number.isInteger(modelCount) ? " Models listed: " + modelCount + "." : "")
        + " Key encrypted in Seldrune.";
      await refreshStatus();
    } catch (error) {
      message.textContent = "Key not saved: " + error.message;
    } finally {
      input.value = "";
      input.type = "password";
      document.querySelector("#model-provider-key-toggle").textContent = "Show";
      button.disabled = false;
    }
  }

  function toggleKeyVisibility(event) {
    const input = document.querySelector("#model-provider-key-value");
    if (!input) return;
    const reveal = input.type === "password";
    input.type = reveal ? "text" : "password";
    event.currentTarget.textContent = reveal ? "Hide" : "Show";
  }

  document.addEventListener("seldrune:portal-ready", mount);
  document.addEventListener("seldrune:console-ready", () => {
    mount();
    refreshStatus();
    if (!refreshTimer) {
      refreshTimer = window.setInterval(() => {
        if (!document.hidden) refreshStatus();
      }, 60000);
    }
  });
  document.addEventListener("seldrune:workspace-change", event => {
    if (event.detail?.workspace === "connections") refreshStatus();
  });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) refreshStatus();
  });
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount, {once: true});
  } else {
    mount();
  }
})();
