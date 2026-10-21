export type Session = { token: string; podId: string; streamUrl: string };
export type PodStatus = {
  podId: string; desiredStatus: string; isRunning: boolean; streamReady: boolean;
  containerHealth: string; streamHealth: string; streamUrl: string; uptime: number;
  gpu: { gpuUtilPercent: number | null; memoryUtilPercent: number | null };
};

export function validateApiUrl(value: string | undefined): string {
  if (!value) throw new Error('Set EXPO_PUBLIC_API_URL to your HTTPS orchestrator URL.');
  const parsed = new URL(value);
  if (parsed.protocol !== 'https:' || parsed.username || parsed.password ||
      parsed.search || parsed.hash || (parsed.pathname !== '/' && parsed.pathname !== '')) {
    throw new Error('EXPO_PUBLIC_API_URL must be an HTTPS origin without a path or credentials.');
  }
  return parsed.origin;
}

export function validateStreamUrl(value: string, podId: string): string {
  const expected = `https://${podId}-3000.proxy.runpod.net`;
  if (value !== expected || !/^[a-z0-9]{6,64}$/i.test(podId)) {
    throw new Error('The server returned an invalid workstation URL.');
  }
  return value;
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

// Only hide known desktop-stream chrome; never remove login fields or arbitrary
// controls. MutationObserver handles late-loaded Selkies/noVNC toolbars.
export const STREAM_CHROME_SCRIPT = `
(function () {
  if (window.__cloudGpuChrome) return true;
  window.__cloudGpuChrome = true;
  var style = document.createElement('style');
  style.textContent = '#noVNC_control_bar, #noVNC_control_bar_anchor, #controlBar, .selkies-toolbar { display:none !important; }';
  function install() {
    if (document.head && !style.isConnected) document.head.appendChild(style);
  }
  install();
  new MutationObserver(install).observe(document.documentElement, {childList:true, subtree:true});
  return true;
})(); true;
`;
