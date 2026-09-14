const $ = selector => document.querySelector(selector);
const state = {
  token: sessionStorage.seldruneToken || '',
  org: '',
  user: null,
  brief: null,
};

const toast = message => {
  const element = $('#toast');
  element.textContent = message;
  element.classList.add('show');
  setTimeout(() => element.classList.remove('show'), 2600);
};

function showView(id) {
  ['#bootstrap-view', '#login-view', '#console-view'].forEach(
    selector => $(selector).classList.add('hidden')
  );
  $(id).classList.remove('hidden');
}

async function request(path, options = {}) {
  const response = await fetch(`/api/v1${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(state.token ? {'Authorization': `Bearer ${state.token}`} : {}),
    },
  });
  if (response.status === 401) {
    logout();
    throw new Error('Your session expired. Please sign in again.');
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${response.status})`);
  }
  return response.json();
}

const api = (path, options = {}) =>
  request(`/organizations/${state.org}${path}`, options);

function logout() {
  state.token = '';
  state.org = '';
  state.user = null;
  sessionStorage.removeItem('seldruneToken');
  $('#password').value = '';
  showView('#login-view');
}

async function establishSession() {
  const me = await request('/auth/me');
  const membership = me.memberships.find(item => item.role === 'owner');
  if (!membership) throw new Error('This console requires an organization owner account.');
  state.org = membership.organization.id;
  state.user = me.user;
  $('#owner-name').textContent =
    `${me.user.display_name} · ${membership.organization.name}`;
  showView('#console-view');
  await load();
}

async function initializeAuth() {
  if (state.token) {
    try {
      await establishSession();
      return;
    } catch (error) {
      logout();
      $('#login-error').textContent = error.message;
      return;
    }
  }
  try {
    const status = await request('/auth/bootstrap-status');
    showView(status.required ? '#bootstrap-view' : '#login-view');
  } catch (error) {
    showView('#login-view');
    $('#login-error').textContent = error.message;
  }
}

$('#bootstrap-form').onsubmit = async event => {
  event.preventDefault();
  const error = $('#bootstrap-error');
  error.textContent = '';
  const password = $('#bootstrap-password').value;
  if (password !== $('#bootstrap-confirm').value) {
    error.textContent = 'Passwords do not match.';
    return;
  }
  try {
    const auth = await request('/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        email: $('#bootstrap-email').value,
        password,
        display_name: $('#bootstrap-name').value,
        organization_name: $('#organization-name').value,
        organization_slug: $('#organization-slug').value,
      }),
    });
    state.token = auth.access_token;
    sessionStorage.seldruneToken = state.token;
    await establishSession();
    toast('Founding owner created securely');
  } catch (caught) {
    error.textContent = caught.message;
    if (caught.message === 'Owner onboarding is already complete') {
      showView('#login-view');
      $('#login-error').textContent =
        'Owner onboarding is complete. Sign in to continue.';
    }
  }
};

$('#login-form').onsubmit = async event => {
  event.preventDefault();
  $('#login-error').textContent = '';
  try {
    const auth = await request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({
        email: $('#email').value,
        password: $('#password').value,
      }),
    });
    state.token = auth.access_token;
    sessionStorage.seldruneToken = state.token;
    await establishSession();
  } catch (error) {
    $('#login-error').textContent = error.message;
  }
};

$('#logout').onclick = logout;
$('#refresh').onclick = load;

function button(label, action, id) {
  const kind = action === 'brief' ? 'ghost' : '';
  return `<button data-action="${action}" data-id="${id}" class="${kind}">${label}</button>`;
}

function renderCommands(items) {
  const root = $('#command-list');
  if (!items.length) {
    root.innerHTML = '<div class="empty">No commands yet. Create your first objective.</div>';
    return;
  }
  root.innerHTML = items.map(command =>
    `<article class="command-card"><div><h3></h3><div class="meta"><span class="pill">${command.status}</span><span class="pill ${command.approval_status === 'awaiting_approval' ? 'pending' : ''}">${command.approval_status.replace('_', ' ')}</span></div></div><div class="actions">${button('Decision brief', 'brief', command.id)}${command.approval_status === 'awaiting_approval' ? button('Approve', 'approve', command.id) : button('Execute', 'execute', command.id)}</div></article>`
  ).join('');
  [...root.querySelectorAll('h3')].forEach(
    (element, index) => { element.textContent = items[index].objective; }
  );
}

async function load() {
  if (!state.org) return;
  try {
    const dashboard = await api('/owner-dashboard');
    $('#total').textContent = dashboard.command_counts.total;
    $('#pending').textContent = dashboard.command_counts.awaiting_approval;
    $('#progress').textContent =
      `${dashboard.execution.succeeded_steps}/${dashboard.execution.total_steps}`;
    $('#cost').textContent =
      `$${dashboard.usage.estimated_cost_usd.toFixed(4)}`;
    renderCommands(dashboard.recent_commands);
  } catch (error) {
    toast(error.message);
  }
}

$('#command-form').onsubmit = async event => {
  event.preventDefault();
  try {
    await api('/owner-commands', {
      method: 'POST',
      body: JSON.stringify({objective: $('#objective').value}),
    });
    $('#objective').value = '';
    toast('Governed plan created');
    load();
  } catch (error) {
    toast(error.message);
  }
};

function metric(label, value) {
  const item = document.createElement('div');
  item.className = 'result-metric';
  const small = document.createElement('small');
  small.textContent = label;
  const strong = document.createElement('strong');
  strong.textContent = value;
  item.append(small, strong);
  return item;
}

function formatDuration(milliseconds) {
  const value = Number(milliseconds || 0);
  return value < 1000 ? `${value} ms` : `${(value / 1000).toFixed(2)} s`;
}

function renderBrief(data) {
  state.brief = data;
  const box = $('#brief-body');
  box.replaceChildren();

  const heading = document.createElement('h2');
  heading.textContent = data.objective;
  box.append(heading);

  const progress = document.createElement('p');
  progress.textContent =
    `${data.progress.completed} of ${data.progress.total} steps complete · ${data.readiness}`;
  box.append(progress);

  const planner = document.createElement('p');
  planner.textContent = data.planner.mode === 'live'
    ? `Planner: Live AI · ${data.planner.model}`
    : `Planner: Safe fallback · ${data.planner.reason || 'provider unavailable'}`;
  box.append(planner);

  const outcome = document.createElement('div');
  outcome.className = `outcome-panel outcome-${data.outcome?.verdict || 'review'}`;
  const outcomeTitle = document.createElement('strong');
  outcomeTitle.textContent =
    `Outcome: ${String(data.outcome?.verdict || 'review').replace('_', ' ').toUpperCase()}`;
  const outcomeReason = document.createElement('span');
  outcomeReason.textContent =
    data.outcome?.reasons?.[0] || 'Outcome evidence requires review.';
  outcome.append(outcomeTitle, outcomeReason);
  box.append(outcome);

  const metrics = document.createElement('div');
  metrics.className = 'result-metrics';
  metrics.append(
    metric('Total tokens', Number(data.usage?.total_tokens || 0).toLocaleString()),
    metric('Recorded cost', `$${Number(data.usage?.estimated_cost_usd || 0).toFixed(6)}`),
    metric('Execution time', formatDuration(data.usage?.execution_duration_ms))
  );
  box.append(metrics);

  data.risks.forEach(risk => {
    const item = document.createElement('p');
    item.className = 'risk';
    item.textContent = `Risk: ${risk}`;
    box.append(item);
  });

  const next = document.createElement('h3');
  next.textContent = `Next: ${data.recommended_next_action}`;
  box.append(next);

  data.steps.forEach(step => {
    const details = document.createElement('details');
    details.className = 'result-step';
    if (step.status === 'succeeded') details.open = true;

    const summary = document.createElement('summary');
    summary.textContent = `${step.sequence}. ${step.title} — ${step.status}`;
    details.append(summary);

    const metadata = document.createElement('p');
    metadata.className = 'result-meta';
    metadata.textContent = [
      step.agent_name || 'Unassigned',
      step.model || 'No model call',
      `${Number(step.tokens || 0).toLocaleString()} tokens`,
      `$${Number(step.estimated_cost_usd || 0).toFixed(6)}`,
      formatDuration(step.duration_ms),
    ].join(' · ');
    details.append(metadata);

    if (step.output) {
      const output = document.createElement('pre');
      output.textContent = step.output;
      details.append(output);
    } else {
      const empty = document.createElement('p');
      empty.className = step.error ? 'risk' : 'result-meta';
      empty.textContent = step.error || 'No output yet.';
      details.append(empty);
    }
    box.append(details);
  });

  if (data.status === 'succeeded') {
    const promotion = document.createElement('div');
    promotion.className = 'promotion-panel';
    if (data.promotion) {
      const note = document.createElement('p');
      note.textContent =
        `Organization project: ${data.promotion.department_name || 'Organization'} · ${data.objective}`;
      const link = document.createElement('a');
      link.href = '/console-assets/organization-board.html';
      link.textContent = 'Open Organization Board';
      promotion.append(note, link);
    } else if (data.outcome?.promotable) {
      const note = document.createElement('p');
      note.textContent =
        'Turn this verified outcome into a governed goal and delivery project.';
      const promote = document.createElement('button');
      promote.textContent = 'Promote to organization';
      promote.onclick = async () => {
        promote.disabled = true;
        promote.textContent = 'Promoting…';
        try {
          await api(`/owner-commands/${data.command_id}/promote`, {method: 'POST'});
          const refreshed = await api(`/owner-commands/${data.command_id}/brief`);
          renderBrief(refreshed);
          toast('Goal and project created');
        } catch (error) {
          promote.disabled = false;
          promote.textContent = 'Promote to organization';
          toast(error.message);
        }
      };
      promotion.append(note, promote);
    } else {
      const note = document.createElement('p');
      note.textContent =
        'Promotion blocked: resolve the outcome evidence and rerun validation first.';
      promotion.append(note);
    }
    box.append(promotion);
  }

  const download = document.createElement('button');
  download.className = 'report-download';
  download.textContent = 'Download report';
  download.onclick = downloadReport;
  box.append(download);
  $('#brief').showModal();
}

function reportMarkdown(data) {
  const lines = [
    '# Seldrune Execution Report',
    '',
    `## Objective`,
    '',
    data.objective,
    '',
    `- Status: ${data.status}`,
    `- Outcome: ${data.outcome?.verdict || 'review'}`,
    `- Outcome reason: ${data.outcome?.reasons?.join('; ') || 'Not assessed'}`,
    `- Approval: ${data.approval_status}`,
    `- Planner: ${data.planner.mode || 'unknown'} · ${data.planner.model || 'fallback'}`,
    `- Progress: ${data.progress.completed}/${data.progress.total}`,
    `- Total tokens: ${data.usage?.total_tokens || 0}`,
    `- Recorded cost: $${Number(data.usage?.estimated_cost_usd || 0).toFixed(8)}`,
    `- Execution time: ${formatDuration(data.usage?.execution_duration_ms)}`,
    `- Organization project: ${data.promotion?.project_id || 'Not promoted'}`,
    '',
  ];
  data.steps.forEach(step => {
    lines.push(
      `## ${step.sequence}. ${step.title}`,
      '',
      `- Status: ${step.status}`,
      `- Agent: ${step.agent_name || 'Unassigned'}`,
      `- Model: ${step.model || 'No model call'}`,
      `- Tokens: ${step.tokens || 0}`,
      `- Recorded cost: $${Number(step.estimated_cost_usd || 0).toFixed(8)}`,
      `- Duration: ${formatDuration(step.duration_ms)}`,
      '',
      step.output || step.error || 'No output yet.',
      ''
    );
  });
  return lines.join('\n');
}

function downloadReport() {
  if (!state.brief) return;
  const blob = new Blob([reportMarkdown(state.brief)], {
    type: 'text/markdown;charset=utf-8',
  });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = `seldrune-report-${state.brief.command_id}.md`;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(link.href);
}

$('#command-list').onclick = async event => {
  const selected = event.target.closest('button');
  if (!selected) return;
  try {
    if (selected.dataset.action === 'approve') {
      await api(`/owner-commands/${selected.dataset.id}/approve`, {method: 'POST'});
      toast('Command approved');
      load();
    } else if (selected.dataset.action === 'execute') {
      selected.disabled = true;
      selected.textContent = 'Executing…';
      await api(`/owner-commands/${selected.dataset.id}/execute`, {
        method: 'POST',
        body: '{}',
      });
      toast('Execution completed');
      load();
    } else {
      const data = await api(`/owner-commands/${selected.dataset.id}/brief`);
      renderBrief(data);
    }
  } catch (error) {
    selected.disabled = false;
    toast(error.message);
  }
};

$('#brief .close').onclick = () => $('#brief').close();
initializeAuth();
