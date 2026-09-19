(() => {
  const q = selector => document.querySelector(selector);
  const apiPrefix = '/api/v1';

  function render(data) {
    const counts = data.counts || {};
    q('#sti-queued').textContent = counts.queued ?? 0;
    q('#sti-running').textContent = counts.running ?? 0;
    q('#sti-verified').textContent = counts.verified ?? 0;
    q('#sti-failed').textContent = counts.failed ?? 0;
    q('#sti-runtime-source').textContent =
      'Measured from ' + (data.source || 'durable-run-store') + ' · no simulated activity';

    const liveshift = data.liveshift || {};
    const stateText = value => value ? 'READY' : 'PENDING';
    q('#ls-webrtc').textContent = stateText(liveshift.webrtc_runtime);
    q('#ls-cuda').textContent = stateText(liveshift.cuda_runtime);
    q('#ls-onnx').textContent = stateText(liveshift.onnx_runtime);
    q('#ls-tensorrt').textContent = stateText(liveshift.tensorrt_runtime);
    q('#ls-face-model').textContent = stateText(liveshift.face_model_loaded);
    q('#ls-first-frame').textContent = stateText(liveshift.first_frame_transformed);
    q('#ls-live-return').textContent = stateText(liveshift.live_stream_returned);
    q('#ls-camera').textContent = stateText(liveshift.virtual_camera_connected);
    q('#liveshift-accelerator').textContent =
      liveshift.accelerator_name || 'Accelerator profile unavailable';
    q('#liveshift-vram').textContent = liveshift.preferred_vram_gb
      ? ' · preferred ' + liveshift.preferred_vram_gb + ' GB VRAM'
      : '';
    q('#liveshift-note').textContent =
      liveshift.note || 'Measured runtime detection · product milestones remain locked until verified.';

    const forge = data.forge || {};
    q('#forge-queued').textContent = forge.queued ?? 0;
    q('#forge-running').textContent = forge.running ?? 0;
    q('#forge-verified').textContent = forge.verified ?? 0;
    q('#forge-failed').textContent = forge.failed ?? 0;

    const list = q('#sti-run-list');
    list.replaceChildren();
    const runs = data.recent || [];
    if (!runs.length) {
      const empty = document.createElement('div');
      empty.className = 'empty';
      empty.textContent = 'No durable STI executions recorded yet.';
      list.append(empty);
      return;
    }
    runs.forEach(run => {
      const row = document.createElement('div');
      row.className = 'sti-run';
      const task = document.createElement('span');
      task.textContent = run.task_id;
      const detail = document.createElement('small');
      detail.textContent =
        run.run_id + ' · attempt ' + run.attempts + ' · ' +
        run.evidence_count + ' evidence item(s)' + (run.error ? ' · ' + run.error : '');
      const state = document.createElement('strong');
      state.className = 'sti-state sti-state-' + run.state;
      state.textContent = run.state;
      row.append(task, detail, state);
      list.append(row);
    });
  }

  async function refresh() {
    const source = q('#sti-runtime-source');
    try {
      const response = await fetch(apiPrefix + '/sti/telemetry', {
        credentials: 'same-origin',
        headers: {Accept: 'application/json'},
      });
      if (!response.ok) throw new Error('telemetry unavailable (' + response.status + ')');
      render(await response.json());
    } catch (error) {
      source.textContent = 'STI telemetry unavailable · ' + error.message;
    }
  }

  q('#sti-runtime-refresh')?.addEventListener('click', refresh);
  refresh();
  window.setInterval(refresh, 15000);
})();
