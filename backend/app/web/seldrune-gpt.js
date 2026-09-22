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

  function addMessage(label, text) {
    if (thread.querySelector('.empty')) thread.replaceChildren();
    const card = document.createElement('article');
    card.className = 'command-card';
    const body = document.createElement('div');
    const heading = document.createElement('strong');
    heading.textContent = label;
    const content = document.createElement('p');
    content.textContent = text;
    body.append(heading, content);
    card.append(body);
    thread.append(card);
    card.scrollIntoView({behavior: 'smooth', block: 'nearest'});
  }

  function setBusy(busy, message) {
    input.disabled = busy;
    chatButton.disabled = busy;
    executeButton.disabled = busy;
    if (message) status.textContent = message;
  }

  async function loadHistory() {
    try {
      const messages = await api('/gpt/history');
      if (!messages.length) return;
      thread.replaceChildren();
      messages.forEach(item => addMessage(item.role === 'assistant' ? 'Seldrune GPT' : 'You', item.content));
      status.textContent = `Restored ${messages.length} saved messages.`;
    } catch (error) {
      status.textContent = `History unavailable: ${error.message}`;
    }
  }

  newConversation?.addEventListener('click', async () => {
    if (!window.confirm('Start a new Seldrune GPT conversation and clear saved context?')) return;
    try {
      await api('/gpt/history', {method: 'DELETE'});
      thread.innerHTML = '<div class="empty">New conversation started.</div>';
      status.textContent = 'Saved GPT context cleared.';
    } catch (error) {
      status.textContent = `Could not clear history: ${error.message}`;
    }
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

  executeButton?.addEventListener('click', async () => {
    const order = input.value.trim();
    if (!order) return;
    setBusy(true, 'Seldrune Operator is planning and executing…');
    addMessage('Owner order', order);
    input.value = '';
    try {
      let result = await executeOrder(order);
      if (result.status === 'configuration_required') {
        const missing = (result.missing_tools || []).join(', ');
        const hints = (result.configuration_hints || []).join(', ');
        addMessage(
          'Seldrune Operator',
          `Configuration required before execution. Missing: ${missing || 'provider tool'}`
          + (hints ? `. Configure service secret(s): ${hints}.` : '.')
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
          `Execution stopped before external action. Planner omitted required tool(s): ${missing}.`
        );
        status.textContent = `No external action performed · evidence ${result.command_id}`;
        return;
      }
      if (result.approval_required) {
        const reasons = (result.risk_reasons || []).join(', ');
        const approved = window.confirm(
          `This order requires explicit owner confirmation: ${reasons}. Continue execution?`
        );
        if (!approved) {
          addMessage('Seldrune Operator', `Paused for approval. Command ${result.command_id} remains unexecuted.`);
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

  loadHistory();

  form.addEventListener('submit', async event => {
    event.preventDefault();
    const message = input.value.trim();
    if (!message) return;
    setBusy(true, 'Seldrune GPT is reasoning…');
    addMessage('You', message);
    input.value = '';
    try {
      const result = await api('/gpt', {
        method: 'POST',
        body: JSON.stringify({message}),
      });
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
})();
