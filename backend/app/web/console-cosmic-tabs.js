(() => {
function initCosmicConsole() {
  const consoleView = document.querySelector('#console-view');
  const main = consoleView?.querySelector('main');
  if (!consoleView || !main || document.querySelector('.cosmic-command-bar')) return;

  document.body.classList.add('cosmic-console');

  const tabs = [
    ['nexus', 'Nexus', '✣'],
    ['ai-core', 'AI Core', '◎'],
    ['missions', 'Missions', '⌘'],
    ['worlds', 'Worlds', '◉'],
    ['intel', 'Intel', '⬡'],
    ['creations', 'Creations', '♧'],
    ['system', 'System', '⚙'],
    ['gpt', 'GPT', '✦'],
  ];

  const bar = document.createElement('header');
  bar.className = 'cosmic-command-bar';
  bar.innerHTML = `
    <div class="cosmic-brand">
      <div class="cosmic-brand-mark"><span>⌁</span></div>
      <div><strong>SELDRUNE</strong><small>HUMANITY × AI × BEYOND</small></div>
    </div>
    <nav class="cosmic-tabs" role="tablist" aria-label="Seldrune workspaces"></nav>
    <div class="cosmic-runtime-pill"><strong>● ONLINE</strong><small id="cosmic-runtime-model">Seldrune STI</small></div>`;
  main.prepend(bar);

  const tabList = bar.querySelector('.cosmic-tabs');
  const panels = new Map();
  const root = document.createElement('div');
  root.id = 'cosmic-tabs-root';
  bar.after(root);

  tabs.forEach(([id, label, icon]) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'cosmic-tab';
    button.dataset.cosmicTab = id;
    button.setAttribute('role', 'tab');
    button.setAttribute('aria-controls', `cosmic-panel-${id}`);
    button.innerHTML = `<span class="cosmic-tab-icon">${icon}</span><span class="cosmic-tab-label">${label}</span>`;
    tabList.append(button);

    const panel = document.createElement('section');
    panel.id = `cosmic-panel-${id}`;
    panel.className = 'cosmic-tab-panel';
    panel.dataset.tabPanel = id;
    panel.setAttribute('role', 'tabpanel');
    panel.innerHTML = `<div class="cosmic-page-heading"><div><p>SELDRUNE STI WORKSPACE</p><h1>${label}</h1></div><small></small></div><div class="cosmic-panel-grid"></div>`;
    root.append(panel);
    panels.set(id, panel);
  });

  const descriptions = {
    nexus: 'Live organization state, priority signals, and unified command access.',
    'ai-core': 'Agent intelligence, execution telemetry, and verified machine work.',
    missions: 'Owner objectives, approvals, execution, recovery, and delivery evidence.',
    worlds: 'LiveShift, Seldrune Face, and real-time media expansion.',
    intel: 'Production incidents, governance events, and integrity evidence.',
    creations: 'Authorized creation tools and experimental product surfaces.',
    system: 'Treasury, execution boundaries, and organization controls.',
    gpt: 'A dedicated ChatGPT-style workspace for reasoning and governed execution.',
  };
  panels.forEach((panel, id) => {
    panel.querySelector('.cosmic-page-heading small').textContent = descriptions[id];
  });

  const grid = id => panels.get(id).querySelector('.cosmic-panel-grid');
  const move = (selector, id) => {
    const node = document.querySelector(selector);
    if (node) grid(id).append(node);
  };

  const home = document.createElement('section');
  home.className = 'cosmic-home';
  home.innerHTML = `
    <article class="cosmic-side-card">
      <h2>CONSCIOUSNESS BRIDGE</h2>
      <h3>Human insight</h3><p>Owner intent remains the source of authority.</p>
      <h3>AI intelligence</h3><p>Agents plan, execute, verify, and preserve evidence.</p>
      <h3>Alien perspective</h3><p>Explore unconventional systems without inventing completion.</p>
      <button type="button" data-open-cosmic-tab="gpt">INITIALIZE DIALOGUE</button>
      <h3>LIVE STATUS</h3>
      <ul><li>AI Core <span>Online</span></li><li>Systems <span>Nominal</span></li><li>Security <span>Shielded</span></li><li>Evidence <span>Durable</span></li></ul>
    </article>
    <article class="cosmic-orb-stage">
      <div class="cosmic-orb-copy"><strong>SELDRUNE</strong><small>THE NEXT EVOLUTION TOGETHER</small></div>
      <div class="cosmic-orb" aria-hidden="true"></div>
      <div class="cosmic-orb-prompt"><p>WHAT SHALL WE CREATE TODAY?</p><button type="button" data-open-cosmic-tab="gpt">Speak to Seldrune →</button></div>
    </article>
    <article class="cosmic-side-card">
      <h2>SELD RUNE GPT CORE</h2>
      <h3 id="cosmic-model-name">gpt-5.6-sol</h3>
      <p>Reason · Research · Create · Plan · Analyze · Execute · Verify</p>
      <ul><li>Model provider <span>OpenAI</span></li><li>Operator <span>Governed</span></li><li>Memory <span>Durable</span></li><li>Owner controls <span>Active</span></li></ul>
      <button type="button" data-open-cosmic-tab="system">CONFIGURE CORE</button>
      <h3>ACTIVE MISSIONS</h3><p>Open the Missions workspace to inspect live commands and approvals.</p>
      <button type="button" data-open-cosmic-tab="missions">VIEW MISSIONS →</button>
    </article>`;
  panels.get('nexus').querySelector('.cosmic-page-heading').after(home);

  move('#overview', 'nexus');
  move('#sti-runtime', 'ai-core');
  move('.agent-observatory', 'ai-core');
  move('#action-inbox', 'missions');
  move('#command', 'missions');
  move('#commands', 'missions');
  move('#face-v01-mission', 'worlds');
  move('#liveshift-mission', 'worlds');
  move('.incident-center', 'intel');
  move('.audit-center', 'intel');
  move('#face-external-test', 'creations');
  move('.treasury', 'system');
  move('.governance-policy', 'system');
  move('#seldrune-gpt', 'gpt');

  const footer = document.createElement('footer');
  footer.className = 'cosmic-footer';
  footer.innerHTML = '<span>SELD RUNE v2 · INTERGALACTIC BUILD · VERIFIED OPERATIONS</span><span>Theme: Alien · Responsive · Owner controlled</span>';
  root.after(footer);

  function activate(id, updateHash = true) {
    if (!panels.has(id)) id = 'nexus';
    document.querySelectorAll('.cosmic-tab').forEach(button => {
      const active = button.dataset.cosmicTab === id;
      button.setAttribute('aria-selected', String(active));
      button.tabIndex = active ? 0 : -1;
    });
    panels.forEach((panel, panelId) => panel.classList.toggle('active', panelId === id));
    if (updateHash) history.replaceState(null, '', `#${id}`);
    window.scrollTo({top: 0, behavior: 'smooth'});
  }

  tabList.addEventListener('click', event => {
    const button = event.target.closest('[data-cosmic-tab]');
    if (button) activate(button.dataset.cosmicTab);
  });
  tabList.addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
    const buttons = [...tabList.querySelectorAll('.cosmic-tab')];
    const current = buttons.indexOf(document.activeElement);
    const delta = event.key === 'ArrowRight' ? 1 : -1;
    const next = buttons[(current + delta + buttons.length) % buttons.length];
    next.focus();
    activate(next.dataset.cosmicTab);
  });
  document.addEventListener('click', event => {
    const trigger = event.target.closest('[data-open-cosmic-tab]');
    if (trigger) activate(trigger.dataset.openCosmicTab);
  });
  window.addEventListener('hashchange', () => activate(location.hash.slice(1), false));

  const runtimeModel = document.querySelector('#runtime-version')?.textContent;
  if (runtimeModel) document.querySelector('#cosmic-runtime-model').textContent = runtimeModel;
  activate(location.hash.slice(1) || 'nexus', false);
}

// Initialize after deferred scripts parse, and retry when auth reveals the console.
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initCosmicConsole, {once: true});
} else {
  initCosmicConsole();
}
document.addEventListener('seldrune:console-ready', initCosmicConsole);
})();
