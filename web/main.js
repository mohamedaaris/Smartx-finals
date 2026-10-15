import { WarehouseView, fleetColors as colors } from './scene.js';

const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const time=t=>t==null?'—':`${String(Math.floor(t/60)).padStart(2,'0')}:${String(Math.floor(t%60)).padStart(2,'0')}`;
const human=s=>(s||'—').replaceAll('_',' ').toLowerCase();
let state=null, selected='AMR-01', selectedTask=null, selectedSlot=null, view='3d', placing=false, lastNotice=0, lastDecisionSignature='';
let scene;
function notice(message,error=false){$('#notice').textContent=message;$('#notice').classList.toggle('error',error);lastNotice=performance.now()}
try{scene=new WarehouseView($('#scene'),$('#world-labels'),selectRobot,id=>selectSlot(id,false),(message,error=false)=>{
  $('#model-status').textContent=message;$('#model-progress').textContent=message;
  if(message.startsWith('Original model loaded'))$('#model-loading').hidden=true;
  if(error){$('#model-loading').querySelector('strong').textContent='Unable to load 3D asset';notice(message,true)}
},inspectScene)}catch(e){notice(`3D renderer unavailable: ${e.message}`,true);$('#model-progress').textContent=e.message}

async function post(path,data){const response=await fetch(`/api/${path}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const result=await response.json();if(!response.ok)throw Error(result.error||'Request failed');return result}
async function action(fn){try{await fn();await refresh()}catch(e){notice(e.message,true)}}
function selectRobot(id){if(!state)return;selected=id;const robot=state.robots.find(r=>r.id===id);if(robot?.task)selectedTask=robot.task;render();scene?.update(state,selected,selectedSlot)}
function selectSlot(id,scroll=true){if(!state?.slots.some(s=>s.id===id))return;selectedSlot=id;render();scene?.update(state,selected,selectedSlot);if(scroll)$('#slot-inspector').scrollIntoView({block:'nearest'})}
function inspectScene(hit){
  const panel=$('#scene-info');if(!hit){panel.hidden=true;return}
  const point={x:hit.point.x,y:-hit.point.z,z:hit.point.y};
  const coords=`${point.x.toFixed(2)}, ${point.y.toFixed(2)}, ${point.z.toFixed(2)} m`;
  const slot=state?.slots.find(s=>s.id===hit.name);
  const pkg=state?.packages.find(p=>p.id===hit.name);
  const nearby=hit.rack&&state?.slots.filter(s=>s.shelf===hit.rack).sort((a,b)=>Math.abs((a.position?.[1]||0)-point.y)-Math.abs((b.position?.[1]||0)-point.y))[0];
  let type='SPACE',name=hit.area?.name||'Open floor',detail=[['Location',coords],['Area',hit.area?.detail||'']],action=null;
  if(hit.kind==='shelf'){
    type='SHELF';name=hit.rack?`Shelf ${hit.rack}`:'Shelf structure';
    detail=[['Source part (bounds match)',hit.source],['Position',coords],['Access',hit.rack?`Aisle ${hit.rack[0]}`:'Check model position']];
    if(nearby)action={label:`Inspect slot ${nearby.id}`,run:()=>selectSlot(nearby.id)};
  }else if(hit.kind==='source-box'){
    type='SOURCE BOX';name=hit.source.split('_')[0];
    const sourceSlot=state?.slots.find(s=>s.shelf===hit.rack&&s.source_backed);
    detail=[['Source part (bounds match)',hit.source],['Shelf',hit.rack||'Outside mapped racks'],['Position',coords],['Inventory',sourceSlot?`${sourceSlot.source_units} source cartons · ${sourceSlot.sku||'depleted'}`:'No mapped stock group']];
    if(sourceSlot)action={label:`Inspect ${sourceSlot.id}`,run:()=>selectSlot(sourceSlot.id)};
  }else if(hit.kind==='slot'){
    type='STORAGE SLOT';name=hit.name;
    detail=[['Shelf / aisle',slot?`${slot.shelf} / ${slot.shelf[0]}`:'Unknown'],['Contents',slot?.sku||'Empty'],['Reservation',slot?.reserved_by||'None'],['Position',coords]];
    action={label:'Assign work for this slot',run:()=>{$('#slot-inspector-action').click();if($('#slot-inspector-action').hidden)selectSlot(hit.name)}};
  }else if(hit.kind==='package'){
    type='TRACKED PACKAGE';name=hit.name;
    detail=[['SKU',pkg?.sku||'Unknown'],['Stage',pkg?.stage||'Unknown'],['Slot',pkg?.slot||'In transit'],['Position',coords]];
    if(pkg?.slot)action={label:`Inspect slot ${pkg.slot}`,run:()=>selectSlot(pkg.slot)};
  }else if(hit.kind==='robot'){
    type='AMR';name=hit.name;
    const robot=state?.robots.find(r=>r.id===hit.name);
    detail=[['Status',robot?.status||'Unknown'],['Job',robot?.task||'None'],['Position',coords]];
  }else if(hit.kind==='depot'){
    type='CHARGING STOP';name=`Charge ${hit.name.split('_')[1]}`;
    const n=state?.geometry.nodes.find(p=>p.id===hit.name);
    const robot=state?.robots.find(r=>r.docked&&n&&Math.hypot(r.x-n.x,r.y-n.y)<1.3);
    detail=[['Area','Extended charging / depot'],['Position',coords],['Occupant',robot?.id||'Available'],['Charging',robot?.charging?'Active':'Ready for a docked AMR']];
  }else if(hit.area?.destination){
    const destination=hit.area.destination;
    action={label:`Plan move to ${destination}`,run:()=>{$('#job-kind').value='MOVE';renderDispatch();$('#job-destination').value=destination;renderDispatch();$('#dispatch').scrollIntoView({block:'center'})}};
  }
  $('#scene-info-type').textContent=type;$('#scene-info-name').textContent=name;
  $('#scene-info-detail').innerHTML=detail.map(([label,value])=>`<div><span>${esc(label)}</span><b>${esc(value)}</b></div>`).join('');
  const button=$('#scene-info-action');button.hidden=!action;button.textContent=action?.label||'';button.onclick=action?.run||null;
  const rect=$('#scene').getBoundingClientRect();
  panel.style.left=`${Math.max(8,Math.min(hit.event.clientX-rect.left+12,rect.width-292))}px`;
  panel.style.top=`${Math.max(54,Math.min(hit.event.clientY-rect.top+12,rect.height-210))}px`;
  panel.hidden=false;
}
$('#scene-info-close').onclick=()=>$('#scene-info').hidden=true;
function setView(value){view=value;$('#views').className=`views ${value==='split'?'split':'only-'+value}`;$$('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===value));scene?.resize();drawMap()}
function full3dActive(){return document.fullscreenElement===$('#visual')||$('#visual').classList.contains('fullscreen-fallback')}
function syncFullscreen(){const active=full3dActive();$('#fullscreen-3d').textContent=active?'↙ Exit full screen':'⛶ Full screen';$('#fullscreen-3d').setAttribute('aria-pressed',String(active));requestAnimationFrame(()=>scene?.resize())}
async function toggleFullscreen(){
  const visual=$('#visual');
  if(full3dActive()){
    if(document.fullscreenElement===visual)await document.exitFullscreen();
    visual.classList.remove('fullscreen-fallback');document.body.classList.remove('fullscreen-fallback-active');syncFullscreen();return;
  }
  setView('3d');
  try{if(!visual.requestFullscreen)throw Error('Fullscreen API unavailable');await visual.requestFullscreen()}
  catch{visual.classList.add('fullscreen-fallback');document.body.classList.add('fullscreen-fallback-active')}
  syncFullscreen();
}
function recordTab(name){$$('[data-record]').forEach(b=>b.classList.toggle('active',b.dataset.record===name));$$('[data-record-panel]').forEach(p=>p.hidden=p.dataset.recordPanel!==name)}
function canvasContext(canvas){const r=canvas.getBoundingClientRect();if(r.width<1||r.height<1)return null;const dpr=Math.min(devicePixelRatio||1,2);canvas.width=Math.round(r.width*dpr);canvas.height=Math.round(r.height*dpr);const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);return {ctx,w:r.width,h:r.height}}
function transform(w,h,g){const [x0,y0,x1,y1]=g.floor;const scale=Math.min((w-55)/(x1-x0),(h-85)/(y1-y0)),ox=(w-(x1-x0)*scale)/2,oy=(h-(y1-y0)*scale)/2;return {scale,point:(x,y)=>[ox+(x-x0)*scale,h-oy-(y-y0)*scale],inverse:(px,py)=>[x0+(px-ox)/scale,y0+(h-oy-py)/scale]}}
function line(ctx,points,color,width=1,dash=[]){if(points.length<2)return;ctx.beginPath();ctx.moveTo(...points[0]);points.slice(1).forEach(p=>ctx.lineTo(...p));ctx.strokeStyle=color;ctx.lineWidth=width;ctx.setLineDash(dash);ctx.stroke();ctx.setLineDash([])}
function worldRect(ctx,t,b,fill,stroke){const a=t.point(b[0],b[3]),c=t.point(b[2],b[1]);if(fill){ctx.fillStyle=fill;ctx.fillRect(a[0],a[1],c[0]-a[0],c[1]-a[1])}if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=1;ctx.strokeRect(a[0],a[1],c[0]-a[0],c[1]-a[1])}}
function drawMap(){
  if(!state)return;const context=canvasContext($('#map'));if(!context)return;const {ctx,w,h}=context,g=state.geometry,t=transform(w,h,g),nodes=new Map(g.nodes.map(n=>[n.id,n]));
  ctx.fillStyle='#142634';ctx.fillRect(0,0,w,h);worldRect(ctx,t,g.floor,'#1d3443','#3b5768');
  for(const [name,b] of Object.entries(g.zones)){worldRect(ctx,t,b,{pickup:'#2b577b',delivery:'#794952',charging:'#286d60'}[name]);const p=t.point((b[0]+b[2])/2,(b[1]+b[3])/2);ctx.fillStyle='#bdd1d9';ctx.font='600 9px Segoe UI';ctx.textAlign='center';ctx.fillText(name==='charging'?'CHARGING / DEPOT':name.toUpperCase(),p[0],p[1])}
  for(const b of g.conveyors)worldRect(ctx,t,b,'#6d8190');
  for(const [a,b] of g.edges){const n=nodes.get(a),m=nodes.get(b);line(ctx,[t.point(n.x,n.y),t.point(m.x,m.y)],(a.startsWith('L')&&b.startsWith('L'))||(a.startsWith('R')&&b.startsWith('R'))?'#c58dba':'#547382',1,[3,4])}
  g.racks.forEach(b=>worldRect(ctx,t,b,'#a7b6ba','#d0d8d3'));
  for(const slot of state.slots){if(!slot.position)continue;const p=t.point(slot.position[0],slot.position[1]),active=slot.id===selectedSlot;ctx.beginPath();ctx.arc(p[0],p[1],active?6:4,0,Math.PI*2);ctx.fillStyle=slot.reserved_by?'#dfb864':slot.sku?'#58b88f':'#d7e9df';ctx.fill();ctx.strokeStyle=active?'#fff1b4':'#254a57';ctx.lineWidth=active?2.5:1;ctx.stroke()}
  for(const n of g.nodes.filter(n=>['waiting','parking','depot'].includes(n.kind))){const p=t.point(n.x,n.y);ctx.beginPath();ctx.arc(...p,n.kind==='waiting'?4:n.kind==='depot'?5:2.5,0,Math.PI*2);ctx.fillStyle=n.kind==='waiting'?'#60a992':n.kind==='depot'?'#7fd5ae':'#607a8d';ctx.fill();if(n.kind==='depot'){ctx.fillStyle='#d7f3e3';ctx.font='bold 8px Segoe UI';ctx.textAlign='center';ctx.fillText(`C${n.id.split('_')[1]}`,p[0],p[1]-9)}}
  for(const [category,locks] of Object.entries(state.locks)){
    if(!['shelves','conveyors','charging','junctions','waiting'].includes(category))continue;
    for(const id of Object.keys(locks)){const n=nodes.get(id);if(!n)continue;const p=t.point(n.x,n.y);ctx.strokeStyle={shelves:'#e8bd6a',conveyors:'#b99ae7',charging:'#5dcc9c',junctions:'#eeb089',waiting:'#e8bd6a'}[category];ctx.lineWidth=1.5;ctx.strokeRect(p[0]-8,p[1]-8,16,16)}
  }
  for(const r of state.robots){if(!$('#views').classList.contains('only-3d')&&$('[data-layer=routes]').checked){const pts=[[r.x,r.y],...r.route.map(id=>nodes.get(id)).filter(Boolean).map(n=>[n.x,n.y])].map(p=>t.point(...p));line(ctx,pts,colors[state.robots.indexOf(r)%colors.length],r.id===selected?2:1.2,[5,3])}}
  for(const o of state.obstacles){const p=t.point(o.x,o.y);ctx.beginPath();ctx.arc(...p,Math.max(5,1.8*t.scale),0,Math.PI*2);ctx.fillStyle='#e09a6977';ctx.fill();ctx.fillStyle='#edb79a';ctx.font='bold 10px Segoe UI';ctx.textAlign='center';ctx.fillText('!',p[0],p[1]+3)}
  for(const pkg of state.conveyor_packages){const x={CONV_1:-8,CONV_2:-3.8,CONV_3:-.3}[pkg.lane],p=t.point(x+(1.45-x)*pkg.progress,13.3);ctx.fillStyle='#e6c295';ctx.fillRect(p[0]-3,p[1]-3,6,6)}
  state.robots.forEach((r,i)=>{const p=t.point(r.x,r.y);if($('[data-layer=sensors]').checked){ctx.beginPath();ctx.arc(...p,state.config.detection_radius*t.scale,0,Math.PI*2);ctx.fillStyle=colors[i%colors.length]+'18';ctx.fill();ctx.strokeStyle=colors[i%colors.length]+'aa';ctx.lineWidth=r.id===selected?2:1;ctx.stroke()}
    ctx.save();ctx.translate(...p);ctx.rotate(-r.heading);ctx.fillStyle=colors[i%colors.length];ctx.fillRect(-6,-4,12,8);ctx.strokeStyle=r.id===selected?'#e8edf2':'#183141';ctx.lineWidth=r.id===selected?2:1;ctx.strokeRect(-6,-4,12,8);ctx.fillStyle='#e9f8f5';ctx.beginPath();ctx.moveTo(8,0);ctx.lineTo(5,-2);ctx.lineTo(5,2);ctx.closePath();ctx.fill();ctx.restore();
    if(r.carrying){ctx.fillStyle='#f1cd91';ctx.fillRect(p[0]-2,p[1]-2,4,4)}if(r.block_reason){ctx.beginPath();ctx.arc(...p,10,0,Math.PI*2);ctx.strokeStyle='#dca475';ctx.lineWidth=1.5;ctx.stroke()}
    ctx.fillStyle='#dce7eb';ctx.font='bold 8px Segoe UI';ctx.textAlign='left';ctx.fillText(r.id.slice(-2),p[0]+9,p[1]+2);
  });$('#map')._transform=t;
}
function renderMetrics(){
  const robots=state.robots,tasks=state.tasks,m=state.metrics,active=robots.filter(r=>r.status!=='IDLE').length,queued=tasks.filter(t=>t.state==='QUEUED').length;
  const stored=state.slots.reduce((total,s)=>total+(s.source_backed?s.source_units:Number(!!s.package_id)),0);
  const free=state.slots.filter(s=>s.validated_vacant&&!s.sku&&!s.reserved_by).length;
  const values=[['Fleet online',robots.length,`${active} active · ${robots.filter(r=>r.status==='IDLE').length} idle`,'◉'],['Active jobs',tasks.filter(t=>['ASSIGNED','IN_PROGRESS','IN_TRANSIT'].includes(t.state)).length,`${queued} waiting in queue`,'↗'],['Stored packages',stored,`${free} available pilot slots`,'▤'],['Completed',m.completed,'Executed jobs','✓'],['Delivered',m.delivered,'Confirmed at conveyor exit','⇥'],['Fleet travel',m.distance_m.toFixed(1)+'<small>m</small>','Measured movement','⌁']];
  $('#metrics').innerHTML=values.map(([label,value,hint,icon])=>`<div class="metric"><span class="metric-icon">${icon}</span><div class="metric-label">${label}</div><div class="metric-value">${value}</div><div class="metric-hint">${hint}</div></div>`).join('');
}
function renderFleet(){
  $('#fleet-count').textContent=`${state.robots.length} / ${state.charging_capacity}`;
  $('#fleet-caption').innerHTML=`${state.robots.length} AMRs<br>1 controller`;
  $('#footer-fleet').textContent=`Vinland · ${state.robots.length} AMRs / ${state.charging_capacity} charging slots`;
  $('#add-robot').disabled=state.robots.length>=state.charging_capacity||!state.available_charging_slots.length;
  $('#add-robot').title=$('#add-robot').disabled?'All charging slots are occupied or reserved':'Place an AMR in a free charging slot';
  $('#fleet-active').textContent=`${state.robots.filter(r=>r.task).length} working / ${state.robots.length} online`;
  $('#fleet-summary').innerHTML=[['Carrying',state.robots.filter(r=>r.carrying).length],['Charging',state.robots.filter(r=>r.charging).length],['To charge',state.robots.filter(r=>r.status==='MOVING_TO_CHARGER').length],['Blocked',state.robots.filter(r=>r.block_reason||r.status.startsWith('WAITING')).length]].map(([label,value])=>`<span><b>${value}</b>${label}</span>`).join('');
  $('#robots').innerHTML=state.robots.map((r,i)=>`<button class="robot-card ${selected===r.id?'selected':''}" data-robot="${r.id}" style="--robot-color:${colors[i%colors.length]}"><div class="robot-line"><span class="robot-name"><i class="robot-dot"></i>${r.id}</span><span class="robot-state ${r.block_reason?'blocked':r.charging?'charging':r.task?'busy':''}">${esc(r.block_reason?'coordinating':r.charging&&r.status==='IDLE'?'idle · charging':human(r.status))}</span></div><div class="robot-detail">${esc(r.task||'No assigned request')} · ${esc(r.target||r.node)}${r.carrying?' · payload':''}</div><div class="battery-line"><div class="battery"><div style="width:${r.battery}%"></div></div><span>${r.battery.toFixed(0)}%</span></div><div class="robot-meta"><span>${r.velocity.toFixed(1)} m/s</span><span>${r.distance_m.toFixed(1)} m travelled</span></div>${r.block_reason?`<div class="robot-warning">${esc(r.block_reason)}</div>`:''}</button>`).join('');
  const r=state.robots.find(r=>r.id===selected)||state.robots[0];$('#selected-name').textContent=r.id;$('#selected-dot').style.background=colors[state.robots.indexOf(r)%colors.length];const assigned=state.tasks.find(t=>t.id===r.task);$('#selected-role').textContent=assigned?(assigned.requested_robot?'Operator-assigned job':'Controller-assigned job'):r.status==='IDLE'?'Available for manual assignment':'Following controller route';
  const details=[['Request',r.task||'Available'],['Destination',r.target||'No destination'],['Position',`${r.x.toFixed(1)}, ${r.y.toFixed(1)} m`],['Shelf / station',r.slot||r.conveyor||r.charge_bay||'—'],['Payload',r.package_id&&r.carrying?r.package_id:'Empty'],['Route',r.route.length?r.route.join(' → '):'No active route']];
  $('#robot-detail').innerHTML=details.map(([label,value])=>`<div><div class="detail-label">${label}</div><div class="detail-value">${esc(value)}</div></div>`).join('');
  $('#coordination').innerHTML=r.coordination.length?r.coordination.map(p=>`<span class="peer">${esc(p.id)} · ${esc(p.next||'holding')} · ${p.battery.toFixed(0)}%${p.carrying?' · carrying':''}${p.blocked?' · blocked':''}</span>`).join(''):'No other AMRs within the 5 m coordination radius.';
  $('#scene-hud').innerHTML=`<strong>${r.id}</strong><div class="hud-state">● ${esc(r.block_reason?'Coordinating':r.charging&&r.status==='IDLE'?'Idle · charging':human(r.status))}</div><div class="hud-line"><span>Battery</span><b>${r.battery.toFixed(0)}%</b></div><div class="hud-line"><span>Payload</span><b>${r.carrying?'Carrying':'Empty'}</b></div><div class="hud-line"><span>Speed</span><b>${r.velocity.toFixed(1)} m/s</b></div>`;
}
function renderWorkflow(){
  const task=state.tasks.find(t=>t.id===selectedTask)||state.tasks.find(t=>['ASSIGNED','IN_PROGRESS','IN_TRANSIT'].includes(t.state))||state.tasks.at(-1);
  if(!task){$('#workflow').textContent='Select a job to inspect its operational stages.';return}
  const robot=state.robots.find(r=>r.task===task.id);let current=0;
  const stages=task.kind==='MOVE'?['Queued','Travel','Arrived']:task.kind==='INBOUND'?['Queued','Pickup','Carry','Store','Clear','Complete']:['Queued','Retrieve','Carry','Pack','Deposit','Conveyor','Delivered'];
  if(task.kind==='INBOUND')current=({MOVING_TO_PICKUP:1,PICKING_PACKAGE:1,MOVING_TO_SHELF:2,STORING_PACKAGE:3,CLEARING_SHELF:4}[robot?.status]??0);
  else if(task.kind==='MOVE')current=robot?.status==='MOVING_TO_DESTINATION'?1:0;
  else current=({MOVING_TO_RETRIEVAL:1,RETRIEVING_PACKAGE:1,MOVING_TO_PACKING:2,PACKING_PACKAGE:3,MOVING_TO_CONVEYOR:4,DEPOSITING_PACKAGE:4,CLEARING_CONVEYOR:5,WAITING_CONVEYOR_CLEAR:5}[robot?.status]??(task.state==='IN_TRANSIT'?5:0));
  if(task.state==='COMPLETED')current=stages.length;
  $('#workflow').innerHTML=`<strong>${esc(task.id)} · ${esc(task.sku)}</strong>`+stages.map((name,i)=>`${i?'<span class="phase-arrow">→</span>':''}<span class="phase ${i<current?'done':i===current?'current':''}"><i>${i<current?'✓':i+1}</i>${name}</span>`).join('');
}
function renderRecords(){
  $('#task-count').textContent=state.tasks.length;$('#tasks-empty').hidden=!!state.tasks.length;
  $('#task-rows').innerHTML=state.tasks.slice().reverse().map(t=>`<tr class="task-row ${t.id===selectedTask?'selected':''}" data-task="${t.id}"><td><strong>${t.id}</strong><small>Created ${time(t.created)}</small></td><td>${t.kind==='INBOUND'?'Store package':t.kind==='OUTBOUND'?'Deliver package':'Move robot'}<small>${esc(t.sku)}</small></td><td>${esc(t.requested_robot||t.robot||'Unassigned')}</td><td>${esc(t.destination||t.requested_slot||t.slot||'—')}${t.requested_conveyor||t.conveyor?`<small>via ${esc(t.requested_conveyor||t.conveyor)}</small>`:''}</td><td><span class="status ${t.state}">${human(t.state)}</span>${t.reason?`<small>${esc(t.reason)}</small>`:''}</td><td>${time((t.completed??state.time)-t.created)}</td><td>${t.state==='QUEUED'?`<button class="text-button" data-cancel="${t.id}">Cancel</button>`:''}</td></tr>`).join('');renderWorkflow();
  const occupied=state.slots.reduce((total,s)=>total+(s.source_backed?s.source_units:Number(!!s.sku)),0),reserved=state.slots.filter(s=>s.reserved_by).length;$('#stock-count').textContent=occupied;
  const free=state.slots.filter(s=>s.validated_vacant&&!s.sku&&!s.reserved_by).length;
  $('#inventory-stats').innerHTML=`<span><b>${occupied}</b>packages</span><span><b>${free}</b>pilot slots free</span><span><b>${reserved}</b>reserved</span>`;
  $('#slot-grid').innerHTML=state.slots.map(s=>`<button class="slot ${s.reserved_by?'reserved':s.sku?'occupied':''} ${s.id===selectedSlot?'selected':''}" data-slot="${s.id}" title="${esc(s.reserved_by||s.package_id||'Free slot')}"><strong>${s.id}</strong>${s.source_backed?`${s.source_units} × `:''}${esc(s.sku||s.reserved_by||'Available')}</button>`).join('');
  const locks=['shelves','conveyors','charging','waiting'].flatMap(kind=>Object.entries(state.locks[kind]).map(([id,owner])=>`<span>${esc(id)} <b>${esc(owner)}</b></span>`));$('#lock-list').innerHTML=`<b>Resource reservations</b>${locks.join('')||'<span>No active reservations</span>'}`;
  $('#packages-empty').hidden=!!state.packages.length;$('#package-rows').innerHTML=state.packages.map(p=>`<tr><td><strong>${esc(p.id)}</strong></td><td>${esc(p.sku)}</td><td><span class="status ${p.stage}">${human(p.stage)}</span></td><td>${esc(p.stage==='DELIVERED'?'Delivery region':p.robot||p.slot||p.lane||'—')}</td><td>${time(p.stored)}</td><td>${time(p.packed)}</td><td>${time(p.delivered)}</td></tr>`).join('');
  $('#events').innerHTML=state.events.slice().reverse().map(e=>`<div class="event ${e.level}"><span class="event-time">${time(e.time)}</span><span>${esc(e.message)}</span></div>`).join('');
  $('#obstacle-count').textContent=state.obstacles.length;$('#incidents').innerHTML=state.obstacles.length?state.obstacles.map(o=>`<div class="incident"><div><strong>${esc(o.id)} · ${esc(o.category)}</strong><p>Position ${o.x.toFixed(1)}, ${o.y.toFixed(1)} m</p></div><span>${state.robots.filter(r=>r.detected_obstacles.includes(o.id)).map(r=>r.id).join(', ')||'No AMR in sensing range'}</span><button class="secondary" data-remove-obstacle="${o.id}">Clear obstacle</button></div>`).join(''):'<div class="empty-state"><strong>No temporary obstacles</strong><p>Use Place obstacle and click a traversable location in the 2D map.</p></div>';
}
function renderSlotInspector(){
  const slot=state.slots.find(s=>s.id===selectedSlot),panel=$('#slot-inspector');panel.hidden=!slot;if(!slot)return;
  const owner=state.tasks.find(t=>t.id===slot.reserved_by),queued=state.tasks.find(t=>t.state==='QUEUED'&&t.requested_slot===slot.id);
  const status=slot.reserved_by?'Reserved':slot.sku?'Occupied':slot.validated_vacant?'Available':'Unavailable';
  $('#slot-inspector-name').textContent=`${slot.id} · rack ${slot.shelf}`;
  $('#slot-inspector-state').textContent=status;
  $('#slot-inspector-state').className=`status ${slot.reserved_by?'reserved':slot.sku?'occupied':'available'}`;
  const details=[['Rack / access aisle',`${slot.shelf} · ${slot.shelf[0]}`],['Position',slot.position?slot.position.map(v=>v.toFixed(2)).join(', ')+' m':'Not measured'],['Contents',slot.source_backed?`${slot.source_units} source-model cartons · ${slot.sku||'depleted'}`:slot.sku?`${slot.sku} · ${slot.package_id}`:'Empty'],['Reservation',slot.reserved_by?`${slot.reserved_by}${owner?.robot?' · '+owner.robot:''}`:queued?`${queued.id} queued`:'None'],['Capacity',slot.source_backed?`${slot.capacity_units} cartons measured in source model`:`${slot.capacity_units} prototype package · ${slot.package_dimensions?.join(' × ')||'unknown'} m`],['Source surface',slot.source_board||'Unmapped'],['Weight limit','Not verified'],['Placement check',slot.source_backed?'Existing source-model stock':slot.validated_vacant?'Vacant source surface verified':'Unavailable']];
  $('#slot-inspector-detail').innerHTML=details.map(([label,value])=>`<div><div class="detail-label">${esc(label)}</div><div class="detail-value">${esc(value)}</div></div>`).join('');
  const canAct=(slot.sku||slot.validated_vacant)&&!slot.reserved_by&&!queued;
  $('#slot-inspector-action').hidden=!canAct;
  $('#slot-inspector-action').textContent=slot.sku?'Create retrieval job':'Create putaway job';
  $('#slot-inspector-help').textContent=slot.source_backed&&!slot.sku?'Source stock depleted.':!slot.validated_vacant&&!slot.sku?'This source surface is not validated for package placement.':slot.reserved_by?`Locked by ${slot.reserved_by}; wait for the protected operation to clear.`:queued?`${queued.id} already requests this slot.`:slot.sku?'Select an available AMR and conveyor for this package.':'Select an available AMR and enter a SKU for the measured prototype package.';
}
function plot(canvas,series,maxY){const c=canvasContext(canvas);if(!c)return;const {ctx,w,h}=c,left=35,right=w-20,top=16,bottom=h-27;ctx.clearRect(0,0,w,h);ctx.font='8px Segoe UI';ctx.textAlign='right';for(let i=0;i<5;i++){const y=top+(bottom-top)*i/4;line(ctx,[[left,y],[right,y]],'#edf2f4');ctx.fillStyle='#afbcc3';ctx.fillText(String(Math.round(maxY*(1-i/4))),left-8,y+3)}if(state.history.length<2)return;
  const start=state.history[0].time,end=state.history.at(-1).time,span=Math.max(1,end-start);ctx.textAlign='center';for(let i=0;i<4;i++){const x=left+(right-left)*i/3;ctx.fillStyle='#adb9c1';ctx.fillText(time(start+span*i/3),x,h-8)}
  series.forEach(({color,values})=>line(ctx,values.flatMap((value,i)=>Number.isFinite(value)?[[left+(right-left)*(state.history[i].time-start)/span,bottom-(bottom-top)*value/maxY]]:[]),color,1.7));
}
function renderAnalytics(){const m=state.metrics;renderBatteryLegend();$('#battery-empty').hidden=state.history.length>1;plot($('#battery-chart'),state.robots.map((r,i)=>({color:colors[i%colors.length],values:state.history.map(s=>s.battery[i])})),100);plot($('#work-chart'),[{color:'#52a28e',values:state.history.map(s=>s.completed)}],Math.max(4,m.completed));const values=[['Jobs / hour',m.throughput_per_hour?.toFixed(0)??'—',''],['Mean completion',m.mean_task_seconds?.toFixed(0)??'—','s'],['Minimum separation',m.minimum_clearance_m?.toFixed(2)??'—','m'],['Coordination wait',m.waiting_seconds.toFixed(1),'s']];$('#performance').innerHTML=values.map(([label,value,unit])=>`<div><strong>${value}<small>${unit}</small></strong><span>${label}</span></div>`).join('')}
function updateSelect(selector,items){const element=$(selector),old=element.value,existing=[...element.options].map(o=>[o.value,o.textContent,o.disabled]);if(JSON.stringify(existing)===JSON.stringify(items))return;element.innerHTML=items.map(([value,label,disabled])=>`<option value="${esc(value)}" ${disabled?'disabled':''}>${esc(label)}</option>`).join('');if([...element.options].some(o=>o.value===old&&!o.disabled))element.value=old;else element.value=[...element.options].find(o=>!o.disabled)?.value||''}
function renderDispatch(){
  const kind=$('#job-kind').value,manualQueue=new Set(state.tasks.filter(t=>t.state==='QUEUED'&&t.requested_robot).map(t=>t.requested_robot));
  updateSelect('#job-robot',state.robots.map(r=>[r.id,`${r.id} · ${r.status.replaceAll('_',' ').toLowerCase()} · ${r.battery.toFixed(0)}%`,!['IDLE','MOVING_TO_DEPOT'].includes(r.status)||r.battery<=state.config.charge_trigger||manualQueue.has(r.id)]));
  const robot=state.robots.find(r=>r.id===$('#job-robot').value),reserved=new Set(state.tasks.filter(t=>t.state==='QUEUED'&&t.requested_slot).map(t=>t.requested_slot));
  $('#job-origin').textContent=robot?`Current position: ${robot.node} (${robot.x.toFixed(1)}, ${robot.y.toFixed(1)} m) · Battery ${robot.battery.toFixed(0)}%`:'No AMR is available. Wait for a job or charging cycle to finish.';
  $('#job-slot-field').hidden=kind==='MOVE';$('#job-sku-field').hidden=kind!=='INBOUND';$('#job-conveyor-field').hidden=kind!=='OUTBOUND';$('#job-destination-field').hidden=kind!=='MOVE';
  const slots=state.slots.filter(s=>!s.reserved_by&&!reserved.has(s.id)&&(kind==='INBOUND'?!s.sku:!!s.sku));
  const slotOptions=kind==='OUTBOUND'
    ? (slots.length?slots.map(s=>[s.id,`${s.id} · ${s.sku} · aisle ${s.shelf[0]}`,false])
      : [['','No available stored packages — store one or wait for a reservation',false]])
    : slots.map(s=>[s.id,`${s.id} · empty · aisle ${s.shelf[0]}`,false]);
  updateSelect('#job-slot',slotOptions);
  updateSelect('#job-conveyor',[1,2,3].map(i=>{const id=`CONV_${i}`;return [id,`Conveyor ${i}${state.locks.conveyors[id]?' · currently reserved':''}`,false]}));
  const shelfNodes=[...new Set(state.slots.map(s=>s.shelf))];
  updateSelect('#job-destination',[...['PICKUP','PACKING','DELIVERY'].map(n=>[n,n,false]),...shelfNodes.map(n=>[n,`${n} · aisle ${n[0]}`,!!state.locks.shelves[n]])]);
  const slot=state.slots.find(s=>s.id===$('#job-slot').value),destination=$('#job-destination').value,lane=$('#job-conveyor').value;
  const shelf=kind==='MOVE'?destination:slot?.shelf;
  const centerLeg=shelf&&/^[ABC]R[1-4]$/.test(shelf)?['CENTER AISLE B',`ROW ${shelf.at(-1)} ACCESS`]:[];
  const stops=kind==='INBOUND'?[robot?.node,'PICKUP',...centerLeg,slot?.id]:kind==='OUTBOUND'?[robot?.node,...centerLeg,slot?.id,'PACKING',lane,'DELIVERY']:[robot?.node,...centerLeg,destination];
  $('#job-plan').innerHTML=`<strong>Planned stops</strong><span>${stops.filter(Boolean).map(esc).join(' → ')||'Select a robot and destination'}</span><small>${kind==='MOVE'?'Travel only; no package is transferred.':!slot?'No matching shelf slot is currently available. Store a package first or wait for a reservation to clear.':kind==='INBOUND'?'The selected AMR collects the package at pickup and stores it in the exact slot you chose.':'The selected AMR retrieves this stocked package, packs it, and deposits it on your chosen conveyor.'}</small>`;
  $('#manual-job-form button[type=submit]').disabled=!robot||(kind!=='MOVE'&&!slot)||(kind==='MOVE'&&!destination);
}
function conflictSolution(reason){if(/obstacle/i.test(reason))return 'Controller waits, then seeks a route around the reported obstacle.';if(/conveyor/i.test(reason))return 'Waiting for the chosen conveyor lane to clear.';if(/charging/i.test(reason))return 'Charging traffic waits for the protected entrance or bay.';if(/forecourt|junction|passage|reserved|yield/i.test(reason))return 'Reservation keeps robots separated; one yields or takes another safe route.';if(/No safe route/i.test(reason))return 'Route remains blocked. Clear an obstacle or conflicting reservation.';return 'Controller holds movement until the path is safe.'}
function renderConflicts(){
  const active=state.robots.filter(r=>r.block_reason||r.status==='POWER_DEPLETED'||r.charge_resume_status);
  $('#conflicts').innerHTML=active.length?active.map(r=>`<div class="conflict-item"><strong>${esc(r.id)} · ${esc(r.status.replaceAll('_',' ').toLowerCase())}</strong><span>${esc(r.block_reason|| (r.status==='POWER_DEPLETED'?'Battery depleted; movement stopped':`Charging before resuming ${r.task}`))}</span><small>${esc(r.status==='POWER_DEPLETED'?'Operator must start a new run.':r.charge_resume_status?'The assigned job remains with this robot and resumes after charging.':conflictSolution(r.block_reason))}</small></div>`).join(''):'<div class="conflict-clear">No active traffic conflicts. Robots follow the center aisle plan and keep protected separation.</div>';
  const recent=state.events.filter(e=>/Conflict resolved|recalculated route|yielding to/i.test(e.message)).at(-1);
  if(recent)$('#conflicts').innerHTML+=`<div class="conflict-recent">Latest resolution · ${time(recent.time)} · ${esc(recent.message)}</div>`;
  const r=state.robots.find(r=>r.id===selected);
  $('#sensing-summary').textContent=r?`${r.id} sensing within ${state.config.detection_radius} m: ${r.near_robots.length?r.near_robots.join(', '):'no nearby AMRs'}; ${r.detected_obstacles.length?r.detected_obstacles.join(', '):'no detected obstacles'}. Nearby objects reduce travel speed; obstructed routes are replanned.`:'';
}
function renderDecisionLog(){
  $('#decision-count').textContent=state.events.length;
  const recent=state.events.slice(-16).reverse(),signature=recent.map(e=>`${e.time}:${e.message}`).join('|');
  if(signature===lastDecisionSignature)return;
  lastDecisionSignature=signature;
  $('#decision-list').innerHTML=recent.length?recent.map(e=>`<div class="decision-entry ${esc(e.level)}"><time>${time(e.time)}</time><span>${esc(e.message)}</span></div>`).join(''):'<div class="decision-empty">Controller decisions will appear here.</div>';
}
function render(){if(!state)return;$('#sim-time').textContent=time(state.time);$('#pause').textContent=state.paused?(state.time?'▶ Resume':'▶ Start run'):'Ⅱ Pause';$('#pause').classList.toggle('running',!state.paused);$('#step').disabled=!state.paused;$('#speed').value=String(state.speed);$('#connection').textContent=state.paused?'Controller paused':'Controller running';$('#connection-dot').classList.add('online');renderMetrics();renderFleet();renderRecords();renderSlotInspector();renderAnalytics();renderDispatch();renderConflicts();renderDecisionLog();drawMap();
  if(performance.now()-lastNotice>6000){$('#notice').classList.remove('error');$('#notice').textContent=state.paused?(state.time?'Run paused. Inspect jobs, routes and measured results.':'Choose an available AMR and assign a job below, then start the controller.'):`Run active · ${state.tasks.filter(t=>t.state==='QUEUED').length} jobs waiting · ${state.robots.filter(r=>r.block_reason).length} AMRs coordinating${!state.tasks.length&&state.robots.every(r=>r.battery>state.config.charge_trigger)?' · Assign a job to see movement':''}`}
}
let refreshing=false;
async function refresh(){if(refreshing)return;refreshing=true;try{const response=await fetch('/api/state',{cache:'no-store'});if(!response.ok)throw Error('Controller unavailable');state=await response.json();if(!state.tasks.some(t=>t.id===selectedTask))selectedTask=null;if(!state.slots.some(s=>s.id===selectedSlot))selectedSlot=null;render();scene?.update(state,selected,selectedSlot)}catch(e){$('#connection').textContent='Disconnected';$('#connection-dot').classList.remove('online');notice(`Controller connection lost: ${e.message}`,true)}finally{refreshing=false}}

$('#robots').onclick=e=>{const card=e.target.closest('[data-robot]');if(card)selectRobot(card.dataset.robot)};
$('#task-rows').onclick=e=>{const cancel=e.target.closest('[data-cancel]');if(cancel){action(async()=>{await post('cancel',{task_id:cancel.dataset.cancel});notice('Queued request cancelled')});return}const row=e.target.closest('[data-task]');if(row){selectedTask=row.dataset.task;const task=state.tasks.find(t=>t.id===selectedTask);if(task.robot)selected=task.robot;render();scene?.update(state,selected,selectedSlot)}};
$('#slot-grid').onclick=e=>{const slot=e.target.closest('[data-slot]');if(slot)selectSlot(slot.dataset.slot)};
$('#slot-inspector-action').onclick=()=>{const slot=state.slots.find(s=>s.id===selectedSlot);if(!slot||slot.reserved_by||(!slot.sku&&!slot.validated_vacant))return;$('#job-kind').value=slot.sku?'OUTBOUND':'INBOUND';renderDispatch();$('#job-slot').value=slot.id;renderDispatch();$('#dispatch').scrollIntoView({block:'center'})};
$('#incidents').onclick=e=>{const b=e.target.closest('[data-remove-obstacle]');if(b)action(async()=>{await post('obstacle',{remove:b.dataset.removeObstacle});notice('Obstacle cleared; controller will recalculate routes')})};
$('#manual-job-form').onsubmit=e=>{e.preventDefault();action(async()=>{const kind=$('#job-kind').value,robot_id=$('#job-robot').value,slot_id=$('#job-slot').value,destination=$('#job-destination').value,conveyor=$('#job-conveyor').value,sku=$('#job-sku').value.trim();const result=await post('manual-job',{kind,robot_id,slot_id,destination,conveyor,sku});selectedTask=result.task_id;$('#job-message').textContent=`${result.task_id} assigned to ${robot_id}`;notice(`${result.task_id} planned for ${robot_id}. ${state.paused?'Click Start run or Resume to execute it.':'Controller is executing it.'}`)})};
$('#job-kind').onchange=renderDispatch;$('#job-robot').onchange=renderDispatch;$('#job-slot').onchange=renderDispatch;$('#job-conveyor').onchange=renderDispatch;$('#job-destination').onchange=renderDispatch;
$('#pause').onclick=()=>action(()=>post('control',{paused:!state.paused}));$('#step').onclick=()=>action(()=>post('control',{step:true}));$('#speed').onchange=()=>action(()=>post('control',{speed:Number($('#speed').value)}));
$('#add-robot').onclick=()=>action(async()=>{const result=await post('add-robot',{});selected=result.robot_id;notice(`${result.robot_id} added at ${result.charging_slot}. Fleet ${result.fleet_size}/${result.capacity}.`)});
$('#reset').onclick=()=>$('#new-run-dialog').showModal();$('#new-run-dialog').addEventListener('close',()=>{if($('#new-run-dialog').returnValue==='confirm')action(async()=>{await post('reset',{initial_battery:Number($('#initial-battery').value)});selectedTask=null;selectedSlot=null;notice('New run created. Inventory, requests and measurements start empty.')})});
$('#export').onclick=()=>action(async()=>{const report=await fetch('/api/report').then(r=>r.json());const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=`vinland-run-${report.run_id}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);notice('Measured run state, traces and events exported')});
$$('[data-view]').forEach(b=>b.onclick=()=>{if(b.dataset.view!=='3d'&&full3dActive())toggleFullscreen();setView(b.dataset.view)});$$('[data-camera]').forEach(b=>b.onclick=()=>{$$('[data-camera]').forEach(x=>x.classList.toggle('active',x===b));scene?.cameraPreset(b.dataset.camera)});
$('#fullscreen-3d').onclick=()=>toggleFullscreen().catch(e=>notice(`Could not enter full screen: ${e.message}`,true));
document.addEventListener('fullscreenchange',syncFullscreen);
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&$('#visual').classList.contains('fullscreen-fallback'))toggleFullscreen()});
$('#follow-selected').onclick=()=>{setView('3d');scene?.cameraPreset('follow');$('#operations').scrollIntoView({block:'start'})};
$$('[data-layer]').forEach(input=>input.onchange=()=>{scene?.setLayer(input.dataset.layer,input.checked);drawMap()});
$$('[data-record]').forEach(b=>b.onclick=()=>recordTab(b.dataset.record));$$('[data-section]').forEach(b=>b.onclick=()=>{$$('[data-section]').forEach(x=>x.classList.toggle('active',x===b));if(['orders','inventory'].includes(b.dataset.section)){recordTab(b.dataset.section);$('#records').scrollIntoView({block:'start'})}else $('#'+b.dataset.section).scrollIntoView({block:'start'})});
$('#log-open').onclick=()=>{recordTab('events');$('#records').scrollIntoView({block:'start'})};
$('#place-obstacle').onclick=()=>{placing=!placing;$('#place-obstacle').classList.toggle('placing',placing);$('#place-obstacle').textContent=placing?'Cancel placement':'＋ Place obstacle';if(placing){setView('2d');$('#map-help').textContent='Click a clear route to place a simulated obstacle.'}else $('#map-help').textContent='Select an AMR to inspect its route.'};
$('#map').onclick=e=>{if(!state||!$('#map')._transform)return;const rect=e.target.getBoundingClientRect(),[x,y]=$('#map')._transform.inverse(e.clientX-rect.left,e.clientY-rect.top);if(placing)action(async()=>{await post('obstacle',{x,y,category:$('#obstacle-kind').value});placing=false;$('#place-obstacle').classList.remove('placing');$('#place-obstacle').textContent='＋ Place obstacle';$('#map-help').textContent='Obstacle placement recorded.';notice('Obstacle added. Nearby robots will detect it geometrically.')});else{const nearSlot=state.slots.filter(s=>s.position).sort((a,b)=>Math.hypot(a.position[0]-x,a.position[1]-y)-Math.hypot(b.position[0]-x,b.position[1]-y))[0];if(nearSlot&&Math.hypot(nearSlot.position[0]-x,nearSlot.position[1]-y)<1.0){selectSlot(nearSlot.id);return}const nearest=state.robots.slice().sort((a,b)=>Math.hypot(a.x-x,a.y-y)-Math.hypot(b.x-x,b.y-y))[0];if(Math.hypot(nearest.x-x,nearest.y-y)<2)selectRobot(nearest.id)}};
$('#settings-open').onclick=()=>{for(const [key,value] of Object.entries(state.config)){const input=$(`#settings-form [name=${key}]`);if(input)input.value=value}$('#settings-dialog').showModal()};$('#settings-form').onsubmit=e=>{e.preventDefault();action(async()=>{const values=Object.fromEntries([...new FormData(e.target)].map(([k,v])=>[k,Number(v)]));await post('configure',values);$('#settings-dialog').close();notice('Simulation parameters applied')})};
$$('[data-close-dialog]').forEach(b=>b.onclick=()=>$('#'+b.dataset.closeDialog).close());
$('#geometry-open').onclick=()=>{const g=state.geometry;$('#geometry-detail').innerHTML=`<p>Coordinates and clearances measured from warehouse1.blend.</p><table class="geometry-table"><thead><tr><th>Aisle</th><th>Width</th><th>Remaining clearance</th></tr></thead><tbody>${Object.entries(g.aisles).map(([name,[a,b]])=>`<tr><td>${name}</td><td>${(b-a).toFixed(2)} m</td><td>${g.lane_clearances[name].toFixed(2)} m</td></tr>`).join('')}</tbody></table><div class="geometry-limit">Three parallel lanes require ${g.three_lane_required_width.toFixed(2)} m with the existing AMR footprint. These aisles use a protected single passage and measured cross aisles.</div><p class="geometry-detail-note">AMR footprint: ${state.config.robot_width} × ${state.config.robot_length} m. Detection radius: ${state.config.detection_radius} m. Charging uses the outer boundary route.</p>`;$('#geometry-dialog').showModal()};
function renderBatteryLegend(){if(!state)return;$('#battery-legend').innerHTML=state.robots.map((robot,i)=>`<span><i style="background:${colors[i%colors.length]}"></i>${esc(robot.id.slice(-2))}</span>`).join('')}
new ResizeObserver(()=>{drawMap();if(state)renderAnalytics()}).observe($('#views'));window.addEventListener('resize',()=>{drawMap();if(state)renderAnalytics()});
refresh();setInterval(refresh,500);
