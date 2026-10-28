(() => {
const url = document.currentScript.dataset.url;
const element = (tag, text, cls) => {const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el};
fetch(url).then(async r=>{if(!r.ok)throw Error();return r.json()}).then(({growth,website})=>{
 document.getElementById('analytics-status').textContent='Daily counts · '+growth.days[0]+' to '+growth.days.at(-1);
 const totals=document.getElementById('growth-totals');
 for(const [name,count] of Object.entries({...growth.totals,'Active guest resumes':website.guest_resumes})) {const tile=element('div',undefined,'stat-tile');tile.append(element('span',name),element('strong',count));totals.append(tile)}
 const daily=rows=>growth.days.map(day=>rows.find(row=>row.day===day)?.count||0);
 const series={...growth.series,'Website requests':daily(website.traffic),'Resume upload events':daily(website.uploads)};
 for(const [name,values] of Object.entries(series)) {
  const col=element('div',undefined,'col-md-6'); const card=element('div',undefined,'border rounded p-3');card.append(element('h3',name,'h5'));
  const max=Math.max(1,...values);const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 600 150');svg.setAttribute('role','img');svg.setAttribute('aria-label',name+' daily counts, maximum '+max);svg.style.width='100%';
  values.forEach((value,index)=>{const bar=document.createElementNS(svg.namespaceURI,'rect');bar.setAttribute('x',index*20);bar.setAttribute('y',140-value/max*130);bar.setAttribute('width',15);bar.setAttribute('height',Math.max(1,value/max*130));bar.setAttribute('fill','#2563eb');const title=document.createElementNS(svg.namespaceURI,'title');title.textContent=growth.days[index]+': '+value;bar.append(title);svg.append(bar)});
  card.append(svg,element('p',values.reduce((a,b)=>a+b,0)+' in this period · peak '+Math.max(...values),'small text-muted'));
  const details=element('details');details.append(element('summary','View daily counts'));const table=element('table',undefined,'table table-sm');values.forEach((value,i)=>{const row=element('tr');row.append(element('th',growth.days[i]),element('td',value));table.append(row)});details.append(table);card.append(details);col.append(card);document.getElementById('growth-charts').append(col);
 }
 document.getElementById('traffic-totals').textContent=`${website.totals.requests} requests · ${website.totals.errors||0} errors · ${website.totals.average_ms||0} ms average`;
 const logs=document.getElementById('request-logs');for(const log of website.logs){const row=element('tr');for(const field of ['created_at','path','method','status','duration_ms','role'])row.append(element('td',log[field]));logs.append(row)}
 if(!website.logs.length){const row=element('tr');row.append(element('td','No requests recorded yet.'));logs.append(row)}
}).catch(()=>document.getElementById('analytics-status').textContent='Analytics are temporarily unavailable. Reload to try again.');
})();
