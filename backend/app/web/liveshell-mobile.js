(() => {
  const q = selector => document.querySelector(selector);
  const token = sessionStorage.getItem('seldruneToken') || '';
  const state = {
    organizationId: '',
    gatewayConfigured: false,
    localStream: null,
    peer: null,
    sessionId: '',
    facingMode: 'user',
    gatewayAudioSampleRate: 0,
    mediaMonitorTimer: 0,
  };

  const api = async (path, options = {}) => {
    const response = await fetch('/api/v1' + path, {
      ...options,
      headers: {
        Accept: 'application/json',
        ...(options.body ? {'Content-Type': 'application/json'} : {}),
        ...(token ? {Authorization: 'Bearer ' + token} : {}),
      },
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || 'Request failed (' + response.status + ')');
    }
    return response.status === 204 ? null : response.json();
  };

  function showStatus(message, kind) {
    const element = q('#session-status');
    element.textContent = message;
    element.className = 'status-message' + (kind ? ' ' + kind : '');
  }

  function setConnection(value) {
    q('#connection-state').textContent = value;
  }

  function captureConstraints() {
    const fullHd = q('#resolution').value === '1080p';
    return {
      audio: {
        channelCount: {ideal: 1},
        sampleRate: {ideal: 48000},
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
      video: {
        width: {ideal: fullHd ? 1920 : 1280},
        height: {ideal: fullHd ? 1080 : 720},
        frameRate: {ideal: 30, max: 30},
        facingMode: {ideal: state.facingMode},
      },
    };
  }

  async function ensureCapture() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error('Camera and microphone require a supported browser on HTTPS.');
    }
    if (state.localStream && state.localStream.active) return state.localStream;
    state.localStream = await navigator.mediaDevices.getUserMedia(captureConstraints());
    q('#local-video').srcObject = state.localStream;
    q('#switch-camera').disabled = false;
    const video = state.localStream.getVideoTracks()[0];
    const audio = state.localStream.getAudioTracks()[0];
    const settings = video ? video.getSettings() : {};
    const width = settings.width || 0;
    const height = settings.height || 0;
    const sampleRate = audio && audio.getSettings().sampleRate;
    q('#capture-resolution').textContent = width && height ? width + '×' + height : 'Captured';
    q('#capture-detail').textContent = width && height ? width + '×' + height + ' · ' + (settings.frameRate || 'fps ?') : 'Camera active';
    q('#audio-detail').textContent = sampleRate ? sampleRate + ' Hz input' : '48 kHz target · input unreported';
    return state.localStream;
  }

  function waitForIceGathering(peer) {
    if (peer.iceGatheringState === 'complete') return Promise.resolve();
    return new Promise(resolve => {
      const timeout = setTimeout(done, 12000);
      function done() {
        clearTimeout(timeout);
        peer.removeEventListener('icegatheringstatechange', check);
        resolve();
      }
      function check() {
        if (peer.iceGatheringState === 'complete') done();
      }
      peer.addEventListener('icegatheringstatechange', check);
    });
  }

  async function refreshReturnedMedia() {
    const peer = state.peer;
    if (!peer) return;

    const video = q('#remote-video');
    const videoTrack = video.srcObject && video.srcObject.getVideoTracks()[0];
    const audioElement = q('#remote-audio');
    const audioTrack = audioElement.srcObject && audioElement.srcObject.getAudioTracks()[0];
    const videoSettings = videoTrack && videoTrack.getSettings ? videoTrack.getSettings() : {};
    const audioSettings = audioTrack && audioTrack.getSettings ? audioTrack.getSettings() : {};
    const width = video.videoWidth || videoSettings.width || 0;
    const height = video.videoHeight || videoSettings.height || 0;
    let videoReport = null;
    let audioReport = null;

    try {
      const reports = await peer.getStats();
      reports.forEach(report => {
        if (report.type !== 'inbound-rtp') return;
        const kind = report.kind || report.mediaType;
        if (kind === 'video') videoReport = report;
        if (kind === 'audio') audioReport = report;
      });
    } catch (_) {
      // Track state and intrinsic video dimensions remain useful if stats are unavailable.
    }

    const framesDecoded = videoReport && Number.isFinite(videoReport.framesDecoded)
      ? videoReport.framesDecoded : null;
    const fps = videoReport && Number.isFinite(videoReport.framesPerSecond)
      ? Math.round(videoReport.framesPerSecond) : null;
    const videoLive = Boolean(videoTrack && videoTrack.readyState === 'live' && width && height);
    const audioLive = Boolean(audioTrack && audioTrack.readyState === 'live');

    q('#output-metrics').textContent = videoLive
      ? 'Browser: ' + width + '×' + height + (fps ? ' · ' + fps + ' fps' : '')
      : 'Waiting for returned frames';

    const measuredRate = Number(audioSettings.sampleRate) || 0;
    const gatewayRate = state.gatewayAudioSampleRate;
    q('#audio-detail').textContent = audioLive
      ? 'Browser track live' + (measuredRate ? ' · ' + measuredRate + ' Hz' : ' · rate unavailable')
        + (gatewayRate ? ' · gateway reports ' + gatewayRate + ' Hz' : '')
      : (gatewayRate ? 'Gateway reports ' + gatewayRate + ' Hz · waiting for browser track' : 'Waiting for returned audio');

    const videoCount = framesDecoded === null ? 'decoder count unavailable' : framesDecoded + ' decoded frames';
    const audioCount = audioReport && Number.isFinite(audioReport.packetsReceived)
      ? audioReport.packetsReceived + ' audio packets'
      : (audioLive ? 'audio track live' : 'audio track pending');
    q('#proof-detail').textContent = videoLive || audioLive
      ? 'Browser receive · ' + videoCount + ' · ' + audioCount
      : 'No returned tracks yet';
  }

  function attachReturnedTrack(event) {
    const track = event.track;
    const stream = new MediaStream([track]);
    if (track.kind === 'video') {
      q('#remote-video').srcObject = stream;
      q('.output-card').classList.add('active');
    } else if (track.kind === 'audio') {
      q('#remote-audio').srcObject = stream;
      q('#remote-audio').play().catch(() => {});
    }
    void refreshReturnedMedia();
  }

  async function startLive(event) {
    event.preventDefault();
    if (!state.gatewayConfigured) {
      showStatus('The GPU session gateway is not configured on this deployment yet.', 'error');
      return;
    }
    if (!q('#face-profile').value.trim() || !q('#voice-profile').value.trim()) {
      showStatus('Enter both authorized enrolled profile IDs.', 'error');
      return;
    }
    if (!q('#face-consent').checked || !q('#voice-consent').checked || !q('#synthetic-indicator').checked) {
      showStatus('Confirm face authorization, voice authorization, and the persistent synthetic-media indicator.', 'error');
      return;
    }

    q('#connect-button').disabled = true;
    q('#preview-button').disabled = true;
    showStatus('Requesting camera and microphone…');
    setConnection('CONNECTING');
    try {
      const stream = await ensureCapture();
      const peer = new RTCPeerConnection({
        iceServers: [{urls: 'stun:stun.l.google.com:19302'}],
      });
      state.peer = peer;
      for (const track of stream.getTracks()) peer.addTrack(track, stream);
      peer.addEventListener('track', attachReturnedTrack);
      peer.addEventListener('connectionstatechange', () => {
        if (peer.connectionState === 'connected') setConnection('CONNECTED');
        if (peer.connectionState === 'disconnected' || peer.connectionState === 'failed') {
          setConnection(peer.connectionState.toUpperCase());
        }
      });

      const offer = await peer.createOffer();
      await peer.setLocalDescription(offer);
      await waitForIceGathering(peer);
      const body = {
        offer: {type: 'offer', sdp: peer.localDescription.sdp},
        face_profile_id: q('#face-profile').value.trim(),
        voice_profile_id: q('#voice-profile').value.trim(),
        consent_confirmed: true,
        synthetic_media_indicator_enabled: true,
        video_resolution: q('#resolution').value,
        target_accelerator_profile: q('#gpu-target').value,
      };
      const result = await api(
        '/organizations/' + state.organizationId + '/liveshift/live/sessions',
        {method: 'POST', body: JSON.stringify(body)},
      );
      state.sessionId = result.session_id;
      await peer.setRemoteDescription(result.answer);
      q('#stop-button').disabled = false;
      q('#switch-camera').disabled = false;

      const actualGpu = result.actual_accelerator_profile || 'worker GPU not reported';
      q('#gpu-detail').textContent = actualGpu;
      const output = result.output || {};
      state.gatewayAudioSampleRate = Number(output.audio_sample_rate_hz) || 0;
      const dimensions = output.width && output.height
        ? output.width + '×' + output.height + ' · ' + (output.fps || 'fps unreported')
        : 'resolution unreported';
      q('#output-metrics').textContent = 'Waiting for browser frames · gateway reports ' + dimensions;
      q('#audio-detail').textContent = state.gatewayAudioSampleRate
        ? 'Gateway reports ' + state.gatewayAudioSampleRate + ' Hz · waiting for browser track'
        : 'Waiting for returned audio';
      q('#proof-detail').textContent = 'Waiting for returned browser tracks';
      const requiredWidth = q('#resolution').value === '1080p' ? 1920 : 1280;
      const requiredHeight = q('#resolution').value === '1080p' ? 1080 : 720;

      if (output.width >= requiredWidth && output.height >= requiredHeight && output.fps >= 24 && state.gatewayAudioSampleRate >= 48000) {
        showStatus('Session connected. The gateway reports the requested HD targets; browser-received frames and audio are measured below.', 'success');
      } else {
        showStatus('Session connected. Waiting for browser-received video and audio measurements.', 'success');
      }
      setConnection('NEGOTIATED');
      if (state.mediaMonitorTimer) window.clearInterval(state.mediaMonitorTimer);
      state.mediaMonitorTimer = window.setInterval(() => { void refreshReturnedMedia(); }, 1000);
      void refreshReturnedMedia();
    } catch (error) {
      showStatus('The live session could not start: ' + error.message, 'error');
      await stopLive(true);
    } finally {
      q('#connect-button').disabled = !state.gatewayConfigured;
      q('#preview-button').disabled = Boolean(state.peer);
    }
  }

  async function stopLive(closeRemote = true) {
    const sessionId = state.sessionId;
    state.sessionId = '';
    if (state.mediaMonitorTimer) {
      window.clearInterval(state.mediaMonitorTimer);
      state.mediaMonitorTimer = 0;
    }
    state.gatewayAudioSampleRate = 0;
    if (closeRemote && sessionId && state.organizationId && token) {
      try {
        await api(
          '/organizations/' + state.organizationId + '/liveshift/live/sessions/' + encodeURIComponent(sessionId),
          {method: 'DELETE'},
        );
      } catch (error) {
        showStatus('Local media stopped. The gateway close request failed: ' + error.message, 'error');
      }
    }
    if (state.peer) {
      state.peer.getSenders().forEach(sender => sender.track && sender.track.stop());
      state.peer.close();
      state.peer = null;
    }
    if (state.localStream) {
      state.localStream.getTracks().forEach(track => track.stop());
      state.localStream = null;
    }
    q('#local-video').srcObject = null;
    q('#remote-video').srcObject = null;
    q('#remote-audio').srcObject = null;
    q('.output-card').classList.remove('active');
    q('#output-placeholder').textContent = 'Transformed video appears here after an authorized GPU session connects.';
    q('#capture-resolution').textContent = '—';
    q('#capture-detail').textContent = 'Not started';
    q('#gpu-detail').textContent = 'Not connected';
    q('#output-metrics').textContent = 'Waiting for returned frames';
    q('#proof-detail').textContent = 'No returned tracks yet';
    q('#audio-detail').textContent = 'Waiting for returned audio';
    q('#stop-button').disabled = true;
    q('#switch-camera').disabled = true;
    q('#preview-button').disabled = false;
    setConnection('OFFLINE');
  }

  async function preview() {
    try {
      await ensureCapture();
      showStatus('Local camera and microphone are active. This is a preview; no transformation has started.', 'success');
      setConnection('PREVIEW');
    } catch (error) {
      showStatus(error.message, 'error');
    }
  }

  async function switchCamera() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return;
    const nextFacing = state.facingMode === 'user' ? 'environment' : 'user';
    try {
      const nextStream = await navigator.mediaDevices.getUserMedia({
        video: {
          ...captureConstraints().video,
          facingMode: {ideal: nextFacing},
        },
        audio: false,
      });
      const nextTrack = nextStream.getVideoTracks()[0];
      const oldTrack = state.localStream && state.localStream.getVideoTracks()[0];
      if (state.peer) {
        const sender = state.peer.getSenders().find(item => item.track && item.track.kind === 'video');
        if (sender) await sender.replaceTrack(nextTrack);
      }
      if (oldTrack && state.localStream) {
        state.localStream.removeTrack(oldTrack);
        oldTrack.stop();
      }
      if (!state.localStream) state.localStream = new MediaStream();
      state.localStream.addTrack(nextTrack);
      q('#local-video').srcObject = state.localStream;
      state.facingMode = nextFacing;
      const settings = nextTrack.getSettings();
      q('#capture-resolution').textContent = settings.width && settings.height ? settings.width + '×' + settings.height : 'Captured';
      q('#capture-detail').textContent = settings.width && settings.height ? settings.width + '×' + settings.height + ' · ' + (settings.frameRate || 'fps ?') : 'Camera active';
    } catch (error) {
      showStatus('Camera switch failed: ' + error.message, 'error');
    }
  }

  async function initialize() {
    if (!token) {
      showStatus('Sign in first, then open this page in the same tab.', 'error');
      q('#gateway-state').textContent = 'Sign-in required';
      q('#gateway-state').classList.add('error');
      q('#preview-button').disabled = true;
      return;
    }
    try {
      const me = await api('/auth/me');
      const membership = me.memberships.find(item => item.role === 'owner') || me.memberships[0];
      if (!membership) throw new Error('No organization is available for this account.');
      state.organizationId = membership.organization.id;
      const readiness = await api('/organizations/' + state.organizationId + '/liveshift/live/readiness');
      state.gatewayConfigured = Boolean(readiness.gateway_configured);
      if (state.gatewayConfigured) {
        q('#gateway-state').textContent = 'Gateway configured · worker and model readiness still require a live session.';
        q('#gateway-state').classList.add('ready');
        q('#connect-button').disabled = false;
        showStatus('Gateway is configured. Confirm both enrolled profiles and start a measured session.', '');
      } else {
        q('#gateway-state').textContent = 'GPU session gateway not configured';
        q('#gateway-state').classList.add('error');
        showStatus('Camera preview is available. Live transformation will unlock after the private GPU gateway and authorized models are configured.', '');
      }
    } catch (error) {
      q('#gateway-state').textContent = 'Sign-in or readiness check failed';
      q('#gateway-state').classList.add('error');
      showStatus(error.message, 'error');
      q('#preview-button').disabled = true;
    }
  }

  q('#session-form').addEventListener('submit', startLive);
  q('#preview-button').addEventListener('click', preview);
  q('#stop-button').addEventListener('click', () => stopLive(true));
  q('#switch-camera').addEventListener('click', switchCamera);
  window.addEventListener('pagehide', () => {
    if (state.peer) state.peer.close();
    if (state.localStream) state.localStream.getTracks().forEach(track => track.stop());
  });
  initialize();
})();

