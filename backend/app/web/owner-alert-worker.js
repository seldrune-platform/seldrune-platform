const DEFAULT_TARGET='/console#action-inbox';
const NOTIFICATION_TITLE='Seldrune Owner Attention';
const COUNT_FIELDS=[
  ['critical','critical'],
  ['reviews','review'],
  ['approvals','approval'],
  ['warnings','warning'],
];

function ownerTarget(value){
  try{
    const url=new URL(value||DEFAULT_TARGET,self.location.origin);
    if(url.origin!==self.location.origin||url.pathname!=='/console')return DEFAULT_TARGET;
    return `${url.pathname}${url.search}${url.hash}`;
  }catch{
    return DEFAULT_TARGET;
  }
}

function safeCount(value){
  const parsed=Number.parseInt(value,10);
  return Number.isFinite(parsed)&&parsed>0?parsed:0;
}

function ownerPushEnvelope(event){
  if(!event.data)return null;
  let payload;
  try{
    payload=event.data.json();
  }catch{
    return null;
  }
  if(!payload||payload.notification_version!==1||payload.read_only!==true)return null;
  if(payload.privacy?.detail_level!=='counts_only'||payload.has_attention!==true)return null;

  const summary={};
  let total=0;
  COUNT_FIELDS.forEach(([key])=>{
    summary[key]=safeCount(payload.summary?.[key]);
    total+=summary[key];
  });
  if(total<1)return null;

  const parts=[];
  COUNT_FIELDS.forEach(([key,label])=>{
    const count=summary[key];
    if(!count)return;
    parts.push(`${count} ${label}${count===1?'':'s'}`);
  });
  const urgency=summary.critical
    ?'critical'
    :summary.reviews
      ?'review'
      :summary.approvals
        ?'approval'
        :'warning';
  return{
    body:`Owner attention: ${parts.join(', ')}.`,
    target:ownerTarget(payload.target),
    urgency,
  };
}

self.addEventListener('install',()=>self.skipWaiting());

self.addEventListener('activate',event=>{
  event.waitUntil(self.clients.claim());
});

self.addEventListener('push',event=>{
  const envelope=ownerPushEnvelope(event);
  if(!envelope)return;
  event.waitUntil(self.registration.showNotification(NOTIFICATION_TITLE,{
    body:envelope.body,
    tag:'seldrune-owner-attention',
    renotify:true,
    data:{target:envelope.target,urgency:envelope.urgency},
  }));
});

self.addEventListener('notificationclick',event=>{
  event.notification.close();
  const target=ownerTarget(event.notification.data?.target);
  event.waitUntil((async()=>{
    const windows=await self.clients.matchAll({type:'window',includeUncontrolled:true});
    const consoleWindow=windows.find(client=>{
      const url=new URL(client.url);
      return url.origin===self.location.origin&&url.pathname==='/console';
    });
    if(consoleWindow){
      if('navigate' in consoleWindow)await consoleWindow.navigate(target);
      await consoleWindow.focus();
      return;
    }
    await self.clients.openWindow(target);
  })());
});
