(() => {
  const missionState = {
    data: null,
    syncing: false,
  };

  const byId = id => document.getElementById(id);

  function text(element, value) {
    if (element) element.textContent = value;
  }

  function percentage(value) {
    return `${Number(value || 0).toFixed(1)}%`;
  }

  function renderOneGo(report) {
    if (!report) return;
    text(byId('mission-one-go-version'), report.controller_version || 'one-go');
    text(byId('mission-one-go-waves'), String(Number(report.waves_executed || 0)));
    text(byId('mission-one-go-executed'), String(Number(report.tasks_executed || 0)));
    text(byId('mission-one-go-verified'), String(Number(report.tasks_verified || 0)));
    text(byId('mission-one-go-unverified'), String(Number(report.tasks_unverified || 0)));
    text(byId('mission-one-go-blocked'), String(Number(report.tasks_blocked || 0)));
    text(byId('mission-one-go-failed'), String(Number(report.tasks_failed || 0)));
    const halt = report.halted_reason
      ? report.halted_reason.replaceAll('_', ' ')
      : 'controller completed requested waves';
    const recoveryAttempts = Number(report.recovery_attempts || 0);
    const gates = [
      Number(report.recovery_owner_gates || 0) ? 'owner approval' : '',
      Number(report.recovery_configuration_gates || 0) ? 'configuration' : '',
      Number(report.recovery_external_resource_gates || 0) ? 'external resource' : '',
    ].filter(Boolean);
    const recoveryText = recoveryAttempts
      ? ` Recovery: ${recoveryAttempts} bounded attempt(s)`
        + (gates.length ? `; stopped at ${gates.join(', ')} gate(s)` : '')
        + '.'
      : '';
    const stageResults = Array.isArray(report.stage_results)
      ? report.stage_results
      : [];
    const githubBillingBlocked = stageResults.some(item => (
      String(item.reason || '').includes('github_actions_billing_block')
    ));
    const resourceHint = githubBillingBlocked
      ? ' GitHub Actions billing/budget blocked job start; '
        + 'check the organization Actions budget and payment state, then rerun.'
      : '';
    text(
      byId('mission-one-go-status'),
      `Progress ${percentage(report.starting_percentage)} → `
      + `${percentage(report.ending_percentage)} · ${halt}.`
      + recoveryText
      + resourceHint
    );
  }

  function stageStatus(stage) {
    if (stage.status === 'completed') return 'completed';
    if (stage.paused) return 'paused';
    if (stage.ready) return 'ready';
    return 'blocked';
  }

  function renderSummary(mission) {
    text(byId('mission-overall'), percentage(mission.overall_percentage));
    text(byId('mission-remaining'), percentage(mission.remaining_percentage));
    text(
      byId('mission-ready-count'),
      String((mission.parallel_ready_stage_ids || []).length)
    );
    text(
      byId('mission-paused-count'),
      String((mission.paused_stage_ids || []).length)
    );
    const bar = byId('mission-progress-bar');
    if (bar) bar.style.width = percentage(mission.overall_percentage);
    text(byId('mission-basis'), mission.percentage_basis || '');
  }

  function renderWorkstreams(mission) {
    const root = byId('mission-workstreams');
    if (!root) return;
    root.replaceChildren();
    (mission.workstreams || []).forEach(stream => {
      const card = document.createElement('article');
      card.className = `mission-stream${stream.paused ? ' paused' : ''}`;

      const top = document.createElement('div');
      top.className = 'mission-stream-top';

      const identity = document.createElement('div');
      const name = document.createElement('strong');
      name.textContent = stream.title;
      const count = document.createElement('small');
      count.textContent =
        `${stream.completed_stage_count}/${stream.stage_count} milestones complete`;
      identity.append(name, count);

      const score = document.createElement('span');
      score.className = `mission-pill${stream.paused ? ' paused' : ''}`;
      score.textContent = percentage(stream.percentage);

      top.append(identity, score);

      const shell = document.createElement('div');
      shell.className = 'mission-progress-shell';
      shell.style.marginTop = '.75rem';
      const bar = document.createElement('div');
      bar.className = 'mission-progress-bar';
      bar.style.width = percentage(stream.percentage);
      shell.append(bar);

      card.append(top, shell);
      if (stream.paused_reason) {
        const reason = document.createElement('small');
        reason.style.marginTop = '.65rem';
        reason.textContent = stream.paused_reason;
        card.append(reason);
      }
      root.append(card);
    });
  }

  function renderStages(mission) {
    const root = byId('mission-ready-stages');
    if (!root) return;
    root.replaceChildren();

    const stages = [...(mission.stages || [])].sort((left, right) => {
      const leftComplete = left.status === 'completed' ? 1 : 0;
      const rightComplete = right.status === 'completed' ? 1 : 0;
      return leftComplete - rightComplete;
    });
    if (!stages.length) {
      const empty = document.createElement('div');
      empty.className = 'empty';
      empty.textContent = 'No roadmap milestones are defined.';
      root.append(empty);
      return;
    }

    stages.forEach(stage => {
      const status = stageStatus(stage);
      const card = document.createElement('article');
      card.className = 'mission-stage';
      card.dataset.status = status;

      const top = document.createElement('div');
      top.className = 'mission-stage-top';

      const identity = document.createElement('div');
      const title = document.createElement('strong');
      title.textContent = stage.title;
      const workstream = document.createElement('small');
      workstream.textContent = stage.workstream.replaceAll('_', ' ');
      identity.append(title, workstream);

      const badge = document.createElement('span');
      badge.className = `mission-pill ${status}`;
      badge.textContent = status.replaceAll('_', ' ');

      top.append(identity, badge);

      const objective = document.createElement('p');
      objective.textContent = stage.objective;

      const dependency = document.createElement('div');
      dependency.className = 'mission-dependency';
      const dependencyText = stage.depends_on.length
        ? `Depends on: ${stage.depends_on.join(', ')}`
        : 'No dependencies';
      const evidenceText = (stage.evidence_refs || []).length
        ? ` · Evidence: ${stage.evidence_refs.join(', ')}`
        : '';
      dependency.textContent = dependencyText + evidenceText;

      card.append(top, objective, dependency);
      root.append(card);
    });
  }

  function renderMission(mission) {
    missionState.data = mission;
    renderSummary(mission);
    renderWorkstreams(mission);
    renderStages(mission);
    renderOneGo(mission.one_go_execution);
    text(
      byId('mission-master-task'),
      mission.master_task_id
        ? `Master task ${mission.master_task_id}`
        : 'Master task not yet synchronized'
    );
    const queued = Number(mission.auto_queued_count || 0);
    text(
      byId('mission-sync-status'),
      queued
        ? `Synchronized · ${queued} new dependency-ready tasks queued in parallel.`
        : 'Synchronized · no duplicate task created and no unsafe stage auto-executed.'
    );
  }

  async function syncMission() {
    if (missionState.syncing) return;
    missionState.syncing = true;
    const button = byId('mission-refresh');
    if (button) button.disabled = true;
    text(byId('mission-sync-status'), 'Synchronizing cognitive mission…');
    try {
      const mission = await api('/development-mission/sync', {
        method: 'POST',
      });
      renderMission(mission);
    } catch (error) {
      text(byId('mission-sync-status'), error.message);
    } finally {
      missionState.syncing = false;
      if (button) button.disabled = false;
    }
  }

  async function queueReadyWave() {
    const button = byId('mission-queue-ready');
    if (button) button.disabled = true;
    try {
      const result = await api('/development-mission/queue-ready', {
        method: 'POST',
      });
      const count = Number(result.queued_count || 0);
      toast(
        count
          ? `${count} dependency-ready mission tasks queued`
          : 'Ready mission tasks were already queued'
      );
      await syncMission();
    } catch (error) {
      toast(error.message);
    } finally {
      if (button) button.disabled = false;
    }
  }

  async function runOneGo() {
    const button = byId('mission-run-one-go');
    if (button) button.disabled = true;
    text(byId('mission-one-go-status'), 'Running evidence-gated execution wave…');
    try {
      const report = await api('/development-mission/execute', {
        method: 'POST',
        body: JSON.stringify({
          max_waves: 3,
          max_tasks: 8,
          recovery_rounds: 3,
        }),
      });
      renderOneGo(report);
      const mission = await api('/development-mission');
      renderMission(mission);
      toast(
        report.tasks_verified
          ? `${report.tasks_verified} mission stages verified`
          : 'One-Go finished without new verified completion evidence'
      );
    } catch (error) {
      text(byId('mission-one-go-status'), error.message);
      toast(error.message);
    } finally {
      if (button) button.disabled = false;
    }
  }

  document.addEventListener('seldrune:console-ready', syncMission);
  document.addEventListener('DOMContentLoaded', () => {
    const refresh = byId('mission-refresh');
    const queue = byId('mission-queue-ready');
    const run = byId('mission-run-one-go');
    if (refresh) refresh.addEventListener('click', syncMission);
    if (queue) queue.addEventListener('click', queueReadyWave);
    if (run) run.addEventListener('click', runOneGo);
  });
})();
