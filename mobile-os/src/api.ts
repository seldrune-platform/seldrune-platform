export type Session = { token: string; podId: string; streamUrl: string; streamPort?: number };
export type AvailablePod = { id: string; name: string; desiredStatus: string; isRunning: boolean };
export type LoginResult = Session | { requiresPodSelection: true; pods: AvailablePod[] };
export type PodStatus = {
  podId: string; desiredStatus: string; isRunning: boolean; streamReady: boolean;
  containerHealth: string; streamHealth: string; streamUrl: string; streamPort?: number; uptime: number;
  gpu: { gpuUtilPercent: number | null; memoryUtilPercent: number | null };
};

// A resume acknowledgement can precede the first RUNNING observation. Bound
// that EXITED grace period, and never keep a failed/stopped pod's lease alive.
export function shouldEndSession(state: string, phase: 'booting' | 'desktop', elapsedMs: number): boolean {
  if (state === 'EXITED') return phase === 'desktop' || elapsedMs >= 15_000;
  return !['RUNNING', 'CREATED', 'RESTARTING', 'STARTING', 'PENDING'].includes(state);
}

export function validateApiUrl(value: string | undefined): string {
  if (!value) throw new Error('Set EXPO_PUBLIC_API_URL to your HTTPS orchestrator URL.');
  const parsed = new URL(value);
  if (parsed.protocol !== 'https:' || parsed.username || parsed.password ||
      parsed.search || parsed.hash || (parsed.pathname !== '/' && parsed.pathname !== '')) {
    throw new Error('EXPO_PUBLIC_API_URL must be an HTTPS origin without a path or credentials.');
  }
  return parsed.origin;
}

export function validateStreamUrl(value: string, podId: string, streamPort = 3000): string {
  const expected = `https://${podId}-${streamPort}.proxy.runpod.net`;
  if (!Number.isInteger(streamPort) || streamPort < 1 || streamPort > 65535 ||
      value !== expected || !/^[a-z0-9]{6,64}$/i.test(podId)) {
    throw new Error('The server returned an invalid workstation URL.');
  }
  return value;
}

export function streamMatchesSession(status: Pick<PodStatus, 'streamUrl' | 'streamPort'>, session: Session): boolean {
  try {
    validateStreamUrl(status.streamUrl, session.podId, status.streamPort);
    return (status.streamPort ?? 3000) === (session.streamPort ?? 3000);
  } catch { return false; }
}

export function canNavigate(url: string, streamUrl: string): boolean {
  if (url === 'about:blank') return true;
  try { return new URL(url).origin === new URL(streamUrl).origin && url.startsWith('https://'); }
  catch { return false; }
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) { super(message); this.status = status; }
}

export async function request<T>(base: string, path: string, token?: string,
  body?: unknown, signal?: AbortSignal): Promise<T> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (signal?.aborted) controller.abort();
  signal?.addEventListener('abort', abort, { once: true });
  const timeout = setTimeout(abort, 20_000);
  try {
    const response = await fetch(`${base}${path}`, {
      method: body === undefined ? 'GET' : 'POST', signal: controller.signal,
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    const result = await response.json();
    if (!response.ok) throw new ApiError(result.error || 'Control plane request failed.', response.status);
    return result as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (signal?.aborted) throw error;
    throw new Error('Cannot reach the control plane. Check your connection and try again.');
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener('abort', abort);
  }
}

// Keep this to one stylesheet. CSS also applies to viewer controls that mount
// after page load, without observing every remote desktop DOM mutation.
export const STREAM_CHROME_SCRIPT = `
(function () {
  if (window.__cloudGpuChrome) return true;
  window.__cloudGpuChrome = true;
  var style = document.createElement('style');
  style.id = 'cloudGpuHiddenStreamChrome';
  style.textContent = '#noVNC_control_bar, #noVNC_control_bar_anchor, #controlBar, .selkies-toolbar { display:none !important; }';
  if (document.head) document.head.appendChild(style);
  return true;
})(); true;
`;

// Kasm/noVNC receive mobile keystrokes through their own hidden keyboard input.
// Reveal the viewer toolbar before focusing it so the device can display its IME.
export const OPEN_REMOTE_KEYBOARD_SCRIPT = `
(function () {
  var hiddenChrome = document.getElementById('cloudGpuHiddenStreamChrome');
  if (hiddenChrome) hiddenChrome.remove();
  var attempts = 0;
  function openKeyboard() {
    var button = document.querySelector('#noVNC_keyboard_button, [aria-label*="keyboard" i], [title*="keyboard" i]');
    if (button) button.click();
    var input = document.querySelector('#noVNC_keyboardinput, #noVNC_keyboard_input, textarea');
    if (input) { input.focus(); return; }
    if (button || attempts++ > 20) return;
    setTimeout(openKeyboard, 250);
  }
  openKeyboard();
})(); true;
`;
