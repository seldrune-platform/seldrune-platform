(() => {
  const form = document.querySelector('#face-test-form');
  if (!form) return;

  const status = document.querySelector('#face-test-status');
  const output = document.querySelector('#face-test-output');
  const MAX_DATA_URI_BYTES = 256 * 1024;

  function asDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(new Error('Could not read image.'));
      reader.onload = () => resolve(reader.result);
      reader.readAsDataURL(file);
    });
  }

  function predictionOutput(prediction) {
    const value = prediction?.output;
    if (typeof value === 'string') return value;
    if (Array.isArray(value) && typeof value[0] === 'string') return value[0];
    return null;
  }

  form.addEventListener('submit', async event => {
    event.preventDefault();
    output.replaceChildren();
    const source = document.querySelector('#face-source-file').files[0];
    const target = document.querySelector('#face-target-file').files[0];
    const consent = document.querySelector('#face-consent').checked;
    if (!source || !target || !consent) {
      status.textContent = 'Choose both images and confirm authorization.';
      return;
    }
    if (source.size > MAX_DATA_URI_BYTES || target.size > MAX_DATA_URI_BYTES) {
      status.textContent = 'For this proof test, each image must be 256 KB or smaller.';
      return;
    }

    status.textContent = 'Submitting authorized transformation…';
    try {
      const [sourceFace, targetImage] = await Promise.all([asDataUrl(source), asDataUrl(target)]);
      const result = await api('/liveshift/face/external', {
        method: 'POST',
        body: JSON.stringify({
          target_image: targetImage,
          source_face: sourceFace,
          consent_confirmed: true,
        }),
      });
      const prediction = result.prediction || {};
      const url = predictionOutput(prediction);
      status.textContent = url
        ? 'Transformation succeeded. Output returned by external provider.'
        : `Provider returned status: ${prediction.status || 'unknown'}`;
      if (url) {
        const image = document.createElement('img');
        image.src = url;
        image.alt = 'Authorized external face transformation result';
        image.loading = 'lazy';
        image.style.maxWidth = '100%';
        image.style.borderRadius = '16px';
        output.append(image);
      }
    } catch (error) {
      status.textContent = `Face test failed: ${error.message}`;
    }
  });
})();
