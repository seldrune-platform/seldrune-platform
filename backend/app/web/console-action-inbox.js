(()=>{
const API='/api/v1';
const POLL_INTERVAL_MS=30000;
const BACKGROUND_ALERT_INTERVAL_MS=60000;
const ALERT_STORAGE_KEY='seldruneOwnerAttentionAlerts';
const $=selector=>document.querySelector(selector);
let organizationId='';
let loading=false;
let polling=false;
let reloadTimer=null;
let pollTimer=null;
let commandObserver=null;
let attentionEtag='';
let lastAttentionFingerprint='';
let hasLoaded=false;
let surfaceStale=false;

function token(){
  return sessionStorage.seldruneToken||'';
}

function notificationsSupported(){
  return 'Notification' in window;
}

function alertsEnabled(){
  return notificationsSupported()
    &&Notification.permission==='granted'
    &&localStorage.getItem(ALERT_STORAGE_KEY)==='enabled';
}

function setAlertPreference(enabled){
  if(enabled)localStorage.setItem(ALERT_STORAGE_KEY,'enabled');
  else localStorage.removeItem(ALERT_STORAGE_KEY);
  renderAlertControl();
}

function renderAlertControl(){
  const button=$('#attention-alert-toggle');
  const detail=$('#attention-alert-detail');
  if(!button||!detail)return;
  if(!notificationsSupported()){
    button.textContent='Browser alerts unavailable';
    button.disabled=true;
    detail.textContent='This browser does not expose the Notification API.';
    return;
  }
  if(Notification.permission==='denied'){
    localStorage.removeItem(ALERT_STORAGE_KEY);
    button.textContent='Browser alerts blocked';
    button.disabled=true;
    detail.textContent='Enable notifications for this site in browser settings to use owner alerts.';
    return;
  }
  button.disabled=false;
  if(alertsEnabled()){
    button.textContent='Disable browser alerts';
    detail.textContent='Armed · privacy-safe counts-only checks every 60s while this console remains open.';
  }else{
    button.textContent='Enable browser alerts';
    detail.textContent='Off · opt in to background alerts for new owner attention.';
  }
}

async function toggleBrowserAlerts(){
  if(!notificationsSupported())return;
  if(alertsEnabled()){
    setAlertPreference(false);
    if(document.hidden){
      clearPoll();
      setSyncStatus('paused','Paused','Live attention resumes when this tab is visible');
    }
    return;
  }
  let permission=Notification.permission;
  if(permission==='default')permission=await Notification.requestPermission();
  if(permission==='granted'){
    setAlertPreference(true);
    schedulePoll(document.hidden?BACKGROUND_ALERT_INTERVAL_MS:0);
  }else{
    setAlertPreference(false);
  }
  renderAlertControl();
}

async function apiFetch(path,{headers={}}={}){
  const ownerToken=token();
  if(!ownerToken)throw new Error('Owner session required');
  return fetch(`${API}${path}`,{
    headers:{Accept:'application/json',Authorization:`Bearer ${ownerToken}`,...headers},
  });
}

async function request(path){
  const response=await apiFetch(path);
  if(!response.ok){
    const body=await response.json().catch(()=>({}));
    throw new Error(body.detail||`Request failed (${response.status})`);
  }
  return response.json();
}

async function resolveOrganization(){
  const me=await request('/auth/me');
  const membership=(me.memberships||[]).find(item=>item.role==='owner');
  if(!membership)throw new Error('Owner organization not available');
  organizationId=membership.organization.id;
  return organizationId;
}

function setSyncStatus(state,label,detail){
  const root=$('#attention-sync');
  if(!root)return;
  root.className=`attention-sync attention-sync-${state}`;
  const strong=root.querySelector('strong');
  const small=root.querySelector('small');
  if(strong)strong.textContent=label;
  if(small)small.textContent=detail;
}

function lastCheckedLabel(){
  const time=new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
  return `Checked ${time} · 30s conditional polling`;
}

function approvalStatus(command){
  return command.context?.owner_command?.approval_status||'awaiting_approval';
}

function commandBudget(command){
  const delivery=command.context?.project_delivery||{};
  const forecast=delivery.cost_forecast||{};
  const governor=command.context?.portfolio_governor||{};
  const reservation=governor.budget_reservation||null;
  const execution=command.summary?.autonomous_execution||{};
  return{
    forecast:Number(forecast.estimated_execution_cost_usd||0),
    reservation,
    recorded:Number(execution.recorded_cost_usd||0),
    halted:execution.halted_reason==='budget_reservation_exceeded',
  };
}

function appendBudget(container,data){
  if(!data.forecast&&!data.reservation&&!data.recorded)return;
  const strip=document.createElement('div');
  strip.className='budget-strip';
  const reservation=Number(data.reservation?.amount_usd||0);
  const status=data.halted
    ?'Circuit breaker stopped execution'
    :`Reservation: ${data.reservation?.status||'not reserved'}`;
  [
    `Forecast ${data.forecast.toFixed(4)}`,
    `Reserved ${reservation.toFixed(4)}`,
    `Recorded ${data.recorded.toFixed(4)}`,
    status,
  ].forEach((value,index)=>{
    const span=document.createElement('span');
    span.textContent=value;
    if(index===3&&data.halted)span.className='budget-alert';
    strip.append(span);
  });
  container.append(strip);
}

function actionButton(label,action,id){
  const button=document.createElement('button');
  button.type='button';
  button.dataset.action=action;
  button.dataset.id=id;
  if(action==='brief')button.className='ghost';
  button.textContent=label;
  return button;
}

function commandIds(root){
  return [...root.querySelectorAll('.command-card[data-command-id]')]
    .map(card=>card.dataset.commandId);
}

function commandListMatches(root,commands){
  const expected=commands.map(command=>String(command.id));
  const rendered=commandIds(root);
  return expected.length===rendered.length
    &&expected.every((value,index)=>value===rendered[index]);
}

function renderAllCommands(commands){
  const root=$('#command-list');
  if(!root||commandListMatches(root,commands))return;
  root.replaceChildren();
  if(!commands.length){
    const empty=document.createElement('div');
    empty.className='empty';
    empty.textContent='No commands yet. Create your first objective.';
    root.append(empty);
    return;
  }
  commands.forEach(command=>{
    const card=document.createElement('article');
    card.className='command-card';
    card.id=`command-${command.id}`;
    card.dataset.commandId=command.id;

    const content=document.createElement('div');
    const title=document.createElement('h3');
    title.textContent=command.objective;
    const meta=document.createElement('div');
    meta.className='meta';
    const status=document.createElement('span');
    status.className='pill';
    status.textContent=command.status;
    const approval=document.createElement('span');
    const approvalValue=approvalStatus(command);
    approval.className=`pill ${approvalValue==='awaiting_approval'?'pending':''}`;
    approval.textContent=approvalValue.replaceAll('_',' ');
    meta.append(status,approval);
    content.append(title,meta);
    appendBudget(content,commandBudget(command));
    const actions=document.createElement('div');
    actions.className='actions';
    actions.append(actionButton('Decision brief','brief',command.id));
    if(approvalValue==='approved'){
      actions.append(
        actionButton('Execute','execute',command.id),
        actionButton('Revoke approval','revoke',command.id),
      );
    }else{
      actions.append(actionButton('Approve','approve',command.id));
    }
    card.append(content,actions);
    root.append(card);
  });
}

function setCount(id,value){
  const element=$(id);
  if(element)element.textContent=String(value||0);
}

function inboxItem(item){
  const root=document.createElement('article');
  root.className=`action-inbox-item action-inbox-${item.severity||'warning'}`;
  const marker=document.createElement('span');
  marker.className='action-inbox-badge';
  marker.textContent=(item.action?.label||item.severity||'Attention').replace('Open ','');
  const content=document.createElement('div');
  const heading=document.createElement('strong');
  heading.textContent=item.title;
  const description=document.createElement('p');
  description.textContent=item.detail;
  content.append(heading,description);
  const meta=item.meta||(item.occurred_at?new Date(item.occurred_at).toLocaleString():'');
  if(meta){
    const small=document.createElement('small');
    small.textContent=meta;
    content.append(small);
  }
  root.append(marker,content);

  const action=item.action||{};
  if(action.kind==='review_command'&&action.command_id){
    const button=document.createElement('button');
    button.type='button';
    button.dataset.inboxCommand=action.command_id;
    button.textContent=action.label||'Review command';
    root.append(button);
  }else if(action.kind==='navigate'&&action.href){
    const link=document.createElement('a');
    link.href=action.href;
    link.textContent=action.label||'Open';
    root.append(link);
  }
  return root;
}

function renderInbox(attention){
  const root=$('#owner-action-list');
  if(!root)return;
  const summary=attention.summary||{};
  setCount('#action-approvals',summary.approvals);
  setCount('#action-reviews',summary.reviews);
  setCount('#action-critical',summary.critical);
  setCount('#action-warnings',summary.warnings);
  root.replaceChildren();
  (attention.items||[]).forEach(item=>root.append(inboxItem(item)));
  if(!root.childElementCount){
    const clear=document.createElement('div');
    clear.className='action-inbox-clear';
    clear.textContent='No owner decisions or operational alerts currently require attention.';
    root.append(clear);
  }
}

function showInboxError(message){
  const root=$('#owner-action-list');
  if(!root)return;
  root.replaceChildren();
  const error=document.createElement('div');
  error.className='action-inbox-clear';
  error.textContent=`Action inbox unavailable: ${message}`;
  root.append(error);
}

function notifyOwnerAttention(envelope){
  if(!alertsEnabled()||!document.hidden||!envelope.has_attention)return;
  const notification=new Notification(envelope.title||'Seldrune Owner Attention',{
    body:envelope.body||'Owner attention changed.',
    tag:'seldrune-owner-attention',
    renotify:true,
  });
  notification.onclick=()=>{
    window.focus();
    window.location.href=envelope.target||'/console#action-inbox';
    notification.close();
  };
}

async function loadActionSurface(){
  const view=$('#console-view');
  if(loading||!view||view.classList.contains('hidden'))return;
  if(!token())return;
  loading=true;
  try{
    if(!organizationId)await resolveOrganization();
    const [attention,commands]=await Promise.all([
      request(`/organizations/${organizationId}/owner-attention`),
      request(`/organizations/${organizationId}/owner-commands`),
    ]);
    renderInbox(attention);
    renderAllCommands(commands);
    hasLoaded=true;
    surfaceStale=false;
  }catch(error){
    if(!hasLoaded)showInboxError(error.message);
    throw error;
  }finally{
    loading=false;
  }
}

function clearPoll(){
  clearTimeout(pollTimer);
  pollTimer=null;
}

function backgroundWatchActive(){
  return document.hidden&&alertsEnabled();
}

function schedulePoll(delay=null){
  clearPoll();
  const view=$('#console-view');
  if(!view||view.classList.contains('hidden')||!token())return;
  if(document.hidden&&!alertsEnabled())return;
  const interval=delay===null
    ?(document.hidden?BACKGROUND_ALERT_INTERVAL_MS:POLL_INTERVAL_MS)
    :delay;
  pollTimer=setTimeout(()=>pollAttention(),interval);
}

async function pollAttention({force=false}={}){
  const view=$('#console-view');
  if(polling||!view||view.classList.contains('hidden')||!token())return;
  if(document.hidden&&!alertsEnabled())return;
  polling=true;
  if(!document.hidden)setSyncStatus('checking','Checking attention','Using conditional owner snapshot');
  try{
    if(!organizationId)await resolveOrganization();
    const headers={};
    if(attentionEtag&&!force)headers['If-None-Match']=attentionEtag;
    const backgroundAlert=backgroundWatchActive();
    const attentionPath=backgroundAlert
      ?`/organizations/${organizationId}/owner-attention/notification-envelope`
      :`/organizations/${organizationId}/owner-attention/snapshot?limit=1`;
    const response=await apiFetch(attentionPath,{headers});
    if(response.status===304){
      if(!document.hidden)setSyncStatus('live','Live',lastCheckedLabel());
      return;
    }
    if(!response.ok){
      const body=await response.json().catch(()=>({}));
      throw new Error(body.detail||`Attention check failed (${response.status})`);
    }
    attentionEtag=response.headers.get('ETag')||'';
    const attentionCheck=await response.json();
    const previousFingerprint=lastAttentionFingerprint;
    lastAttentionFingerprint=attentionCheck.fingerprint||'';
    const changed=Boolean(
      previousFingerprint
      &&lastAttentionFingerprint
      &&previousFingerprint!==lastAttentionFingerprint,
    );
    if(document.hidden){
      surfaceStale=true;
      if(changed)notifyOwnerAttention(attentionCheck);
    }else{
      await loadActionSurface();
      setSyncStatus('live',changed?'Live · updated':'Live',lastCheckedLabel());
    }
  }catch(error){
    if(!hasLoaded)showInboxError(error.message);
    if(!document.hidden){
      setSyncStatus('error','Sync unavailable','Keeping the last good owner-attention view');
    }
  }finally{
    polling=false;
    schedulePoll();
  }
}

function scheduleReload({force=false}={}){
  clearTimeout(reloadTimer);
  reloadTimer=setTimeout(()=>pollAttention({force}),160);
}

function observeCommandList(){
  const root=$('#command-list');
  if(!root||commandObserver)return;
  commandObserver=new MutationObserver(()=>{
    if(!loading)scheduleReload();
  });
  commandObserver.observe(root,{childList:true});
}

$('#owner-action-list')?.addEventListener('click',event=>{
  const control=event.target.closest('[data-inbox-command]');
  if(!control)return;
  const card=document.getElementById(`command-${control.dataset.inboxCommand}`);
  if(!card)return;
  document.querySelectorAll('.command-card.inbox-focus').forEach(item=>item.classList.remove('inbox-focus'));
  card.classList.add('inbox-focus');
  card.scrollIntoView({behavior:'smooth',block:'center'});
  setTimeout(()=>card.querySelector('button[data-action="brief"]')?.click(),180);
});

$('#attention-alert-toggle')?.addEventListener('click',()=>toggleBrowserAlerts());
$('#refresh')?.addEventListener('click',()=>scheduleReload({force:true}));

document.addEventListener('visibilitychange',()=>{
  renderAlertControl();
  if(document.hidden){
    if(alertsEnabled()){
      setSyncStatus('live','Alerts armed','60s privacy-safe background watch while this console remains open');
      schedulePoll(BACKGROUND_ALERT_INTERVAL_MS);
    }else{
      clearPoll();
      setSyncStatus('paused','Paused','Live attention resumes when this tab is visible');
    }
  }else{
    scheduleReload({force:surfaceStale});
  }
});
window.addEventListener('focus',()=>{
  renderAlertControl();
  if(!document.hidden)scheduleReload({force:surfaceStale});
});

const consoleView=$('#console-view');
if(consoleView){
  new MutationObserver(()=>{
    if(consoleView.classList.contains('hidden')){
      clearPoll();
      organizationId='';
      attentionEtag='';
      lastAttentionFingerprint='';
      hasLoaded=false;
      surfaceStale=false;
      setSyncStatus('paused','Paused','Sign in to resume live owner attention');
    }else{
      renderAlertControl();
      scheduleReload({force:true});
    }
  }).observe(consoleView,{attributes:true,attributeFilter:['class']});
}
renderAlertControl();
observeCommandList();
if(consoleView&&!consoleView.classList.contains('hidden'))scheduleReload({force:true});
})();