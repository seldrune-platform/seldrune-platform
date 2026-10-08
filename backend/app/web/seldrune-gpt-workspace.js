/* Seldrune GPT header model picker and media capability cards. */
(() => {
  "use strict";

  function moveModelPicker() {
    const select = document.getElementById("seldrune-gpt-provider");
    const actions = document.querySelector("#seldrune-gpt .gpt-top-actions");
    if (!select || !actions) return;
    const label = select.closest("label");
    if (!label || actions.contains(label)) return;
    label.classList.add("gpt-header-model-picker");
    const labelText = label.querySelector("span");
    if (labelText) labelText.textContent = "Model";
    actions.prepend(label);
    const currentLabel = actions.querySelector(".gpt-provider-label");
    if (currentLabel) currentLabel.textContent = "Current";
  }

  function makeMediaPanel() {
    const page = document.querySelector("#seldrune-gpt [data-gpt-page=\"tools\"]");
    const panels = page && page.querySelector(".gpt-tool-panels");
    if (!page || !panels) return null;
    let panel = page.querySelector(".gpt-media-capabilities");
    if (panel) return panel.querySelector(".gpt-media-tool-grid");
    panel = document.createElement("section");
    panel.className = "gpt-media-capabilities";
    panel.setAttribute("aria-labelledby", "seldrune-gpt-media-tools-title");
    const heading = document.createElement("div");
    heading.className = "gpt-media-capabilities-heading";
    const headingCopy = document.createElement("div");
    const title = document.createElement("h3");
    title.id = "seldrune-gpt-media-tools-title";
    title.textContent = "Media tools";
    const description = document.createElement("p");
    description.textContent = "Use image, narration, and document creation from the same Seldrune chat.";
    headingCopy.append(title, description);
    const mediaLink = document.createElement("a");
    mediaLink.className = "gpt-top-tool-button";
    mediaLink.href = "/media";
    mediaLink.textContent = "Open Media Studio";
    heading.append(headingCopy, mediaLink);
    const grid = document.createElement("div");
    grid.className = "gpt-media-tool-grid";
    grid.id = "seldrune-gpt-media-tool-grid";
    const note = document.createElement("p");
    note.className = "gpt-media-action-note";
    note.textContent = "Chat requests for connected actions are routed through Seldrune’s operator. High-impact actions still require owner confirmation.";
    panel.append(heading, grid, note);
    panels.insertAdjacentElement("afterend", panel);
    return grid;
  }

  function showConnections(provider) {
    window.seldrunePortal?.activate?.("connections");
    window.setTimeout(() => {
      window.seldruneConnections?.selectProvider?.(provider);
    }, 150);
  }

  function beginMode(mode, needsSetup) {
    if (needsSetup) {
      showConnections("openai");
      return;
    }
    if (typeof window.seldruneGPT?.setCreationMode === "function") {
      window.seldruneGPT.setCreationMode(mode);
    }
    document.querySelector("#seldrune-gpt [data-gpt-view=\"chat\"]")?.click();
    window.setTimeout(() => document.getElementById("seldrune-gpt-input")?.focus(), 0);
  }

  function renderMediaTools(eventDetail) {
    const grid = makeMediaPanel();
    if (!grid) return;
    grid.replaceChildren();

    const caps = eventDetail && eventDetail.capabilities;
    const policy = caps && caps.cost_policy || {};
    const openai = Array.isArray(caps && caps.model_providers)
      ? caps.model_providers.find(item => item && item.provider === "openai")
      : null;
    const openaiReady = Boolean(openai && openai.configured === true);
    const imageReady = Boolean(policy.image && policy.image.available === true && openaiReady);
    const speechReady = Boolean(policy.speech && policy.speech.available === true && openaiReady);
    const videoReady = Boolean(policy.video && policy.video.available === true);
    const definitions = [
      {
        mode: "image",
        title: "Image generation",
        ready: imageReady,
        state: eventDetail && eventDetail.error ? "Status unavailable" : (!policy.image || policy.image.available !== true ? "Unavailable" : (imageReady ? "Ready" : "Connect OpenAI")),
        detail: eventDetail && eventDetail.error
          ? "Capability status could not be loaded. Refresh Seldrune and check Connections."
          : (!policy.image || policy.image.available !== true
            ? "Image generation is not enabled on this Seldrune server."
            : (imageReady
              ? "Create an image in chat" + (policy.image.model ? " · " + policy.image.model : "")
              : "Connect OpenAI in Seldrune Connections to enable image creation.")),
        setup: Boolean(policy.image && policy.image.available === true && !imageReady && !eventDetail?.error),
      },
      {
        mode: "speech",
        title: "Spoken audio",
        ready: speechReady,
        state: eventDetail && eventDetail.error ? "Status unavailable" : (!policy.speech || policy.speech.available !== true ? "Unavailable" : (speechReady ? "Ready" : "Connect OpenAI")),
        detail: eventDetail && eventDetail.error
          ? "Capability status could not be loaded. Refresh Seldrune and check Connections."
          : (!policy.speech || policy.speech.available !== true
            ? "Spoken audio is not enabled on this Seldrune server."
            : (speechReady
              ? "Create narration in chat" + (policy.speech.model ? " · " + policy.speech.model : "")
              : "Connect OpenAI in Seldrune Connections to enable narration.")),
        setup: Boolean(policy.speech && policy.speech.available === true && !speechReady && !eventDetail?.error),
      },
      {
        mode: "document",
        title: "PDF documents",
        ready: true,
        state: "Ready",
        detail: "Create a document and save the rendered PDF in Outputs.",
        setup: false,
      },
      {
        mode: "video",
        title: "Video",
        ready: videoReady,
        state: videoReady ? "Ready" : "Not connected",
        detail: videoReady
          ? "Video creation is available."
          : (policy.video && policy.video.configuration_hint || "Seldrune has no video renderer connected yet."),
        setup: false,
      },
    ];

    definitions.forEach(item => {
      const card = document.createElement("article");
      card.className = "gpt-media-tool-card";
      const title = document.createElement("strong");
      title.textContent = item.title;
      const state = document.createElement("span");
      state.className = "gpt-media-tool-state";
      state.dataset.state = item.ready ? "ready" : (item.setup ? "setup" : "off");
      state.textContent = item.state;
      const detail = document.createElement("small");
      detail.textContent = item.detail;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "gpt-media-tool-action";
      button.textContent = item.setup ? "Connect OpenAI" : (item.ready ? "Use in chat" : "Unavailable");
      button.disabled = !item.ready && !item.setup;
      button.addEventListener("click", () => beginMode(item.mode, item.setup));
      card.append(title, state, detail, button);
      grid.append(card);
    });
  }

  function init() {
    moveModelPicker();
    makeMediaPanel();
    document.addEventListener("seldrune:gpt-capabilities-ready", event => {
      renderMediaTools(event.detail || {});
    });
    if (window.seldruneGPTCapabilities) {
      renderMediaTools({capabilities: window.seldruneGPTCapabilities});
    } else if (window.seldruneGPTCapabilitiesError) {
      renderMediaTools({error: window.seldruneGPTCapabilitiesError});
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, {once: true});
  } else {
    init();
  }
})();
