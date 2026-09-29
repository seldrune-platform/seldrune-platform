(() => {
  'use strict';

  const STORAGE_KEY = 'seldrune.media.default.v1';
  const TOKEN_KEY = 'seldruneToken';
  const PROFILE_ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,99}$/;
  const GPU_PROFILES = new Set([
    'rtx-4090',
    'rtx-pro-4500-se',
    'rtx-5090',
    'rtx-pro-6000-blackwell',
  ]);
  const mediaDevices = navigator.mediaDevices;
  const nativeGetUserMedia = mediaDevices && mediaDevices.getUserMedia
    ? mediaDevices.getUserMedia.bind(mediaDevices)
    : null;
  let installed = false;
  let required = true;
  let activeSession = null;
  let pendingSession = null;
  const consumerTracks = new Set();

  function readDefault() {
    try {
      const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
      if (!value || value.enabled !== true) return null;
      return value;
    } catch (_) {
      return null;
    }
  }

  function validateConfig(value) {
    if (!value || typeof value !== 'object') {
      throw new Error('Set up Seldrune Media in the Media Console first.');
    }
    const result = {
      enabled: value.enabled === true,
      organizationId: String(value.organizationId || ''),
      userId: String(value.userId || ''),
      faceProfileId: String(value.faceProfileId || '').trim(),
      voiceProfileId: String(value.voiceProfileId || '').trim(),
      videoResolution: value.videoResolution === '720p' ? '720p' : '1080p',
      targetAcceleratorProfile: String(value.targetAcceleratorProfile || 'rtx-4090'),
      consentConfirmed: value.consentConfirmed === true,
      syntheticMediaIndicatorEnabled: value.syntheticMediaIndicatorEnabled === true,
    };
    if (!result.enabled) throw new Error('Seldrune Media default is turned off.');
    if (!result.organizationId) throw new Error('Seldrune Media has no organization selected.');
    if (!result.userId) throw new Error('Set up Seldrune Media for your signed-in account first.');
    if (!PROFILE_ID.test(result.faceProfileId) || !PROFILE_ID.test(result.voiceProfileId)) {
      throw new Error('Choose valid face and voice profile IDs in the Media Console.');
    }
    if (!GPU_PROFILES.has(result.targetAcceleratorProfile)) {
      result.targetAcceleratorProfile = 'rtx-4090';
    }
    if (!result.consentConfirmed || !result.syntheticMediaIndicatorEnabled) {
      throw new Error('Confirm profile authorization and keep the synthetic-media indicator on.');
    }
    return result;
  }

  function setDefault(value) {
    const config = validateConfig({...value, enabled: true});
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
    return {...config};
  }

  function clearDefault() {
    localStorage.removeItem(STORAGE_KEY);
    return true;
  }

  async function api(path, options) {
    const token = sessionStorage.getItem(TOKEN_KEY) || '';
    if (!token) throw new Error('Sign in to Seldrune in this browser before using Media.');
    const settings = options || {};
    const response = await fetch('/api/v1' + path, {
      ...settings,
      headers: {
        Accept: 'application/json',
        ...(settings.body ? {'Content-Type': 'application/json'} : {}),
        Authorization: 'Bearer ' + token,
        ...(settings.headers || {}),
      },
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || 'Seldrune Media request failed (' + response.status + ').');
    }
    return response.status === 204 ? null : response.json();
  }

  function requestedKinds(constraints) {
    return {
      audio: Boolean(constraints && constraints.audio),
      video: Boolean(constraints && constraints.video),
    };
  }

  function captureConstraints(constraints, config) {
    const requestedVideo = constraints && constraints.video;
    const requestedAudio = constraints && constraints.audio;
    const video = {
      width: {ideal: config.videoResolution === '1080p' ? 1920 : 1280},
      height: {ideal: config.videoResolution === '1080p' ? 1080 : 720},
      frameRate: {ideal: 30, max: 30},
      ...(requestedVideo && typeof requestedVideo === 'object' ? requestedVideo : {}),
    };
    const audio = {
      sampleRate: {ideal: 48000},
      channelCount: {ideal: 1},
      ...(requestedAudio && typeof requestedAudio === 'object' ? requestedAudio : {}),
    };
    return {audio, video};
  }

  function waitForIce(peer, timeoutMs) {
    if (peer.iceGatheringState === 'complete') return Promise.resolve();
    return new Promise((resolve, reject) => {
      let timer = setTimeout(() => {
        cleanup();
        reject(new Error('Timed out gathering WebRTC connection details.'));
      }, timeoutMs);
      const onState = () => {
        if (peer.iceGatheringState === 'complete') {
          cleanup();
          resolve();
        }
      };
      const cleanup = () => {
        clearTimeout(timer);
        timer = null;
        peer.removeEventListener('icegatheringstatechange', onState);
      };
      peer.addEventListener('icegatheringstatechange', onState);
    });
  }

  function waitForOutput(session, kinds, timeoutMs) {
    const hasKinds = () => {
      const available = new Set(session.output.getTracks()
        .filter(track => track.readyState === 'live')
        .map(track => track.kind));
      return (!kinds.video || available.has('video')) && (!kinds.audio || available.has('audio'));
    };
    if (hasKinds()) return Promise.resolve(session.output);
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        cleanup();
        reject(new Error('The GPU returned no transformed camera or microphone track.'));
      }, timeoutMs);
      const cleanup = () => {
        clearTimeout(timer);
        session.peer.removeEventListener('track', onTrack);
        session.peer.removeEventListener('connectionstatechange', onConnection);
      };
      const check = () => {
        if (hasKinds()) {
          cleanup();
          resolve(session.output);
        }
      };
      const onTrack = event => {
        if (!session.output.getTracks().includes(event.track)) session.output.addTrack(event.track);
        check();
      };
      const onConnection = () => {
        if (session.peer.connectionState === 'failed') {
          cleanup();
          reject(new Error('The Seldrune Media WebRTC connection failed.'));
        }
      };
      session.peer.addEventListener('track', onTrack);
      session.peer.addEventListener('connectionstatechange', onConnection);
      check();
    });
  }

  function closeRemote(session) {
    if (!session) return Promise.resolve();
    if (session.closePromise) return session.closePromise;
    session.closePromise = (async () => {
      if (session.peer && session.peer.signalingState !== 'closed') session.peer.close();
      if (session.local) session.local.getTracks().forEach(track => track.stop());
      if (session.output) session.output.getTracks().forEach(track => track.stop());
      if (session.sessionId) {
        const path = '/organizations/' + encodeURIComponent(session.organizationId) +
          '/liveshift/live/sessions/' + encodeURIComponent(session.sessionId);
        await api(path, {method: 'DELETE'}).catch(() => null);
      }
      if (activeSession === session) activeSession = null;
    })();
    return session.closePromise;
  }

  async function openSession(constraints, config) {
    if (!nativeGetUserMedia || typeof RTCPeerConnection === 'undefined' ||
        typeof MediaStream === 'undefined') {
      throw new Error('This browser does not support Seldrune Media WebRTC.');
    }

    const session = {
      organizationId: config.organizationId,
      configKey: JSON.stringify(config),
      local: null,
      output: new MediaStream(),
      peer: null,
      sessionId: '',
      closePromise: null,
    };
    try {
      const me = await api('/auth/me');
      const membership = (me.memberships || []).find(item =>
        item.organization && item.organization.id === config.organizationId
      );
      if (!membership) throw new Error('Your Seldrune account has no access to the selected organization.');
      const userId = me.user && me.user.id;
      if (!userId || userId !== config.userId) {
        clearDefault();
        throw new Error('This Seldrune Media default belongs to another signed-in account. Set it up again.');
      }
      const grants = await api('/organizations/' + encodeURIComponent(config.organizationId) +
        '/liveshift/profile-authorizations');
      const approved = (kind, profileId) => grants.some(item =>
        item.user_id === userId && item.profile_kind === kind &&
        item.profile_id === profileId && item.status === 'approved'
      );
      if (!approved('face', config.faceProfileId) || !approved('voice', config.voiceProfileId)) {
        throw new Error('Both selected profiles need current owner/admin approval.');
      }
      const readiness = await api('/organizations/' + encodeURIComponent(config.organizationId) +
        '/liveshift/live/readiness');
      if (!readiness.gateway_configured) {
        throw new Error('The private Seldrune GPU gateway is not connected yet.');
      }
      const ice = await api('/organizations/' + encodeURIComponent(config.organizationId) +
        '/liveshift/live/ice-servers');
      if (!ice || !Array.isArray(ice.ice_servers) || !ice.ice_servers.length) {
        throw new Error('The Seldrune Media gateway did not provide ICE servers.');
      }
      session.local = await nativeGetUserMedia(captureConstraints(constraints, config));
      session.peer = new RTCPeerConnection({iceServers: ice.ice_servers});
      for (const track of session.local.getTracks()) {
        session.peer.addTrack(track, session.local);
      }
      session.peer.addEventListener('track', event => {
        if (!session.output.getTracks().includes(event.track)) session.output.addTrack(event.track);
      });
      const offer = await session.peer.createOffer();
      await session.peer.setLocalDescription(offer);
      await waitForIce(session.peer, 10000);
      const result = await api('/organizations/' + encodeURIComponent(config.organizationId) +
        '/liveshift/live/sessions', {
          method: 'POST',
          body: JSON.stringify({
            offer: {type: 'offer', sdp: session.peer.localDescription.sdp},
            face_profile_id: config.faceProfileId,
            voice_profile_id: config.voiceProfileId,
            consent_confirmed: true,
            synthetic_media_indicator_enabled: true,
            marker_x: 1,
            marker_y: 0,
            video_resolution: config.videoResolution,
            target_accelerator_profile: config.targetAcceleratorProfile,
          }),
        });
      session.sessionId = result.session_id;
      await session.peer.setRemoteDescription(result.answer);
      await waitForOutput(session, {audio: true, video: true}, 20000);
      session.peer.addEventListener('connectionstatechange', () => {
        if (session.peer.connectionState === 'failed' ||
            session.peer.connectionState === 'closed') closeRemote(session);
      });
      window.dispatchEvent(new CustomEvent('seldrune-media-connected', {
        detail: {
          sessionId: session.sessionId,
          syntheticMediaIndicatorEnabled: true,
          output: result.output || {},
        },
      }));
      return session;
    } catch (error) {
      await closeRemote(session);
      throw error;
    }
  }

  async function ensureSession(constraints) {
    const config = validateConfig(readDefault());
    const kinds = requestedKinds(constraints);
    if (!kinds.audio && !kinds.video) return nativeGetUserMedia(constraints);
    const configKey = JSON.stringify(config);
    if (activeSession && activeSession.peer &&
        activeSession.configKey === configKey &&
        activeSession.peer.connectionState !== 'failed' &&
        activeSession.peer.connectionState !== 'closed') return activeSession;
    if (activeSession) await closeRemote(activeSession);
    if (pendingSession && pendingSession.key === configKey) return pendingSession.promise;
    if (pendingSession) {
      const previous = await pendingSession.promise.catch(() => null);
      if (previous) await closeRemote(previous);
    }
    const promise = openSession(constraints, config);
    pendingSession = {key: configKey, promise};
    try {
      activeSession = await promise;
      return activeSession;
    } finally {
      if (pendingSession && pendingSession.promise === promise) pendingSession = null;
    }
  }

  function cloneTracksForRequest(session, constraints) {
    const kinds = requestedKinds(constraints);
    const selected = session.output.getTracks().filter(track =>
      (track.kind === 'video' && kinds.video) || (track.kind === 'audio' && kinds.audio)
    );
    const requiredKinds = [];
    if (kinds.video) requiredKinds.push('video');
    if (kinds.audio) requiredKinds.push('audio');
    for (const kind of requiredKinds) {
      if (!selected.some(track => track.kind === kind)) {
        throw new Error('The GPU did not return the requested transformed ' + kind + ' track.');
      }
    }
    const output = new MediaStream();
    for (const source of selected) {
      const track = source.clone();
      consumerTracks.add(track);
      const stop = track.stop.bind(track);
      let stopped = false;
      track.stop = () => {
        if (stopped) return;
        stopped = true;
        stop();
        consumerTracks.delete(track);
        if (!consumerTracks.size && activeSession) closeRemote(activeSession);
      };
      track.addEventListener('ended', () => {
        consumerTracks.delete(track);
        if (!consumerTracks.size && activeSession) closeRemote(activeSession);
      }, {once: true});
      output.addTrack(track);
    }
    return output;
  }

  async function getUserMedia(constraints) {
    if (!constraints) return nativeGetUserMedia(constraints);
    const kinds = requestedKinds(constraints);
    if (!kinds.audio && !kinds.video) return nativeGetUserMedia(constraints);
    const value = readDefault();
    if (!value) {
      if (required) throw new Error('Turn on “Use Seldrune Media by default” in the Media Console.');
      return nativeGetUserMedia(constraints);
    }
    const session = await ensureSession(constraints);
    return cloneTracksForRequest(session, constraints);
  }

  function installDefault(options) {
    if (!mediaDevices || !nativeGetUserMedia) {
      throw new Error('This browser does not support camera and microphone capture.');
    }
    const settings = options || {};
    required = settings.required !== false;
    if (!installed) {
      mediaDevices.getUserMedia = getUserMedia;
      installed = true;
      window.addEventListener('pagehide', stop);
    }
    return true;
  }

  async function stop() {
    const session = activeSession;
    consumerTracks.forEach(track => track.stop());
    consumerTracks.clear();
    await closeRemote(session);
  }

  function uninstallDefault() {
    if (installed && mediaDevices && nativeGetUserMedia) {
      mediaDevices.getUserMedia = nativeGetUserMedia;
      window.removeEventListener('pagehide', stop);
      installed = false;
    }
    return stop();
  }

  window.SeldruneMedia = Object.freeze({
    version: '1.0.0',
    getDefault: readDefault,
    setDefault,
    clearDefault,
    installDefault,
    uninstallDefault,
    stop,
  });

  const script = document.currentScript;
  if (script && script.dataset && script.dataset.default === 'true') {
    installDefault({required: true});
  }
})();
