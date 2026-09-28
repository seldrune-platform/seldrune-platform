(() => {
  const q = selector => document.querySelector(selector);
  const token = sessionStorage.getItem('seldruneToken') || '';
  const state = {
    organizationId: '',
    userId: '',
    gatewayConfigured: false,
    localStream: null,
    peer: null,
    disconnectTimer: null,
    sessionId: '',
    facingMode: 'user',
    browserDecodedVideo: null,
    outputProfile: null,
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

  const markerPositionStorageKey = 'seldrune.liveShell.markerPosition';
  let markerPosition = null;
  let markerDrag = null;

  try {
    const savedPosition = JSON.parse(localStorage.getItem(markerPositionStorageKey) || 'null');
    if (savedPosition && Number.isFinite(savedPosition.x) && Number.isFinite(savedPosition.y)) {
      markerPosition = {
        x: Math.min(1, Math.max(0, savedPosition.x)),
        y: Math.min(1, Math.max(0, savedPosition.y)),
      };
    }
  } catch {}

  function setMarkerPosition(left, top) {
    const wrap = q('.output-wrap');
    const badge = q('#synthetic-badge');
    if (!wrap || !badge || !wrap.clientWidth || !badge.offsetWidth) return;

    const min = 8;
    const maxLeft = Math.max(min, wrap.clientWidth - badge.offsetWidth - min);
    const maxTop = Math.max(min, wrap.clientHeight - badge.offsetHeight - min);
    const boundedLeft = Math.min(maxLeft, Math.max(min, left));
    const boundedTop = Math.min(maxTop, Math.max(min, top));
    const leftRange = Math.max(0, maxLeft - min);
    const topRange = Math.max(0, maxTop - min);

    badge.style.left = boundedLeft + 'px';
    badge.style.top = boundedTop + 'px';
    badge.style.right = 'auto';
    badge.style.bottom = 'auto';
    markerPosition = {
      x: leftRange ? (boundedLeft - min) / leftRange : 0,
      y: topRange ? (boundedTop - min) / topRange : 0,
    };
    try {
      localStorage.setItem(markerPositionStorageKey, JSON.stringify(markerPosition));
    } catch {}
  }

  function applyMarkerPosition() {
    const wrap = q('.output-wrap');
    const badge = q('#synthetic-badge');
    if (!markerPosition || !wrap || !badge || !wrap.clientWidth || !badge.offsetWidth) return;
    const min = 8;
    const maxLeft = Math.max(min, wrap.clientWidth - badge.offsetWidth - min);
    const maxTop = Math.max(min, wrap.clientHeight - badge.offsetHeight - min);
    setMarkerPosition(
      min + markerPosition.x * Math.max(0, maxLeft - min),
      min + markerPosition.y * Math.max(0, maxTop - min),
    );
  }

  function installMarkerPositionControl() {
    const wrap = q('.output-wrap');
    const badge = q('#synthetic-badge');
    if (!wrap || !badge) return;

    badge.addEventListener('pointerdown', event => {
      if (event.pointerType === 'mouse' && event.button !== 0) return;
      event.preventDefault();
      const rect = badge.getBoundingClientRect();
      markerDrag = {
        pointerId: event.pointerId,
        x: event.clientX - rect.left,
        y: event.clientY - rect.top,
      };
      badge.setAttribute('aria-grabbed', 'true');
      badge.setPointerCapture?.(event.pointerId);
    });

    badge.addEventListener('pointermove', event => {
      if (!markerDrag || markerDrag.pointerId !== event.pointerId) return;
      const rect = wrap.getBoundingClientRect();
      setMarkerPosition(
        event.clientX - rect.left - markerDrag.x,
        event.clientY - rect.top - markerDrag.y,
      );
    });

    const finishMarkerDrag = event => {
      if (!markerDrag || markerDrag.pointerId !== event.pointerId) return;
      markerDrag = null;
      badge.setAttribute('aria-grabbed', 'false');
    };
    badge.addEventListener('pointerup', finishMarkerDrag);
    badge.addEventListener('pointercancel', finishMarkerDrag);
    badge.addEventListener('lostpointercapture', finishMarkerDrag);

    badge.addEventListener('keydown', event => {
      const step = 12;
      const movement = {
        ArrowLeft: [-step, 0],
        ArrowRight: [step, 0],
        ArrowUp: [0, -step],
        ArrowDown: [0, step],
      }[event.key];
      if (!movement) return;
      event.preventDefault();
      setMarkerPosition(badge.offsetLeft + movement[0], badge.offsetTop + movement[1]);
    });

    window.addEventListener('resize', applyMarkerPosition, {passive: true});
  }

  function renderOutputMetrics() {
    const profile = state.outputProfile || {};
    const decoded = state.browserDecodedVideo;
    if (decoded) {
      q('#output-metrics').textContent =
        'Browser decoded ' + decoded.width + '×' + decoded.height + ' · ' +
        (Number.isFinite(decoded.fps) ? decoded.fps.toFixed(1) + ' preview fps' : 'FPS pending');
    } else if (profile.width && profile.height) {
      q('#output-metrics').textContent =
        'Gateway profile ' + profile.width + '×' + profile.height + ' · unmeasured';
    } else {
      q('#output-metrics').textContent = 'Awaiting first decoded frame';
    }

    const sampleRate = profile.audio_sample_rate_hz || 0;
    q('#audio-detail').textContent = profile.measurement_status === 'measured'
      ? (sampleRate ? 'Measured ' + sampleRate + ' Hz return' : 'Return rate unreported')
      : (sampleRate ? 'Gateway profile ' + sampleRate + ' Hz · unmeasured' : '48 kHz target · measurement pending');
  }

  function showBrowserVideoStatus() {
    const decoded = state.browserDecodedVideo;
    if (!decoded) return;
    const shortEdge = Math.min(decoded.width, decoded.height);
    const longEdge = Math.max(decoded.width, decoded.height);
    const tier = shortEdge >= 1080 && longEdge >= 1920
      ? '1080p'
      : shortEdge >= 720 && longEdge >= 1280
        ? '720p'
        : '';
    const measuredFps = Number.isFinite(decoded.fps);
    const fpsDetail = measuredFps ? ' at ' + decoded.fps.toFixed(1) + ' preview fps' : '';
    const pending = measuredFps
      ? 'Audio and evaluator evidence remain pending.'
      : 'FPS, audio, and evaluator evidence remain pending.';
    if (!tier) {
      showStatus('The browser decoded video below the 720p minimum' + fpsDetail + '. ' + pending, 'error');
    } else if (measuredFps && decoded.fps < 29) {
      showStatus('The browser decoded ' + tier + ' video' + fpsDetail + ', below the 30 fps target. ' + pending, 'error');
    } else if (tier === '720p' && q('#resolution').value === '1080p') {
      showStatus('The browser decoded the 720p fallback' + fpsDetail + '. ' + pending, 'success');
    } else {
      showStatus('The browser decoded ' + tier + ' video' + fpsDetail + '. ' + pending, 'success');
    }
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

  function attachReturnedTrack(event) {
    const track = event.track;
    const stream = new MediaStream([track]);
    if (track.kind === 'video') {
      const video = q('#remote-video');
      const observedPeer = state.peer;
      video.srcObject = stream;
      q('.output-card').classList.add('active');
      requestAnimationFrame(applyMarkerPosition);
      video.addEventListener('loadeddata', () => {
        let windowStartMs = null;
        let windowFrameCount = null;
        let lastFrameMs = null;
        const active = () => state.peer === observedPeer && video.srcObject === stream;
        const recordFrame = (now, metadata = {}) => {
          if (!active()) return;
          const width = video.videoWidth;
          const height = video.videoHeight;
          if (width && height) {
            const previous = state.browserDecodedVideo;
            const resolutionChanged = !previous || previous.width !== width || previous.height !== height;
            const presentedFrames = Number.isFinite(metadata.presentedFrames)
              ? metadata.presentedFrames : null;
            let fps = resolutionChanged ? null : previous.fps;
            if (Number.isFinite(now)) lastFrameMs = now;
            if (resolutionChanged) {
              windowStartMs = null;
              windowFrameCount = null;
            }
            if (fps === 0 && windowStartMs === null) fps = null;
            if (Number.isFinite(now) && presentedFrames !== null) {
              if (windowStartMs === null || windowFrameCount === null || presentedFrames < windowFrameCount) {
                windowStartMs = now;
                windowFrameCount = presentedFrames;
              } else if (now - windowStartMs >= 2000) {
                fps = Math.max(0, (presentedFrames - windowFrameCount) * 1000 / (now - windowStartMs));
                windowStartMs = now;
                windowFrameCount = presentedFrames;
              }
            }
            if (resolutionChanged || fps !== previous.fps) {
              state.browserDecodedVideo = {width, height, fps};
              renderOutputMetrics();
              showBrowserVideoStatus();
            }
          }
          if (typeof video.requestVideoFrameCallback === 'function') {
            video.requestVideoFrameCallback(recordFrame);
          }
        };
        if (typeof video.requestVideoFrameCallback === 'function') {
          const checkStall = () => {
            if (!active()) return;
            if (lastFrameMs !== null && performance.now() - lastFrameMs >= 3000 &&
                state.browserDecodedVideo && state.browserDecodedVideo.fps !== 0) {
              state.browserDecodedVideo = {...state.browserDecodedVideo, fps: 0};
              windowStartMs = null;
              windowFrameCount = null;
              renderOutputMetrics();
              showBrowserVideoStatus();
            }
            setTimeout(checkStall, 1000);
          };
          video.requestVideoFrameCallback(recordFrame);
          setTimeout(checkStall, 1000);
        } else {
          recordFrame();
        }
      }, {once: true});
    } else if (track.kind === 'audio') {
      q('#remote-audio').srcObject = stream;
      q('#remote-audio').play().catch(() => {});
    }
  }

  async function startLive(event) {
    event.preventDefault();
    if (!state.gatewayConfigured) {
      showStatus('The GPU session gateway is not configured on this Seldrune deployment yet.', 'error');
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

    state.browserDecodedVideo = null;
    state.outputProfile = null;
    q('#connect-button').disabled = true;
    q('#preview-button').disabled = true;
    q('#synthetic-indicator').disabled = true;
    showStatus('Requesting camera and microphone…');
    setConnection('CONNECTING');
    try {
      const grants = await api('/organizations/' + state.organizationId + '/liveshift/profile-authorizations');
      const activeGrant = (kind, profileId) => grants.some(item =>
        item.user_id === state.userId && item.profile_kind === kind &&
        item.profile_id === profileId && item.status === 'approved'
      );
      if (!activeGrant('face', q('#face-profile').value.trim()) ||
          !activeGrant('voice', q('#voice-profile').value.trim())) {
        throw new Error('Both profiles need a current owner/admin approval. Open Profile authorization to enroll or review them.');
      }
      const stream = await ensureCapture();
      const iceConfiguration = await api(
        '/organizations/' + state.organizationId + '/liveshift/live/ice-servers'
      );
      if (!iceConfiguration || !Array.isArray(iceConfiguration.ice_servers) ||
          !iceConfiguration.ice_servers.length) {
        throw new Error('The LiveShell gateway returned no ICE servers.');
      }
      const peer = new RTCPeerConnection({
        iceServers: iceConfiguration.ice_servers,
      });
      state.peer = peer;
      for (const track of stream.getTracks()) peer.addTrack(track, stream);
      peer.addEventListener('track', attachReturnedTrack);
      peer.addEventListener('connectionstatechange', () => {
        if (state.peer !== peer) return;
        if (peer.connectionState === 'connected') {
          if (state.disconnectTimer) clearTimeout(state.disconnectTimer);
          state.disconnectTimer = null;
          setConnection('CONNECTED');
        } else if (peer.connectionState === 'disconnected') {
          setConnection('DISCONNECTED');
          if (!state.disconnectTimer) {
            state.disconnectTimer = setTimeout(() => {
              state.disconnectTimer = null;
              if (state.peer === peer && peer.connectionState === 'disconnected') {
                showStatus('Connection lost. Local camera and microphone stopped.', 'error');
                stopLive(true);
              }
            }, 15000);
          }
        } else if (peer.connectionState === 'failed') {
          showStatus('LiveShell connection failed. Local media stopped.', 'error');
          stopLive(true);
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
      const outputMeasured = output.measurement_status === 'measured';
      state.outputProfile = output;
      renderOutputMetrics();
      q('#proof-detail').textContent = 'Live session · evidence pending';

      if (state.browserDecodedVideo) {
        showBrowserVideoStatus();
      } else if (outputMeasured) {
        const sampleRate = output.audio_sample_rate_hz || 0;
        const shortEdge = Math.min(output.width || 0, output.height || 0);
        const longEdge = Math.max(output.width || 0, output.height || 0);
        const fullHd = shortEdge >= 1080 && longEdge >= 1920;
        const hdFallback = shortEdge >= 720 && longEdge >= 1280;
        const meetsResolution = q('#resolution').value === '1080p'
          ? (fullHd || hdFallback)
          : hdFallback;
        if (meetsResolution && output.fps >= 29 && sampleRate === 48000) {
          showStatus(
            fullHd || q('#resolution').value === '720p'
              ? 'Connected. Measured HD video and 48 kHz audio passed; evaluator and latency evidence remain pending.'
              : 'Connected at the measured 720p fallback. Evaluator and latency evidence remain pending.',
            'success',
          );
        } else {
          showStatus('Connected, but measured video or audio output is below the supported profile.', 'error');
        }
      } else {
        showStatus(
          'Connected. Worker session validated; waiting for the first transformed frame. Audio and quality evidence remain pending.',
          'success',
        );
      }
      if (state.peer === peer && peer.connectionState !== 'connected') setConnection('NEGOTIATED');
    } catch (error) {
      showStatus('LiveShell could not start: ' + error.message, 'error');
      await stopLive(true);
    } finally {
      q('#connect-button').disabled = !state.gatewayConfigured;
      q('#preview-button').disabled = Boolean(state.peer);
    }
  }

  async function stopLive(closeRemote = true, reportStopped = false) {
    if (state.disconnectTimer) clearTimeout(state.disconnectTimer);
    state.disconnectTimer = null;
    const sessionId = state.sessionId;
    state.sessionId = '';
    state.browserDecodedVideo = null;
    state.outputProfile = null;
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
    q('#output-metrics').textContent = 'HD pending';
    q('#proof-detail').textContent = 'Not verified';
    q('#audio-detail').textContent = '48 kHz target';
    q('#stop-button').disabled = true;
    q('#switch-camera').disabled = true;
    q('#synthetic-indicator').disabled = false;
    q('#preview-button').disabled = false;
    setConnection('OFFLINE');
    if (reportStopped) showStatus('Local media stopped.', 'success');
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
      showStatus('Sign in through the Seldrune console, then open LiveShell in the same tab.', 'error');
      q('#gateway-state').textContent = 'Sign-in required';
      q('#gateway-state').classList.add('error');
      q('#preview-button').disabled = true;
      return;
    }
    try {
      const me = await api('/auth/me');
      const membership = me.memberships.find(item => item.role === 'owner') || me.memberships[0];
      if (!membership) throw new Error('No Seldrune organization is available for this account.');
      state.organizationId = membership.organization.id;
      state.userId = me.user.id;
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
      q('#gateway-state').textContent = 'Seldrune sign-in or readiness check failed';
      q('#gateway-state').classList.add('error');
      showStatus(error.message, 'error');
      q('#preview-button').disabled = true;
    }
  }

  q('#session-form').addEventListener('submit', startLive);
  q('#preview-button').addEventListener('click', preview);
  q('#stop-button').addEventListener('click', () => stopLive(true, true));
  q('#switch-camera').addEventListener('click', switchCamera);
  installMarkerPositionControl();
  window.addEventListener('pagehide', () => {
    if (state.disconnectTimer) clearTimeout(state.disconnectTimer);
    if (state.peer) state.peer.close();
    if (state.localStream) state.localStream.getTracks().forEach(track => track.stop());
  });
  initialize();
})();

