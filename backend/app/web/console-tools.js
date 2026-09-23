(() => {
  const byId = id => document.getElementById(id);
  let adapters = [];
  let secrets = [];
  let tools = [];
  let runs = [];
  let bootstrapStatus = null;
  let providerPreflight = null;
  let toolDefaults = [];

  function setStatus(message) {
    const element = byId('tool-control-status');
    if (element) element.textContent = message;
  }

  function createPill(text, className = '') {
    const span = document.createElement('span');
    span.className = `pill ${className}`.trim();
    span.textContent = text;
    return span;
  }

  function clearAndMessage(root, message) {
    root.replaceChildren();
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.textContent = message;
    root.append(empty);
  }

  function currentAdapter() {
    const value = byId('tool-adapter-select')?.value || '';
    return adapters.find(item => `${item.provider}:${item.action_name}` === value) || null;
  }

  function renderBootstrapStatus() {
    const root = byId('tool-provider-readiness');
    if (!root) return;
    root.replaceChildren();
    const providers = bootstrapStatus?.providers || [];
    const targets = bootstrapStatus?.runtime_targets || {};
    if (targets.github_full_name || targets.render_service_id) {
      const targetCard = document.createElement('article');
      targetCard.className = 'tool-readiness-card';
      const title = document.createElement('strong');
      title.textContent = 'PRODUCTION TARGET';
      const detail = document.createElement('p');
      const parts = [];
      if (targets.github_full_name) {
        parts.push(
          `GitHub: ${targets.github_full_name} @ ${targets.github_ref || 'default'}`
        );
      }
      if (targets.render_service_id) {
        parts.push(`Render: ${targets.render_service_id}`);
      } else if (targets.render_service_name) {
        parts.push(`Render: ${targets.render_service_name}`);
      }
      detail.textContent = parts.join(' · ');
      targetCard.append(title, detail);
      root.append(targetCard);
    }
    if (!providers.length) {
      clearAndMessage(root, 'No provider bootstrap metadata is available.');
      return;
    }
    providers.forEach(provider => {
      const card = document.createElement('article');
      card.className = 'tool-readiness-card';
      const top = document.createElement('div');
      top.className = 'tool-row-top';
      const name = document.createElement('strong');
      name.textContent = provider.provider.toUpperCase();
      top.append(
        name,
        createPill(provider.ready ? 'ready' : 'not connected', provider.ready ? '' : 'pending')
      );
      const meta = document.createElement('small');
      const readyActions = provider.actions.filter(action => action.ready).length;
      meta.textContent =
        `${readyActions}/${provider.actions.length} actions ready · ${provider.credential_env_locator}`;
      const detail = document.createElement('p');
      if (provider.ready) {
        detail.textContent = 'Credential resolves and all built-in actions are registered.';
      } else if (provider.secret_available) {
        detail.textContent =
          'Credential is available. Activate configured providers to create missing tools.';
      } else {
        detail.textContent =
          'Connect this provider in Owner Credential Vault or add its environment/AWS secret.';
      }
      card.append(top, meta, detail);
      root.append(card);
    });
  }

  function renderProviderPreflight() {
    const root = byId('tool-provider-preflight-results');
    if (!root) return;
    root.replaceChildren();
    const providers = providerPreflight?.providers || [];
    if (!providers.length) {
      clearAndMessage(
        root,
        'Remote provider access has not been verified in this session.'
      );
      return;
    }
    providers.forEach(provider => {
      const card = document.createElement('article');
      card.className = 'tool-readiness-card';
      const top = document.createElement('div');
      top.className = 'tool-row-top';
      const name = document.createElement('strong');
      name.textContent = `${provider.provider.toUpperCase()} remote access`;
      top.append(
        name,
        createPill(
          provider.status,
          provider.verified ? '' : 'pending'
        )
      );
      const detail = document.createElement('p');
      detail.textContent = provider.detail || 'No provider detail returned.';
      card.append(top, detail);

      const identityEntries = Object.entries(provider.identity || {})
        .filter(([, value]) => value !== null && value !== undefined && value !== '');
      if (identityEntries.length) {
        const identity = document.createElement('small');
        identity.textContent = identityEntries
          .map(([key, value]) => `${key}: ${value}`)
          .join(' · ');
        card.append(identity);
      }
      root.append(card);
    });
  }

  function renderAdapters() {
    const root = byId('tool-adapter-list');
    if (!root) return;
    root.replaceChildren();
    if (!adapters.length) {
      clearAndMessage(root, 'No registered adapters.');
      return;
    }
    adapters.forEach(adapter => {
      const card = document.createElement('div');
      card.className = 'tool-row';
      const top = document.createElement('div');
      top.className = 'tool-row-top';
      const name = document.createElement('strong');
      name.textContent = adapter.name;
      top.append(name, createPill(adapter.risk_level || 'low'));
      const meta = document.createElement('small');
      meta.textContent = `${adapter.provider} · ${adapter.action_name}`;
      const description = document.createElement('p');
      description.textContent = adapter.description || 'Registered provider action.';
      card.append(top, meta, description);
      root.append(card);
    });
  }

  function renderSecrets() {
    const root = byId('secret-reference-list');
    const select = byId('tool-credential-select');
    if (!root || !select) return;
    root.replaceChildren();
    select.innerHTML = '<option value="">No credential</option>';
    secrets.forEach(secret => {
      const option = document.createElement('option');
      option.value = secret.id;
      option.textContent = `${secret.name} · ${secret.provider}`;
      select.append(option);

      const row = document.createElement('div');
      row.className = 'tool-row';
      const top = document.createElement('div');
      top.className = 'tool-row-top';
      const name = document.createElement('strong');
      name.textContent = secret.name;
      top.append(name, createPill(secret.status, secret.status === 'active' ? '' : 'pending'));
      const meta = document.createElement('small');
      meta.textContent = `${secret.slug} · ${secret.provider} · ${secret.locator}`;
      row.append(top, meta);
      root.append(row);
    });
    if (!secrets.length) clearAndMessage(root, 'No credential references.');
  }

  function renderTools() {
    const root = byId('tool-definition-list');
    const runSelect = byId('tool-run-select');
    if (!root || !runSelect) return;
    root.replaceChildren();
    runSelect.replaceChildren();

    tools.forEach(tool => {
      const option = document.createElement('option');
      option.value = tool.id;
      option.textContent = `${tool.name} · ${tool.provider}`;
      runSelect.append(option);

      const row = document.createElement('div');
      row.className = 'tool-row';
      const top = document.createElement('div');
      top.className = 'tool-row-top';
      const name = document.createElement('strong');
      name.textContent = tool.name;
      top.append(
        name,
        createPill(tool.status),
        createPill(tool.risk_level, tool.risk_level === 'high' ? 'pending' : '')
      );
      const meta = document.createElement('small');
      meta.textContent =
        `${tool.slug} · ${tool.provider}:${tool.action_name} · ${tool.approval_mode}`;
      row.append(top, meta);
      const defaults = toolDefaults.find(item => item.tool_slug === tool.slug);
      if (defaults?.defaulted_fields?.length) {
        const defaultInfo = document.createElement('small');
        defaultInfo.textContent =
          `Runtime defaults: ${defaults.defaulted_fields.join(', ')}`;
        row.append(defaultInfo);
      }
      root.append(row);
    });
    if (!tools.length) {
      clearAndMessage(root, 'No registered tools.');
      const option = document.createElement('option');
      option.value = '';
      option.textContent = 'No tools available';
      runSelect.append(option);
    }
  }

  function renderRuns() {
    const root = byId('tool-run-list');
    if (!root) return;
    root.replaceChildren();
    runs.slice(0, 20).forEach(run => {
      const tool = tools.find(item => item.id === run.tool_id);
      const row = document.createElement('div');
      row.className = 'tool-row';

      const top = document.createElement('div');
      top.className = 'tool-row-top';
      const name = document.createElement('strong');
      name.textContent = tool?.name || run.tool_id;
      top.append(
        name,
        createPill(run.status, run.status === 'pending_approval' ? 'pending' : '')
      );

      const meta = document.createElement('small');
      const receipt = run.output_data?.evidence?.receipt_id || 'no receipt';
      meta.textContent = `${receipt} · ${new Date(run.requested_at).toLocaleString()}`;
      row.append(top, meta);

      if (run.error_message) {
        const error = document.createElement('p');
        error.className = 'risk';
        error.textContent = run.error_message;
        row.append(error);
      }

      if (run.status === 'pending_approval') {
        const actions = document.createElement('div');
        actions.className = 'tool-row-actions';
        const approve = document.createElement('button');
        approve.type = 'button';
        approve.dataset.toolRunAction = 'approve';
        approve.dataset.runId = run.id;
        approve.textContent = 'Approve & execute';
        const reject = document.createElement('button');
        reject.type = 'button';
        reject.className = 'ghost';
        reject.dataset.toolRunAction = 'reject';
        reject.dataset.runId = run.id;
        reject.textContent = 'Reject';
        actions.append(approve, reject);
        row.append(actions);
      }
      root.append(row);
    });
    if (!runs.length) clearAndMessage(root, 'No execution receipts yet.');
  }

  function refreshSummary() {
    byId('tool-adapter-count').textContent = String(adapters.length);
    byId('tool-secret-count').textContent = String(secrets.length);
    byId('tool-definition-count').textContent = String(tools.length);
    byId('tool-pending-count').textContent =
      String(runs.filter(run => run.status === 'pending_approval').length);
  }

  function refreshAdapterForm() {
    const select = byId('tool-adapter-select');
    if (!select) return;
    const previous = select.value;
    select.replaceChildren();
    adapters.forEach(adapter => {
      const option = document.createElement('option');
      option.value = `${adapter.provider}:${adapter.action_name}`;
      option.textContent = adapter.name;
      select.append(option);
    });
    if (previous && [...select.options].some(option => option.value === previous)) {
      select.value = previous;
    }
    const adapter = currentAdapter();
    if (!adapter) return;
    byId('tool-risk-level').value = adapter.risk_level || 'low';
    byId('tool-input-schema').textContent =
      JSON.stringify(adapter.input_schema || {}, null, 2);
    const credential = byId('tool-credential-select');
    credential.required = Boolean(adapter.credential_required);
  }

  async function loadToolControl() {
    if (!document.getElementById('tool-control') || !state?.org) return;
    setStatus('Synchronizing universal tool fabric…');
    try {
      try {
        bootstrapStatus = await api('/tool-bootstrap', {
          method: 'POST',
          body: '{}',
        });
      } catch (bootstrapError) {
        console.warn('Automatic tool bootstrap was unavailable', bootstrapError);
      }
      [adapters, secrets, tools, runs, bootstrapStatus, toolDefaults] =
        await Promise.all([
          api('/tool-adapters'),
          api('/secret-references'),
          api('/tools'),
          api('/tool-runs'),
          api('/tool-bootstrap/status'),
          api('/tool-defaults'),
        ]);
      renderBootstrapStatus();
      renderProviderPreflight();
      renderAdapters();
      renderSecrets();
      renderTools();
      renderRuns();
      refreshSummary();
      refreshAdapterForm();
      setStatus(
        `Universal action fabric synchronized · ${tools.length} tools available.`
      );
    } catch (error) {
      setStatus(error.message);
    }
  }

  byId('provider-vault-toggle')?.addEventListener('click', event => {
    const input = byId('provider-vault-secret');
    if (!input) return;
    const reveal = input.type === 'password';
    input.type = reveal ? 'text' : 'password';
    event.currentTarget.textContent = reveal ? 'Hide' : 'Show';
  });

  byId('provider-vault-form')?.addEventListener('submit', async event => {
    event.preventDefault();
    const provider = byId('provider-vault-provider')?.value || '';
    const secretInput = byId('provider-vault-secret');
    const secretValue = secretInput?.value || '';
    const vaultStatus = byId('provider-vault-status');
    if (!provider || !secretValue) return;
    const submit = event.currentTarget.querySelector('button[type="submit"]');
    submit.disabled = true;
    if (vaultStatus) vaultStatus.textContent = `Encrypting and activating ${provider}…`;
    try {
      const result = await api('/tool-bootstrap/credentials', {
        method: 'POST',
        body: JSON.stringify({
          provider,
          secret_value: secretValue,
        }),
      });
      if (secretInput) {
        secretInput.value = '';
        secretInput.type = 'password';
      }
      const toggle = byId('provider-vault-toggle');
      if (toggle) toggle.textContent = 'Show';
      if (vaultStatus) {
        vaultStatus.textContent =
          `${provider.toUpperCase()} connected · ${result.tool_count} active tools.`;
      }
      toast(`${provider.toUpperCase()} credential saved and activated`);
      await loadToolControl();
      try {
        providerPreflight = await api('/tool-bootstrap/preflight', {
          method: 'POST',
          body: '{}',
        });
        renderProviderPreflight();
      } catch (preflightError) {
        console.warn('Provider preflight after credential save failed', preflightError);
      }
    } catch (error) {
      if (vaultStatus) vaultStatus.textContent = `Credential save failed: ${error.message}`;
      toast(error.message);
    } finally {
      submit.disabled = false;
    }
  });

  byId('tool-control-refresh')?.addEventListener('click', loadToolControl);
  byId('tool-provider-preflight')?.addEventListener('click', async event => {
    event.currentTarget.disabled = true;
    setStatus('Verifying remote provider access without taking external actions…');
    try {
      providerPreflight = await api('/tool-bootstrap/preflight', {
        method: 'POST',
        body: '{}',
      });
      renderProviderPreflight();
      const verified = providerPreflight.verified || 0;
      const total = providerPreflight.total || 0;
      toast(`Verified ${verified}/${total} provider credentials`);
      setStatus(
        `Provider preflight complete · ${verified}/${total} remotely verified.`
      );
    } catch (error) {
      toast(error.message);
      setStatus(`Provider preflight failed: ${error.message}`);
    } finally {
      event.currentTarget.disabled = false;
    }
  });
  byId('tool-auto-activate')?.addEventListener('click', async event => {
    event.currentTarget.disabled = true;
    try {
      const result = await api('/tool-bootstrap', {
        method: 'POST',
        body: '{}',
      });
      const created = result.created_tools?.length || 0;
      const missing = result.missing_env_locators || [];
      if (created) {
        toast(`Activated ${created} configured provider tool${created === 1 ? '' : 's'}`);
      } else if (missing.length) {
        toast(`Add provider secrets: ${missing.join(', ')}`);
      } else {
        toast('Configured provider tools are already active');
      }
      await loadToolControl();
    } catch (error) {
      toast(error.message);
    } finally {
      event.currentTarget.disabled = false;
    }
  });
  byId('tool-adapter-select')?.addEventListener('change', refreshAdapterForm);

  byId('secret-reference-form')?.addEventListener('submit', async event => {
    event.preventDefault();
    try {
      await api('/secret-references', {
        method: 'POST',
        body: JSON.stringify({
          name: byId('tool-secret-name').value.trim(),
          slug: byId('tool-secret-slug').value.trim(),
          provider: byId('tool-secret-provider').value,
          locator: byId('tool-secret-locator').value.trim(),
        }),
      });
      event.currentTarget.reset();
      toast('Credential reference created');
      await loadToolControl();
    } catch (error) {
      toast(error.message);
    }
  });

  byId('tool-definition-form')?.addEventListener('submit', async event => {
    event.preventDefault();
    const adapter = currentAdapter();
    if (!adapter) {
      toast('Select a registered adapter');
      return;
    }
    const credentialId = byId('tool-credential-select').value;
    if (adapter.credential_required && !credentialId) {
      toast('This adapter requires a credential reference');
      return;
    }
    try {
      await api('/tools', {
        method: 'POST',
        body: JSON.stringify({
          name: byId('tool-definition-name').value.trim(),
          slug: byId('tool-definition-slug').value.trim(),
          provider: adapter.provider,
          action_name: adapter.action_name,
          credential_reference_id: credentialId || null,
          risk_level: byId('tool-risk-level').value,
          approval_mode: adapter.risk_level === 'high' ? 'always' : 'never',
          input_schema: adapter.input_schema || {},
        }),
      });
      byId('tool-definition-name').value = '';
      byId('tool-definition-slug').value = '';
      toast('Tool registered');
      await loadToolControl();
    } catch (error) {
      toast(error.message);
    }
  });

  byId('tool-run-form')?.addEventListener('submit', async event => {
    event.preventDefault();
    const toolId = byId('tool-run-select').value;
    if (!toolId) {
      toast('Register a tool first');
      return;
    }
    let inputData;
    try {
      inputData = JSON.parse(byId('tool-run-input').value || '{}');
    } catch {
      toast('Input JSON is invalid');
      return;
    }
    if (!inputData || Array.isArray(inputData) || typeof inputData !== 'object') {
      toast('Input JSON must be an object');
      return;
    }
    try {
      const run = await api('/tool-runs', {
        method: 'POST',
        body: JSON.stringify({tool_id: toolId, input_data: inputData}),
      });
      toast(
        run.status === 'pending_approval'
          ? 'Tool run is awaiting approval'
          : `Tool run ${run.status}`
      );
      await loadToolControl();
    } catch (error) {
      toast(error.message);
    }
  });

  byId('tool-run-list')?.addEventListener('click', async event => {
    const button = event.target.closest('[data-tool-run-action]');
    if (!button) return;
    button.disabled = true;
    try {
      const action = button.dataset.toolRunAction;
      await api(`/tool-runs/${button.dataset.runId}/${action}`, {
        method: 'POST',
        body: JSON.stringify(
          action === 'reject' ? {reason: 'Rejected from owner console'} : {}
        ),
      });
      toast(action === 'approve' ? 'Tool run approved and executed' : 'Tool run rejected');
      await loadToolControl();
    } catch (error) {
      button.disabled = false;
      toast(error.message);
    }
  });

  document.addEventListener('seldrune:console-ready', loadToolControl);
})();
