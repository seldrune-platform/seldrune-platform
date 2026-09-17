(()=>{
const API='/api/v1';
const ALERT_STORAGE_KEY='seldruneOwnerAttentionAlerts';
const SUBSCRIPTION_ID_KEY='seldruneOwnerPushSubscriptionId';
let organizationId='';
let reconciling=false;
let reconcileQueued=null;

function token(){
  return sessionStorage.seldruneToken||'';
}

function pushSupported(){
  return 'serviceWorker' in navigator&&'PushManager' in window&&'Notification' in window;
}

function alertsEnabled(){
  return pushSupported()
    &&Notification.permission==='granted'
    &&localStorage.getItem(ALERT_STORAGE_KEY)==='enabled';
}

function applicationServerKey(value){
  const padding='='.repeat((4-value.length%4)%4);
  const base64=(value+padding).replaceAll('-','+').replaceAll('_','/');
  const raw=atob(base64);
  return Uint8Array.from(raw,character=>character.charCodeAt(0));
}

async function api(path,{method='GET',body=null}={}){
  const ownerToken=token();
  if(!ownerToken)throw new Error('Owner session required');
  const response=await fetch(`${API}${path}`,{
    method,
    headers:{
      Accept:'application/json',
      Authorization:`Bearer ${ownerToken}`,
      ...(body?{'Content-Type':'application/json'}:{}),
    },
    body:body?JSON.stringify(body):null,
  });
  return response;
}

async function resolveOrganization(){
  if(organizationId)return organizationId;
  const response=await api('/auth/me');
  if(!response.ok)throw new Error('Owner identity unavailable');
  const me=await response.json();
  const membership=(me.memberships||[]).find(item=>item.role==='owner');
  if(!membership)throw new Error('Owner organization not available');
  organizationId=membership.organization.id;
  return organizationId;
}

async function registerPersistentPush(){
  const org=await resolveOrganization();
  const configResponse=await api(`/organizations/${org}/owner-push/config`);
  if(!configResponse.ok)return;
  const config=await configResponse.json();
  if(!config.enabled||!config.application_server_key)return;

  const registration=await navigator.serviceWorker.ready;
  let subscription=await registration.pushManager.getSubscription();
  if(!subscription){
    subscription=await registration.pushManager.subscribe({
      userVisibleOnly:true,
      applicationServerKey:applicationServerKey(config.application_server_key),
    });
  }
  const serialized=subscription.toJSON();
  if(!serialized.endpoint||!serialized.keys?.p256dh||!serialized.keys?.auth)return;

  const response=await api(`/organizations/${org}/owner-push/subscriptions`,{
    method:'POST',
    body:{
      endpoint:serialized.endpoint,
      expiration_time:serialized.expirationTime??null,
      keys:{p256dh:serialized.keys.p256dh,auth:serialized.keys.auth},
    },
  });
  if(!response.ok)return;
  const registered=await response.json();
  if(registered.id)localStorage.setItem(SUBSCRIPTION_ID_KEY,registered.id);
}

async function revokePersistentPush(){
  const registration=await navigator.serviceWorker.ready.catch(()=>null);
  const subscription=registration?await registration.pushManager.getSubscription():null;
  const subscriptionId=localStorage.getItem(SUBSCRIPTION_ID_KEY);
  if(subscriptionId&&token()){
    try{
      const org=await resolveOrganization();
      const response=await api(
        `/organizations/${org}/owner-push/subscriptions/${subscriptionId}`,
        {method:'DELETE'},
      );
      if(response.ok||response.status===404)localStorage.removeItem(SUBSCRIPTION_ID_KEY);
    }catch(error){
      console.warn('Owner push registry revocation unavailable',error);
    }
  }
  if(subscription){
    try{
      await subscription.unsubscribe();
    }catch(error){
      console.warn('Browser push unsubscribe unavailable',error);
    }
  }
  if(!subscription)localStorage.removeItem(SUBSCRIPTION_ID_KEY);
}

async function reconcile(){
  if(reconciling||!pushSupported())return;
  reconciling=true;
  try{
    if(alertsEnabled())await registerPersistentPush();
    else await revokePersistentPush();
  }catch(error){
    console.warn('Persistent owner push unavailable; browser-local alerts remain active',error);
  }finally{
    reconciling=false;
  }
}

function queueReconcile(delay=80){
  clearTimeout(reconcileQueued);
  reconcileQueued=setTimeout(()=>reconcile(),delay);
}

const alertToggle=document.querySelector('#attention-alert-toggle');
const alertDetail=document.querySelector('#attention-alert-detail');
if(alertToggle){
  new MutationObserver(()=>queueReconcile()).observe(alertToggle,{childList:true,attributes:true});
  alertToggle.addEventListener('click',()=>queueReconcile(500));
}
if(alertDetail){
  new MutationObserver(()=>queueReconcile()).observe(alertDetail,{childList:true,subtree:true});
}
window.addEventListener('focus',()=>queueReconcile());
document.addEventListener('visibilitychange',()=>{
  if(!document.hidden)queueReconcile();
});
queueReconcile(1200);
})();
