(() => {
  const form = document.querySelector('#seldrune-gpt-form');
  if (!form) return;

  const input = document.querySelector('#seldrune-gpt-input');
  const thread = document.querySelector('#seldrune-gpt-thread');
  const status = document.querySelector('#seldrune-gpt-status');
  const model = document.querySelector('#seldrune-gpt-model');
  const newConversation = document.querySelector('#seldrune-gpt-new');
  const chatButton = document.querySelector('#seldrune-gpt-chat');
  const executeButton = document.querySelector('#seldrune-gpt-execute');
  const attachButton = document.querySelector('#seldrune-gpt-attach');
  const fileInput = document.querySelector('#seldrune-gpt-files');
  const dropzone = document.querySelector('#seldrune-gpt-dropzone');
  const attachmentList = document.querySelector('#seldrune-gpt-attachments');
  const attachmentSummary = document.querySelector('#seldrune-gpt-attachment-summary');
  const modePill = document.querySelector('#seldrune-gpt-mode');
  const pdfPasswordWrap = document.querySelector('#seldrune-gpt-pdf-password-wrap');
  const pdfPassword = document.querySelector('#seldrune-gpt-pdf-password');

  const MAX_FILES = 6;
  const MAX_FILE_BYTES = 8 * 1024 * 1024;
  const MAX_PDF_EDIT_BYTES = 25 * 1024 * 1024;
  const MAX_TOTAL_BYTES = 32 * 1024 * 1024;
  const attachments = [];

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
  }

  function setBusy(busy, message) {
    input.disabled = busy;
    chatButton.disabled = busy;
    executeButton.disabled = busy;
    attachButton.disabled = busy;
    fileInput.disabled = busy;
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
      modePill.textContent = aiPdfMode ? 'AI PDF Editor' : 'Chat';
      modePill.classList.toggle('active', aiPdfMode);
    }
    if (chatButton) {
      chatButton.innerHTML = aiPdfMode
        ? 'AI Edit PDF <span>✦</span>'
        : 'Chat <span>→</span>';
    }
    if (executeButton) executeButton.hidden = aiPdfMode;
    if (input) {
      input.placeholder = aiPdfMode
        ? 'Tell Seldrune exactly what to change in this PDF…'
        : 'Message Seldrune GPT…';
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

  async function loadHistory() {
    try {
      const messages = await api('/gpt/history');
      if (!messages.length) return;
      thread.replaceChildren();
      messages.forEach(item => addMessage(
        item.role === 'assistant' ? 'Seldrune GPT' : 'You',
        item.content,
        item.role === 'assistant' ? 'assistant' : 'user',
      ));
      status.textContent = `Restored ${messages.length} saved messages.`;
    } catch (error) {
      status.textContent = `History unavailable: ${error.message}`;
    }
  }

  newConversation?.addEventListener('click', async () => {
    if (!window.confirm('Start a new Seldrune GPT conversation and clear saved context?')) return;
    try {
      await api('/gpt/history', {method: 'DELETE'});
      clearAttachments();
      thread.innerHTML = '<div class="empty">New conversation started.</div>';
      status.textContent = 'Saved GPT context cleared.';
    } catch (error) {
      status.textContent = `Could not clear history: ${error.message}`;
    }
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

  document.querySelectorAll('[data-gpt-prompt]').forEach(button => {
    button.addEventListener('click', () => {
      input.value = button.dataset.gptPrompt || '';
      input.focus();
    });
  });

  async function executeOrder(order, commandId = null, confirmed = false) {
    return api('/gpt/operate', {
      method: 'POST',
      body: JSON.stringify({
        order,
        command_id: commandId,
        confirm_sensitive_action: confirmed,
        stop_on_failure: true,
        max_steps: 50,
        max_retries_per_step: 1,
      }),
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
      ].filter(Boolean).join(' · ');
      addDownloadMessage(
        'Seldrune GPT · AI PDF Editor',
        `${result.summary || 'PDF edit completed.'} Applied edits: ${result.applied_edits || 0}. ${verification}. ${fidelity}. ${layout}. ${profile}.${warningText}`,
        result.filename,
        result.data_base64,
      );
      status.textContent = `Edited PDF ready · ${verification} · ${fidelity} · ${layout} · ${result.filename}`;
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

  executeButton?.addEventListener('click', async () => {
    const order = input.value.trim();
    if (!order) return;
    if (attachments.length) {
      status.textContent = 'Analyze attachments with Chat first, then execute the resulting text order.';
      return;
    }
    setBusy(true, 'Seldrune Operator is planning and executing…');
    addMessage('Owner order', order, 'user');
    input.value = '';
    try {
      let result = await executeOrder(order);
      if (result.status === 'configuration_required') {
        const missing = (result.missing_tools || []).join(', ');
        const hints = (result.configuration_hints || []).join(', ');
        addMessage(
          'Seldrune Operator',
          `Configuration required before execution. Missing: ${missing || 'provider tool'}`
          + (hints ? `. Configure service secret(s): ${hints}.` : '.'),
        );
        status.textContent = 'External action not started · provider configuration required.';
        return;
      }
      if (
        result.status === 'failed'
        && result.halted_reason === 'required_external_tool_not_planned'
      ) {
        const missing = (result.missing_tools || []).join(', ');
        addMessage(
          'Seldrune Operator',
          `Execution stopped before external action. Required tool input was unresolved: ${missing}.`,
        );
        status.textContent = `No external action performed · evidence ${result.command_id}`;
        return;
      }
      if (result.approval_required) {
        const reasons = (result.risk_reasons || []).join(', ');
        const approved = window.confirm(
          `This order requires explicit owner confirmation: ${reasons}. Continue execution?`,
        );
        if (!approved) {
          addMessage(
            'Seldrune Operator',
            `Paused for approval. Command ${result.command_id} remains unexecuted.`,
          );
          status.textContent = 'Execution paused by owner.';
          return;
        }
        status.textContent = 'Owner confirmed. Executing governed command…';
        result = await executeOrder(order, result.command_id, true);
      }
      const summary = `${result.status}: ${result.executed_steps || 0} executed, ${result.failed_steps || 0} failed, ${result.blocked_steps || 0} blocked. Command ${result.command_id}.`;
      addMessage('Seldrune Operator', summary);
      status.textContent = `Verified operator result · ${result.status} · evidence ${result.command_id}`;
      window.dispatchEvent(new CustomEvent('seldrune:refresh'));
    } catch (error) {
      addMessage('System', `Operator request failed: ${error.message}`);
      status.textContent = 'Operator request failed.';
    } finally {
      setBusy(false);
      input.focus();
    }
  });

  form.addEventListener('submit', async event => {
    event.preventDefault();
    const message = input.value.trim();
    if (!message) return;

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
    setBusy(true, 'Seldrune GPT is reasoning across your message and attachments…');
    addMessage(
      'You',
      message + (attachmentNames.length ? `\nAttachments: ${attachmentNames.join(', ')}` : ''),
      'user',
    );
    input.value = '';
    try {
      const result = await api('/gpt', {
        method: 'POST',
        body: JSON.stringify({message, attachments: outgoingAttachments}),
      });
      clearAttachments();
      model.textContent = result.model || 'OpenAI';
      addMessage('Seldrune GPT', result.response || '(No text returned)');
      status.textContent = `${result.provider || 'openai'} · ${result.model || 'model'} · ${result.latency_ms || 0} ms · ${result.input_tokens || 0} input · ${result.output_tokens || 0} output tokens`;
    } catch (error) {
      addMessage('System', `GPT request failed: ${error.message}`);
      status.textContent = 'Request failed.';
    } finally {
      setBusy(false);
      input.focus();
    }
  });

  renderAttachments();
  loadHistory();
})();