(() => {
  const shell = document.querySelector('.brief-shell, .monitor-shell, .org-shell');
  const header = shell?.querySelector('header');
  if (!shell || !header) return;

  const strip = document.createElement('section');
  strip.className = 'surface-runtime surface-runtime-checking';
  strip.setAttribute('aria-live', 'polite');

  const indicator = document.createElement('span');
  indicator.className = 'surface-runtime-indicator';

  const summary = document.createElement('div');
  summary.className = 'surface-runtime-summary';
  const title = document.createElement('strong');
  title.textContent = 'Checking runtime';
  const detail = document.createElement('small');
  detail.textContent = 'Seldrune runtime health';
  summary.append(title, detail);

  const facts = document.createElement('div');
  facts.className = 'surface-runtime-facts';

  strip.append(indicator, summary, facts);
  header.insertAdjacentElement('afterend', strip);

  const fact = (label, value) => {
    const item = document.createElement('span');
    const key = document.createElement('small');
    key.textContent = label;
    const strong = document.createElement('strong');
    strong.textContent = value;
    item.append(key, strong);
    return item;
  };

  const render = status => {
    const provider = status.checks?.model_provider || {};
    const database = status.checks?.database || {};
    strip.className = `surface-runtime ${status.ready ? 'surface-runtime-ready' : 'surface-runtime-degraded'}`;
    title.textContent = status.ready ? 'Runtime ready' : 'Runtime degraded';
    detail.textContent = `v${status.version} · ${status.environment}`;
    facts.replaceChildren(
      fact('Provider', provider.provider || 'unknown'),
      fact('Model', provider.model || 'unknown'),
      fact('Database', database.status || 'unknown'),
      fact('AI mode', provider.live_ai ? 'live' : 'fallback'),
    );
  };

  const renderFailure = error => {
    strip.className = 'surface-runtime surface-runtime-degraded';
    title.textContent = 'Runtime check failed';
    detail.textContent = error instanceof Error ? error.message : 'Status unavailable';
    facts.replaceChildren();
  };

  fetch('/api/v1/status', {headers: {'Accept': 'application/json'}})
    .then(response => {
      if (!response.ok) throw new Error(`Status request failed (${response.status})`);
      return response.json();
    })
    .then(render)
    .catch(renderFailure);
})();
