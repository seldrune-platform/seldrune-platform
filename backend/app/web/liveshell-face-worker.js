import { FilesetResolver, FaceLandmarker } from 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1/vision_bundle.mjs';

let landmarker = null;
let busy = false;
let lastTimestamp = -1;
const indices = {
  forehead: 10,
  chin: 152,
  left: 234,
  right: 454,
  eyeL: 33,
  eyeR: 263,
};

self.onmessage = async event => {
  const message = event.data || {};
  if (message.type === 'init') {
    try {
      const vision = await FilesetResolver.forVisionTasks(message.wasmRoot);
      landmarker = await FaceLandmarker.createFromOptions(vision, {
        baseOptions: {
          modelAssetPath: message.modelUrl,
          delegate: 'CPU',
        },
        runningMode: 'VIDEO',
        numFaces: 1,
        outputFaceBlendshapes: false,
      });
      self.postMessage({ type: 'ready' });
    } catch (error) {
      self.postMessage({ type: 'error', message: 'CPU face model could not initialize: ' + (error && error.message ? error.message : error) });
    }
    return;
  }
  if (message.type === 'close') {
    if (landmarker) landmarker.close();
    landmarker = null;
    return;
  }
  if (message.type !== 'frame' || !landmarker || busy) {
    if (message.bitmap && message.bitmap.close) message.bitmap.close();
    return;
  }

  busy = true;
  const bitmap = message.bitmap;
  try {
    const timestamp = Math.max(lastTimestamp + 1, Number(message.timestamp) || 0);
    lastTimestamp = timestamp;
    const result = landmarker.detectForVideo(bitmap, timestamp);
    const face = result.faceLandmarks && result.faceLandmarks[0];
    let points = null;
    if (face) {
      points = {};
      Object.keys(indices).forEach(key => {
        const point = face[indices[key]];
        if (point) points[key] = { x: point.x, y: point.y };
      });
    }
    self.postMessage({ type: 'landmarks', points });
  } catch (error) {
    self.postMessage({ type: 'error', message: 'CPU face tracking failed: ' + (error && error.message ? error.message : error) });
  } finally {
    if (bitmap && bitmap.close) bitmap.close();
    busy = false;
  }
};
