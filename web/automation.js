import { WarehouseView, fleetColors } from './scene.js';

const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];
const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const elapsed = value => `${String(Math.floor(value / 60)).padStart(2,'0')}:${String(Math.floor(value % 60)).padStart(2,'0')}`;
const orderForRobot = (orders, robot) => !robot ? null : robot.task
  ? orders.find(order => order.active_task === robot.task)
  : orders.slice().reverse().find(order => order.assigned_robot === robot.id);
let current = null;
let selectedRobot = null;
let selectedSlot = null;
let selectedOrder = null;
let userSelected = false;
let sourceTouched = false;
let scene;
const visualSlot = () => selectedSlot?.endsWith('-SRC') ? `${selectedSlot.slice(0,-4)}-1` : selectedSlot;

function notice(message, error=false) {
  const element = $('#notice');
  element.hidden = false;
  element.textContent = message;
  element.classList.toggle('error', error);
}

function selectRobot(id) {
  if (!current?.warehouse.robots.some(robot => robot.id === id)) return;
  selectedRobot = id;
  userSelected = true;
  render(current);
}

function selectSlot(id) {
  if (!current?.warehouse.slots.some(slot => slot.id === id)) return;
  selectedSlot = id;
  userSelected = true;
  render(current);
}

function inspectScene(hit) {
  const panel = $('#scene-info');
  if (!hit) { panel.hidden = true; return; }
  const warehouse = current?.warehouse;
  const point = hit.point;
  const coordinates = `${point.x.toFixed(2)}, ${(-point.z).toFixed(2)}, ${point.y.toFixed(2)} m`;
  let title = hit.area?.name || 'Warehouse floor';
  let type = 'LOCATION';
  let details = [['Position', coordinates]];
  if (hit.kind === 'robot') {
    selectRobot(hit.name);
    const robot = warehouse?.robots.find(item => item.id === hit.name);
    const order = current && orderForRobot(current.orders, robot);
    type = 'AMR'; title = hit.name;
    details = [['Status', robot?.status || 'Unknown'], ['Order', order?.orderid || 'None'],
               ['Task', robot?.task || 'None'], ['Position', coordinates]];
  } else if (hit.kind === 'slot') {
    selectSlot(hit.name);
    const slot = warehouse?.slots.find(item => item.id === hit.name);
    type = 'SHELF SLOT'; title = hit.name;
    details = [['Shelf', slot?.shelf || 'Unknown'], ['Product', slot?.sku || 'Empty'],
               ['Source cartons', slot?.source_units ?? 0], ['Reservation', slot?.reserved_by || 'None']];
  } else if (hit.kind === 'source-box' || hit.kind === 'shelf') {
    const product = current?.products.find(item => item.shelf === hit.rack);
    const source = warehouse?.slots.find(item => item.id === `${hit.rack}-SRC`);
    type = hit.kind === 'source-box' ? 'SOURCE BOX' : 'SHELF';
    title = hit.rack ? `${hit.rack} · ${product?.name || 'Unmapped'}` : hit.source || 'Shelf';
    details = [['Product', product?.name || 'Unmapped'], ['Source cartons', source?.source_units ?? 0],
               ['Position', coordinates]];
    if (source) selectedSlot = source.id;
  } else if (hit.kind === 'package') {
    const pkg = warehouse?.packages.find(item => item.id === hit.name);
    type = 'PACKAGE'; title = hit.name;
    details = [['Product', pkg?.sku || 'Unknown'], ['Stage', pkg?.stage || 'Unknown'],
               ['Shelf slot', pkg?.slot || 'In transit'], ['Position', coordinates]];
  } else if (hit.kind === 'depot') {
    type = 'CHARGING STOP'; title = hit.name;
  }
  $('#scene-info-type').textContent = type;
  $('#scene-info-name').textContent = title;
  $('#scene-info-detail').innerHTML = details.map(([label,value]) => `<div><span>${esc(label)}</span><b>${esc(value)}</b></div>`).join('');
  const rect = $('#scene').getBoundingClientRect();
  panel.style.left = `${Math.max(8, Math.min(hit.event.clientX - rect.left + 12, rect.width - 292))}px`;
  panel.style.top = `${Math.max(54, Math.min(hit.event.clientY - rect.top + 12, rect.height - 210))}px`;
  panel.hidden = false;
  scene?.update(warehouse, selectedRobot, visualSlot());
}

try {
  scene = new WarehouseView($('#scene'), $('#world-labels'), selectRobot, selectSlot,
    (message, error=false) => {
      $('#model-status').textContent = message;
      $('#model-progress').textContent = message;
      if (message.startsWith('Original model loaded')) $('#model-loading').hidden = true;
      if (error) {
        $('#model-loading').querySelector('strong').textContent = 'Unable to load 3D asset';
        notice(message, true);
      }
    }, inspectScene);
} catch (error) {
  $('#model-progress').textContent = error.message;
  notice(`3D renderer unavailable: ${error.message}`, true);
}

async function post(path, body) {
  const response = await fetch(`/api/automation/${path}`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw Error(data.error || 'Request failed');
  return data;
}

function render(data) {
  current = data;
  const {orders, warehouse, source} = data;
  const active = orders.filter(order => !['COMPLETED','FAILED','WAITING_STOCK','WAITING_CAPACITY'].includes(order.status)).length;
  const waiting = orders.filter(order => order.status.startsWith('WAITING')).length;
  const completed = orders.filter(order => order.status === 'COMPLETED').length;
  const firstActive = orders.find(order => order.assigned_robot && !['COMPLETED','FAILED'].includes(order.status));
  if (!userSelected) {
    selectedRobot = firstActive?.assigned_robot || warehouse.robots[0]?.id || null;
    selectedSlot = firstActive?.assigned_slot || null;
  }
  $('#connection').textContent = 'Automation running';
  $('#connection-dot').classList.add('online');
  $('#sim-time').textContent = elapsed(warehouse.time);
  $('#metrics').innerHTML = [[orders.length,'Orders received'],[active,'In progress'],[waiting,'Waiting for stock / space'],[completed,'Completed']]
    .map(([number,label]) => `<div class="metric"><div class="metric-label">${label}</div><div class="metric-value">${number}</div></div>`).join('');
  $('#robot-count').textContent = warehouse.robots.length;
  $('#robots').innerHTML = warehouse.robots.map((robot,index) => {
    const order = orderForRobot(orders, robot);
    return `<button class="robot-card ${robot.id === selectedRobot ? 'selected' : ''}" data-robot="${esc(robot.id)}" style="--robot-color:${fleetColors[index % fleetColors.length]}"><strong>${esc(robot.id)}</strong><span class="robot-state">${esc(robot.status.replaceAll('_',' '))}</span><small>${esc(order?.orderid || robot.task || 'Available')} · ${Math.round(robot.battery)}% battery</small><div class="battery"><div style="width:${Math.max(0,Math.min(100,robot.battery))}%"></div></div></button>`;
  }).join('');
  const robot = warehouse.robots.find(item => item.id === selectedRobot);
  const robotOrder = orderForRobot(orders, robot);
  $('#scene-hud').innerHTML = robot ? `<strong>${esc(robot.id)}</strong><div class="hud-state">● ${esc(robot.status.replaceAll('_',' '))}</div><div class="hud-line"><span>Order</span><b>${esc(robotOrder?.orderid || '—')}</b></div><div class="hud-line"><span>Operation</span><b>${esc(robotOrder?.operation || '—')}</b></div><div class="hud-line"><span>Shelf</span><b>${esc(robotOrder?.assigned_slot || '—')}</b></div><div class="hud-line"><span>Battery</span><b>${Math.round(robot.battery)}%</b></div><div class="hud-line"><span>Payload</span><b>${robot.carrying ? 'Carrying' : 'Empty'}</b></div>` : '';
  $('#products').innerHTML = data.products.map(product => `<button class="product ${selectedSlot?.startsWith(`${product.shelf}-`) ? 'selected' : ''}" data-shelf="${esc(product.shelf)}"><strong>${esc(product.name)}</strong><small>${esc(product.shelf)} · ${product.occupied} stocked · ${product.source_units} from Blender</small></button>`).join('');
  $('#orders').innerHTML = orders.length ? orders.slice().reverse().map(order => `<tr data-order="${esc(order.orderid)}" class="${order.orderid === selectedOrder ? 'selected' : ''}"><td><strong>${esc(order.orderid)}</strong><small>${esc(order.ordertime)}</small></td><td>${esc(order.productname)}</td><td>${esc(order.operation)}</td><td>${order.units_completed}/${order.quantity}${order.active_task ? `<small>${esc(order.active_task)}</small>` : ''}</td><td>${esc(order.assigned_robot || 'Pending')}<small>${esc(order.assigned_slot || '—')}</small></td><td><span class="status ${esc(order.status)}">${esc(order.status.replaceAll('_',' '))}</span>${order.reason ? `<small>${esc(order.reason)}</small>` : ''}</td></tr>`).join('') : '<tr><td colspan="6">Waiting for orders.</td></tr>';
  if (!sourceTouched) { $('#source-url').value = source.url; $('#source-interval').value = source.interval_seconds; }
  $('#source-detail').textContent = `${source.enabled ? 'Polling enabled' : 'Source not configured'} · Last poll: ${source.last_poll ? new Date(source.last_poll * 1000).toLocaleString() : 'never'}${source.error ? ` · ${source.error}` : ''}`;
  $('#source-detail').classList.toggle('error', Boolean(source.error));
  if (!$('#order-product').options.length) $('#order-product').innerHTML = data.products.map(product => `<option value="${esc(product.id)}">${esc(product.name)}</option>`).join('');
  scene?.update(warehouse, selectedRobot, visualSlot());
}

let refreshing = false;
async function refresh() {
  if (refreshing) return;
  refreshing = true;
  try {
    const response = await fetch('/api/automation/state', {cache:'no-store'});
    if (!response.ok) throw Error('Controller unavailable');
    render(await response.json());
  } catch (error) {
    $('#connection').textContent = 'Disconnected';
    $('#connection-dot').classList.remove('online');
    notice(`Controller connection lost: ${error.message}`, true);
  } finally { refreshing = false; }
}

$('#robots').onclick = event => {
  const button = event.target.closest('[data-robot]');
  if (button) selectRobot(button.dataset.robot);
};
$('#products').onclick = event => {
  const button = event.target.closest('[data-shelf]');
  if (button) selectSlot(`${button.dataset.shelf}-SRC`);
};
$('#orders').onclick = event => {
  const row = event.target.closest('[data-order]');
  if (!row) return;
  const order = current?.orders.find(item => item.orderid === row.dataset.order);
  if (!order) return;
  selectedOrder = order.orderid;
  if (order.assigned_robot) selectedRobot = order.assigned_robot;
  if (order.assigned_slot) selectedSlot = order.assigned_slot;
  userSelected = true;
  render(current);
  $('#operations').scrollIntoView({block:'start'});
};
$('#scene-info-close').onclick = () => $('#scene-info').hidden = true;
$$('[data-camera]').forEach(button => button.onclick = () => {
  $$('[data-camera]').forEach(item => item.classList.toggle('active', item === button));
  scene?.cameraPreset(button.dataset.camera);
});
$$('[data-layer]').forEach(input => input.onchange = () => scene?.setLayer(input.dataset.layer, input.checked));
function fullscreenActive() { return document.fullscreenElement === $('#visual') || $('#visual').classList.contains('fullscreen-fallback'); }
function syncFullscreen() {
  const active = fullscreenActive();
  $('#fullscreen-3d').textContent = active ? '↙ Exit full screen' : '⛶ Full screen';
  $('#fullscreen-3d').setAttribute('aria-pressed', String(active));
  requestAnimationFrame(() => scene?.resize());
}
$('#fullscreen-3d').onclick = async () => {
  const visual = $('#visual');
  if (fullscreenActive()) {
    if (document.fullscreenElement === visual) await document.exitFullscreen();
    visual.classList.remove('fullscreen-fallback');
    document.body.classList.remove('fullscreen-fallback-active');
  } else {
    try { await visual.requestFullscreen(); }
    catch { visual.classList.add('fullscreen-fallback'); document.body.classList.add('fullscreen-fallback-active'); }
  }
  syncFullscreen();
};
document.addEventListener('fullscreenchange', syncFullscreen);
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && $('#visual').classList.contains('fullscreen-fallback')) {
    $('#visual').classList.remove('fullscreen-fallback');
    document.body.classList.remove('fullscreen-fallback-active');
    syncFullscreen();
  }
});
$('#source-url').addEventListener('input', () => sourceTouched = true);
$('#source-form').onsubmit = async event => {
  event.preventDefault();
  try {
    const body = {url:$('#source-url').value.trim(), interval_seconds:Number($('#source-interval').value)};
    if ($('#source-token').value) body.bearer_token = $('#source-token').value;
    const result = await post('source', body);
    $('#source-token').value = '';
    sourceTouched = false;
    notice(result.enabled ? 'Order API source saved. Polling is active.' : 'Order API source disabled.');
    await refresh();
  } catch (error) { notice(error.message, true); }
};
$('#poll-now').onclick = async () => {
  try {
    const result = await post('source/poll', {});
    notice(`Poll: ${result.accepted} new, ${result.duplicates} already imported, ${result.rejected.length} rejected.`);
    await refresh();
  } catch (error) { notice(error.message, true); }
};
function newOrder() {
  const now = new Date();
  $('#order-id').value = `ORD-${Date.now()}`;
  $('#order-time').value = new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0,16);
}
$('#order-form').onsubmit = async event => {
  event.preventDefault();
  try {
    const result = await post('orders', {orderid:$('#order-id').value.trim(),
      productname:$('#order-product').selectedOptions[0].textContent, productid:$('#order-product').value,
      ordertime:new Date($('#order-time').value).toISOString(), operation:$('#order-operation').value,
      quantity:Number($('#order-quantity').value)});
    notice(result.duplicate ? `Order ${result.orderid} was already imported.` : `Order ${result.orderid} accepted: ${result.status}.`);
    if (!result.duplicate) newOrder();
    await refresh();
  } catch (error) { notice(error.message, true); }
};

newOrder();
refresh();
setInterval(refresh, 1000);
