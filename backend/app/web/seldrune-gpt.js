(() => {
  const form = document.querySelector('#seldrune-gpt-form');
  if (!form) return;

  const input = document.querySelector('#seldrune-gpt-input');
  const thread = document.querySelector('#seldrune-gpt-thread');
  const status = document.querySelector('#seldrune-gpt-status');
  const model = document.querySelector('#seldrune-gpt-model');
  const newConversation = document.querySelector('#seldrune-gpt-new');
  const chatButton = document.querySelector('#seldrune-gpt-chat');
  const attachButton = document.querySelector('#seldrune-gpt-attach');
  const fileInput = document.querySelector('#seldrune-gpt-files');
  const dropzone = document.querySelector('#seldrune-gpt-dropzone');
  const attachmentList = document.querySelector('#seldrune-gpt-attachments');
  const attachmentSummary = document.querySelector('#seldrune-gpt-attachment-summary');
  const modePill = document.querySelector('#seldrune-gpt-mode');
  const pdfPasswordWrap = document.querySelector('#seldrune-gpt-pdf-password-wrap');
  const pdfPassword = document.querySelector('#seldrune-gpt-pdf-password');
  const capabilityStatus = document.querySelector('#seldrune-gpt-capabilities');
  const openToolsButton = document.querySelector('#seldrune-gpt-open-tools');
  const creationStatus = document.querySelector('#seldrune-gpt-creation-status');
  const providerSelect = document.querySelector('#seldrune-gpt-provider');
  const workspace = document.querySelector('#seldrune-gpt');
  const historySidebar = document.querySelector('#seldrune-gpt-history-list');
  const historyPageList = document.querySelector('#seldrune-gpt-history-page-list');
  const historySearch = document.querySelector('#seldrune-gpt-history-search');
  const historyPageSearch = document.querySelector('[data-gpt-history-filter]');
  const providerList = document.querySelector('#seldrune-gpt-provider-list');
  const toolList = document.querySelector('#seldrune-gpt-tool-list');
  const sidebarToggle = document.querySelector('#seldrune-gpt-sidebar-toggle');
  const sidebarScrim = document.querySelector('#seldrune-gpt-sidebar-scrim');
  const initialWelcomeMarkup = thread.querySelector('.gpt-welcome')?.outerHTML
    || '<div class="gpt-welcome empty"><span class="gpt-welcome-mark" aria-hidden="true">✦</span><p class="gpt-welcome-kicker">A clearer place to think and build</p><h2>What would you like to work on?</h2><p class="gpt-welcome-copy">Ask a question, explore an idea, or bring in a file. Your chats stay in your history.</p><div class="gpt-suggestions"><button type="button" data-gpt-prompt="Check production readiness, active tools, provider configuration, and owner attention items."><strong>Review system status</strong><small>Check runtime and connected tools</small></button><button type="button" data-gpt-prompt="Inspect the Seldrune repository state and summarize the safest next engineering action."><strong>Review a codebase</strong><small>Find the next useful engineering step</small></button></div></div>';
  let conversations = [];
  let activeConversationId = null;
  let activeConversationTitle = 'Seldrune GPT';
  let currentGptView = 'chat';
  let workspaceInitialization = null;

  const MAX_FILES = 6;
  const MAX_FILE_BYTES = 8 * 1024 * 1024;
  const MAX_PDF_EDIT_BYTES = 25 * 1024 * 1024;
  const MAX_TOTAL_BYTES = 32 * 1024 * 1024;
  const attachments = [];
  let creationMode = 'any';
  let registeredTools = [];
  let providerReadiness = {};
  let externalToolProviders = [];
  let unrealStatusError = '';
  let outputDatabasePromise = null;
  let outputFilter = 'all';
  let outputSearch = '';
  const outputPreviewUrls = new Set();

  const CREATION_MODES = {
    any: {
      label: 'Anything',
      guidance: '',
      status: 'Text chat · open Product Studio for image, narration, or PDF files.',
    },
    app: {
      label: 'App',
      guidance: 'Create a working app deliverable for the request. Use enabled coding tools to create a branch named for this isolated change, write source and tests into it, run available checks, and report exact files and verification receipts. When building or cloning a camera or microphone app hosted on the authenticated Seldrune origin, load the shared media client as a required bootstrap before app code: `<script src="/console-assets/seldrune-media.js" data-default="true" defer></script>`. Use navigator.mediaDevices.getUserMedia for all capture so each app uses the owner's saved /media face and voice profiles. Tell the owner to enable Use Seldrune Media by default in /media. Preserve fail-closed behavior; never silently use raw device media as a fallback. For apps hosted outside Seldrune, do not claim this same-origin client is installed. If tools are unavailable, return a source draft and say it was not committed or tested.',
      status: 'App · Seldrune tries connected coding tools first; any fallback draft is saved as a file and labeled unbuilt.',
    },
    game: {
      label: 'Game',
      guidance: 'Create a playable game deliverable for the request. Use enabled coding tools to create a branch named for this isolated change, write source and tests into it, run available checks, and report exact files and verification receipts. When the game uses a camera or microphone and will run on the authenticated Seldrune origin, load `<script src="/console-assets/seldrune-media.js" data-default="true" defer></script>` before game code and use navigator.mediaDevices.getUserMedia for all capture. Tell the user to enable Use Seldrune Media by default in /media. Preserve fail-closed behavior; never silently use raw device media as a fallback. For games hosted outside Seldrune, do not claim this same-origin client is installed. If tools are unavailable, return a source draft and say it was not committed or tested.',
      status: 'Game · Seldrune tries connected coding tools first; any fallback draft is saved as a file and labeled unbuilt.',
    },
    song: {
      label: 'Song',
      guidance: 'Do not substitute lyrics for a rendered song. Music generation is not connected in Seldrune yet.',
      status: 'Music rendering is unavailable until a music-generation provider is connected.',
    },
    image: {
      label: 'Image',
      guidance: 'Create one image file from this brief. Return the image itself, not a text-only image plan.',
      status: 'Image · creates a downloadable PNG with the connected OpenAI provider.',
    },
    speech: {
      label: 'Spoken audio',
      guidance: 'Create a spoken narration file from this text. Return the audio itself, not a text-only audio plan.',
      status: 'Spoken audio · creates a downloadable MP3 using an AI-generated voice.',
    },
    document: {
      label: 'PDF document',
      guidance: 'Write the requested document with a clear title, useful section headings, complete content, and readable lists. Seldrune will render the completed answer as a downloadable PDF file.',
      status: 'PDF document · Seldrune creates a real, multi-page PDF from the completed answer and saves it in Outputs.',
    },
    video: {
      label: 'Video',
      guidance: 'Video rendering is not connected in Seldrune. Do not return a text plan as if it were a video file.',
      status: 'Video · no supported video renderer is connected, so no video file will be created.',
    },
    visual: {
      label: 'Visual / 3D',
      guidance: 'Create an original visual or 3D asset package with art direction, composition, asset list, and a ready-to-use prompt. Only claim a rendered image or 3D file when an actual asset and provider receipt are returned; otherwise label this as a design package.',
      status: 'Visual / 3D · art direction can be returned as text; a rendered asset requires an enabled image or 3D generation provider.',
    },
  };

  function setCreationMode(mode) {
    const next = CREATION_MODES[mode] ? mode : 'any';
    creationMode = next;
    document.querySelectorAll('.gpt-creation-mode').forEach(button => {
      const selected = button.dataset.creationMode === next;
      button.classList.toggle('active', selected);
      button.setAttribute('aria-pressed', String(selected));
    });
    if (creationStatus) creationStatus.textContent = CREATION_MODES[next].status;
    if (input && !input.disabled) {
      input.placeholder = next === 'image'
        ? 'Describe the image to create…'
        : next === 'speech'
          ? 'Enter narration text (up to 700 characters)…'
          : next === 'document'
            ? 'Describe the document to create as a PDF…'
          : next === 'video'
            ? 'Describe the video you want; Seldrune will report renderer availability…'
            : 'Ask Seldrune anything: create, code, analyze, or take action…';
    }
    if (modePill) {
      const mediaLabel = ({
        song: 'Media · Music unavailable',
        image: 'Media · Image',
        speech: 'Media · Spoken audio',
        document: 'Product · PDF document',
        video: 'Media · Video unavailable',
      })[next] || 'Text chat';
      modePill.textContent = mediaLabel;
      modePill.classList.toggle('active', next !== 'any');
    }
  }

  function buildCreativeOrder(request) {
    const selectedGuidance = CREATION_MODES[creationMode]?.guidance;
    const inferredKind = creationMode === 'any' ? classifyOutputKind(request) : creationMode;
    const inferredGuidance = ['app', 'game'].includes(inferredKind)
      ? CREATION_MODES[inferredKind]?.guidance
      : '';
    const guidance = selectedGuidance || inferredGuidance;
    return guidance ? `${guidance}\n\nUser request: ${request}` : request;
  }

  const MIME_BY_EXTENSION = {
    pdf: 'application/pdf',
    txt: 'text/plain',
    md: 'text/markdown',
    csv: 'text/csv',
    json: 'application/json',
    png: 'image/png',
    jpg: 'image/jpeg',
    jpeg: 'image/jpeg',
    webp: 'image/webp',
    gif: 'image/gif',
    docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    pptx: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  };

  const ALLOWED_TYPES = new Set(Object.values(MIME_BY_EXTENSION));

  const OUTPUT_KIND_LABELS = {
    app: 'App source draft',
    game: 'Game source draft',
    song: 'Song package',
    image: 'Generated image',
    speech: 'Spoken audio',
    video: 'Video package',
    visual: 'Visual / 3D package',
    build: 'Coding build receipt',
    document: 'Document',
    creative: 'Creative output',
  };

  function outputDatabase() {
    if (outputDatabasePromise) return outputDatabasePromise;
    outputDatabasePromise = new Promise((resolve, reject) => {
      if (!window.indexedDB) {
        reject(new Error('This browser does not support local output storage.'));
        return;
      }
      const request = window.indexedDB.open('seldrune-output-library', 1);
      request.onupgradeneeded = () => {
        const database = request.result;
        if (!database.objectStoreNames.contains('outputs')) {
          database.createObjectStore('outputs', {keyPath: 'id'});
        }
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error || new Error('Output storage could not open.'));
      request.onblocked = () => reject(new Error('Output storage is busy in another Seldrune tab.'));
    });
    return outputDatabasePromise;
  }

  async function saveOutputRecord(record) {
    const database = await outputDatabase();
    await new Promise((resolve, reject) => {
      const transaction = database.transaction('outputs', 'readwrite');
      transaction.objectStore('outputs').put(record);
      transaction.oncomplete = resolve;
      transaction.onerror = () => reject(transaction.error || new Error('Output could not be saved.'));
      transaction.onabort = () => reject(transaction.error || new Error('Output save was canceled.'));
    });
    document.dispatchEvent(new CustomEvent('seldrune:outputs-changed'));
    return record;
  }

  async function listOutputRecords() {
    const database = await outputDatabase();
    return new Promise((resolve, reject) => {
      const request = database.transaction('outputs', 'readonly').objectStore('outputs').getAll();
      request.onsuccess = () => resolve((request.result || []).sort((a, b) => b.createdAt.localeCompare(a.createdAt)));
      request.onerror = () => reject(request.error || new Error('Saved outputs could not be read.'));
    });
  }

  async function deleteOutputRecord(id) {
    const database = await outputDatabase();
    await new Promise((resolve, reject) => {
      const transaction = database.transaction('outputs', 'readwrite');
      transaction.objectStore('outputs').delete(id);
      transaction.oncomplete = resolve;
      transaction.onerror = () => reject(transaction.error || new Error('Output could not be deleted.'));
      transaction.onabort = () => reject(transaction.error || new Error('Output deletion was canceled.'));
    });
    document.dispatchEvent(new CustomEvent('seldrune:outputs-changed'));
  }

  function createOutputRecord({title, kind, fileName, blob, note}) {
    return {
      id: window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      title: String(title || 'Seldrune output').slice(0, 120),
      kind: OUTPUT_KIND_LABELS[kind] ? kind : 'creative',
      fileName,
      mimeType: blob.type || 'application/octet-stream',
      blob,
      note: String(note || '').slice(0, 500),
      createdAt: new Date().toISOString(),
    };
  }

  function outputFilename(title, extension = 'md') {
    const slug = String(title || 'seldrune-output')
      .normalize('NFKD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 64) || 'seldrune-output';
    return `${slug}.${extension}`;
  }

  function classifyOutputKind(request, mode = creationMode) {
    if (mode === 'document') return 'document';
    const text = `${mode === 'any' ? '' : mode} ${request}`.toLowerCase();
    if (/\b(game|playable|gameplay|level design)\b/.test(text)) return 'game';
    const mediaForExistingApp = /\b(song|music|lyrics|soundtrack|audio|video|film|movie|clip|storyboard|image|illustration|picture|visual|poster|artwork)\b.{0,60}\b(?:for|about)\s+(?:(?:my|our|the|an?)\s+)?(?:app|application|website|web app)\b/.test(text);
    const appIntent = /\b(app|application|website|web app|software|program|source code|coding)\b/.test(text) && !mediaForExistingApp;
    if (appIntent) return 'app';
    if (/\b(narration|voiceover|voice over|spoken audio|speech)\b/.test(text)) return 'speech';
    if (/\b(song|music|lyrics|soundtrack)\b/.test(text)) return 'song';
    if (/\b(video|film|movie|clip|storyboard)\b/.test(text)) return 'video';
    if (/\b(image|illustration|picture|poster|artwork)\b/.test(text)) return 'image';
    if (/\b(visual|3d scene|3d model)\b/.test(text)) return 'visual';
    if (/\b(pdf|document|spreadsheet|presentation|report)\b/.test(text)) return 'document';
    if (/\b(build|test|preview|pipeline|repository|repo|feature|bug)\b/.test(text)) return 'build';
    return 'creative';
  }

  function titleFromRequest(request, kind) {
    const cleaned = String(request || '').replace(/\s+/g, ' ').trim();
    return cleaned.length > 72 ? `${cleaned.slice(0, 69)}…` : cleaned || OUTPUT_KIND_LABELS[kind] || 'Seldrune output';
  }

  function formatBytes(value) {
    if (value < 1024) return `${value} B`;
    if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
    return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  }

  function mediaTypeFor(file) {
    if (file.type && ALLOWED_TYPES.has(file.type)) return file.type;
    const extension = (file.name.split('.').pop() || '').toLowerCase();
    return MIME_BY_EXTENSION[extension] || '';
  }

  function outputShortcut(card) {
    if (!card || card.querySelector('[data-open-portal="outputs"]')) return;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'ghost output-shortcut';
    button.dataset.openPortal = 'outputs';
    button.textContent = 'Open Outputs';
    card.append(button);
  }

  async function saveTextArtifact(request, content, kind, note = 'Text output · no rendered media or external build is implied.') {
    const title = titleFromRequest(request, kind);
    const created = new Date().toISOString();
    const body = `# ${title}\n\n**Request:** ${request}\n\n**Created:** ${created}\n\n---\n\n${content}\n\n---\n\n${note}`;
    const blob = new Blob([body], {type: 'text/markdown;charset=utf-8'});
    const record = createOutputRecord({
      title,
      kind,
      fileName: outputFilename(title),
      blob,
      note,
    });
    await saveOutputRecord(record);
    return record;
  }

  function base64Blob(value, mimeType) {
    const binary = window.atob(value);
    const bytes = new Uint8Array(binary.length);
    for (let offset = 0; offset < binary.length; offset += 1) {
      bytes[offset] = binary.charCodeAt(offset);
    }
    return new Blob([bytes], {type: mimeType});
  }

  async function saveBinaryArtifact({title, kind, fileName, dataBase64, mimeType, note}) {
    const blob = base64Blob(dataBase64, mimeType);
    return saveOutputRecord(createOutputRecord({
      title,
      kind,
      fileName: fileName || outputFilename(title, 'bin'),
      blob,
      note,
    }));
  }

  async function createPdfOutput(request, content, card) {
    const title = titleFromRequest(request, 'document');
    const result = await api('/gpt/pdf/create', {
      method: 'POST',
      body: JSON.stringify({
        title,
        content,
        conversation_id: activeConversationId,
      }),
    });
    if (!result.data_base64 || !result.filename) {
      throw new Error('The PDF renderer did not return a downloadable file.');
    }
    const record = await saveBinaryArtifact({
      title,
      kind: 'document',
      fileName: result.filename,
      dataBase64: result.data_base64,
      mimeType: result.mime_type || 'application/pdf',
      note: `PDF document · ${result.page_count || 1} page(s) · created from the Seldrune response.`,
    });
    const link = document.createElement('a');
    link.className = 'ghost';
    link.href = URL.createObjectURL(record.blob);
    link.download = record.fileName;
    link.dataset.outputDownload = 'pdf';
    link.textContent = `Download ${record.fileName}`;
    card.append(link);
    outputShortcut(card);
    return {record, pageCount: Number(result.page_count || 1)};
  }

  function addPdfExportButton(card, request, content) {
    if (!card || card.querySelector('[data-create-pdf]')) return null;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'ghost';
    button.dataset.createPdf = 'true';
    button.textContent = 'Create PDF';
    button.addEventListener('click', async () => {
      button.disabled = true;
      button.textContent = 'Creating PDF…';
      try {
        const created = await createPdfOutput(request, content, card);
        button.textContent = 'Create another PDF';
        status.textContent = `${created.record.fileName} created · ${created.pageCount} page(s) · saved in Outputs.`;
      } catch (error) {
        button.textContent = 'Retry PDF';
        status.textContent = `The answer is ready, but PDF creation failed: ${error.message}`;
      } finally {
        button.disabled = false;
      }
    });
    card.append(button);
    return button;
  }

  function requestNeedsPdf(request) {
    return creationMode === 'document' || /\bpdf\b/i.test(String(request || ''));
  }

  async function renderOutputLibrary() {
    const list = document.querySelector('#seldrune-output-list');
    const outputStatus = document.querySelector('#seldrune-output-status');
    if (!list || !outputStatus) return;
    outputPreviewUrls.forEach(url => URL.revokeObjectURL(url));
    outputPreviewUrls.clear();
    try {
      const outputs = await listOutputRecords();
      const filtered = outputs.filter(item => {
        const matchesKind = outputFilter === 'all' || item.kind === outputFilter;
        const query = outputSearch.toLowerCase();
        const matchesSearch = !query || `${item.title} ${item.fileName} ${item.note}`.toLowerCase().includes(query);
        return matchesKind && matchesSearch;
      });
      list.replaceChildren();
      outputStatus.textContent = outputs.length
        ? `${outputs.length} saved file${outputs.length === 1 ? '' : 's'} · stored in this browser`
        : 'Files you create here will appear in this browser’s Outputs library.';
      if (!filtered.length) {
        const empty = document.createElement('p');
        empty.className = 'output-empty';
        empty.textContent = outputs.length
          ? 'No saved files match this filter.'
          : 'Nothing saved yet. Ask Seldrune to create something, then find the file here.';
        list.append(empty);
        return;
      }
      filtered.forEach(item => {
        const card = document.createElement('article');
        card.className = 'output-card';
        card.setAttribute('role', 'listitem');
        const headingRow = document.createElement('div');
        headingRow.className = 'output-card-head';
        const title = document.createElement('h3');
        title.className = 'output-card-title';
        title.textContent = item.title;
        const kind = document.createElement('span');
        kind.className = 'output-kind-pill';
        kind.textContent = OUTPUT_KIND_LABELS[item.kind] || 'Seldrune output';
        headingRow.append(title, kind);
        card.append(headingRow);

        const meta = document.createElement('p');
        meta.className = 'output-card-meta';
        meta.textContent = `${item.fileName} · ${new Date(item.createdAt).toLocaleString()} · ${formatBytes(item.blob?.size || 0)}`;
        card.append(meta);
        const mimeType = item.mimeType || item.blob?.type || '';
        if (/^(image|video|audio)\//.test(mimeType) && item.blob instanceof Blob) {
          const preview = document.createElement('div');
          preview.className = 'output-card-preview';
          const url = URL.createObjectURL(item.blob);
          outputPreviewUrls.add(url);
          let media;
          if (mimeType.startsWith('image/')) {
            media = document.createElement('img');
            media.alt = item.title;
          } else {
            media = document.createElement(mimeType.startsWith('video/') ? 'video' : 'audio');
            media.controls = true;
          }
          media.src = url;
          preview.append(media);
          card.append(preview);
        } else if (item.note) {
          const note = document.createElement('p');
          note.className = 'output-card-meta';
          note.textContent = item.note;
          card.append(note);
        }
        const actions = document.createElement('div');
        actions.className = 'output-card-actions';
        const download = document.createElement('a');
        download.className = 'ghost';
        download.href = URL.createObjectURL(item.blob);
        outputPreviewUrls.add(download.href);
        download.download = item.fileName;
        download.textContent = 'Download file';
        actions.append(download);
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'ghost output-delete';
        remove.textContent = 'Delete';
        remove.setAttribute('aria-label', `Delete ${item.fileName}`);
        remove.addEventListener('click', async () => {
          if (!window.confirm(`Delete ${item.fileName} from this browser’s Outputs library?`)) return;
          try {
            await deleteOutputRecord(item.id);
            outputStatus.textContent = `${item.fileName} deleted.`;
          } catch (error) {
            outputStatus.textContent = `Could not delete output: ${error.message}`;
          }
        });
        actions.append(remove);
        card.append(actions);
        list.append(card);
      });
    } catch (error) {
      list.replaceChildren();
      const empty = document.createElement('p');
      empty.className = 'output-empty';
      empty.textContent = 'Local output storage is unavailable in this browser.';
      list.append(empty);
      outputStatus.textContent = error.message;
    }
  }

  function initializeOutputLibrary() {
    const search = document.querySelector('#seldrune-output-search');
    if (!search || search.dataset.bound === 'true') return;
    search.dataset.bound = 'true';
    search.addEventListener('input', () => {
      outputSearch = search.value.trim();
      void renderOutputLibrary();
    });
    document.querySelectorAll('[data-output-filter]').forEach(button => {
      button.addEventListener('click', () => {
        outputFilter = button.dataset.outputFilter || 'all';
        document.querySelectorAll('[data-output-filter]').forEach(filter => {
          filter.setAttribute('aria-pressed', String(filter === button));
        });
        void renderOutputLibrary();
      });
    });
    void renderOutputLibrary();
  }

  function addMessage(label, text, role = 'assistant') {
    if (thread.querySelector('.empty')) thread.replaceChildren();
    const card = document.createElement('article');
    card.className = 'command-card';
    card.dataset.role = role;
    const body = document.createElement('div');
    const heading = document.createElement('strong');
    heading.textContent = label;
    const message = document.createElement('p');
    message.textContent = text;
    body.append(heading, message);
    card.append(body);
    thread.append(card);
    card.scrollIntoView({
      behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
      block: 'nearest',
    });
    return card;
  }

  function addDownloadMessage(label, text, filename, dataBase64) {
    if (thread.querySelector('.empty')) thread.replaceChildren();
    const card = document.createElement('article');
    card.className = 'command-card';
    card.dataset.role = 'assistant';
    const body = document.createElement('div');
    const heading = document.createElement('strong');
    heading.textContent = label;
    const message = document.createElement('p');
    message.textContent = text;
    const download = document.createElement('a');
    download.className = 'ghost';
    download.textContent = `Download ${filename}`;
    download.download = filename;
    download.href = `data:application/pdf;base64,${dataBase64}`;
    body.append(heading, message, download);
    card.append(body);
    thread.append(card);
    card.scrollIntoView({
      behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
      block: 'nearest',
    });
    outputShortcut(card);
    void saveBinaryArtifact({
      title: filename,
      kind: 'document',
      fileName: filename,
      dataBase64,
      mimeType: 'application/pdf',
      note: 'AI edited PDF · content and layout verification are reported in the conversation.',
    }).catch(error => {
      status.textContent = `PDF is downloadable here; it could not be added to Outputs: ${error.message}`;
    });
  }

  function setBusy(busy, message) {
    input.disabled = busy;
    if (chatButton) chatButton.disabled = busy;
    attachButton.disabled = busy;
    fileInput.disabled = busy;
    const codingButton = document.querySelector('#coding-lab-submit');
    if (codingButton) codingButton.disabled = busy;
    document.querySelectorAll('#coding-lab-repository, #coding-lab-brief').forEach(control => {
      control.disabled = busy;
    });
    if (message) status.textContent = message;
  }

  function clearAttachments() {
    attachments.splice(0);
    if (fileInput) fileInput.value = '';
    if (pdfPassword) pdfPassword.value = '';
    renderAttachments();
  }

  function renderAttachments() {
    attachmentList.replaceChildren();
    attachments.forEach((item, index) => {
      const chip = document.createElement('div');
      chip.className = 'gpt-attachment-chip';
      const label = document.createElement('span');
      label.textContent = item.name;
      const size = document.createElement('small');
      size.textContent = formatBytes(item.size);
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'ghost';
      remove.setAttribute('aria-label', `Remove ${item.name}`);
      remove.textContent = '×';
      remove.addEventListener('click', () => {
        attachments.splice(index, 1);
        renderAttachments();
      });
      chip.append(label, size, remove);
      attachmentList.append(chip);
    });
    const total = attachments.reduce((sum, item) => sum + item.size, 0);
    attachmentSummary.textContent = attachments.length
      ? `${attachments.length} attached · ${formatBytes(total)}`
      : 'No attachments';
    const pdfAttachments = attachments.filter(
      item => item.media_type === 'application/pdf',
    );
    const hasPdf = pdfAttachments.length > 0;
    const aiPdfMode = pdfAttachments.length === 1 && attachments.length === 1;
    pdfPasswordWrap?.classList.toggle('hidden', !hasPdf);
    dropzone?.classList.toggle('ai-pdf-mode', aiPdfMode);
    if (modePill) {
      const mediaLabel = ({
        song: 'Media · Music unavailable',
        image: 'Media · Image',
        speech: 'Media · Spoken audio',
        video: 'Media · Video unavailable',
      })[creationMode] || 'Text chat';
      modePill.textContent = aiPdfMode ? 'AI PDF Editor' : mediaLabel;
      modePill.classList.toggle('active', aiPdfMode || creationMode !== 'any');
    }
    if (chatButton) {
      chatButton.innerHTML = aiPdfMode
        ? 'AI Edit PDF <span>✦</span>'
        : 'Send to Seldrune <span>→</span>';
    }
    if (input) {
      input.placeholder = aiPdfMode
        ? 'Tell Seldrune exactly what to change in this PDF…'
        : creationMode === 'image'
          ? 'Describe the image to create…'
          : creationMode === 'speech'
            ? 'Enter narration text (up to 700 characters)…'
            : 'Ask Seldrune anything: create, code, analyze, or take action…';
    }
    if (aiPdfMode && !input.disabled) {
      status.textContent =
        'AI PDF Editor ready · describe the edit in plain language and submit.';
    }
  }

  function fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(new Error(`Could not read ${file.name}`));
      reader.onload = () => {
        const dataUrl = String(reader.result || '');
        const comma = dataUrl.indexOf(',');
        if (comma < 0) {
          reject(new Error(`Could not encode ${file.name}`));
          return;
        }
        resolve(dataUrl.slice(comma + 1));
      };
      reader.readAsDataURL(file);
    });
  }

  async function addFiles(files) {
    const incoming = [...files];
    if (!incoming.length) return;
    if (attachments.length + incoming.length > MAX_FILES) {
      status.textContent = `Maximum ${MAX_FILES} attachments per message.`;
      return;
    }

    const incomingBytes = incoming.reduce((sum, file) => sum + file.size, 0);
    const currentBytes = attachments.reduce((sum, item) => sum + item.size, 0);
    if (currentBytes + incomingBytes > MAX_TOTAL_BYTES) {
      status.textContent = 'Attachments exceed the 20 MB total limit.';
      return;
    }

    for (const file of incoming) {
      const mediaType = mediaTypeFor(file);
      if (!mediaType) {
        status.textContent = `Unsupported attachment: ${file.name}`;
        continue;
      }
      const fileLimit = mediaType === 'application/pdf'
        ? MAX_PDF_EDIT_BYTES
        : MAX_FILE_BYTES;
      if (file.size > fileLimit) {
        status.textContent = mediaType === 'application/pdf'
          ? `${file.name} exceeds the 25 MB advanced PDF limit.`
          : `${file.name} exceeds the 8 MB per-file limit.`;
        continue;
      }
      try {
        const dataBase64 = await fileToBase64(file);
        attachments.push({
          name: file.name,
          media_type: mediaType,
          data_base64: dataBase64,
          size: file.size,
        });
      } catch (error) {
        status.textContent = error.message;
      }
    }
    renderAttachments();
  }

  function showWelcome() {
    thread.innerHTML = initialWelcomeMarkup;
  }

  function setGptView(view) {
    currentGptView = ['chat', 'history', 'tools'].includes(view) ? view : 'chat';
    document.querySelectorAll('[data-gpt-view]').forEach(button => {
      const selected = button.dataset.gptView === currentGptView;
      button.classList.toggle('active', selected);
      button.setAttribute('aria-pressed', String(selected));
    });
    document.querySelectorAll('[data-gpt-page]').forEach(page => {
      const selected = page.dataset.gptPage === currentGptView;
      page.hidden = !selected;
      page.classList.toggle('active', selected);
    });
    if (currentGptView === 'history') renderConversationLists();
    if (currentGptView === 'tools') renderToolCatalog();
    closeMobileSidebar();
  }

  function closeMobileSidebar() {
    workspace?.classList.remove('sidebar-open');
    sidebarToggle?.setAttribute('aria-expanded', 'false');
    sidebarScrim?.classList.add('hidden');
  }

  function formatConversationDate(value) {
    if (!value) return 'Earlier';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? 'Saved chat' : date.toLocaleDateString(undefined, {month: 'short', day: 'numeric'});
  }

  function renderConversationList(target, query, pageList = false) {
    if (!target) return;
    target.replaceChildren();
    const filter = String(query || '').trim().toLowerCase();
    const visible = conversations.filter(item => !filter || String(item.title || '').toLowerCase().includes(filter));
    if (!visible.length) {
      const empty = document.createElement('p');
      empty.className = 'gpt-history-empty';
      empty.textContent = filter ? 'No chats match that search.' : 'Your saved chats will appear here.';
      target.append(empty);
      return;
    }
    visible.forEach(item => {
      const row = document.createElement('div');
      row.className = 'gpt-history-row';
      const open = document.createElement('button');
      open.type = 'button';
      open.className = 'gpt-history-open';
      open.textContent = String(item.title || 'Untitled chat');
      open.title = open.textContent + ' · ' + formatConversationDate(item.updated_at);
      const isActive = item.id
        ? String(item.id) === String(activeConversationId)
        : Boolean(item.legacy) && activeConversationId === null;
      if (isActive) open.setAttribute('aria-current', 'page');
      open.addEventListener('click', () => { void openConversation(item); });
      row.append(open);
      if (item.id) {
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'gpt-history-delete';
        remove.textContent = '×';
        remove.setAttribute('aria-label', 'Delete ' + open.textContent);
        remove.title = 'Delete chat';
        remove.addEventListener('click', event => {
          event.stopPropagation();
          void deleteConversation(item);
        });
        row.append(remove);
      } else if (pageList && item.legacy) {
        const archive = document.createElement('small');
        archive.textContent = 'Archive';
        row.append(archive);
      }
      if (pageList) {
        const details = document.createElement('small');
        details.className = 'gpt-history-date';
        details.textContent = formatConversationDate(item.updated_at);
        row.append(details);
      }
      target.append(row);
    });
  }

  function renderConversationLists() {
    renderConversationList(historySidebar, historySearch?.value || '');
    renderConversationList(historyPageList, historyPageSearch?.value || '', true);
  }

  async function refreshConversations() {
    try {
      const result = await api('/gpt/conversations');
      conversations = Array.isArray(result) ? result : [];
      const active = activeConversationId
        ? conversations.find(item => String(item.id) === String(activeConversationId))
        : conversations.find(item => item.legacy);
      if (active?.title) {
        activeConversationTitle = active.title;
        const title = document.querySelector('#seldrune-gpt-title');
        if (title) title.textContent = activeConversationTitle;
      }
      renderConversationLists();
    } catch (error) {
      conversations = [];
      renderConversationLists();
      if (historySidebar) {
        historySidebar.replaceChildren();
        const message = document.createElement('p');
        message.className = 'gpt-history-empty';
        message.textContent = 'Chat history unavailable: ' + error.message;
        historySidebar.append(message);
      }
    }
  }

  async function loadHistory() {
    try {
      const query = activeConversationId
        ? '?conversation_id=' + encodeURIComponent(activeConversationId)
        : '';
      const messages = await api('/gpt/history' + query);
      if (!messages.length) {
        showWelcome();
        status.textContent = activeConversationTitle === 'Earlier saved history'
          ? 'Earlier saved history · ready.'
          : 'New chat · ready.';
        return;
      }
      thread.replaceChildren();
      messages.forEach(item => addMessage(
        item.role === 'assistant' ? 'Seldrune AI' : 'You',
        item.content,
        item.role === 'assistant' ? 'assistant' : 'user',
      ));
      status.textContent = 'Restored ' + messages.length + ' saved messages.';
    } catch (error) {
      showWelcome();
      status.textContent = 'History unavailable: ' + error.message;
    }
  }

  async function createConversation() {
    const conversation = await api('/gpt/conversations', {
      method: 'POST',
      body: JSON.stringify({}),
    });
    activeConversationId = conversation.id || null;
    activeConversationTitle = conversation.title || 'New chat';
    clearAttachments();
    if (input) input.value = '';
    if (model) model.textContent = 'Seldrune Auto';
    const title = document.querySelector('#seldrune-gpt-title');
    if (title) title.textContent = activeConversationTitle;
    showWelcome();
    setGptView('chat');
    await refreshConversations();
    status.textContent = 'New chat · ready.';
    return conversation;
  }

  async function openConversation(conversation) {
    if (!conversation) return;
    activeConversationId = conversation.id || null;
    activeConversationTitle = conversation.title || 'Seldrune GPT';
    const title = document.querySelector('#seldrune-gpt-title');
    if (title) title.textContent = activeConversationTitle;
    if (input) input.value = '';
    clearAttachments();
    setGptView('chat');
    await loadHistory();
    renderConversationLists();
  }

  async function deleteConversation(conversation) {
    if (!conversation?.id) return;
    const label = conversation.title || 'this chat';
    if (!window.confirm('Delete "' + label + '"? This removes its saved messages.')) return;
    try {
      await api('/gpt/conversations/' + encodeURIComponent(conversation.id), {method: 'DELETE'});
      const wasActive = String(conversation.id) === String(activeConversationId);
      await refreshConversations();
      if (wasActive) {
        if (conversations.length) await openConversation(conversations[0]);
        else await createConversation();
      }
      status.textContent = 'Chat deleted.';
    } catch (error) {
      status.textContent = 'Could not delete chat: ' + error.message;
    }
  }

  function openUnrealConnections() {
    window.seldrunePortal?.activate?.('connections');
    window.setTimeout(() => {
      window.seldruneConnections?.selectProvider?.('unreal');
    }, 150);
  }

  function addUnrealConnectionButton(card, label = 'Connect Unreal worker') {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'gpt-unreal-connect';
    button.textContent = label;
    button.addEventListener('click', openUnrealConnections);
    card.append(button);
  }

  function renderToolCatalog() {
    if (providerList) {
      providerList.replaceChildren();
      const providers = Object.entries(providerReadiness || {});
      if (!providers.length) {
        const empty = document.createElement('p');
        empty.className = 'gpt-history-empty';
        empty.textContent = 'Provider status is not available yet.';
        providerList.append(empty);
      } else {
        providers.forEach(([name, ready]) => {
          const card = document.createElement('div');
          card.className = 'gpt-provider-card';
          const title = document.createElement('strong');
          title.textContent = name.replaceAll('_', ' ').replace(/\b\w/g, character => character.toUpperCase());
          const state = document.createElement('small');
          state.textContent = ready ? 'Ready' : 'Needs setup';
          card.append(title, state);
          providerList.append(card);
        });
      }
    }
    if (!toolList) return;
    toolList.replaceChildren();
    if (!registeredTools.length) {
      const empty = document.createElement('p');
      empty.className = 'gpt-history-empty';
      empty.textContent = 'No tools are currently connected to this workspace.';
      toolList.append(empty);
    } else {
      registeredTools.forEach(slug => {
        const card = document.createElement('div');
        card.className = 'gpt-tool-card';
        const title = document.createElement('strong');
        title.textContent = String(slug).replaceAll('_', ' ').replaceAll('-', ' ');
        const state = document.createElement('small');
        const normalizedSlug = String(slug).toLowerCase().replaceAll('_', '-');
        if (normalizedSlug.startsWith('unreal-engine-')) {
          const actionName = normalizedSlug.endsWith('install') ? 'install-engine' : 'engine-status';
          const worker = externalToolProviders.find(item => item.provider === 'unreal');
          const action = worker?.actions?.find(item => item.action_name === actionName);
          state.textContent = action?.ready
            ? 'Connected · ready'
            : worker?.secret_available ? 'Connection needs attention' : 'Connect worker';
        } else {
          state.textContent = 'Available';
        }
        card.append(title, state);
        toolList.append(card);
      });
    }

    const worker = externalToolProviders.find(item => item.provider === 'unreal');
    const actions = Array.isArray(worker?.actions) ? worker.actions : [];
    const readyActions = actions.filter(item => item.ready);
    const card = document.createElement('div');
    card.className = 'gpt-tool-card gpt-unreal-tool-card';
    card.dataset.state = worker?.ready ? 'ready' : 'setup';
    const title = document.createElement('strong');
    title.textContent = 'Unreal Engine worker';
    const state = document.createElement('small');
    state.textContent = worker?.ready
      ? 'Connected · ' + readyActions.length + ' actions ready'
      : worker?.secret_available ? 'Connection needs attention' : 'Not connected';
    const detail = document.createElement('p');
    detail.textContent = worker?.ready
      ? 'Worker health is verified. GPT can check engine status and queue install jobs.'
      : worker?.secret_available
        ? 'A worker credential is saved, but its supported GPT actions are not ready yet. Open Connections to refresh the verification.'
        : unrealStatusError
          ? 'Worker status could not be refreshed. Open Connections to see the current verification result.'
          : 'Connect a compatible HTTPS worker in Connections to enable engine checks and install jobs.';
    card.append(title, state, detail);
    addUnrealConnectionButton(card, worker?.secret_available ? 'Manage connection' : 'Connect Unreal worker');
    toolList.append(card);
  }

  async function loadCapabilities() {
    if (capabilityStatus) {
      capabilityStatus.dataset.state = 'checking';
      capabilityStatus.textContent = 'Checking cognitive runtime…';
    }
    try {
      const capabilities = await api('/gpt/capabilities');
      registeredTools = Array.isArray(capabilities.registered_tools)
        ? capabilities.registered_tools
        : [];
      providerReadiness = capabilities.provider_readiness || {};
      externalToolProviders = [];
      unrealStatusError = '';
      try {
        const toolStatus = await api('/tool-bootstrap/status');
        externalToolProviders = Array.isArray(toolStatus.providers)
          ? toolStatus.providers
          : [];
      } catch (error) {
        unrealStatusError = error.message || 'Worker status could not be loaded.';
      }
      updateModelProviderOptions(capabilities.model_providers || []);
      const providers = Object.entries(capabilities.provider_readiness || {});
      const readyProviders = providers.filter(([, ready]) => Boolean(ready)).length;
      const hints = Array.isArray(capabilities.configuration_hints)
        ? capabilities.configuration_hints
        : [];
      const needsSetup = hints.length > 0 || readyProviders < providers.length;
      if (capabilityStatus) {
        capabilityStatus.dataset.state = needsSetup ? 'attention' : 'ready';
        capabilityStatus.textContent = needsSetup
          ? 'Cognitive runtime · ' + registeredTools.length + ' tools · '
            + readyProviders + '/' + providers.length + ' providers ready'
          : 'Cognitive runtime ready · ' + registeredTools.length + ' tools';
        capabilityStatus.title = hints.length
          ? 'Provider setup needed: ' + hints.join(', ')
          : '';
      }
      openToolsButton?.classList.toggle('hidden', !needsSetup);
      renderCodingProviderStatus();
      renderToolCatalog();
    } catch (error) {
      externalToolProviders = [];
      unrealStatusError = error.message || 'Worker status could not be loaded.';
      if (capabilityStatus) {
        capabilityStatus.dataset.state = 'attention';
        capabilityStatus.textContent = 'Cognitive runtime status unavailable';
        capabilityStatus.title = error.message;
      }
      openToolsButton?.classList.remove('hidden');
      renderCodingProviderStatus(error.message);
      renderToolCatalog();
    }
  }

  function updateModelProviderOptions(providers) {
    if (!providerSelect) return;
    const byName = new Map(
      providers.map(provider => [provider.provider, provider]),
    );
    [...providerSelect.options].forEach(option => {
      const provider = byName.get(option.value);
      if (!provider) return;
      option.disabled = !provider.configured;
      option.textContent = provider.configured
        ? provider.label + ' · configured'
        : provider.label + ' · needs setup';
      option.title = provider.configured
        ? 'Credential is configured; Seldrune checks provider availability when selected.'
        : 'Set ' + (provider.configuration_hint || 'provider credentials')
          + ' on the Seldrune server.';
    });
    const selected = byName.get(providerSelect.value);
    const auto = byName.get('auto');
    if (selected && !selected.configured && auto?.configured) {
      providerSelect.value = 'auto';
    }
  }

  function renderCodingProviderStatus(error = '') {
    const labels = {
      github: 'GitHub',
      circleci: 'CircleCI',
      railway: 'Railway',
    };
    document.querySelectorAll('.coding-provider-card').forEach(card => {
      const provider = card.dataset.provider;
      const providerTools = registeredTools.filter(slug => slug.toLowerCase().includes(provider));
      const ready = providerReadiness[provider] === true;
      const listed = providerTools.length > 0;
      const stateLabel = card.querySelector('span');
      if (!stateLabel) return;
      if (error) {
        card.dataset.state = 'unknown';
        stateLabel.textContent = 'Status unavailable';
      } else if (ready || listed) {
        card.dataset.state = 'ready';
        stateLabel.textContent = ready
          ? `${providerTools.length || 'Provider'} ready`
          : `${providerTools.length} active tool${providerTools.length === 1 ? '' : 's'} · access unverified`;
      } else {
        card.dataset.state = 'missing';
        stateLabel.textContent = 'Not configured';
      }
      card.setAttribute('aria-label', `${labels[provider] || provider}: ${stateLabel.textContent}`);
    });
  }

  function initializeGptWorkspace() {
    if (workspaceInitialization) return workspaceInitialization;
    workspaceInitialization = (async () => {
      await refreshConversations();
      const current = conversations.find(item => item.id && String(item.id) === String(activeConversationId));
      const first = current || conversations[0];
      if (first) await openConversation(first);
      else await createConversation();
      await loadCapabilities();
    })().catch(error => {
      status.textContent = 'Seldrune GPT could not start: ' + error.message;
      workspaceInitialization = null;
    });
    return workspaceInitialization;
  }

  async function startNewConversation() {
    try {
      await createConversation();
    } catch (error) {
      status.textContent = 'Could not start a new chat: ' + error.message;
    }
  }

  newConversation?.addEventListener('click', () => { void startNewConversation(); });
  document.querySelector('#seldrune-gpt-history-new')?.addEventListener('click', () => { void startNewConversation(); });
  document.querySelectorAll('[data-gpt-view]').forEach(button => {
    button.addEventListener('click', () => setGptView(button.dataset.gptView));
  });
  historySearch?.addEventListener('input', renderConversationLists);
  historyPageSearch?.addEventListener('input', renderConversationLists);
  sidebarToggle?.addEventListener('click', () => {
    const isOpen = workspace?.classList.toggle('sidebar-open') || false;
    sidebarToggle.setAttribute('aria-expanded', String(isOpen));
    sidebarScrim?.classList.toggle('hidden', !isOpen);
  });
  sidebarScrim?.addEventListener('click', closeMobileSidebar);

  openToolsButton?.addEventListener('click', () => {
    const systemTab = document.querySelector('[data-portal-tab="intelligence"]');
    if (systemTab) {
      systemTab.click();
      return;
    }
    document.getElementById('tool-auto-activate')?.click();
  });

  attachButton?.addEventListener('click', () => fileInput?.click());
  fileInput?.addEventListener('change', () => addFiles(fileInput.files || []));

  ['dragenter', 'dragover'].forEach(type => {
    dropzone?.addEventListener(type, event => {
      event.preventDefault();
      dropzone.classList.add('dragging');
    });
  });
  ['dragleave', 'drop'].forEach(type => {
    dropzone?.addEventListener(type, event => {
      event.preventDefault();
      dropzone.classList.remove('dragging');
    });
  });
  dropzone?.addEventListener('drop', event => addFiles(event.dataTransfer?.files || []));
  input?.addEventListener('paste', event => {
    const files = [...(event.clipboardData?.files || [])];
    if (files.length) addFiles(files);
  });

  document.addEventListener('click', event => {
    const button = event.target.closest('[data-gpt-prompt]');
    if (!button) return;
    if (button.dataset.creationMode) setCreationMode(button.dataset.creationMode);
    input.value = button.dataset.gptPrompt || '';
    const startedFromMedia = Boolean(button.closest('#seldrune-media-creation'));
    if (startedFromMedia) window.seldrunePortal?.activate('operator');
    requestAnimationFrame(() => input.focus());
  });

  document.querySelectorAll('.gpt-creation-mode').forEach(button => {
    button.addEventListener('click', () => {
      setCreationMode(button.dataset.creationMode);
      if (button.closest('#seldrune-media-creation')) {
        window.seldrunePortal?.activate('operator');
        requestAnimationFrame(() => input?.focus());
      }
    });
  });

  async function runCognitiveRequest(order, commandId = null, confirmed = false) {
    return api('/gpt/operate', {
      method: 'POST',
      body: JSON.stringify({
        order,
        conversation_id: activeConversationId,
        command_id: commandId,
        confirm_sensitive_action: confirmed,
        stop_on_failure: true,
        max_steps: 50,
        max_retries_per_step: 1,
      }),
    });
  }

  function mediaToolReady(kind) {
    const terms = {
      song: ['audio', 'music', 'song', 'speech'],
      video: ['video', 'movie', 'clip'],
      visual: ['image', 'visual', '3d', 'render'],
    }[kind] || [];
    return registeredTools.some(slug => terms.some(term => slug.toLowerCase().includes(term)));
  }

  function requestNeedsAction(request, mode = creationMode, hasAttachments = false) {
    if (hasAttachments) return false;
    if (mode === 'app' || mode === 'game') return true;
    const text = String(request || '').trim();
    const mediaIntent = /\b(create|generate|make|compose|produce|render)\b.{0,70}\b(audio|song|music|video|film|movie|clip)\b/i.test(text);
    const unrealAction = /\b(download|install|set\s+up|setup|check|inspect|show|get|verify|is)\b.{0,90}\b(unreal(?:\s+engine)?|ue[45](?:\.\d+)?)\b/i.test(text)
      || /\b(unreal(?:\s+engine)?|ue[45](?:\.\d+)?)\b.{0,40}\b(status|ready|installed|version|worker|connection|connected)\b/i.test(text);
    if (unrealAction) return true;
    const inferredMediaKind = classifyOutputKind(text, 'any');
    if (['song', 'video', 'visual'].includes(mode)) {
      return mediaIntent && inferredMediaKind === mode && mediaToolReady(mode);
    }
    const startsAsInfoQuestion = /^(how do i|how can i|what is|what are|why|who|when|where|explain|tell me about|compare|summari[sz]e|recommend|suggest|brainstorm)\b/i.test(text);
    const directBuildRequest = /\b(create|build|develop|implement|write|generate|make|fix|update|deploy|run|test|commit|push|connect|activate|configure|publish|schedule|send|delete|remove|purchase|transfer|sign|hire|fire)\b.{0,90}\b(app|application|game|website|web app|software|code|script|repository|repo|branch|feature|bug|server|service|project|account|email|message|invoice|contract|job|event|media|image|video|audio|song)\b/i.test(text);
    const directExternalAction = /\b(deploy|run|execute|perform|fix|update|change|activate|configure|connect|commit|push|merge|publish|schedule|send|delete|remove|purchase|transfer|sign|hire|fire|open a pull request|create (?:a |an )?(?:repository|repo|branch))\b/i.test(text);
    const codeDelivery = /\b(create|build|develop|implement|write|generate|make)\b.{0,90}\b(app|application|game|website|web app|software|code|script|repository|repo|feature|project)\b/i.test(text);
    if (startsAsInfoQuestion && !/\b(for me|on my behalf|please (?:create|build|deploy|run|write|make|fix))\b/i.test(text)) {
      return codeDelivery && /^(?:can you|could you|please|i want you to)\b/i.test(text);
    }
    const kind = classifyOutputKind(text, mode);
    if (['song', 'video', 'visual'].includes(kind)) {
      // Media creation is opt-in from the Media workspace; ordinary chat stays text-only.
      return mode !== 'any' && mediaIntent && inferredMediaKind === kind && mediaToolReady(kind);
    }
    return directExternalAction || codeDelivery;
  }

  function buildChatRequest(request, kind) {
    const instructions = {
      app: 'Return a useful source draft with a clear file tree, concise runnable code blocks, and focused tests. State clearly that the chat response itself did not write or test repository files.',
      game: 'Return a playable game source draft with controls, game loop, accessibility notes, and focused tests. State clearly that chat did not write or test repository files.',
      song: 'Return lyrics, chords, tempo, structure, and production notes. This chat cannot render audio; label the result as a text package and do not claim an audio file exists.',
      video: 'Return script, storyboard, shot list, and edit cues. This chat cannot render video; label the result as a text package and do not claim a video file exists.',
      visual: 'Return art direction and a detailed visual/3D design package. This chat cannot render an image or 3D asset; label the result as a text package and do not claim a binary asset exists.',
      document: 'Return a complete, clearly structured document suitable for saving as Markdown.',
      creative: 'Complete the requested creative output as usable text and say exactly what file type is being returned.',
      build: 'Provide a useful technical analysis or build plan. Do not claim that a build, deployment, or external action ran.',
    }[kind] || 'Return a useful answer as text.';
    return `${request}\n\nSeldrune output instructions: ${instructions}`;
  }

  async function saveOperatorReceipt(request, result, source = 'Seldrune Coding Lab') {
    const receipt = {
      requested_by: source,
      objective: request,
      status: result.status,
      run_status: result.run_status,
      command_id: result.command_id,
      executed_steps: result.executed_steps || 0,
      failed_steps: result.failed_steps || 0,
      blocked_steps: result.blocked_steps || 0,
      halted_reason: result.halted_reason || null,
      evidence_url: result.evidence_url || null,
      recorded_at: new Date().toISOString(),
    };
    const title = titleFromRequest(request, 'build');
    return saveOutputRecord(createOutputRecord({
      title,
      kind: 'build',
      fileName: outputFilename(title, 'json'),
      blob: new Blob([JSON.stringify(receipt, null, 2)], {type: 'application/json'}),
      note: 'Execution receipt · reports only the status and evidence returned by Seldrune.',
    }));
  }

  function renderCodingRun(request, result, receipt) {
    const root = document.querySelector('#coding-lab-run-list');
    const labStatus = document.querySelector('#coding-lab-status');
    if (!root) return;
    const card = document.createElement('article');
    card.className = 'coding-lab-run';
    const title = document.createElement('h3');
    title.textContent = `${result.status || 'unknown'} · ${titleFromRequest(request, 'build')}`;
    const detail = document.createElement('p');
    detail.textContent = `${result.executed_steps || 0} steps executed · ${result.failed_steps || 0} failed · ${result.blocked_steps || 0} blocked · run ${result.run_status || 'not reported'}`;
    card.append(title, detail);
    if (result.halted_reason) {
      const halted = document.createElement('p');
      halted.textContent = `Stopped: ${result.halted_reason}`;
      card.append(halted);
    }
    if (result.evidence_url) {
      const evidence = document.createElement('a');
      evidence.href = result.evidence_url;
      evidence.target = '_blank';
      evidence.rel = 'noopener noreferrer';
      evidence.textContent = 'Open verified run evidence';
      card.append(evidence);
    }
    if (receipt) {
      const saved = document.createElement('p');
      saved.textContent = `Receipt saved as ${receipt.fileName}.`;
      card.append(saved);
    }
    const outputsButton = document.createElement('button');
    outputsButton.type = 'button';
    outputsButton.className = 'ghost';
    outputsButton.dataset.openPortal = 'outputs';
    outputsButton.textContent = 'Open Outputs';
    card.append(outputsButton);
    root.prepend(card);
    if (labStatus) {
      const evidence = result.evidence_url
        ? 'Open the returned run evidence for detail.'
        : 'No provider evidence URL was returned.';
      const saved = receipt
        ? 'The run receipt is saved in Outputs.'
        : 'No run receipt was saved.';
      labStatus.textContent = `Build request status: ${result.status}. ${evidence} ${saved}`;
    }
  }

  async function generateTextDraft(request, kind, reason = '') {
    const notice = reason ? `${reason}\n\n` : '';
    const result = await api('/gpt', {
      method: 'POST',
      body: JSON.stringify({
        message: `${notice}${buildChatRequest(request, kind)}`,
        attachments: [],
        conversation_id: activeConversationId,
        provider: providerSelect?.value || 'auto',
      }),
    });
    model.textContent = (result.provider ? result.provider + ' · ' : '') + (result.model || 'Seldrune AI');
    const draftText = result.response || '(No text returned)';
    const label = ['app', 'game'].includes(kind)
      ? 'Seldrune AI · source draft · not committed or tested'
      : 'Seldrune AI · text package · media not rendered';
    const card = addMessage(label, draftText);
    addPdfExportButton(card, request, draftText);
    const record = await saveTextArtifact(
      request,
      draftText,
      kind,
      ['song', 'video', 'visual'].includes(kind)
        ? 'Text package · no rendered media file was produced.'
        : ['app', 'game'].includes(kind)
          ? 'Source draft · not committed to a repository and not run through CI.'
          : 'Generated text output · saved as Markdown.',
    );
    outputShortcut(card);
    status.textContent = `${record.fileName} saved in Outputs · ${['app', 'game'].includes(kind) ? 'draft only; no repository files or tests were changed' : 'text file; no rendered media was produced'}.`;
    return record;
  }

  async function runOperatorRequest({request, order, label = 'Seldrune AI', fallbackKind = null, codingLab = false}) {
    const labStatus = document.querySelector('#coding-lab-status');
    if (order.length > 8000) {
      const message = 'This tool request is over the 8,000 character limit. Shorten it or split it into smaller requests; no external action was started.';
      addMessage('Seldrune AI', message);
      status.textContent = 'Request too long · no external action started.';
      if (codingLab && labStatus) labStatus.textContent = message;
      return;
    }
    setBusy(true, 'Seldrune is routing this request through connected tools and verification…');
    if (codingLab && labStatus) labStatus.textContent = 'Planning with Seldrune agents and checking connected provider tools…';
    addMessage(codingLab ? 'You · Coding Lab' : 'You', request, 'user');
    try {
      const result = await runCognitiveRequest(order);
      await refreshConversations();
      await loadCapabilities();
      if (result.status === 'configuration_required') {
        const missing = (result.missing_tools || []).join(', ');
        const hints = (result.configuration_hints || []).join(', ');
        const needsUnreal = /unreal/i.test(missing + ' ' + hints);
        const setupMessage = needsUnreal
          ? 'Unreal Engine is integrated with Seldrune GPT. Connect a compatible worker in Connections once to enable engine checks and install jobs.'
          : `No external action started. Required provider tools are not configured: ${missing || 'provider tool'}`
            + (hints ? `. Configure: ${hints}.` : '.');
        const setupCard = addMessage('Seldrune AI', setupMessage);
        if (needsUnreal) addUnrealConnectionButton(setupCard);
        let draft = null;
        if (fallbackKind) {
          try {
            draft = await generateTextDraft(request, fallbackKind, 'Connected tools could not start this build, so Seldrune is returning a downloadable draft instead.');
          } catch (error) {
            addMessage('Seldrune AI', `The source draft could not be generated or saved: ${error.message}`);
          }
        }
        if (codingLab) {
          renderCodingRun(request, result, null);
          if (labStatus) labStatus.textContent = draft
            ? `No repository changes were made. Source draft saved in Outputs as ${draft.fileName}.`
            : 'No repository changes were made and no source draft was saved.';
        }
        status.textContent = codingLab
          ? 'Build tools are not ready · no repository changes were made.'
          : 'No external action started · provider configuration required.';
        return;
      }
      if (result.status === 'failed' && result.halted_reason === 'required_external_tool_not_planned') {
        const missing = (result.missing_tools || []).join(', ');
        const missingUnreal = /unreal/i.test(missing);
        const haltedCard = addMessage(
          'Seldrune AI',
          missingUnreal
            ? 'Unreal Engine is integrated with Seldrune GPT. Connect and verify its worker in Connections to run this action.'
            : `Stopped before the external action because required tool inputs were unresolved: ${missing || 'see command evidence'}.`,
        );
        if (missingUnreal) addUnrealConnectionButton(haltedCard);
        const receipt = result.command_id ? await saveOperatorReceipt(request, result, label) : null;
        if (receipt) outputShortcut(thread.lastElementChild);
        let draft = null;
        if (fallbackKind) {
          try {
            draft = await generateTextDraft(request, fallbackKind, 'Seldrune could not complete the connected build action, so this is a draft file.');
          } catch (error) {
            addMessage('Seldrune AI', `The source draft could not be generated or saved: ${error.message}`);
          }
        }
        if (codingLab) {
          renderCodingRun(request, result, receipt);
          if (labStatus) labStatus.textContent = `The connected action stopped before completion.${draft ? ` Draft saved as ${draft.fileName}.` : ' No source draft was saved.'}${receipt ? ` Receipt saved as ${receipt.fileName}.` : ''}`;
        }
        status.textContent = `No external action completed · evidence ${result.command_id || 'unavailable'}`;
        return;
      }
      if (result.approval_required) {
        if (window.seldrunePortal?.activate) window.seldrunePortal.activate('operator');
        addApprovalPrompt(order, result, {request, codingLab, label});
        status.textContent = 'Sensitive action paused · waiting for your confirmation.';
        if (codingLab && labStatus) labStatus.textContent = 'Owner confirmation is required in the Seldrune AI conversation.';
        return;
      }
      const summary = `${result.status}: ${result.executed_steps || 0} executed, ${result.failed_steps || 0} failed, ${result.blocked_steps || 0} blocked. Command ${result.command_id || 'not recorded'}.`;
      const card = addMessage('Seldrune AI', summary);
      let receipt = null;
      if (result.command_id) {
        try {
          receipt = await saveOperatorReceipt(request, result, label);
          outputShortcut(card);
        } catch (error) {
          status.textContent = `Run finished; receipt could not be saved to Outputs: ${error.message}`;
        }
      }
      if (codingLab) renderCodingRun(request, result, receipt);
      status.textContent = `Seldrune run ${result.status} · ${result.executed_steps || 0} steps · evidence ${result.command_id || 'unavailable'}`;
      window.dispatchEvent(new CustomEvent('seldrune:refresh'));
    } catch (error) {
      addMessage('System', `Seldrune could not complete the request: ${error.message}`);
      if (fallbackKind) {
        try {
          await generateTextDraft(request, fallbackKind, 'The connected action did not complete. This is a draft output only.');
        } catch (draftError) {
          status.textContent = `Request failed: ${error.message}. Draft fallback failed: ${draftError.message}`;
        }
      } else {
        status.textContent = 'Request failed before a verified result was returned.';
      }
    } finally {
      setBusy(false);
      if (codingLab) document.querySelector('#coding-lab-brief')?.focus();
      else input.focus();
    }
  }

  function addApprovalPrompt(order, result, context = {}) {
    if (thread.querySelector('.empty')) thread.replaceChildren();
    const card = document.createElement('article');
    card.className = 'command-card gpt-approval-card';
    card.dataset.role = 'assistant';

    const heading = document.createElement('strong');
    heading.textContent = 'Owner confirmation';
    const message = document.createElement('p');
    const reasons = Array.isArray(result.risk_reasons) ? result.risk_reasons : [];
    message.textContent = 'Sensitive action paused: ' + reasons.join(', ')
      + '. Nothing has run yet. Confirm once to continue.';
    const actions = document.createElement('div');
    actions.className = 'gpt-approval-actions';

    const confirmButton = document.createElement('button');
    confirmButton.type = 'button';
    confirmButton.textContent = 'Confirm once and run';
    const cancelButton = document.createElement('button');
    cancelButton.type = 'button';
    cancelButton.className = 'ghost';
    cancelButton.textContent = 'Cancel';

    cancelButton.addEventListener('click', () => {
      message.textContent = 'Execution canceled. No sensitive action ran.';
      actions.remove();
      status.textContent = 'No action ran · command ' + result.command_id
        + ' remains unexecuted.';
    });
    confirmButton.addEventListener('click', async () => {
      confirmButton.disabled = true;
      cancelButton.disabled = true;
      setBusy(true, 'Owner confirmed once · Seldrune is executing and verifying…');
      try {
        const completed = await runCognitiveRequest(order, result.command_id, true);
        const summary = completed.status + ': '
          + (completed.executed_steps || 0) + ' executed, '
          + (completed.failed_steps || 0) + ' failed, '
          + (completed.blocked_steps || 0) + ' blocked. Command '
          + completed.command_id + '.';
        const responseCard = addMessage('Seldrune AI', summary);
        try {
          const receipt = await saveOperatorReceipt(
            context.request || order,
            completed,
            context.label || 'Seldrune AI',
          );
          outputShortcut(responseCard);
          if (context.codingLab) renderCodingRun(context.request || order, completed, receipt);
        } catch (error) {
          status.textContent = `Run finished; receipt could not be saved to Outputs: ${error.message}`;
        }
        status.textContent = 'Verified cognitive run · ' + completed.status
          + ' · evidence ' + completed.command_id;
        window.dispatchEvent(new CustomEvent('seldrune:refresh'));
        await loadCapabilities();
      } catch (error) {
        message.textContent = 'Execution did not complete: ' + error.message;
        confirmButton.disabled = false;
        cancelButton.disabled = false;
        status.textContent = 'Execution needs attention.';
      } finally {
        setBusy(false);
        if (context.codingLab) document.querySelector('#coding-lab-brief')?.focus();
        else input.focus();
      }
    });

    actions.append(confirmButton, cancelButton);
    card.append(heading, message, actions);
    thread.append(card);
    card.scrollIntoView({
      behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
      block: 'nearest',
    });
  }

  async function runAiPdfEdit(instruction, pdf) {
    setBusy(
      true,
      'AI PDF Editor is analyzing the document and applying your instruction…',
    );
    addMessage('You', `${instruction}\nAI PDF edit: ${pdf.name}`, 'user');
    try {
      const result = await api('/gpt/pdf/edit', {
        method: 'POST',
        body: JSON.stringify({
          instruction,
          conversation_id: activeConversationId,
          pdf: {
            name: pdf.name,
            media_type: pdf.media_type,
            data_base64: pdf.data_base64,
          },
          password: pdfPassword?.value || null,
        }),
      });
      clearAttachments();
      input.value = '';
      model.textContent = result.model || 'OpenAI';
      await refreshConversations();
      const warningText = (result.warnings || []).length
        ? ` Warnings: ${result.warnings.join('; ')}`
        : '';
      const verification = Number.isFinite(result.verification_score)
        ? `${result.verification_score}% content-verified`
        : 'content verification unavailable';
      const fidelity = Number.isFinite(result.visual_fidelity_score)
        ? `${result.visual_fidelity_score}% original-look fidelity`
        : 'original-look fidelity not machine-verifiable for this PDF type';
      const layout = Number.isFinite(result.layout_integrity_score)
        ? `${result.layout_integrity_score}% layout integrity`
        : 'layout integrity unavailable';
      const cost = Number.isFinite(result.estimated_ai_cost_usd)
        ? `AI cost ~${Number(result.estimated_ai_cost_usd).toFixed(4)}`
        : 'AI cost unavailable';
      const modelRoute = (result.models_used || []).length
        ? `${result.models_used.join(' → ')} · ${result.model_calls || 0} model call${result.model_calls === 1 ? '' : 's'}`
        : null;
      const profile = [
        result.document_type || 'PDF',
        `${result.page_count || 0} pages`,
        result.image_only_pages
          ? `${result.image_only_pages} scanned/image pages`
          : 'native text',
        result.form_fields
          ? `${result.form_fields} form fields`
          : null,
        result.reconstruction_attempts > 1
          ? `${result.reconstruction_attempts} clean reconstruction attempts`
          : null,
        modelRoute,
        cost,
      ].filter(Boolean).join(' · ');
      addDownloadMessage(
        'Seldrune AI · AI PDF Editor',
        `${result.summary || 'PDF edit completed.'} Applied edits: ${result.applied_edits || 0}. ${verification}. ${fidelity}. ${layout}. ${profile}.${warningText}`,
        result.filename,
        result.data_base64,
      );
      status.textContent = `Edited PDF ready · ${verification} · ${layout} · ${cost} · ${result.filename}`;
    } catch (error) {
      addMessage('System', `AI PDF edit failed: ${error.message}`);
      status.textContent =
        'AI PDF edit failed. The original PDF is still attached so you can refine the instruction and retry.';
    } finally {
      setBusy(false);
      renderAttachments();
      input.focus();
    }
  }

  function shouldSaveTextOutput(request, mode = creationMode) {
    return mode !== 'any' || /\b(create|build|write|generate|make|compose|draft|design|produce|draw|render)\b/i.test(request);
  }

  function requestedMediaKind(request) {
    if (['image', 'speech', 'video', 'song'].includes(creationMode)) return creationMode;
    if (creationMode === 'visual') {
      return /\b(3d model|3d scene)\b/i.test(request) ? 'visual3d' : 'image';
    }
    const text = String(request || '').trim();
    const mediaForExistingApp = /\b(song|music|lyrics|soundtrack|audio|spoken audio|voiceover|video|film|movie|clip|trailer|storyboard|image|illustration|picture|visual|poster|artwork)\b.{0,60}\b(?:for|about|of)\s+(?:(?:my|our|the|an?)\s+)?(?:app|application|website|web app|game)\b/i.test(text);
    const appRequest = /\b(app|application|website|web app|software|program|source code|coding|game)\b/i.test(text);
    if (appRequest && !mediaForExistingApp) return null;
    if (/\b(create|generate|make|render|produce)\b.{0,100}\b(video|film|movie|clip|trailer)\b/i.test(text)) {
      return 'video';
    }
    if (/\b(create|generate|make|render|draw|produce)\b.{0,100}\b(image|illustration|picture|poster|artwork|visual)\b/i.test(text)) {
      return 'image';
    }
    if (/\b(create|generate|make|produce|narrate|speak)\b.{0,100}\b(spoken audio|narration|voice ?over|speech|voice)\b/i.test(text)
      || /\b(read|speak)\b.{0,40}\b(aloud|out loud)\b/i.test(text)) {
      return 'speech';
    }
    if (/\b(create|generate|make|compose|produce|write)\b.{0,100}\b(song|music|soundtrack)\b/i.test(text)) {
      return 'song';
    }
    if (/\b(create|generate|make|render|produce)\b.{0,100}\b(3d model|3d scene)\b/i.test(text)) {
      return 'visual3d';
    }
    return null;
  }

  function showMediaUnavailable(kind, request, attachmentNames = []) {
    addMessage(
      'You',
      request + (attachmentNames.length ? `\nAttachments: ${attachmentNames.join(', ')}` : ''),
      'user',
    );
    input.value = '';
    clearAttachments();
    const messages = {
      video: 'No video file was created. Seldrune does not have a supported video renderer connected yet.',
      song: 'No music file was created. Seldrune does not have a music-generation provider connected yet.',
      visual3d: 'No 3D file was created. Seldrune image generation creates 2D PNG images only.',
    };
    const card = addMessage('Seldrune AI', messages[kind] || 'No media file was created.');
    if (kind === 'video' || kind === 'song') {
      const connections = document.createElement('button');
      connections.type = 'button';
      connections.className = 'ghost';
      connections.dataset.openPortal = 'connections';
      connections.textContent = 'Open Connections';
      card.append(connections);
    }
    status.textContent = messages[kind] || 'No media file was created.';
  }

  async function runMediaCreation(kind, request, outgoingAttachments, attachmentNames) {
    addMessage(
      'You',
      request + (attachmentNames.length ? `\nAttachments: ${attachmentNames.join(', ')}` : ''),
      'user',
    );
    input.value = '';
    clearAttachments();
    setBusy(true, `Creating ${kind === 'image' ? 'image' : 'spoken audio'} file…`);
    try {
      if (outgoingAttachments.length) {
        throw new Error('Reference attachments are not supported for media creation yet.');
      }
      const result = await api('/gpt/media', {
        method: 'POST',
        body: JSON.stringify({
          kind,
          prompt: request,
          conversation_id: activeConversationId,
        }),
      });
      if (!result.data_base64 || !result.file_name || !result.mime_type) {
        throw new Error('The provider did not return a downloadable file.');
      }
      if (result.conversation_id) activeConversationId = result.conversation_id;
      model.textContent = `${result.model || 'OpenAI'} · ${kind === 'image' ? 'image' : 'speech'}`;
      const blob = base64Blob(result.data_base64, result.mime_type);
      const title = titleFromRequest(request, kind);
      const fileName = result.file_name;
      const previewUrl = URL.createObjectURL(blob);
      const disclosure = result.disclosure ? ` ${result.disclosure}` : '';
      const card = addMessage(
        'Seldrune AI',
        `Created ${kind === 'image' ? 'image' : 'spoken-audio'} file: ${fileName}.${disclosure}`,
      );
      const preview = kind === 'image'
        ? document.createElement('img')
        : document.createElement('audio');
      preview.className = 'gpt-generated-media-preview';
      preview.src = previewUrl;
      if (kind === 'image') {
        preview.alt = title;
        preview.loading = 'lazy';
        preview.style.maxWidth = '100%';
        preview.style.maxHeight = '560px';
      } else {
        preview.controls = true;
        preview.preload = 'metadata';
        preview.style.width = 'min(100%, 480px)';
      }
      const download = document.createElement('a');
      download.className = 'ghost';
      download.href = previewUrl;
      download.download = fileName;
      download.textContent = `Download ${fileName}`;
      card.append(preview, download);
      outputShortcut(card);

      const note = kind === 'image'
        ? 'AI-generated PNG image.'
        : `AI-generated narration. ${result.disclosure || ''}`.trim();
      try {
        await saveOutputRecord(createOutputRecord({
          title,
          kind,
          fileName,
          blob,
          note,
        }));
        const cost = Number(result.estimated_cost_usd || 0).toFixed(4);
        status.textContent = `${fileName} created and saved in Outputs · estimated cost USD ${cost}`;
      } catch (error) {
        status.textContent = `${fileName} was created and is downloadable here, but could not be saved to Outputs: ${error.message}`;
      }
      try {
        await refreshConversations();
      } catch (error) {
        status.textContent = `${fileName} is created and saved; chat history could not refresh: ${error.message}`;
      }
    } catch (error) {
      const errorCard = addMessage('Seldrune AI', `No downloadable file was returned. ${error.message}`);
      if (/connect openai|saved openai|openai.*connection|configure.*openai_api_key/i.test(error.message)) {
        const connections = document.createElement('button');
        connections.type = 'button';
        connections.className = 'ghost';
        connections.dataset.openPortal = 'connections';
        connections.textContent = 'Open Connections';
        errorCard.append(connections);
      }
      status.textContent = `No downloadable file was returned. ${error.message}`;
    } finally {
      setBusy(false);
      input.focus();
    }
  }

  async function runUniversalMessage(request, outgoingAttachments, attachmentNames) {
    const connectUnreal = /\b(connect|configure|set\s+up|setup)\b.{0,80}\bunreal(?:\s+engine)?\b/i.test(request);
    if (connectUnreal && !outgoingAttachments.length) {
      addMessage('You', request, 'user');
      input.value = '';
      clearAttachments();
      const card = addMessage(
        'Seldrune AI',
        'Unreal Engine worker setup is built into Seldrune GPT. I’m opening its secure connection form; once a worker verifies, GPT can check engine status and queue installs.',
      );
      addUnrealConnectionButton(card, 'Open secure Unreal connection');
      status.textContent = 'Opening Unreal Engine connection setup…';
      openUnrealConnections();
      return;
    }
    const mediaKind = requestedMediaKind(request);
    if (mediaKind) {
      if (mediaKind === 'image' || mediaKind === 'speech') {
        await runMediaCreation(mediaKind, request, outgoingAttachments, attachmentNames);
      } else {
        showMediaUnavailable(mediaKind, request, attachmentNames);
      }
      return;
    }
    const kind = classifyOutputKind(request);
    const useTools = requestNeedsAction(request, creationMode, outgoingAttachments.length > 0);
    if (useTools) {
      input.value = '';
      clearAttachments();
      const fallbackKind = ['app', 'game'].includes(kind)
        ? kind
        : (creationMode === 'app' || creationMode === 'game' ? creationMode : null);
      await runOperatorRequest({
        request,
        order: buildCreativeOrder(request),
        fallbackKind,
      });
      return;
    }

    setBusy(true, 'Seldrune is reasoning across your message and attachments…');
    addMessage(
      'You',
      request + (attachmentNames.length ? `\nAttachments: ${attachmentNames.join(', ')}` : ''),
      'user',
    );
    input.value = '';
    try {
      const chatMessage = shouldSaveTextOutput(request)
        ? buildChatRequest(buildCreativeOrder(request), kind)
        : request;
      const result = await api('/gpt', {
        method: 'POST',
        body: JSON.stringify({
          message: chatMessage,
          attachments: outgoingAttachments,
          conversation_id: activeConversationId,
          provider: providerSelect?.value || 'auto',
        }),
      });
      clearAttachments();
      model.textContent = (result.provider ? result.provider + ' · ' : '') + (result.model || 'Seldrune AI');
      if (result.conversation_id) activeConversationId = result.conversation_id;
      const responseText = result.response || '(No text returned)';
      const responseCard = addMessage('Seldrune AI', responseText);
      const pdfExportButton = addPdfExportButton(responseCard, request, responseText);
      await refreshConversations();
      let savedOutput = null;
      if (shouldSaveTextOutput(request)) {
        try {
          const note = kind === 'song' || kind === 'video' || kind === 'visual'
            ? 'Text package · no rendered media file was produced.'
            : kind === 'app' || kind === 'game'
              ? 'Source draft · not committed to a repository and not run through CI.'
              : 'Generated text output · saved as Markdown.';
          savedOutput = await saveTextArtifact(request, responseText, kind, note);
          outputShortcut(responseCard);
        } catch (error) {
          status.textContent = `Response received; it could not be saved to Outputs: ${error.message}`;
        }
      }
      const chatCost = Number.isFinite(result.estimated_cost_usd)
        ? ` · ~${Number(result.estimated_cost_usd).toFixed(4)}`
        : '';
      const cached = Number(result.cached_input_tokens || 0);
      const outputNote = savedOutput ? ` · saved ${savedOutput.fileName} in Outputs` : '';
      const textOnlyNote = ['song', 'video', 'visual'].includes(kind) && shouldSaveTextOutput(request)
        ? ' · text package only; no media render'
        : '';
      status.textContent = `${result.provider || 'openai'} · ${result.model || 'model'} (${result.cost_tier || 'auto'}) · ${result.latency_ms || 0} ms · ${result.input_tokens || 0} input · ${result.output_tokens || 0} output${cached ? ` · ${cached} cached` : ''}${chatCost}${outputNote}${textOnlyNote}`;
      if (requestNeedsPdf(request)) {
        try {
          const created = await createPdfOutput(request, responseText, responseCard);
          if (pdfExportButton) pdfExportButton.textContent = 'Create another PDF';
          status.textContent = `${created.record.fileName} created · ${created.pageCount} page(s) · saved in Outputs.`;
        } catch (error) {
          status.textContent = `Answer received; PDF creation failed: ${error.message}`;
        }
      }
    } catch (error) {
      addMessage('System', `Seldrune AI request failed: ${error.message}`);
      status.textContent = 'Request failed.';
    } finally {
      setBusy(false);
      input.focus();
    }
  }

  function initializeCodingLab() {
    const labForm = document.querySelector('#coding-lab-form');
    if (!labForm || labForm.dataset.bound === 'true') return;
    labForm.dataset.bound = 'true';
    renderCodingProviderStatus();
    labForm.addEventListener('submit', async event => {
      event.preventDefault();
      const brief = document.querySelector('#coding-lab-brief')?.value.trim() || '';
      const repository = document.querySelector('#coding-lab-repository')?.value.trim() || '';
      if (brief.length < 5) return;
      const target = repository
        ? `Target repository or project: ${repository}.`
        : 'Use a connected repository only if the owner has a single unambiguous target; otherwise stop and ask which repository to use.';
      const order = [
        'Seldrune RapidBuild Loop coding request.',
        target,
        `Build goal: ${brief}`,
        'When building or cloning a camera or microphone app hosted on the authenticated Seldrune origin, load the shared media client as a required bootstrap before app code: <script src="/console-assets/seldrune-media.js" data-default="true" defer></script>. Use navigator.mediaDevices.getUserMedia for all capture so every app uses the owner's saved /media face and voice profiles. Tell the owner to enable Use Seldrune Media by default in /media. Preserve fail-closed behavior; never silently fall back to raw device media. For apps hosted on other origins, do not claim this same-origin client is installed.',
        'Use connected GitHub tools to create a branch named for this isolated change, write the requested source and focused tests to repository files, and report the exact changed paths. Run the repository checks using an actually configured CI workflow and report the returned status and run URL. If Railway is connected, use only an existing preview environment and report its deployment receipt. Do not merge a pull request, deploy to production, create new paid services, or spend outside existing budget controls. If any required provider is missing, stop before external changes and return the missing provider details. Never claim files, tests, or previews exist without a tool receipt.',
      ].join('\n\n');
      const fallbackBrief = `${brief}\n\nTarget repository or project: ${repository || 'not specified'}.`;
      const fallbackKind = classifyOutputKind(brief) === 'game' ? 'game' : 'app';
      await runOperatorRequest({
        request: fallbackBrief,
        order,
        label: 'Seldrune Coding Lab',
        fallbackKind,
        codingLab: true,
      });
    });
  }

  form.addEventListener('submit', async event => {
    event.preventDefault();
    const message = input.value.trim();
    if (!message) return;

    const mediaModeUsed = ['image', 'speech', 'song', 'video', 'visual', 'document'].includes(creationMode);
    try {
      const pdfAttachments = attachments.filter(
        item => item.media_type === 'application/pdf',
      );
      if (pdfAttachments.length === 1 && attachments.length === 1) {
        await runAiPdfEdit(message, pdfAttachments[0]);
        return;
      }
      const outgoingAttachments = attachments.map(item => ({
        name: item.name,
        media_type: item.media_type,
        data_base64: item.data_base64,
      }));
      const attachmentNames = attachments.map(item => item.name);
      await runUniversalMessage(message, outgoingAttachments, attachmentNames);
    } finally {
      if (mediaModeUsed) setCreationMode('any');
    }
  });

  document.addEventListener('seldrune:integrations-updated', () => {
    void loadCapabilities();
  });
  document.addEventListener('seldrune:portal-ready', () => {
    initializeOutputLibrary();
    initializeCodingLab();
    renderCodingProviderStatus();
  });
  document.addEventListener('seldrune:workspace-change', event => {
    if (event.detail?.workspace === 'outputs') void renderOutputLibrary();
  });
  document.addEventListener('seldrune:outputs-changed', () => {
    if (document.querySelector('#seldrune-output-list')) void renderOutputLibrary();
  });

  renderAttachments();
  initializeOutputLibrary();
  initializeCodingLab();
  document.addEventListener('seldrune:console-ready', initializeGptWorkspace);
  if (typeof state !== 'undefined' && state.org) initializeGptWorkspace();
})();
