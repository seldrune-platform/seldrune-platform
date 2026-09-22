(()=>{const view=document.getElementById("console-view");if(!view)return;
const tabs=[...view.querySelectorAll("nav a[data-console-tab]")];
const groups={
overview:["overview",".incident-center",".treasury",".agent-observatory"],
gpt:["seldrune-gpt"],runtime:["sti-runtime"],face:["face-v01-mission","face-external-test"],
liveshift:["liveshift-mission"],actions:["action-inbox"],tools:["tool-control"],governance:[".governance-policy",".audit-center"],commands:["command","commands"]};
const all=new Set();Object.values(groups).flat().forEach(sel=>{const el=sel.startsWith(".")?view.querySelector(sel):document.getElementById(sel);if(el){el.dataset.consolePane="1";all.add(el)}});
function activate(name,push=true){const selected=groups[name]?name:"overview";all.forEach(el=>el.classList.remove("console-tab-active"));groups[selected].forEach(sel=>{const el=sel.startsWith(".")?view.querySelector(sel):document.getElementById(sel);el?.classList.add("console-tab-active")});tabs.forEach(a=>a.classList.toggle("active",a.dataset.consoleTab===selected));if(push)history.replaceState(null,"","#"+selected);localStorage.setItem("seldrune.console.tab",selected);if(selected==="gpt")document.getElementById("seldrune-gpt-input")?.focus()}
tabs.forEach(a=>a.addEventListener("click",e=>{e.preventDefault();activate(a.dataset.consoleTab)}));
const requested=location.hash.slice(1);const initial=groups[requested]?requested:(localStorage.getItem("seldrune.console.tab")||"overview");activate(initial,false);
window.addEventListener("hashchange",()=>{const n=location.hash.slice(1);if(groups[n])activate(n,false)});
window.addEventListener("seldrune:open-tab",e=>activate(e.detail?.tab||"overview"));
})();