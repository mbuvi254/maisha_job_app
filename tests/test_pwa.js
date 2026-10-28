const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
async function workerChecks(){
 const listeners={},stored=new Map([['/offline',new Response('<h1>Reconnect</h1>')]]),removed=[];
 const cache={addAll:async()=>{},match:async key=>stored.get(key)?.clone(),put:async(key,value)=>stored.set(key,value)};
 let fetcher=async()=>new Response('server page');
 const scope={Response,URL,self:{location:{origin:'https://jobs.example'},addEventListener:(type,fn)=>listeners[type]=fn,skipWaiting(){},clients:{claim(){}}},caches:{open:async()=>cache,keys:async()=>['unrelated-cache','maisha-jobs-static-v3','maisha-jobs-static-v4'],delete:async key=>removed.push(key)},fetch:(request)=>fetcher(request)};
 vm.runInNewContext(fs.readFileSync('app/static/pwa/sw.js','utf8'),scope);
 let pending;listeners.activate({waitUntil:p=>pending=p});await pending;
 assert.deepEqual(removed,['maisha-jobs-static-v3']);
 async function request(path,mode='navigate',method='GET'){
  let response;
  listeners.fetch({request:{url:'https://jobs.example'+path,mode,method},respondWith:p=>response=p,waitUntil:p=>p.catch(()=>{})});
  return response ? await response : null;
 }
 const online=await request('/candidates/profile');assert.equal(await online.text(),'server page');
 assert.equal(stored.has('/candidates/profile'),false);
 fetcher=async()=>new Response('Not found',{status:404});
 assert.equal((await request('/missing')).status,404);
 fetcher=async()=>{throw Error('offline')};
 const offline=await request('/employers/dashboard');
 assert.equal(offline.status,503);assert.match(await offline.text(),/Reconnect/);
 assert.equal(await request('/interview/answer','cors','POST'),null);
 assert.equal(await request('/api/private','cors'),null);
 stored.set('/static/js/pwa-navigation.js',new Response('navigation script'));
 assert.equal(await (await request('/static/js/pwa-navigation.js?v=1','cors')).text(),'navigation script');
}
function navigationChecks(){
 const buttons={};for(const name of ['back','forward','refresh'])buttons[name]={disabled:false,addEventListener(type,fn){this.click=fn}};
 const toolbar={hidden:true,querySelector:selector=>buttons[selector.match(/data-app-(\w+)/)[1]]};
 let back=0,forward=0,reload=0,home=0,installed=true;
 const navigation={canGoBack:false,canGoForward:false,addEventListener(){}};
 const window={navigation,navigator:{},history:{length:1,back:()=>back++,forward:()=>forward++},location:{reload:()=>reload++,assign:()=>home++},matchMedia:()=>({get matches(){return installed},addEventListener(){}}),addEventListener(){}};
 const document={querySelector:selector=>selector==='.pwa-navigation'?toolbar:buttons[selector.match(/data-app-(\w+)/)[1]],querySelectorAll:()=>[buttons.back],documentElement:{classList:{toggle(){}}}};
 vm.runInNewContext(fs.readFileSync('app/static/js/pwa-navigation.js','utf8'),{window,document});
 assert.equal(toolbar.hidden,false);assert.equal(buttons.back.disabled,true);assert.equal(buttons.forward.disabled,true);
 navigation.canGoBack=true;buttons.back.click();buttons.forward.click();buttons.refresh.click();
 assert.equal(back,1);assert.equal(forward,1);assert.equal(reload,1);assert.equal(home,0);
}
(async()=>{await workerChecks();navigationChecks();console.log('PWA history controls, offline fallback, private-page exclusion, HTTP errors, API handling and cache cleanup passed.');})();
