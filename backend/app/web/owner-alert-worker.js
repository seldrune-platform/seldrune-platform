const DEFAULT_TARGET='/console#action-inbox';

function ownerTarget(value){
  try{
    const url=new URL(value||DEFAULT_TARGET,self.location.origin);
    if(url.origin!==self.location.origin||url.pathname!=='/console')return DEFAULT_TARGET;
    return `${url.pathname}${url.search}${url.hash}`;
  }catch{
    return DEFAULT_TARGET;
  }
}

self.addEventListener('install',()=>self.skipWaiting());

self.addEventListener('activate',event=>{
  event.waitUntil(self.clients.claim());
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
