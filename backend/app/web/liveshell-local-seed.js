(() => {
  const $ = selector => document.querySelector(selector);
  const startButton = $('#local-seed-start');
  if (!startButton) return;

  const FHD = { width: 1920, height: 1080, fps: 30, sampleRate: 48000 };
  const MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task';
  const VISION_WASM_URL = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1/wasm';
  const PRESETS = {
    aurora: { hue: 184, warmth: 0.18, ring: 1.0 },
    ember: { hue: 22, warmth: 0.34, ring: 0.86 },
    violet: { hue: 274, warmth: 0.24, ring: 1.12 },
  };
  const state = {
    running: false,
    stream: null,
    canvasStream: null,
    audioContext: null,
    audioNode: null,
    worker: null,
    raf: 0,
    inferenceBusy: false,
    lastInferenceAt: 0,
    landmarks: null,
    seed: null,
    readyResolve: null,
    readyReject: null,
    frameWindowStart: 0,
    frameWindowCount: 0,
    lastVideoTimestamp: -1,
    lastDrawAt: 0,
    faceCount: 0,
  };
  const camera = $('#local-seed-input');
  const canvas = $('#local-seed-canvas');
  const view = $('#local-seed-output');
  const audioView = $('#local-seed-audio-output');
  const ctx = canvas.getContext('2d', { alpha: false, desynchronized: true });
  const status = $('#local-seed-status');

  function setStatus(message, kind) {
    status.textContent = message;
    status.className = 'local-seed-status' + (kind ? ' ' + kind : '');
  }

  function makeSeed() {
    const presetName = $('#local-seed-style').value;
    const preset = PRESETS[presetName] || PRESETS.aurora;
    const warmth = Number($('#local-seed-warmth').value);
    state.seed = {
      v: 1,
      style: presetName,
      hue: preset.hue,
      ring: preset.ring,
      warmth: Math.max(0, Math.min(1, warmth)),
    };
    const json = JSON.stringify(state.seed);
    $('#local-seed-seed').textContent = json;
    $('#local-seed-seed-size').textContent = new TextEncoder().encode(json).length + ' bytes';
    if (state.audioNode && state.audioContext) {
      const parameter = state.audioNode.parameters.get('warmth');
      parameter.setTargetAtTime(state.seed.warmth, state.audioContext.currentTime, 0.04);
    }
    return state.seed;
  }

  function waitForMetadata(video) {
    if (video.readyState >= HTMLMediaElement.HAVE_METADATA) return Promise.resolve();
    return new Promise((resolve, reject) => {
      const failed = () => reject(new Error('The camera did not provide a video track.'));
      video.addEventListener('loadedmetadata', resolve, { once: true });
      video.addEventListener('error', failed, { once: true });
    });
  }

  function waitForWorkerReady(worker) {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('The local face model did not finish loading. Check the connection and try again.')), 30000);
      state.readyResolve = () => {
        clearTimeout(timer);
        state.readyResolve = null;
        state.readyReject = null;
        resolve();
      };
      state.readyReject = error => {
        clearTimeout(timer);
        state.readyResolve = null;
        state.readyReject = null;
        reject(error);
      };
      worker.postMessage({ type: 'init', modelUrl: MODEL_URL, wasmRoot: VISION_WASM_URL });
    });
  }

  function onWorkerMessage(event) {
    const message = event.data || {};
    if (message.type === 'ready') {
      $('#local-seed-model-metrics').textContent = 'Face landmarks ready · CPU';
      if (state.readyResolve) state.readyResolve();
      return;
    }
    if (message.type === 'landmarks') {
      state.landmarks = message.points || null;
      state.faceCount = state.landmarks ? 1 : 0;
      state.inferenceBusy = false;
      $('#local-seed-face-metrics').textContent = state.faceCount ? '1 face · local landmarks' : 'No face detected';
      return;
    }
    if (message.type === 'error') {
      const error = new Error(message.message || 'The local face model failed.');
      $('#local-seed-model-metrics').textContent = 'Face model unavailable';
      if (state.readyReject) {
        state.readyReject(error);
      } else {
        setStatus(error.message, 'error');
        void stop(false);
      }
    }
  }

  async function createFaceWorker() {
    const worker = new Worker('/console-assets/liveshell-face-worker.js', { type: 'module' });
    state.worker = worker;
    worker.addEventListener('message', onWorkerMessage);
    worker.addEventListener('error', event => {
      const error = new Error(event.message || 'The CPU face worker stopped unexpectedly.');
      if (state.readyReject) state.readyReject(error);
      else {
        setStatus(error.message, 'error');
        void stop(false);
      }
    });
    await waitForWorkerReady(worker);
  }

  function drawCameraFrame() {
    const sourceW = camera.videoWidth || canvas.width;
    const sourceH = camera.videoHeight || canvas.height;
    if (!sourceW || !sourceH) return;

    ctx.save();
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const scale = Math.max(canvas.width / sourceW, canvas.height / sourceH);
    const drawW = sourceW * scale;
    const drawH = sourceH * scale;
    const dx = (canvas.width - drawW) / 2;
    const dy = (canvas.height - drawH) / 2;
    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(camera, dx, dy, drawW, drawH);
    ctx.restore();

    const seed = state.seed;
    if (!seed) return;
    const points = state.landmarks;
    if (points && points.forehead && points.chin && points.left && points.right) {
      const mirrorX = point => ({ x: (1 - point.x) * canvas.width, y: point.y * canvas.height });
      const forehead = mirrorX(points.forehead);
      const chin = mirrorX(points.chin);
      const left = mirrorX(points.left);
      const right = mirrorX(points.right);
      const eyeL = points.eyeL && mirrorX(points.eyeL);
      const eyeR = points.eyeR && mirrorX(points.eyeR);
      const centerX = (left.x + right.x) / 2;
      const centerY = (forehead.y + chin.y) / 2;
      const radiusX = Math.max(12, Math.abs(right.x - left.x) * 0.62 * seed.ring);
      const radiusY = Math.max(16, Math.abs(chin.y - forehead.y) * 0.61 * seed.ring);

      ctx.save();
      ctx.globalCompositeOperation = 'screen';
      const aura = ctx.createRadialGradient(centerX, centerY, radiusX * 0.15, centerX, centerY, radiusX * 1.45);
      aura.addColorStop(0, 'hsla(' + seed.hue + ', 100%, 66%, 0.16)');
      aura.addColorStop(0.72, 'hsla(' + seed.hue + ', 100%, 64%, 0.055)');
      aura.addColorStop(1, 'hsla(' + seed.hue + ', 100%, 60%, 0)');
      ctx.fillStyle = aura;
      ctx.beginPath();
      ctx.ellipse(centerX, centerY, radiusX * 1.45, radiusY * 1.28, 0, 0, Math.PI * 2);
      ctx.fill();

      ctx.shadowColor = 'hsla(' + seed.hue + ', 100%, 68%, 0.82)';
      ctx.shadowBlur = Math.max(8, canvas.width * 0.016);
      ctx.strokeStyle = 'hsla(' + seed.hue + ', 96%, 76%, 0.82)';
      ctx.lineWidth = Math.max(2, canvas.width * 0.0021);
      ctx.beginPath();
      ctx.ellipse(centerX, centerY, radiusX, radiusY, 0, 0.12, Math.PI * 1.89);
      ctx.stroke();

      ctx.shadowBlur = 0;
      ctx.globalAlpha = 0.82;
      ctx.lineWidth = Math.max(1, canvas.width * 0.00115);
      ctx.setLineDash([canvas.width * 0.007, canvas.width * 0.006]);
      ctx.strokeStyle = 'hsla(' + seed.hue + ', 95%, 82%, 0.75)';
      ctx.beginPath();
      ctx.ellipse(centerX, centerY, radiusX * 1.16, radiusY * 1.12, 0, Math.PI * 0.08, Math.PI * 1.77);
      ctx.stroke();
      ctx.setLineDash([]);
      [eyeL, eyeR].forEach((eye, index) => {
        if (!eye) return;
        ctx.fillStyle = index ? 'rgba(255,255,255,0.9)' : 'hsla(' + seed.hue + ',100%,84%,0.95)';
        ctx.beginPath();
        ctx.arc(eye.x, eye.y, Math.max(2, canvas.width * 0.003), 0, Math.PI * 2);
        ctx.fill();
      });
      ctx.restore();
    }

    ctx.save();
    ctx.globalCompositeOperation = 'soft-light';
    ctx.fillStyle = 'hsla(' + seed.hue + ', 75%, 52%, 0.07)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.restore();
  }

  function trackFace() {
    if (!state.running) return;
    const now = performance.now();
    if (!state.inferenceBusy && state.worker && camera.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA &&
        now - state.lastInferenceAt >= 66 && camera.currentTime !== state.lastVideoTimestamp) {
      state.inferenceBusy = true;
      state.lastInferenceAt = now;
      state.lastVideoTimestamp = camera.currentTime;
      createImageBitmap(camera).then(bitmap => {
        if (!state.running || !state.worker) {
          bitmap.close();
          state.inferenceBusy = false;
          return;
        }
        state.worker.postMessage({ type: 'frame', bitmap, timestamp: Math.max(0, Math.round(now)) }, [bitmap]);
      }).catch(() => { state.inferenceBusy = false; });
    }
  }

  function updateDecodedFps(now) {
    if (!state.running) return;
    if (!state.frameWindowStart) {
      state.frameWindowStart = now;
      state.frameWindowCount = 0;
    } else {
      state.frameWindowCount += 1;
    }
    if (now - state.frameWindowStart >= 2000) {
      const fps = state.frameWindowCount * 1000 / (now - state.frameWindowStart);
      $('#local-seed-video-metrics').textContent = canvas.width + '×' + canvas.height + ' · ' + fps.toFixed(1) + ' decoded fps';
      if (fps < 29) {
        setStatus('The local effect is running, but the measured preview is below 30 fps on this device.', 'error');
      } else {
        setStatus('Local CPU effect running · ' + fps.toFixed(1) + ' preview fps. This is a preview, not a verified call.', 'success');
      }
      state.frameWindowStart = now;
      state.frameWindowCount = 0;
    }
    if (typeof view.requestVideoFrameCallback === 'function') {
      view.requestVideoFrameCallback(updateDecodedFps);
    }
  }

  function renderLoop() {
    if (!state.running) return;
    const now = performance.now();
    if (now - state.lastDrawAt >= 1000 / FHD.fps) {
      state.lastDrawAt = now;
      drawCameraFrame();
      trackFace();
    }
    state.raf = requestAnimationFrame(renderLoop);
  }

  async function setupAudio() {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass || typeof AudioWorkletNode === 'undefined') throw new Error('This browser does not support local AudioWorklet processing.');
    const audioContext = new AudioContextClass({ sampleRate: FHD.sampleRate, latencyHint: 'interactive' });
    state.audioContext = audioContext;
    if (audioContext.sampleRate !== FHD.sampleRate) {
      throw new Error('This browser opened audio at ' + audioContext.sampleRate + ' Hz, not the 48 kHz target.');
    }
    await audioContext.audioWorklet.addModule('/console-assets/liveshell-voice-worklet.js');
    const source = audioContext.createMediaStreamSource(state.stream);
    const processor = new AudioWorkletNode(audioContext, 'seldrune-seed-warmth', {
      numberOfInputs: 1,
      numberOfOutputs: 1,
      outputChannelCount: [1],
    });
    state.audioNode = processor;
    source.connect(processor);
    const destination = audioContext.createMediaStreamDestination();
    processor.connect(destination);
    await audioContext.resume();
    audioView.srcObject = destination.stream;
    audioView.muted = !$('#local-seed-hear').checked;
    await audioView.play().catch(() => {});
    const inputRate = state.stream.getAudioTracks()[0]?.getSettings().sampleRate;
    $('#local-seed-audio-metrics').textContent = 'Worklet 48,000 Hz · mic ' + (inputRate ? inputRate.toLocaleString() + ' Hz' : 'rate unreported');
  }

  async function start() {
    if (!$('#local-seed-consent').checked) {
      setStatus('Confirm local camera and microphone use before starting.', 'error');
      return;
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setStatus('Camera and microphone access require a supported browser on HTTPS.', 'error');
      return;
    }
    startButton.disabled = true;
    $('#local-seed-stop').disabled = true;
    makeSeed();
    setStatus('Requesting camera and microphone permission…');
    try {
      state.stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: FHD.width },
          height: { ideal: FHD.height },
          frameRate: { ideal: FHD.fps, max: FHD.fps },
          facingMode: { ideal: 'user' },
        },
        audio: {
          channelCount: { ideal: 1 },
          sampleRate: { ideal: FHD.sampleRate },
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      camera.srcObject = state.stream;
      await camera.play();
      await waitForMetadata(camera);

      const capture = state.stream.getVideoTracks()[0].getSettings();
      const portrait = (capture.width || camera.videoWidth) < (capture.height || camera.videoHeight);
      canvas.width = portrait ? 1080 : FHD.width;
      canvas.height = portrait ? FHD.height : 1080;
      $('#local-seed-video-metrics').textContent =
        (capture.width && capture.height ? capture.width + '×' + capture.height : 'Camera resolution unreported') + ' input · 30 fps requested';
      await setupAudio();
      setStatus('Loading the pinned face model for local CPU inference…');
      await createFaceWorker();

      state.canvasStream = canvas.captureStream(FHD.fps);
      view.srcObject = state.canvasStream;
      await view.play();
      state.running = true;
      state.frameWindowStart = 0;
      state.frameWindowCount = 0;
      state.lastVideoTimestamp = -1;
      state.lastDrawAt = 0;
      $('#local-seed-stop').disabled = false;
      $('#local-seed-model-metrics').textContent = 'Face landmarks ready · CPU';
      $('#local-seed-output-badge').hidden = false;
      setStatus('Local CPU effect running. Raw camera and microphone stay in this browser; model files load from the listed providers.', 'success');
      if (typeof view.requestVideoFrameCallback === 'function') view.requestVideoFrameCallback(updateDecodedFps);
      renderLoop();
    } catch (error) {
      setStatus(error.message || 'The local preview could not start.', 'error');
      await stop(false);
    } finally {
      startButton.disabled = state.running;
    }
  }

  async function stop(showMessage) {
    state.running = false;
    if (state.raf) cancelAnimationFrame(state.raf);
    state.raf = 0;
    if (state.worker) {
      state.worker.postMessage({ type: 'close' });
      state.worker.terminate();
      state.worker = null;
    }
    state.inferenceBusy = false;
    state.landmarks = null;
    state.faceCount = 0;
    state.frameWindowStart = 0;
    state.frameWindowCount = 0;
    state.lastInferenceAt = 0;
    state.lastVideoTimestamp = -1;
    state.lastDrawAt = 0;
    if (state.canvasStream) {
      state.canvasStream.getTracks().forEach(track => track.stop());
      state.canvasStream = null;
    }
    if (state.stream) {
      state.stream.getTracks().forEach(track => track.stop());
      state.stream = null;
    }
    if (state.audioContext && state.audioContext.state !== 'closed') {
      await state.audioContext.close().catch(() => {});
    }
    state.audioContext = null;
    state.audioNode = null;
    camera.pause();
    camera.srcObject = null;
    view.pause();
    view.srcObject = null;
    audioView.pause();
    audioView.srcObject = null;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    $('#local-seed-output-badge').hidden = true;
    $('#local-seed-stop').disabled = true;
    $('#local-seed-video-metrics').textContent = 'Not running';
    $('#local-seed-audio-metrics').textContent = '48 kHz target · not running';
    $('#local-seed-face-metrics').textContent = 'Waiting for camera';
    $('#local-seed-model-metrics').textContent = 'Not loaded';
    if (showMessage) setStatus('Local camera, microphone, and processing stopped.', 'success');
  }

  $('#local-seed-style').addEventListener('change', makeSeed);
  $('#local-seed-warmth').addEventListener('input', makeSeed);
  $('#local-seed-hear').addEventListener('change', () => {
    audioView.muted = !$('#local-seed-hear').checked;
    if ($('#local-seed-hear').checked) audioView.play().catch(() => {});
  });
  startButton.addEventListener('click', () => void start());
  $('#local-seed-stop').addEventListener('click', () => void stop(true));
  window.addEventListener('pagehide', () => { void stop(false); });
  makeSeed();
})();
