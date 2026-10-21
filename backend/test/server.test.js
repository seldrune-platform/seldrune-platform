import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { once } from 'node:events';
import { createApp, createLeaseStore, createRunpodClient, readConfig, IDLE_MS } from '../server.js';

const password = 'test-only-password-123';
const config = { username: 'admin', password, jwtSecret: 'test-only-jwt-signing-key-at-least-32-bytes',
  apiKey: 'test-key', podId: 'testpod123', origins: [], trustProxy: false };

async function fixture(t, { health = 200 } = {}) {
  let now = 1_000_000;
  let pod = { id: config.podId, desiredStatus: 'EXITED', runtime: null };
  let resumes = 0;
  let stops = 0;
  let failStop = false;
  let failResume = false;
  let lease = { epoch: 'initial', active: false, lastHeartbeat: now };
  const { app, watchdog } = createApp(config, {
    now: () => now,
    store: { get: () => ({ ...lease }), update: patch => { lease = { ...lease, ...patch }; } },
    client: {
      pod: async () => pod,
      resume: async () => { resumes++; if (failResume) throw new Error('secret provider detail');
        pod = { ...pod, desiredStatus: 'RUNNING' }; return pod; },
      stop: async () => { stops++; if (failStop) throw new Error('secret');
        pod = { ...pod, desiredStatus: 'EXITED', runtime: null }; return pod; },
    },
    fetchImpl: async () => new Response(null, { status: health }),
    log: { error() {}, info() {} },
  });
  const server = app.listen(0, '127.0.0.1');
  await once(server, 'listening');
  t.after(() => new Promise(resolve => { server.close(resolve); server.closeAllConnections(); }));
  const base = `http://127.0.0.1:${server.address().port}`;
  async function call(path, { token, body, headers = {} } = {}) {
    const response = await fetch(base + path, { method: body === undefined ? 'GET' : 'POST',
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(body === undefined ? {} : { 'Content-Type': 'application/json' }), ...headers },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    return { status: response.status, headers: response.headers, data: await response.json() };
  }
  async function login() {
    const response = await call('/api/login', { body: { username: 'admin', password } });
    assert.equal(response.status, 200);
    return response.data;
  }
  return { call, login, watchdog, advance: ms => { now += ms; }, setPod: value => { pod = value; },
    counters: () => ({ resumes, stops }), failStop: value => { failStop = value; },
    failResume: () => { failResume = true; } };
}

test('configuration fails closed without secrets and rejects weak keys', () => {
  assert.throws(() => readConfig({}), /HOST_PASSWORD/);
  assert.throws(() => readConfig({ HOST_PASSWORD: password, JWT_SECRET: 'weak',
    RUNPOD_API_KEY: 'key', RUNPOD_POD_ID: 'testpod123' }), /32 bytes/);
});

test('invalid credentials and anonymous requests never operate a pod', async t => {
  const f = await fixture(t);
  assert.equal((await f.call('/api/login', { body: { username: 'admin', password: 'wrong' } })).status, 401);
  for (const [path, body] of [['/api/status', undefined], ['/api/shutdown', {}], ['/api/heartbeat', {}]]) {
    assert.equal((await f.call(path, { body })).status, 401);
  }
  assert.deepEqual(f.counters(), { resumes: 0, stops: 0 });
});

test('login resumes once, reports truthful telemetry and shutdown revokes JWT', async t => {
  const f = await fixture(t);
  const session = await f.login();
  assert.equal(session.streamUrl, 'https://testpod123-3000.proxy.runpod.net');
  const starting = await f.call('/api/status', { token: session.token });
  assert.equal(starting.data.streamReady, false);
  assert.equal(starting.data.gpu.gpuUtilPercent, null);
  f.setPod({ desiredStatus: 'RUNNING', runtime: { uptimeInSeconds: 50,
    gpus: [{ id: '0', gpuUtilPercent: 42, memoryUtilPercent: 63 }] } });
  const ready = await f.call('/api/status', { token: session.token });
  assert.equal(ready.data.streamReady, true);
  assert.equal(ready.data.gpu.memoryUtilPercent, 63);
  assert.equal(ready.headers.get('cache-control'), 'no-store');
  assert.equal((await f.call('/api/shutdown', { token: session.token, body: {} })).data.stopped, true);
  assert.equal((await f.call('/api/heartbeat', { token: session.token, body: {} })).status, 401);
  assert.deepEqual(f.counters(), { resumes: 1, stops: 1 });
});

test('status polling does not renew idle lease; heartbeat does', async t => {
  const f = await fixture(t);
  const { token } = await f.login();
  f.advance(IDLE_MS - 1);
  await f.call('/api/heartbeat', { token, body: {} });
  f.advance(IDLE_MS - 1);
  await f.watchdog();
  assert.equal(f.counters().stops, 0);
  await f.call('/api/status', { token });
  f.advance(1);
  await f.watchdog();
  assert.equal(f.counters().stops, 1);
  assert.equal((await f.call('/api/status', { token })).status, 401);
});

test('watchdog retries failed stops and reconciles an already-running pod after restart', async t => {
  const f = await fixture(t);
  f.setPod({ desiredStatus: 'RUNNING', runtime: {} });
  f.failStop(true);
  f.advance(IDLE_MS);
  await f.watchdog();
  assert.equal(f.counters().stops, 1);
  f.failStop(false);
  await f.watchdog();
  assert.equal(f.counters().stops, 2);
});

test('failed resume never issues a token or reveals upstream errors', async t => {
  const f = await fixture(t);
  f.failResume();
  const result = await f.call('/api/login', { body: { username: 'admin', password } });
  assert.equal(result.status, 502);
  assert.equal(result.data.token, undefined);
  assert.doesNotMatch(result.data.error, /secret/);
});

test('401 stream health requires separate stream authentication and is not ready', async t => {
  const f = await fixture(t, { health: 401 });
  const { token } = await f.login();
  f.setPod({ desiredStatus: 'RUNNING', runtime: {} });
  const result = await f.call('/api/status', { token });
  assert.equal(result.data.streamReady, false);
  assert.equal(result.data.streamHealth, 'authentication_required');
});

test('proxy errors never masquerade as a ready stream', async t => {
  const f = await fixture(t, { health: 503 });
  const { token } = await f.login();
  f.setPod({ desiredStatus: 'RUNNING', runtime: {} });
  const result = await f.call('/api/status', { token });
  assert.equal(result.data.isRunning, true);
  assert.equal(result.data.streamReady, false);
});

test('failed shutdown reports failure and preserves access to retry', async t => {
  const f = await fixture(t);
  const { token } = await f.login();
  f.failStop(true);
  assert.equal((await f.call('/api/shutdown', { token, body: {} })).status, 502);
  assert.equal((await f.call('/api/heartbeat', { token, body: {} })).status, 200);
  f.failStop(false);
  assert.equal((await f.call('/api/shutdown', { token, body: {} })).status, 200);
});

test('repeat login to running pod avoids resume and supersedes previous session', async t => {
  const f = await fixture(t);
  const first = await f.login();
  const second = await f.login();
  assert.equal(f.counters().resumes, 1);
  assert.equal((await f.call('/api/status', { token: first.token })).status, 401);
  assert.equal((await f.call('/api/status', { token: second.token })).status, 200);
});

test('persisted lease survives restarts without resetting the idle clock', t => {
  const dir = mkdtempSync(join(tmpdir(), 'cloud-gpu-test-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const file = join(dir, 'lease.json');
  createLeaseStore(file, config.podId, () => 100);
  const store = createLeaseStore(file, config.podId, () => 900);
  assert.equal(store.get().lastHeartbeat, 100);
  store.update({ active: true, epoch: 'persisted' });
  assert.equal(createLeaseStore(file, config.podId).get().epoch, 'persisted');
  assert.throws(() => createLeaseStore(file, 'differentpod'), /Invalid persisted lease/);
});

test('GraphQL uses bearer authentication and variables, and rejects GraphQL errors', async () => {
  let captured;
  const client = createRunpodClient(config, async (url, options) => {
    captured = { url, options };
    return Response.json({ data: { pod: { id: config.podId } } });
  });
  await client.pod();
  assert.equal(captured.url, 'https://api.runpod.io/graphql');
  assert.equal(captured.options.headers.Authorization, 'Bearer test-key');
  assert.deepEqual(JSON.parse(captured.options.body).variables, { podId: config.podId });
  const broken = createRunpodClient(config, async () => Response.json({ errors: [{ message: 'sensitive' }] }));
  await assert.rejects(broken.stop(), /RunPod GraphQL failure/);
});

test('login rate limit prevents unlimited credential guessing', async t => {
  const f = await fixture(t);
  for (let i = 0; i < 10; i++) {
    assert.equal((await f.call('/api/login', { body: {} })).status, 401);
  }
  assert.equal((await f.call('/api/login', { body: {} })).status, 429);
});
