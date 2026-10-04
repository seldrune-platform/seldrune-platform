(() => {
  const PREFS = {
    background: "seldrune.appearance.background",
    shade: "seldrune.appearance.shade.v2",
    font: "seldrune.appearance.font",
  };
  const DB_NAME = "seldrune-appearance";
  const DB_STORE = "images";
  const DB_KEY = "custom-background";
  const DEFAULTS = {background: "celestial", shade: 0, font: "modern"};
  const root = document.documentElement;
  let customUrl = "";
  let customAvailable = false;
  let initialized = false;

  function readPreference(name) {
    try {
      const value = localStorage.getItem(PREFS[name]);
      return value === null ? DEFAULTS[name] : value;
    } catch {
      return DEFAULTS[name];
    }
  }

  function writePreference(name, value) {
    try {
      localStorage.setItem(PREFS[name], String(value));
    } catch {
      setStatus("Your browser applied this choice for now, but blocked saving it.");
    }
  }

  function applyPreferences() {
    const background = readPreference("background");
    const shade = Math.max(0, Math.min(28, Number(readPreference("shade")) || 0));
    const font = readPreference("font");
    root.dataset.seldruneBackground = background;
    root.dataset.seldruneFont = font;
    if (document.body) {
      document.body.style.setProperty("--seldrune-background-shade", String(shade / 100));
    }
  }

  function openDatabase() {
    return new Promise((resolve, reject) => {
      if (!("indexedDB" in window)) {
        reject(new Error("Image storage is unavailable in this browser."));
        return;
      }
      const request = indexedDB.open(DB_NAME, 1);
      request.onupgradeneeded = () => {
        if (!request.result.objectStoreNames.contains(DB_STORE)) {
          request.result.createObjectStore(DB_STORE);
        }
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error || new Error("Could not open image storage."));
      request.onblocked = () => reject(new Error("Image storage is busy. Reload this page and try again."));
    });
  }

  async function readCustomImage() {
    const db = await openDatabase();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(DB_STORE, "readonly");
      const request = transaction.objectStore(DB_STORE).get(DB_KEY);
      request.onsuccess = () => resolve(request.result || null);
      request.onerror = () => reject(request.error || new Error("Could not read the saved image."));
      transaction.oncomplete = () => db.close();
      transaction.onerror = () => {
        db.close();
        reject(transaction.error || new Error("Could not read the saved image."));
      };
    });
  }

  async function writeCustomImage(blob) {
    const db = await openDatabase();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(DB_STORE, "readwrite");
      transaction.objectStore(DB_STORE).put(blob, DB_KEY);
      transaction.oncomplete = () => {
        db.close();
        resolve();
      };
      transaction.onerror = () => {
        db.close();
        reject(transaction.error || new Error("Could not save the image."));
      };
      transaction.onabort = () => {
        db.close();
        reject(transaction.error || new Error("Image saving was cancelled."));
      };
    });
  }

  async function removeCustomImage() {
    const db = await openDatabase();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(DB_STORE, "readwrite");
      transaction.objectStore(DB_STORE).delete(DB_KEY);
      transaction.oncomplete = () => {
        db.close();
        resolve();
      };
      transaction.onerror = () => {
        db.close();
        reject(transaction.error || new Error("Could not remove the saved image."));
      };
    });
  }

  function setCustomBackground(blob) {
    if (customUrl) URL.revokeObjectURL(customUrl);
    customUrl = URL.createObjectURL(blob);
    customAvailable = true;
    if (document.body) {
      document.body.style.setProperty("--seldrune-custom-art", 'url("' + customUrl + '")');
    }
    updateControls();
  }

  async function restoreCustomBackground() {
    try {
      const blob = await readCustomImage();
      if (blob) {
        setCustomBackground(blob);
      } else if (readPreference("background") === "custom") {
        writePreference("background", "celestial");
        applyPreferences();
      }
    } catch {
      if (readPreference("background") === "custom") {
        writePreference("background", "celestial");
        applyPreferences();
      }
    }
  }

  function setStatus(message) {
    const status = document.getElementById("seldrune-appearance-status");
    if (status) status.textContent = message;
  }

  function updateControls() {
    document.querySelectorAll("[data-background-choice]").forEach(button => {
      const selected = button.dataset.backgroundChoice === readPreference("background");
      button.setAttribute("aria-pressed", selected ? "true" : "false");
      if (button.dataset.backgroundChoice === "custom") {
        button.disabled = !customAvailable;
        button.setAttribute("aria-label", customAvailable
          ? "Use uploaded custom background"
          : "Upload an image to enable the custom background");
      }
    });
    const shade = document.getElementById("seldrune-background-shade");
    const shadeOutput = document.getElementById("seldrune-background-shade-value");
    const font = document.getElementById("seldrune-font-choice");
    if (shade) shade.value = readPreference("shade");
    if (shadeOutput) shadeOutput.value = readPreference("shade") + "%";
    if (font) font.value = readPreference("font");
  }

  function addAppearancePanel() {
    const grid = document.querySelector("#portal-panel-settings .owner-portal-grid");
    if (!grid || document.getElementById("seldrune-appearance-settings")) return;

    const panel = document.createElement("section");
    panel.id = "seldrune-appearance-settings";
    panel.className = "panel";
    panel.setAttribute("aria-labelledby", "seldrune-appearance-title");
    panel.innerHTML =
      '<div class="seldrune-appearance-heading">' +
        '<p class="eyebrow">YOUR LOOK · ALL WORKSPACES</p>' +
        '<h2 id="seldrune-appearance-title">Background &amp; style</h2>' +
        '<p>Choose a crisp full-screen design. Your choice follows you across every workspace on this device.</p>' +
      '</div>' +
      '<div class="seldrune-background-options" role="group" aria-label="Background design">' +
        '<button class="seldrune-background-option" type="button" data-background-choice="celestial" aria-pressed="false">' +
          '<span class="seldrune-background-preview seldrune-preview-celestial" aria-hidden="true"></span>' +
          '<span class="seldrune-background-option-copy"><strong>Celestial</strong><small>Seldrune world artwork</small></span><span class="seldrune-background-check" aria-hidden="true">✓</span>' +
        '</button>' +
        '<button class="seldrune-background-option" type="button" data-background-choice="aurora" aria-pressed="false">' +
          '<span class="seldrune-background-preview seldrune-preview-aurora" aria-hidden="true"></span>' +
          '<span class="seldrune-background-option-copy"><strong>Aurora</strong><small>Emerald and violet light</small></span><span class="seldrune-background-check" aria-hidden="true">✓</span>' +
        '</button>' +
        '<button class="seldrune-background-option" type="button" data-background-choice="nebula" aria-pressed="false">' +
          '<span class="seldrune-background-preview seldrune-preview-nebula" aria-hidden="true"></span>' +
          '<span class="seldrune-background-option-copy"><strong>Nebula</strong><small>Violet cosmic gradients</small></span><span class="seldrune-background-check" aria-hidden="true">✓</span>' +
        '</button>' +
        '<button class="seldrune-background-option" type="button" data-background-choice="ocean" aria-pressed="false">' +
          '<span class="seldrune-background-preview seldrune-preview-ocean" aria-hidden="true"></span>' +
          '<span class="seldrune-background-option-copy"><strong>Deep ocean</strong><small>Blue, teal, and midnight</small></span><span class="seldrune-background-check" aria-hidden="true">✓</span>' +
        '</button>' +
        '<button class="seldrune-background-option" type="button" data-background-choice="eclipse" aria-pressed="false">' +
          '<span class="seldrune-background-preview seldrune-preview-eclipse" aria-hidden="true"></span>' +
          '<span class="seldrune-background-option-copy"><strong>Eclipse</strong><small>Quiet silver and indigo</small></span><span class="seldrune-background-check" aria-hidden="true">✓</span>' +
        '</button>' +
        '<button class="seldrune-background-option" type="button" data-background-choice="custom" aria-pressed="false">' +
          '<span class="seldrune-background-preview seldrune-preview-custom" aria-hidden="true"></span>' +
          '<span class="seldrune-background-option-copy"><strong>My image</strong><small>Use your uploaded picture</small></span><span class="seldrune-background-check" aria-hidden="true">✓</span>' +
        '</button>' +
      '</div>' +
      '<div class="seldrune-appearance-controls">' +
        '<label class="seldrune-appearance-control" for="seldrune-background-shade">' +
          '<span>Background visibility</span>' +
          '<small>Lower shade shows more of the artwork; the default shows the artwork at full brightness.</small>' +
          '<span class="seldrune-shade-row"><input id="seldrune-background-shade" type="range" min="0" max="28" step="1"><output id="seldrune-background-shade-value" for="seldrune-background-shade">0%</output></span>' +
        '</label>' +
        '<label class="seldrune-appearance-control" for="seldrune-font-choice">' +
          '<span>Typography</span>' +
          '<small>Choose the text style used throughout the portal.</small>' +
          '<select id="seldrune-font-choice"><option value="modern">Modern clean</option><option value="humanist">Warm humanist</option><option value="editorial">Editorial headings</option></select>' +
        '</label>' +
      '</div>' +
      '<div class="seldrune-custom-image-actions">' +
        '<label class="seldrune-image-file-label">Add a custom background image ' +
          '<input id="seldrune-background-file" type="file" accept="image/*" aria-label="Choose a custom background image">' +
        '</label>' +
        '<button class="seldrune-appearance-reset" id="seldrune-appearance-reset" type="button">Reset appearance</button>' +
      '</div>' +
      '<p class="seldrune-appearance-help">Images are resized for fast display and saved only in this browser.</p>' +
      '<p class="seldrune-appearance-status" id="seldrune-appearance-status" aria-live="polite">Changes save as you make them.</p>';

    grid.prepend(panel);
    updateControls();

    panel.querySelectorAll("[data-background-choice]").forEach(button => {
      button.addEventListener("click", async () => {
        const choice = button.dataset.backgroundChoice;
        if (choice === "custom" && !customAvailable) {
          setStatus("Choose an image below first to enable your custom background.");
          return;
        }
        writePreference("background", choice);
        applyPreferences();
        if (choice === "custom" && customUrl && document.body) {
          document.body.style.setProperty("--seldrune-custom-art", 'url("' + customUrl + '")');
        }
        updateControls();
        setStatus("Background applied across all workspaces.");
      });
    });

    const shade = document.getElementById("seldrune-background-shade");
    shade?.addEventListener("input", () => {
      writePreference("shade", shade.value);
      applyPreferences();
      updateControls();
      setStatus("Background visibility updated.");
    });

    const font = document.getElementById("seldrune-font-choice");
    font?.addEventListener("change", () => {
      writePreference("font", font.value);
      applyPreferences();
      updateControls();
      setStatus("Typography updated across all workspaces.");
    });

    const fileInput = document.getElementById("seldrune-background-file");
    fileInput?.addEventListener("change", async () => {
      const file = fileInput.files && fileInput.files[0];
      if (!file) return;
      if (!file.type.startsWith("image/")) {
        setStatus("Choose an image file to use as a background.");
        fileInput.value = "";
        return;
      }
      if (file.size > 40 * 1024 * 1024) {
        setStatus("That image is over 40 MB. Choose a smaller image and try again.");
        fileInput.value = "";
        return;
      }
      setStatus("Preparing your background image…");
      try {
        const blob = await resizeImage(file);
        await writeCustomImage(blob);
        setCustomBackground(blob);
        writePreference("background", "custom");
        applyPreferences();
        updateControls();
        setStatus("Custom image saved and applied across all workspaces.");
      } catch (error) {
        setStatus(error && error.message ? error.message : "Could not save that image. Try another one.");
      } finally {
        fileInput.value = "";
      }
    });

    document.getElementById("seldrune-appearance-reset")?.addEventListener("click", async () => {
      for (const name of Object.keys(PREFS)) {
        try {
          localStorage.removeItem(PREFS[name]);
        } catch {}
      }
      applyPreferences();
      if (customUrl) {
        URL.revokeObjectURL(customUrl);
        customUrl = "";
      }
      customAvailable = false;
      try {
        await removeCustomImage();
      } catch {}
      document.body?.style.removeProperty("--seldrune-custom-art");
      updateControls();
      setStatus("Appearance reset to the Seldrune celestial defaults.");
    });
  }

  async function decodeImage(file) {
    if ("createImageBitmap" in window) return createImageBitmap(file);
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file);
      const image = new Image();
      image.onload = () => resolve({
        width: image.naturalWidth,
        height: image.naturalHeight,
        drawImage: image,
        close: () => URL.revokeObjectURL(url),
      });
      image.onerror = () => {
        URL.revokeObjectURL(url);
        reject(new Error("This image could not be opened."));
      };
      image.src = url;
    });
  }

  function canvasBlob(canvas, quality) {
    return new Promise((resolve, reject) => {
      canvas.toBlob(blob => {
        if (blob) resolve(blob);
        else reject(new Error("This browser could not prepare the image."));
      }, "image/webp", quality);
    });
  }

  async function resizeImage(file) {
    const bitmap = await decodeImage(file);
    try {
      if (!bitmap.width || !bitmap.height) throw new Error("This image has no usable dimensions.");
      const maxEdge = 3840;
      const ratio = Math.min(1, maxEdge / Math.max(bitmap.width, bitmap.height));
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(bitmap.width * ratio));
      canvas.height = Math.max(1, Math.round(bitmap.height * ratio));
      const context = canvas.getContext("2d", {alpha: false});
      if (!context) throw new Error("Image editing is unavailable in this browser.");
      context.fillStyle = "#08101e";
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.drawImage(bitmap.drawImage || bitmap, 0, 0, canvas.width, canvas.height);
      let blob = await canvasBlob(canvas, .9);
      if (blob.size > 7 * 1024 * 1024) {
        const smaller = document.createElement("canvas");
        const secondRatio = Math.min(1, 2560 / Math.max(canvas.width, canvas.height));
        smaller.width = Math.max(1, Math.round(canvas.width * secondRatio));
        smaller.height = Math.max(1, Math.round(canvas.height * secondRatio));
        const secondContext = smaller.getContext("2d", {alpha: false});
        if (!secondContext) throw new Error("Image editing is unavailable in this browser.");
        secondContext.drawImage(canvas, 0, 0, smaller.width, smaller.height);
        blob = await canvasBlob(smaller, .84);
      }
      return blob;
    } finally {
      bitmap.close?.();
    }
  }

  applyPreferences();
  restoreCustomBackground();

  function initialize() {
    if (initialized) return;
    addAppearancePanel();
    initialized = Boolean(document.getElementById("seldrune-appearance-settings"));
    if (initialized) updateControls();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialize, {once: true});
  } else {
    initialize();
  }
  document.addEventListener("seldrune:portal-ready", initialize);
})();