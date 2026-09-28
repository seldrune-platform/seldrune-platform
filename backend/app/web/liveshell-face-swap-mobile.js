(() => {
  const q = selector => document.querySelector(selector);
  const token = sessionStorage.getItem('seldruneToken') || '';
  const state = {organizationId: '', workerReady: false, jobId: '', outputUrl: ''};
  const api = async (path, options = {}) => {
    const headers = {Accept: 'application/json', ...(token ? {Authorization: 'Bearer ' + token} : {})};
    if (!(options.body instanceof FormData) && options.body) headers['Content-Type'] = 'application/json';
    const response = await fetch('/api/v1' + path, {...options, headers: {...headers, ...(options.headers || {})}});
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || 'Request failed (' + response.status + ')');
    }
    return response.status === 204 ? null : response.json();
  };
  const jobPath = () => '/organizations/' + state.organizationId + '/liveshift/video-jobs';
  function status(message, kind = '') {
    q('#job-status').textContent = message;
    q('#job-status').className = 'status-message' + (kind ? ' ' + kind : '');
  }
  function setBusy(busy) {
    q('#process-button').disabled = busy || !state.workerReady;
    q('#delete-button').disabled = busy || !state.jobId;
  }
  async function pollJob() {
    const started = Date.now();
    while (Date.now() - started < 30 * 60 * 1000) {
      const job = await api(jobPath() + '/' + encodeURIComponent(state.jobId));
      q('#job-state').textContent = job.status.toUpperCase();
      if (job.status === 'failed') throw new Error(job.error || 'The GPU worker could not complete this job.');
      if (job.status === 'completed') return job;
      status(job.status === 'processing' ? 'RTX 4090 is processing the video…' : 'Your video is queued for the GPU…');
      await new Promise(resolve => setTimeout(resolve, 4000));
    }
    throw new Error('This job is still processing. Check back shortly; the worker keeps it for up to one hour.');
  }
  async function processVideo(event) {
    event.preventDefault();
    const face = q('#source-face').files[0];
    const video = q('#target-video').files[0];
    if (!state.workerReady) return status('The RunPod GPU worker is not ready yet.', 'error');
    if (!face || !video) return status('Choose both an authorized face image and a target video.', 'error');
    if (!q('#face-consent').checked || !q('#video-rights').checked || !q('#synthetic-indicator').checked) {
      return status('Confirm face permission, video rights, and the synthetic-media label.', 'error');
    }
    q('#output-video').removeAttribute('src');
    q('#output-video').load();
    q('#download-button').hidden = true;
    q('#output-placeholder').hidden = false;
    q('#job-state').textContent = 'UPLOADING';
    q('#output-model').textContent = 'Ghost 1 · 256';
    setBusy(true);
    const form = new FormData();
    form.append('source_face', face);
    form.append('target_video', video);
    form.append('consent_confirmed', 'true');
    form.append('synthetic_media_indicator_enabled', 'true');
    try {
      status('Uploading media to the authorized GPU worker…');
      const created = await api(jobPath(), {method: 'POST', body: form});
      state.jobId = created.job_id;
      q('#job-state').textContent = 'QUEUED';
      q('#output-model').textContent = created.model + ' · ' + created.model_license;
      const result = await pollJob();
      q('#job-state').textContent = 'COMPLETE';
      q('#output-dimensions').textContent = result.output_width && result.output_height
        ? result.output_width + '×' + result.output_height + (result.output_fps ? ' · ' + result.output_fps.toFixed(1) + ' fps' : '')
        : 'Not reported';
      q('#output-audio').textContent = result.audio_sample_rate_hz
        ? result.audio_sample_rate_hz + ' Hz · original audio retained'
        : 'No audio stream reported';
      q('#output-gpu').textContent = result.actual_accelerator_profile || 'GPU not reported';
      const download = await fetch('/api/v1' + jobPath() + '/' + encodeURIComponent(state.jobId) + '/download', {
        headers: {Authorization: 'Bearer ' + token},
      });
      if (!download.ok) throw new Error('The processed video could not be downloaded.');
      const blob = await download.blob();
      state.outputUrl = URL.createObjectURL(blob);
      q('#output-video').src = state.outputUrl;
      q('#output-video').load();
      q('#output-placeholder').hidden = true;
      const link = q('#download-button');
      link.href = state.outputUrl;
      link.download = 'seldrune-face-swap-synthetic.mp4';
      link.hidden = false;
      status('Complete. The output has a visible synthetic-media label and the source audio is retained at 48 kHz.', 'success');
    } catch (error) {
      q('#job-state').textContent = 'ERROR';
      status(error.message, 'error');
    } finally {
      setBusy(false);
    }
  }
  async function deleteJob() {
    if (!state.jobId) return;
    q('#delete-button').disabled = true;
    try {
      await api(jobPath() + '/' + encodeURIComponent(state.jobId), {method: 'DELETE'});
      state.jobId = '';
      q('#job-state').textContent = 'READY';
      q('#output-gpu').textContent = 'Not connected';
      q('#output-dimensions').textContent = 'Not measured';
      q('#output-audio').textContent = 'Original audio retained';
      q('#output-model').textContent = 'Not started';
      q('#output-video').removeAttribute('src');
      q('#output-video').load();
      q('#output-placeholder').hidden = false;
      q('#download-button').hidden = true;
      if (state.outputUrl) URL.revokeObjectURL(state.outputUrl);
      state.outputUrl = '';
      status('Job files deleted from the worker.', 'success');
    } catch (error) {
      status(error.message, 'error');
      q('#delete-button').disabled = false;
    }
  }
  async function initialize() {
    if (!token) {
      q('#worker-state').textContent = 'Sign-in required';
      q('#worker-state').classList.add('error');
      status('Sign in through the Seldrune console, then reopen this page.', 'error');
      return;
    }
    try {
      const me = await api('/auth/me');
      const membership = me.memberships.find(item => item.role === 'owner') || me.memberships[0];
      if (!membership) throw new Error('No Seldrune organization is available for this account.');
      state.organizationId = membership.organization.id;
      const readiness = await api(jobPath() + '/readiness');
      state.workerReady = Boolean(readiness.worker_ready);
      if (readiness.accelerator) q('#gpu-target').textContent = readiness.accelerator;
      if (state.workerReady) {
        q('#worker-state').textContent = 'GPU worker ready · ' + (readiness.accelerator || 'accelerator detected');
        q('#worker-state').classList.add('ready');
        status('Choose a face image and a video to start an authorized job.');
      } else {
        q('#worker-state').textContent = readiness.worker_configured ? 'GPU worker offline' : 'GPU worker not configured';
        q('#worker-state').classList.add('error');
        status('The app is connected to Seldrune. Processing unlocks when the authenticated RunPod worker is online.', '');
      }
      setBusy(false);
    } catch (error) {
      q('#worker-state').textContent = 'Seldrune readiness check failed';
      q('#worker-state').classList.add('error');
      status(error.message, 'error');
    }
  }
  q('#job-form').addEventListener('submit', processVideo);
  q('#delete-button').addEventListener('click', deleteJob);
  window.addEventListener('pagehide', () => { if (state.outputUrl) URL.revokeObjectURL(state.outputUrl); });
  initialize();
})();
