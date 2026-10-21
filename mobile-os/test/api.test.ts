import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ApiError, canNavigate, request, shouldEndSession, streamMatchesSession, validateApiUrl, validateStreamUrl } from '../src/api.ts';

test('failed resume leaves boot mode after a bounded observation grace period', () => {
  assert.equal(shouldEndSession('EXITED', 'booting', 0), false);
  assert.equal(shouldEndSession('EXITED', 'booting', 14_999), false);
  assert.equal(shouldEndSession('EXITED', 'booting', 15_000), true);
  assert.equal(shouldEndSession('EXITED', 'desktop', 0), true);
});
test('terminal states end boot and desktop sessions', () => {
  for (const state of ['DEAD', 'PAUSED', 'STOPPED', 'TERMINATED', 'UNKNOWN']) {
    assert.equal(shouldEndSession(state, 'booting', 0), true, state);
    assert.equal(shouldEndSession(state, 'desktop', 0), true, state);
  }
});
test('running and genuinely transitional states remain observable', () => {
  for (const state of ['RUNNING', 'CREATED', 'RESTARTING', 'STARTING', 'PENDING']) {
    assert.equal(shouldEndSession(state, 'booting', 20_000), false, state);
    assert.equal(shouldEndSession(state, 'desktop', 20_000), false, state);
  }
});

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

test('configured stream ports preserve exact pod and origin validation', () => {
  const url = 'https://testpod123-6901.proxy.runpod.net';
  assert.equal(validateStreamUrl(url, 'testpod123', 6901), url);
  assert.throws(() => validateStreamUrl(url, 'testpod123'));
  assert.throws(() => validateStreamUrl(url, 'differentpod', 6901));
  for (const port of [0, -1, 65536, 3.5, NaN]) {
    assert.throws(() => validateStreamUrl(`https://testpod123-${port}.proxy.runpod.net`, 'testpod123', port));
  }
});

test('a changed or invalid stream ends a stale session instead of renewing it', () => {
  const session = { token: 'token', podId: 'testpod123', streamUrl: 'https://testpod123-3000.proxy.runpod.net' };
  assert.equal(streamMatchesSession({ streamUrl: session.streamUrl }, session), true);
  assert.equal(streamMatchesSession({ streamUrl: 'https://testpod123-6901.proxy.runpod.net', streamPort: 6901 }, session), false);
  assert.equal(streamMatchesSession({ streamUrl: 'https://evil.example', streamPort: 3000 }, session), false);
  assert.equal(streamMatchesSession({ streamUrl: 'https://otherpod-3000.proxy.runpod.net', streamPort: 3000 }, session), false);
  assert.equal(streamMatchesSession({ streamUrl: 'https://testpod123-6901.proxy.runpod.net', streamPort: 6901 },
    { ...session, streamPort: 6901 }), true);
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
