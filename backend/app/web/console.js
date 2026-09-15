const $ = selector => document.querySelector(selector);
const state = {
  token: sessionStorage.seldruneToken || '',
  org: '',
  user: null,
  brief: null,
  auditEvents: [],
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

function commandActions(command) {
  const brief = button('Decision brief', 'brief', command.id);
  if (command.approval_status === 'approved') {
    return brief
      + button('Execute', 'execute', command.id)
      + button('Revoke approval', 'revoke', command.id);
  }
  return brief + button('Approve', 'approve', command.id);
}

function budgetSummary(command) {
  const reservation = command.reservation || {};
  const forecast = Number(command.forecast_cost_usd || 0);
  const recorded = Number(command.recorded_cost_usd || 0);
  if (!forecast && !reservation.amount_usd && !recorded) return '';
  const state = command.budget_halted
    ? 'Circuit breaker stopped execution'
    : `Reservation: ${reservation.status || 'not reserved'}`;
  return `<div class="budget-strip"><span>Forecast <b>${forecast.toFixed(4)}</b></span><span>Reserved <b>${Number(reservation.amount_usd || 0).toFixed(4)}</b></span><span>Recorded <b>${recorded.toFixed(4)}</b></span><span class="${command.budget_halted ? 'budget-alert' : ''}">${state}</span></div>`;
}

function renderCommands(items) {
  const root = $('#command-list');
  if (!items.length) {
    root.innerHTML = '<div class="empty">No commands yet. Create your first objective.</div>';
    return;
  }
  root.innerHTML = items.map(command =>
    `<article class="command-card"><div><h3></h3><div class="meta"><span class="pill">${command.status}</span><span class="pill ${command.approval_status === 'awaiting_approval' ? 'pending' : ''}">${command.approval_status.replaceAll('_', ' ')}</span></div>${budgetSummary(command)}</div><div class="actions">${commandActions(command)}</div></article>`
  ).join('');
  [...root.querySelectorAll('h3')].forEach(
    (element, index) => { element.textContent = items[index].objective; }
  );
}

function renderAgentPerformance(performance) {
  const root = $('#agent-performance-list');
  const agents = performance?.ranked_agents || [];
  $('#agent-active-count').textContent =
    `${Number(performance?.active_agent_count || 0)} active`;
  root.replaceChildren();
  if (!agents.length) {
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.textContent = 'No agent evidence yet.';
    root.append(empty);
    return;
  }
  agents.forEach((agent, index) => {
    const card = document.createElement('article');
    card.className = 'agent-scorecard';

    const identity = document.createElement('div');
    identity.className = 'agent-identity';
    const rank = document.createElement('span');
    rank.className = 'agent-rank';
    rank.textContent = `#${index + 1}`;
    const name = document.createElement('strong');
    name.textContent = agent.name;
    const status = document.createElement('small');
    status.textContent = agent.status;
    identity.append(rank, name, status);

    const success = document.createElement('div');
    success.innerHTML = '<small>Success rate</small>';
    const successValue = document.createElement('strong');
    successValue.textContent = agent.success_rate === null
      ? 'No evidence'
      : `${(Number(agent.success_rate) * 100).toFixed(1)}%`;
    success.append(successValue);

    const tasks = document.createElement('div');
    tasks.innerHTML = '<small>Verified tasks</small>';
    const taskValue = document.createElement('strong');
    taskValue.textContent =
      `${agent.succeeded_tasks}/${agent.completed_tasks}`;
    tasks.append(taskValue);

    const cost = document.createElement('div');
    cost.innerHTML = '<small>Cost / success</small>';
    const costValue = document.createElement('strong');
    costValue.textContent = agent.cost_per_success_usd === null
      ? '—'
      : `${Number(agent.cost_per_success_usd).toFixed(6)}`;
    cost.append(costValue);

    const latency = document.createElement('div');
    latency.innerHTML = '<small>Avg latency</small>';
    const latencyValue = document.createElement('strong');
    latencyValue.textContent = agent.average_latency_ms === null
      ? '—'
      : formatDuration(agent.average_latency_ms);
    latency.append(latencyValue);

    card.append(identity, success, tasks, cost, latency);
    root.append(card);
  });
}

function renderOperationalIncidents(data) {
  const incidents = data?.recent || [];
  $('#incident-critical').textContent =
    `${Number(data?.critical || 0)} critical`;
  $('#incident-warning').textContent =
    `${Number(data?.warning || 0)} warnings`;
  const root = $('#incident-list');
  root.replaceChildren();
  if (!incidents.length) {
    const clear = document.createElement('div');
    clear.className = 'incident-clear';
    const title = document.createElement('strong');
    title.textContent = 'No active incidents';
    const detail = document.createElement('span');
    detail.textContent = 'Seldrune has not detected failed work or blocked delivery.';
    clear.append(title, detail);
    root.append(clear);
    return;
  }
  incidents.forEach(incident => {
    const item = document.createElement('article');
    item.className = `incident-item incident-${incident.severity}`;
    const badge = document.createElement('span');
    badge.textContent = incident.severity;
    const content = document.createElement('div');
    const title = document.createElement('strong');
    title.textContent = incident.title;
    const detail = document.createElement('p');
    detail.textContent = incident.detail;
    const time = document.createElement('small');
    time.textContent = new Date(incident.occurred_at).toLocaleString();
    content.append(title, detail, time);
    item.append(badge, content);
    root.append(item);
  });
}


function renderAuditLog(data) {
  if (data) state.auditEvents = data.events || [];
  const filter = $('#audit-filter').value;
  const events = state.auditEvents.filter(event =>
    !filter || event.action.startsWith(filter)
      || event.resource_type === filter
  );
  $('#audit-count').textContent = `${events.length} events`;
  const root = $('#audit-list');
  root.replaceChildren();
  if (!events.length) {
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.textContent = filter
      ? 'No events match this filter.'
      : 'No governance events yet.';
    root.append(empty);
    return;
  }
  events.forEach(event => {
    const item = document.createElement('article');
    item.className = `audit-event audit-${event.severity || "info"}`;
    const marker = document.createElement('span');
    marker.className = 'audit-marker';
    const content = document.createElement('div');
    const title = document.createElement('strong');
    title.textContent = event.action.replaceAll('_', ' ').replaceAll('.', ' · ');
    const resource = document.createElement('p');
    resource.textContent = event.resource_id
      ? `${event.resource_type} · ${event.resource_id}`
      : event.resource_type;
    const time = document.createElement('small');
    time.textContent = new Date(event.occurred_at).toLocaleString();
    content.append(title, resource, time);
    item.append(marker, content);
    root.append(item);
  });
}

function renderRuntimeStatus(status) {
  const badge = $('#runtime-status');
  const database = status.checks?.database?.status || 'unknown';
  const provider = status.checks?.model_provider || {};
  badge.className = `runtime-status ${status.ready ? 'runtime-ready' : 'runtime-degraded'}`;
  badge.querySelector('strong').textContent =
    status.ready ? 'Runtime ready' : 'Runtime degraded';
  $('#runtime-version').textContent = [
    `v${status.version}`,
    status.environment,
    `DB ${database}`,
    provider.live_ai ? `Live AI · ${provider.model}` : `${provider.provider} · ${provider.status}`,
  ].join(' · ');
}

async function load() {
  if (!state.org) return;
  try {
    const [dashboard, runtimeStatus, auditLog] = await Promise.all([
      api('/owner-dashboard'),
      request('/status'),
      api('/audit-log?limit=30'),
    ]);
    renderRuntimeStatus(runtimeStatus);
    $('#total').textContent = dashboard.command_counts.total;
    $('#pending').textContent = dashboard.command_counts.awaiting_approval;
    $('#progress').textContent =
      `${dashboard.execution.succeeded_steps}/${dashboard.execution.total_steps}`;
    $('#cost').textContent =
      `${dashboard.usage.estimated_cost_usd.toFixed(4)}`;
    const treasury = dashboard.treasury || {};
    $('#treasury-projects').textContent =
      `${Number(treasury.project_count || 0)} projects`;
    $('#treasury-utilization').textContent =
      `${(Number(treasury.utilization || 0) * 100).toFixed(1)}% utilized`;
    $('#treasury-allocated').textContent =
      `${Number(treasury.allocated_budget_usd || 0).toFixed(2)}`;
    $('#treasury-spent').textContent =
      `${Number(treasury.spent_budget_usd || 0).toFixed(2)}`;
    $('#treasury-reserved').textContent =
      `${Number(treasury.reserved_budget_usd || 0).toFixed(2)}`;
    $('#treasury-available').textContent =
      `${Number(treasury.available_budget_usd || 0).toFixed(2)}`;
    $('#treasury-bar').style.width =
      `${Math.min(Number(treasury.utilization || 0) * 100, 100)}%`;
    $('#treasury-alert').classList.toggle('hidden', !treasury.overcommitted);
    renderOperationalIncidents(dashboard.operational_incidents);
    renderAuditLog(auditLog);
    renderAgentPerformance(dashboard.agent_performance);
    renderCommands(dashboard.recent_commands);
  } catch (error) {
    const badge = $('#runtime-status');
    badge.className = 'runtime-status runtime-degraded';
    badge.querySelector('strong').textContent = 'Runtime check failed';
    $('#runtime-version').textContent = error.message;
    toast(error.message);
  }
}

$('#audit-filter').onchange = () => renderAuditLog();

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

  const budget = data.budget_control || {};
  if (budget.forecast_cost_usd || budget.reservation || budget.recorded_cost_usd) {
    const reservation = budget.reservation || {};
    const controls = document.createElement('div');
    controls.className = `budget-panel ${budget.halted ? 'budget-panel-alert' : ''}`;
    const title = document.createElement('strong');
    title.textContent = budget.halted
      ? 'Budget circuit breaker triggered'
      : 'Governed project budget';
    const detail = document.createElement('span');
    detail.textContent = [
      `Forecast ${Number(budget.forecast_cost_usd || 0).toFixed(4)}`,
      `Reserved ${Number(reservation.amount_usd || 0).toFixed(4)} (${reservation.status || 'none'})`,
      `Recorded ${Number(budget.recorded_cost_usd || 0).toFixed(4)}`,
    ].join(' · ');
    controls.append(title, detail);
    box.append(controls);
  }

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
      note.textContent = data.recovery_command_id
        ? 'A linked recovery plan is awaiting your review.'
        : 'Promotion blocked: create a recovery plan to resolve the evidence gap.';
      promotion.append(note);
      if (!data.recovery_command_id) {
        const recover = document.createElement('button');
        recover.textContent = 'Create recovery plan';
        recover.onclick = async () => {
          recover.disabled = true;
          recover.textContent = 'Creating…';
          try {
            await api(`/owner-commands/${data.command_id}/recover`, {method: 'POST'});
            const refreshed = await api(`/owner-commands/${data.command_id}/brief`);
            renderBrief(refreshed);
            load();
            toast('Recovery plan created for approval');
          } catch (error) {
            recover.disabled = false;
            recover.textContent = 'Create recovery plan';
            toast(error.message);
          }
        };
        promotion.append(recover);
      }
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
    `- Recovery command: ${data.recovery_command_id || 'Not created'}`,
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
    } else if (selected.dataset.action === 'revoke') {
      selected.disabled = true;
      selected.textContent = 'Revoking…';
      await api(`/owner-commands/${selected.dataset.id}/revoke`, {
        method: 'POST',
      });
      toast('Approval revoked and budget released');
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
