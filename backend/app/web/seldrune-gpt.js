(() => {
  const form = document.querySelector('#seldrune-gpt-form');
  if (!form) return;
  const input = document.querySelector('#seldrune-gpt-input');
  const thread = document.querySelector('#seldrune-gpt-thread');
  const status = document.querySelector('#seldrune-gpt-status');
  const model = document.querySelector('#seldrune-gpt-model');
  const newConversation = document.querySelector('#seldrune-gpt-new');

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

  loadHistory();

  form.addEventListener('submit', async event => {
    event.preventDefault();
    const message = input.value.trim();
    if (!message) return;
    input.disabled = true;
    form.querySelector('button').disabled = true;
    status.textContent = 'Seldrune GPT is reasoning…';
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
      input.disabled = false;
      form.querySelector('button').disabled = false;
      input.focus();
    }
  });
})();
