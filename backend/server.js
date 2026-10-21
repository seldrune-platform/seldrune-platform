import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import { rateLimit } from 'express-rate-limit';
import jwt from 'jsonwebtoken';
import { scrypt, timingSafeEqual, randomUUID, randomBytes } from 'node:crypto';
import { promisify } from 'node:util';
import { mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const GRAPHQL_URL = 'https://api.runpod.io/graphql';
export const IDLE_MS = 300_000;
export const WATCHDOG_MS = 60_000;
const issuer = 'cloud-gpu-os';
const audience = 'cloud-gpu-mobile';

export function readConfig(env = process.env) {
  for (const key of ['HOST_PASSWORD', 'JWT_SECRET', 'RUNPOD_API_KEY', 'RUNPOD_POD_ID']) {
    if (!env[key]?.trim()) throw new Error(`${key} is required`);
  }
  if (env.HOST_PASSWORD.length < 12) throw new Error('HOST_PASSWORD needs at least 12 characters');
  if (Buffer.byteLength(env.JWT_SECRET) < 32) throw new Error('JWT_SECRET needs at least 32 bytes');
  if (!/^[a-z0-9]{6,64}$/i.test(env.RUNPOD_POD_ID)) throw new Error('Invalid RUNPOD_POD_ID');
  const port = Number(env.PORT || 10000);
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Invalid PORT');
  const streamPort = Number(env.STREAM_PORT || 3000);
  if (!Number.isInteger(streamPort) || streamPort < 1 || streamPort > 65535) {
    throw new Error('Invalid STREAM_PORT');
  }
  const origins = (env.ALLOWED_ORIGINS || '').split(',').map(s => s.trim()).filter(Boolean);
  for (const origin of origins) {
    if (new URL(origin).origin !== origin || !origin.startsWith('https://')) {
      throw new Error('ALLOWED_ORIGINS must contain exact HTTPS origins');
    }
  }
  return {
    username: env.HOST_USERNAME || 'admin', password: env.HOST_PASSWORD,
    jwtSecret: env.JWT_SECRET, apiKey: env.RUNPOD_API_KEY, podId: env.RUNPOD_POD_ID,
    port, streamPort, origins, trustProxy: env.RENDER === 'true' ? 1 : false,
    stateFile: resolve(env.STATE_FILE || '.runtime/lease.json'),
  };
}

const derivePassword = promisify(scrypt);

function equalUsername(a, b) {
  const left = Buffer.from(a);
  const right = Buffer.from(b);
  return left.length === right.length && timingSafeEqual(left, right);
}

export function createRunpodClient(config, fetchImpl = fetch) {
  async function graphql(query, variables) {
    const response = await fetchImpl(GRAPHQL_URL, {
      method: 'POST', redirect: 'error', signal: AbortSignal.timeout(12_000),
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${config.apiKey}` },
      body: JSON.stringify({ query, variables }),
    });
    if (!response.ok) throw new Error('RunPod HTTP failure');
    const result = await response.json();
    // Never forward provider errors: they can include request metadata or secrets.
    if (result.errors?.length || !result.data) throw new Error('RunPod GraphQL failure');
    return result.data;
  }
  return {
    async pod() {
      const data = await graphql(`query Pod($podId: String!) {
        pod(input: {podId: $podId}) { id desiredStatus runtime { uptimeInSeconds gpus {
          id gpuUtilPercent memoryUtilPercent
        } } }
      }`, { podId: config.podId });
      const pod = data.pod;
      if (!pod) throw new Error('Configured pod not found');
      return pod;
    },
    async resume() {
      const data = await graphql(`mutation Resume($podId: String!) {
        podResume(input: {podId: $podId, gpuCount: 1}) { id desiredStatus }
      }`, { podId: config.podId });
      if (data.podResume?.id !== config.podId) throw new Error('Invalid resume response');
      return data.podResume;
    },
    async stop() {
      const data = await graphql(`mutation Stop($podId: String!) {
        podStop(input: {podId: $podId}) { id desiredStatus }
      }`, { podId: config.podId });
      if (data.podStop?.id !== config.podId) throw new Error('Invalid stop response');
      return data.podStop;
    },
  };
}

export function createLeaseStore(path, podId, now = Date.now) {
  let state;
  try {
    state = JSON.parse(readFileSync(path, 'utf8'));
    if (state.podId !== podId || typeof state.epoch !== 'string' ||
        !Number.isFinite(state.lastHeartbeat) || typeof state.active !== 'boolean') {
      throw new Error('Invalid persisted lease; inspect STATE_FILE before starting');
    }
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
    // Reconcile a running dedicated pod even if this process has never handled login.
    state = { podId, epoch: randomUUID(), lastHeartbeat: now(), active: false };
  }
  const store = {
    get: () => ({ ...state }),
    update(patch) {
      const updated = { ...state, ...patch };
      mkdirSync(dirname(path), { recursive: true, mode: 0o700 });
      writeFileSync(`${path}.tmp`, JSON.stringify(updated), { mode: 0o600 });
      renameSync(`${path}.tmp`, path);
      state = updated;
    },
  };
  store.update({});
  return store;
}

export function createApp(config, { client = createRunpodClient(config), now = Date.now,
  store = createLeaseStore(config.stateFile, config.podId, now), fetchImpl = fetch,
  log = console } = {}) {
  const app = express();
  const passwordSalt = randomBytes(16);
  const passwordOptions = { N: 32768, r: 8, p: 1, maxmem: 64 * 1024 * 1024 };
  const expectedPassword = derivePassword(config.password, passwordSalt, 64, passwordOptions);
  const streamPort = config.streamPort ?? 3000;
  const streamUrl = `https://${config.podId}-${streamPort}.proxy.runpod.net`;
  app.disable('x-powered-by');
  app.set('trust proxy', config.trustProxy);
  app.use(helmet());
  app.use(cors({ origin(origin, callback) {
    callback(null, !origin || config.origins.includes(origin));
  }, methods: ['GET', 'POST'], allowedHeaders: ['Authorization', 'Content-Type'] }));
  app.use(express.json({ limit: '4kb', strict: true }));
  app.use('/api', (_req, res, next) => { res.set('Cache-Control', 'no-store'); next(); });
  const limiter = rateLimit({ windowMs: 60_000, limit: 120, standardHeaders: 'draft-8',
    legacyHeaders: false, message: { error: 'Too many requests. Try again shortly.' } });
  app.use('/api', limiter);
  const loginLimiter = rateLimit({ windowMs: 15 * 60_000, limit: 10,
    standardHeaders: 'draft-8', legacyHeaders: false, skipSuccessfulRequests: true,
    message: { error: 'Too many login attempts. Try again later.' } });

  // Serialise lifecycle changes, heartbeat updates and watchdog decisions. A late
  // status response cannot extend the lease or resurrect a shut-down session.
  let queue = Promise.resolve();
  function exclusive(operation) {
    const pending = queue.then(operation);
    queue = pending.catch(() => {});
    return pending;
  }
  function authenticate(req, res, next) {
    const header = req.get('Authorization') || '';
    if (!header.startsWith('Bearer ')) return res.status(401).json({ error: 'Authentication required' });
    try {
      const claims = jwt.verify(header.slice(7), config.jwtSecret, {
        algorithms: ['HS256'], issuer, audience,
      });
      const lease = store.get();
      if (!lease.active || claims.sub !== config.username || claims.epoch !== lease.epoch) {
        throw new Error('Session ended');
      }
      req.session = claims;
      next();
    } catch {
      res.status(401).json({ error: 'Session expired. Sign in again.' });
    }
  }
  function currentSession(req) {
    const lease = store.get();
    if (!lease.active || lease.epoch !== req.session.epoch) {
      const error = new Error('Session ended. Sign in again.');
      error.status = 401;
      throw error;
    }
  }
  app.get('/healthz', (_req, res) => res.json({ ok: true }));
  app.post('/api/login', loginLimiter, async (req, res) => {
    const { username, password } = req.body || {};
    if (typeof username !== 'string' || typeof password !== 'string' ||
        !equalUsername(username, config.username)) {
      return res.status(401).json({ error: 'Invalid host credentials' });
    }
    const candidatePassword = await derivePassword(password, passwordSalt, 64, passwordOptions);
    if (!timingSafeEqual(candidatePassword, await expectedPassword)) {
      return res.status(401).json({ error: 'Invalid host credentials' });
    }
    await exclusive(async () => {
      const pod = await client.pod();
      // Persist intent before resuming: a lost upstream response must not orphan
      // an active GPU outside the watchdog's scope.
      store.update({ lastHeartbeat: now() });
      if (pod.desiredStatus !== 'RUNNING') await client.resume();
      const epoch = randomUUID();
      store.update({ active: true, epoch, lastHeartbeat: now() });
      const token = jwt.sign({ epoch }, config.jwtSecret, {
        algorithm: 'HS256', subject: config.username, issuer, audience, expiresIn: '12h',
      });
      res.json({ token, podId: config.podId, streamUrl, streamPort, expiresIn: 43_200,
        heartbeatIntervalSeconds: 30, idleTimeoutSeconds: IDLE_MS / 1000 });
    });
  });

  let statusPending;
  async function status() {
    const pod = await client.pod();
    const isRunning = pod.desiredStatus === 'RUNNING' && pod.runtime != null;
    let streamReady = false;
    let streamHealth = isRunning ? 'unreachable' : 'waiting';
    if (isRunning) {
      try {
        const response = await fetchImpl(streamUrl, { method: 'HEAD', redirect: 'manual',
          signal: AbortSignal.timeout(3000) });
        streamReady = response.ok;
        streamHealth = response.status === 401 || response.status === 403
          ? 'authentication_required' : streamReady ? 'ready' : 'starting';
        await response.body?.cancel();
      } catch { /* A proxy timeout is not readiness. */ }
    }
    const percent = value => typeof value === 'number' && Number.isFinite(value)
      ? Math.min(100, Math.max(0, value)) : null;
    const gpus = (pod.runtime?.gpus || []).map(gpu => ({ id: gpu.id,
      gpuUtilPercent: percent(gpu.gpuUtilPercent), memoryUtilPercent: percent(gpu.memoryUtilPercent) }));
    return { podId: config.podId, desiredStatus: pod.desiredStatus, isRunning,
      containerHealth: isRunning ? 'running' : 'waiting', streamReady, streamHealth,
      streamUrl, streamPort, uptime: pod.runtime?.uptimeInSeconds ?? 0, gpus,
      gpu: gpus[0] || { gpuUtilPercent: null, memoryUtilPercent: null } };
  }
  app.get('/api/status', authenticate, async (_req, res) => {
    // Coalesce concurrent polls, without caching stale status indefinitely.
    statusPending ??= status().finally(() => { statusPending = undefined; });
    res.json(await statusPending);
  });
  app.post('/api/heartbeat', authenticate, async (req, res) => {
    await exclusive(async () => {
      currentSession(req);
      store.update({ lastHeartbeat: now() });
      res.json({ ok: true, idleTimeoutSeconds: IDLE_MS / 1000 });
    });
  });
  app.post('/api/shutdown', authenticate, async (req, res) => {
    await exclusive(async () => {
      currentSession(req);
      await client.stop();
      store.update({ active: false, epoch: randomUUID() });
      res.json({ stopped: true });
    });
  });
  app.use((_req, res) => res.status(404).json({ error: 'Route not found' }));
  app.use((error, _req, res, _next) => {
    const statusCode = error.type === 'entity.too.large' ? 413
      : error instanceof SyntaxError && 'body' in error ? 400 : error.status || 502;
    if (statusCode === 502) log.error('Control-plane operation failed; upstream or lease storage unavailable');
    if (!res.headersSent) res.status(statusCode).json({ error: statusCode === 401
      ? 'Session ended. Sign in again.' : statusCode === 400 || statusCode === 413
        ? 'Invalid request body' : 'GPU service unavailable. Please retry.' });
  });

  async function watchdog() {
    return exclusive(async () => {
      if (now() - store.get().lastHeartbeat < IDLE_MS) return;
      try {
        const pod = await client.pod();
        if (pod.desiredStatus !== 'EXITED' && pod.desiredStatus !== 'TERMINATED') {
          await client.stop();
          log.info('Idle GPU stop acknowledged');
        }
        store.update({ active: false, epoch: randomUUID() });
      } catch {
        // Keep the expired lease. The next tick retries the stop; no false success.
        log.error('Idle GPU stop failed; retry scheduled in 60 seconds');
      }
    });
  }
  return { app, watchdog };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const config = readConfig();
  const { app, watchdog } = createApp(config);
  const server = app.listen(config.port, '0.0.0.0', () => console.info(`Control plane listening on ${config.port}`));
  const timer = setInterval(() => { void watchdog(); }, WATCHDOG_MS);
  timer.unref();
  server.requestTimeout = 30_000;
  server.headersTimeout = 15_000;
  for (const signal of ['SIGTERM', 'SIGINT']) process.once(signal, () => {
    clearInterval(timer);
    server.close(() => process.exit(0));
    setTimeout(() => process.exit(1), 10_000).unref();
  });
}
