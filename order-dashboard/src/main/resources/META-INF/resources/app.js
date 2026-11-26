import Keycloak from '/vendor/keycloak.js';
'use strict';
const $ = id => document.getElementById(id);
const names = {'aiven':'Aiven S3 Sink','camel':'Camel Quarkus','camel-connect':'Camel Connect'};
const descriptions = {'aiven':'Batched JSON Lines · Kafka Connect','camel':'One JSON event per object · Quarkus','camel-connect':'One JSON event per object · Kafka Connect'};
const labels = {'delivered':'Delivered','not-observed':'Not observed','pending':'Pending','starting':'Starting','unconfigured':'Unconfigured','access-denied':'Access denied','unavailable':'Unavailable','stale':'Stale scan'};
let records=[], selected=null, busy=false, loading=null, preview=false, identity=null, canWrite=true;
let dataRevision=0, pendingAction=null;
const actionFeedback=new Map();
const el=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
const money=n=>Number(n).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
function error(message){$('error').textContent=message;$('error').hidden=!message;}
async function request(path,method='GET',body){
 const headers={'Content-Type':'application/json','X-Streamforge-Action':'orders'};
 if(identity){try{await identity.updateToken(30);}catch{await identity.login();throw Error('Please sign in again.');}headers.Authorization='Bearer '+identity.token;}
 let r;
 try{r=await fetch(path,{method,headers,body:body?JSON.stringify(body):undefined,cache:'no-store'});}
 catch{throw Error('Connection interrupted. Refresh to check the saved order before trying again.');}
 let data;try{data=await r.json();}catch{}
 if(!r.ok){
  const messages={401:'Your session is no longer valid. Sign out and sign in again.',403:'The gateway or access policy rejected this request.',409:'This order changed elsewhere. Refresh and try again.',429:'Too many requests. Wait a minute before trying again.'};
  throw Error((data?.error||messages[r.status]||'The server could not complete the request.')+' (HTTP '+r.status+')');
 }
 if(!data)throw Error('The server returned an unexpected response. Refresh to check the saved order.');
 return data;
}
async function refresh(){
 if(loading)return loading;
 const revision=dataRevision;
 const pending=(async()=>{
  try{
   const d=await request('/api/orders');
   // A response started before a write must never restore the previous order version.
   if(revision!==dataRevision)return false;
   records=d.orders;preview=d.preview;$('preview').hidden=!preview;
   $('connection').textContent=preview?'● Preview · simulated delivery':'● Connected to order database';
   $('updated').textContent='Updated '+new Date(d.serverTime).toLocaleTimeString();
   if(!selected&&records.length)selected=records[0].order.id;
   render();error('');return true;
  }catch(e){if(revision===dataRevision){$('connection').textContent='Connection unavailable';error(e.message);}return false;}
 })();
 loading=pending;
 try{return await pending;}finally{if(loading===pending)loading=null;}
}
function savedOrder(order){
 const previous=records.find(v=>v.order.id===order.id);
 const delivery=(previous?.delivery||Object.keys(names).map(sink=>({sink}))).map(s=>({...s,state:'pending',objectKey:null,scannedAt:null,bounded:false}));
 const view={order,nextStatuses:[],delivery};
 records=[view,...records.filter(v=>v.order.id!==order.id)].slice(0,100);
 render();
}
function setBusy(value){
 busy=value;$('refresh').disabled=value;
 $('create-form').querySelectorAll('input,button').forEach(e=>e.disabled=value||!canWrite);
 $('detail').setAttribute('aria-busy',String(value));renderDetail();
}
async function changeStatus(order,next){
 if(busy||!canWrite)return;
 if(next==='cancelled'&&!confirm('Cancel this order? This changes its status in PostgreSQL.'))return;
 dataRevision++;pendingAction={id:order.id,status:next};
 actionFeedback.set(order.id,{message:'Saving '+next+'…',kind:'saving'});setBusy(true);
 try{
  const saved=await request('/api/orders/'+order.id+'/status','PATCH',{status:next,expectedUpdatedAt:order.updatedAt});
  dataRevision++;savedOrder(saved);
  actionFeedback.set(order.id,{message:'Saved as '+saved.status+'. Delivery below tracks this saved version.',kind:'success'});
  if(loading)await loading;
  await refresh();
 }catch(e){actionFeedback.set(order.id,{message:'Status change failed: '+e.message,kind:'error'});}
 finally{pendingAction=null;setBusy(false);}
}
function render(){
 $('total').textContent=records.length;$('active').textContent=records.filter(v=>['created','paid','shipped'].includes(v.order.status)).length;$('delivered').textContent=records.filter(v=>v.delivery.every(s=>s.state==='delivered')).length;$('value').textContent=money(records.filter(v=>v.order.status==='completed').reduce((n,v)=>n+Number(v.order.amount),0));
 const query=$('search').value.toLowerCase(),tbody=$('orders');tbody.replaceChildren();
 for(const v of records.filter(v=>(v.order.customerName+' '+v.order.id).toLowerCase().includes(query))){const o=v.order,tr=el('tr',undefined,o.id===selected?'selected':'');const customer=el('td'),button=el('button','#'+o.id,'order-link');button.addEventListener('click',()=>{selected=o.id;render();$('detail').scrollIntoView({behavior:'smooth',block:'nearest'});});customer.append(button,el('small',o.customerName));tr.append(customer,el('td',money(o.amount)));const status=el('td');status.append(el('span',o.status,'badge '+o.status));tr.append(status);const delivery=el('td'),dots=el('div',undefined,'dots');for(const s of v.delivery){const dot=el('span',undefined,'dot '+s.state);dot.title=names[s.sink]+': '+labels[s.state];dot.setAttribute('aria-label',dot.title);dots.append(dot);}delivery.append(dots,el('small',v.delivery.filter(s=>s.state==='delivered').length+'/3 observed'));tr.append(delivery);tbody.append(tr);}
 if(!tbody.children.length){const td=el('td','No orders found. Create an order to start its journey.','empty');td.colSpan=4;const tr=el('tr');tr.append(td);tbody.append(tr);}renderDetail();
}
function renderDetail(){const v=records.find(v=>v.order.id===selected);$('detail').hidden=!v;if(!v)return;const o=v.order;$('detail-title').textContent='Order #'+o.id;$('detail-subtitle').textContent=o.customerName+' · '+money(o.amount)+' · Updated '+new Date(o.updatedAt).toLocaleString();$('detail-status').className='badge '+o.status;$('detail-status').textContent=o.status;
 const lifecycle=$('lifecycle');lifecycle.replaceChildren();const stages=['created','paid','shipped','completed'];if(o.status==='cancelled')stages.push('cancelled');stages.forEach((s,i)=>{if(i)lifecycle.append(el('b','→'));lifecycle.append(el('span',s,s===o.status?'current':''));});
 const feedback=actionFeedback.get(o.id),notice=$('action-feedback');
 notice.hidden=!feedback;notice.textContent=feedback?.message||'';notice.className='action-feedback '+(feedback?.kind||'');
 notice.setAttribute('role',feedback?.kind==='error'?'alert':'status');
 const actions=$('actions');actions.replaceChildren();
 for(const next of (canWrite?v.nextStatuses:[])){
  const saving=pendingAction?.id===o.id&&pendingAction.status===next;
  const b=el('button',saving?'Saving…':next==='cancelled'?'Cancel order':'Mark '+next,next==='cancelled'?'secondary':'primary');
  b.type='button';b.disabled=busy;b.addEventListener('click',()=>changeStatus(o,next));actions.append(b);
 }
 if(!canWrite)actions.append(el('span','Viewer access: order changes require the operator role.','fine-print'));
 else if(!v.nextStatuses.length&&!busy)actions.append(el('span',['completed','cancelled'].includes(o.status)?'This order has reached its final status.':'Refresh to load the next available action.','fine-print'));
 const sinks=$('sinks');sinks.replaceChildren();for(const s of v.delivery){const card=el('article',undefined,'sink'),head=el('div',undefined,'sink-head');head.append(el('h3',names[s.sink]),el('span',labels[s.state],'badge '+s.state));card.append(head,el('p',descriptions[s.sink]));card.append(el('code',s.objectKey||(preview?'Simulated delivery — no S3 object':s.state==='delivered'?'Current version observed':'Waiting for an observation of this version')));card.append(el('small',s.scannedAt?'Last successful scan: '+new Date(s.scannedAt).toLocaleTimeString():'No successful scan yet'));if(s.bounded)card.append(el('p','Scan limit reached. Older events may fall outside the observation window.'));sinks.append(card);}
}
$('create-form').addEventListener('submit',async e=>{
 e.preventDefault();if(busy||!canWrite)return;
 const form=e.currentTarget,data=new FormData(form);dataRevision++;setBusy(true);error('');
 try{
  const id=Date.now()*100+crypto.getRandomValues(new Uint32Array(1))[0]%100;
  const created=await request('/api/orders','POST',{id,customerName:data.get('customerName'),amount:Number(data.get('amount'))});
  dataRevision++;selected=created.id;savedOrder(created);form.reset();
  actionFeedback.set(created.id,{message:'Order saved as created. Use Mark paid to begin fulfillment.',kind:'success'});
  if(loading)await loading;await refresh();
 }catch(e){error(e.message);}
 finally{setBusy(false);}
});
$('refresh').addEventListener('click',refresh);$('search').addEventListener('input',render);
async function start(){
 try {
  const r=await fetch('/auth/config');if(!r.ok)throw Error('Login configuration is unavailable.');const config=await r.json();
  if(config.enabled){
   identity=new Keycloak({url:config.url,realm:config.realm,clientId:config.clientId});
   await identity.init({onLoad:'login-required',pkceMethod:'S256',checkLoginIframe:false,responseMode:'query',redirectUri:location.origin+'/'});
   canWrite=identity.hasRealmRole('streamforge-operator');
   $('logout').hidden=false;$('logout').addEventListener('click',()=>identity.logout({redirectUri:location.origin+'/'}));
   $('create-form').querySelectorAll('input,button').forEach(e=>e.disabled=!canWrite);
  }
  await refresh();setInterval(()=>{if(!document.hidden&&!busy)refresh();},5000);
 }catch(e){error('Unable to initialize secure login. Please reload or contact the administrator.');$('connection').textContent='Login unavailable';$('create-form').querySelectorAll('input,button').forEach(e=>e.disabled=true);}
}
start();
