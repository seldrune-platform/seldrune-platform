import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ApiError, canNavigate, request, validateApiUrl, validateStreamUrl } from '../src/api.ts';

test('only HTTPS origins can configure the control plane', () => {
  assert.equal(validateApiUrl('https://example.com/'), 'https://example.com');
  for (const url of [undefined, 'http://example.com', 'https://user:pass@example.com',
    'https://example.com/api', 'https://example.com?token=secret']) {
    assert.throws(() => validateApiUrl(url));
  }
});
test('stream URL must match the exact RunPod pod and port', () => {
  const url = 'https://testpod123-3000.proxy.runpod.net';
  assert.equal(validateStreamUrl(url, 'testpod123'), url);
  assert.throws(() => validateStreamUrl('https://evil.example', 'testpod123'));
  assert.equal(canNavigate(url + '/?resize=1', url), true);
  assert.equal(canNavigate('https://evil.example', url), false);
  assert.equal(canNavigate('javascript:alert(1)', url), false);
  assert.equal(canNavigate('file:///etc/passwd', url), false);
  assert.equal(canNavigate('about:blank', url), true);
});
test('API sends bearer credentials only to control plane and propagates session expiry', async t => {
  const original = globalThis.fetch;
  t.after(() => { globalThis.fetch = original; });
  globalThis.fetch = async (url, options) => {
    assert.equal(url, 'https://control.example/api/heartbeat');
    assert.equal(options?.method, 'POST');
    assert.equal((options?.headers as Record<string, string>).Authorization, 'Bearer test-token');
    return Response.json({ error: 'Session expired' }, { status: 401 });
  };
  await assert.rejects(request('https://control.example', '/api/heartbeat', 'test-token', {}),
    error => error instanceof ApiError && error.status === 401);
});
test('API aborts requests when lifecycle is cancelled', async t => {
  const original = globalThis.fetch;
  t.after(() => { globalThis.fetch = original; });
  globalThis.fetch = async (_url, options) => {
    assert.equal(options?.signal?.aborted, true);
    throw new DOMException('Aborted', 'AbortError');
  };
  const controller = new AbortController(); controller.abort();
  await assert.rejects(request('https://control.example', '/api/status', 'token', undefined, controller.signal),
    { name: 'AbortError' });
});
