// Exercise real UI code against controlled HTTP responses, including poll/write races.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const http=require('node:http');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../src/main/resources/META-INF/resources');
const files={'/':'index.html','/app.js':'app.js','/app.css':'app.css','/vendor/keycloak.js':'vendor/keycloak.js'};
const server=http.createServer((req,res)=>{
 const name=files[req.url];if(!name){res.writeHead(404);return res.end();}
 res.setHeader('Content-Type',name.endsWith('.js')?'application/javascript':name.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(path.join(root,name)));
});
const gate=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const browser=await chromium.launch({headless:true});
 try{
  async function fixture(){
   const page=await browser.newPage({viewport:{width:1440,height:1100}});
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   let order={id:12345,customerName:'Synthetic regression',amount:150,status:'created',updatedAt:'2026-01-01T00:00:00Z'};
   let version=0,patches=0,getOverride=null,patchOverride=null;
   const next={created:['paid','cancelled'],paid:['shipped','cancelled'],shipped:['completed'],completed:[],cancelled:[]};
   const response=()=>({preview:false,serverTime:new Date().toISOString(),orders:[{order:{...order},nextStatuses:next[order.status],delivery:['aiven','camel','camel-connect'].map(sink=>({sink,state:version?'pending':'delivered',objectKey:version?null:'created.json',scannedAt:new Date().toISOString(),bounded:false}))}]});
   await page.route('**/auth/config',r=>r.fulfill({json:{enabled:false}}));
   await page.route('**/api/orders**',async route=>{
    if(route.request().method()==='GET'){
     if(getOverride)return getOverride(route,response());
     return route.fulfill({json:response()});
    }
    patches++;
    if(patchOverride)return patchOverride(route);
    const input=route.request().postDataJSON();assert.equal(input.expectedUpdatedAt,order.updatedAt);
    assert(next[order.status].includes(input.status));
    version++;order={...order,status:input.status,updatedAt:`2026-01-01T00:00:0${version}Z`};
    return route.fulfill({json:order});
   });
   await page.goto('http://127.0.0.1:'+server.address().port);
   await page.getByRole('button',{name:'Mark paid',exact:true}).waitFor();
   return {page,errors,get patches(){return patches;},set get(fn){getOverride=fn;},set patch(fn){patchOverride=fn;}};
  }
  // Successful transitions immediately show the saved version; old delivered flags disappear.
  {
   const f=await fixture();
   for(const status of ['paid','shipped','completed']){
    await f.page.getByRole('button',{name:'Mark '+status,exact:true}).click();
    await f.page.waitForFunction(s=>document.querySelector('#detail-status').textContent===s,status);
    await f.page.waitForFunction(()=>!document.querySelector('#detail').getAttribute('aria-busy')||document.querySelector('#detail').getAttribute('aria-busy')==='false');
    assert.equal(await f.page.locator('#orders .badge').textContent(),status);
    assert.match(await f.page.locator('#orders').textContent(),/0\/3 observed/);
    assert.equal(await f.page.locator('#sinks .badge.delivered').count(),0);
    assert.match(await f.page.locator('#action-feedback').textContent(),new RegExp('Saved as '+status));
   }
   assert.equal(f.patches,3);assert.deepEqual(f.errors,[]);await f.page.close();
   console.log('PASS: paid → shipped → completed; table/detail agree; delivery tracks saved version');
  }
  // Coraza can return an empty 403; polling must not erase the actionable error.
  {
   const f=await fixture();f.patch=r=>r.fulfill({status:403,body:''});
   await f.page.getByRole('button',{name:'Mark paid',exact:true}).click();
   await f.page.locator('#action-feedback.error').waitFor();
   await f.page.getByRole('button',{name:'↻ Refresh',exact:true}).click();
   await f.page.waitForTimeout(5500); // Includes an automatic poll.
   assert.match(await f.page.locator('#action-feedback').textContent(),/HTTP 403/);
   assert.equal(await f.page.locator('#detail-status').textContent(),'created');
   assert(await f.page.locator('#action-feedback').isVisible());
   assert.deepEqual(f.errors,[]);await f.page.close();console.log('PASS: empty gateway 403 stays visible after manual and automatic refresh');
  }
  // A slow poll captured before PATCH must never roll the UI back after the save.
  {
   const f=await fixture(),started=gate(),release=gate();
   f.get=async(r,snapshot)=>{f.get=null;started.resolve();await release.promise;await r.fulfill({json:snapshot});};
   await f.page.getByRole('button',{name:'↻ Refresh',exact:true}).click();await started.promise;
   await f.page.getByRole('button',{name:'Mark paid',exact:true}).click();
   await f.page.waitForFunction(()=>document.querySelector('#detail-status').textContent==='paid');
   assert.equal(await f.page.locator('#orders .badge').textContent(),'paid');
   assert.match(await f.page.locator('#orders').textContent(),/0\/3 observed/);
   release.resolve();await f.page.getByRole('button',{name:'Mark shipped',exact:true}).waitFor();
   assert.equal(await f.page.locator('#detail-status').textContent(),'paid');assert.deepEqual(f.errors,[]);
   await f.page.close();console.log('PASS: stale poll cannot overwrite confirmed PATCH response');
  }
  // A pending action is visibly saving and blocks duplicate submissions.
  {
   const f=await fixture(),started=gate(),release=gate();
   f.patch=async r=>{started.resolve();await release.promise;await r.fulfill({status:409,json:{error:'Order changed. Refresh and try again.'}});};
   await f.page.getByRole('button',{name:'Mark paid',exact:true}).click();await started.promise;
   assert(await f.page.getByRole('button',{name:'Saving…',exact:true}).isDisabled());
   assert(await f.page.getByRole('button',{name:'Cancel order',exact:true}).isDisabled());
   assert(await f.page.getByRole('button',{name:'↻ Refresh',exact:true}).isDisabled());
   release.resolve();await f.page.locator('#action-feedback.error').waitFor();assert.equal(f.patches,1);
   assert.match(await f.page.locator('#action-feedback').textContent(),/HTTP 409/);
   await f.page.setViewportSize({width:390,height:844});
   assert.equal(await f.page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   assert.deepEqual(f.errors,[]);await f.page.close();console.log('PASS: saving feedback, duplicate-submit protection, conflict feedback, mobile layout');
  }
 }finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;server.close();});
