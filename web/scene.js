import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

export const fleetColors = ['#25bfa5','#5e91f4','#eba83e','#dc7182','#aa83e8'];
const vector = (x,y,z) => new THREE.Vector3(x,z,-y);

export class WarehouseView {
  constructor(canvas, labels, onSelect, onStatus) {
    this.canvas=canvas; this.labels=labels; this.onSelect=onSelect; this.onStatus=onStatus;
    this.robotMeshes=new Map(); this.packageMeshes=new Map(); this.obstacleMeshes=new Map();
    this.intakeMeshes=new Map();
    this.robotLabels=new Map(); this.paths=new Map(); this.rings=new Map(); this.locks=new Map();
    this.stationLabels=[];
    this.selected='AMR-01'; this.state=null; this.showRoutes=true; this.showSensors=false; this.showLabels=true;
    this.scene=new THREE.Scene(); this.scene.background=new THREE.Color('#e1e9ed');
    this.renderer=new THREE.WebGLRenderer({canvas,antialias:true,powerPreference:'high-performance'});
    this.renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));
    this.renderer.outputColorSpace=THREE.SRGBColorSpace;
    this.renderer.toneMapping=THREE.ACESFilmicToneMapping; this.renderer.toneMappingExposure=1.3;
    this.camera=new THREE.PerspectiveCamera(42,1,.1,600);
    this.controls=new OrbitControls(this.camera,canvas); this.controls.enableDamping=true;
    this.controls.maxPolarAngle=Math.PI*.495; this.controls.minDistance=5; this.controls.maxDistance=240;
    this.scene.add(new THREE.HemisphereLight(0xf1faff,0x8d9693,2.1));
    const light=new THREE.DirectionalLight(0xfff1df,2.6); light.position.set(-25,60,30); this.scene.add(light);
    const fill=new THREE.DirectionalLight(0xd0e7ff,1.4);fill.position.set(30,30,-25);this.scene.add(fill);
    this.overlay=new THREE.Group();this.scene.add(this.overlay);
    this.cameraPreset('overview');
    this.controls.addEventListener('start',()=>this.preset=null);
    this.resizeObserver=new ResizeObserver(()=>this.resize());this.resizeObserver.observe(canvas.parentElement);
    this.lastFrame=performance.now(); this.follow=false;
    this.raycaster=new THREE.Raycaster();
    canvas.addEventListener('pointerdown',e=>this.pointerStart=[e.clientX,e.clientY]);
    canvas.addEventListener('pointerup',e=>this.pick(e));
    this.load();this.animate();
  }
  resize(){const r=this.canvas.parentElement.getBoundingClientRect();if(r.width<1||r.height<1)return;this.renderer.setSize(r.width,r.height,false);this.camera.aspect=r.width/r.height;this.camera.updateProjectionMatrix();if(this.preset)this.cameraPreset(this.preset)}
  async load(){
    try{
      this.manifest=await fetch('/assets/model_manifest.json').then(r=>r.json());
      this.floor=this.manifest.floor_z;
      const loader=new GLTFLoader();
      const gltf=await loader.loadAsync('/assets/warehouse.glb',e=>this.onStatus(`Loading supplied Blender model · ${e.total?Math.round(e.loaded/e.total*100)+'%':Math.round(e.loaded/1048576)+' MB'}`));
      this.model=gltf.scene;this.scene.add(this.model);this.model.updateMatrixWorld(true);
      const find=name=>{let result;this.model.traverse(o=>{if(o.name===name||o.userData.name===name)result=o});return result};
      for(const [i,[id,source]] of Object.entries(this.manifest.robots).entries()){
        const obj=find(source.node);if(!obj)throw Error(`Original robot mesh missing: ${source.source_object}`);
        obj.userData.robotId=id;obj.traverse(o=>{o.userData.robotId=id});
        this.robotMeshes.set(id,{obj,base:obj.quaternion.clone(),source,position:obj.position.clone(),target:obj.position.clone()});
        const el=document.createElement('button');el.className='world-label';el.style.setProperty('--robot-color',fleetColors[i]);el.textContent=id;el.onclick=()=>this.onSelect(id);this.labels.append(el);this.robotLabels.set(id,el);
        const ring=new THREE.Mesh(new THREE.RingGeometry(.95,1.08,48),new THREE.MeshBasicMaterial({color:fleetColors[i],side:THREE.DoubleSide,transparent:true,opacity:.95,depthWrite:false}));
        ring.rotation.x=-Math.PI/2;this.overlay.add(ring);this.rings.set(id,ring);
      }
      this.walls=(this.manifest.walls||[]).map(w=>find(w.node)).filter(Boolean);
      this.walls.forEach(w=>w.visible=false);
      this.onStatus(`Original model loaded · ${this.manifest.source_objects.toLocaleString()} source meshes`);
      this.ready=true;if(this.state)this.update(this.state,this.selected);
    }catch(e){this.error=e.message;this.onStatus(`3D asset error: ${e.message}`,true)}
  }
  pick(e){
    if(!this.ready||!this.pointerStart||Math.hypot(e.clientX-this.pointerStart[0],e.clientY-this.pointerStart[1])>5)return;
    const rect=this.canvas.getBoundingClientRect();this.raycaster.setFromCamera(new THREE.Vector2((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1),this.camera);
    const hit=this.raycaster.intersectObjects([...this.robotMeshes.values()].map(r=>r.obj),true)[0];
    if(hit?.object.userData.robotId)this.onSelect(hit.object.userData.robotId);
  }
  cameraPreset(name){
    this.preset=name;
    this.follow=name==='follow';
    const positions={overview:[[43,62,70],[-4,2,17]],top:[[-4,87,17],[-4,2,17]],stations:[[18,28,13],[-5,2,-10]],charging:[[8,26,68],[-14,2,45]]};
    if(positions[name]){this.controls.target.set(...positions[name][1]);const eye=new THREE.Vector3(...positions[name][0]);const fit=Math.max(1,(name==='top'?.65:1.15)/this.camera.aspect);this.camera.position.copy(this.controls.target.clone().add(eye.sub(this.controls.target).multiplyScalar(fit)));this.controls.update()}
  }
  setLayer(layer,value){
    if(layer==='walls')this.walls?.forEach(w=>w.visible=value);
    if(layer==='routes')this.showRoutes=value;
    if(layer==='sensors')this.showSensors=value;
    if(layer==='labels')this.showLabels=value;
    if(this.state)this.update(this.state,this.selected);
  }
  line(key,points,color,kind='path'){
    const store=kind==='path'?this.paths:this.locks;
    let line=store.get(key);
    if(!line){line=new THREE.Line(new THREE.BufferGeometry(),new THREE.LineBasicMaterial({color,transparent:true,opacity:.85,depthTest:false}));line.renderOrder=3;this.overlay.add(line);store.set(key,line)}
    const hash=JSON.stringify(points);
    if(line.userData.hash!==hash){line.geometry.dispose();line.geometry=new THREE.BufferGeometry().setFromPoints(points.map(p=>vector(...p)));line.userData.hash=hash}
    line.material.color.set(color);return line;
  }
  update(state,selected){
    this.state=state;this.selected=selected;if(!this.ready)return;
    const floor=this.floor+.04;
    if(!this.zoneGroup){
      this.zoneGroup=new THREE.Group();this.overlay.add(this.zoneGroup);
      const zoneColors={pickup:'#579fd3',delivery:'#d77e83',charging:'#56b995'};
      for(const [name,b] of Object.entries(state.geometry.zones)){
        const plane=new THREE.Mesh(new THREE.PlaneGeometry(b[2]-b[0],b[3]-b[1]),new THREE.MeshBasicMaterial({color:zoneColors[name],transparent:true,opacity:.15,side:THREE.DoubleSide,depthWrite:false}));
        plane.rotation.x=-Math.PI/2;plane.position.copy(vector((b[0]+b[2])/2,(b[1]+b[3])/2,this.floor+.018));this.zoneGroup.add(plane);
      }
      for(const [name,nodeId] of [['PICKUP','PICKUP'],['PACKING','PACKING'],['DELIVERY','DELIVERY'],['CHARGING','CHARGE_1']]){
        const n=state.geometry.nodes.find(p=>p.id===nodeId),el=document.createElement('div');el.className='station-label';el.textContent=name;this.labels.append(el);this.stationLabels.push({el,position:vector(n.x,n.y+.9,this.floor+1)});
      }
    }
    const nodes=new Map(state.geometry.nodes.map(n=>[n.id,n]));
    for(const [i,r] of state.robots.entries()){
      const data=this.robotMeshes.get(r.id);if(!data)continue;
      const source=data.source;
      const z=this.floor+source.position[2]-source.bounds[2]+.015;
      data.target.copy(vector(r.x,r.y,z));
      if(this.lastRun!==state.run_id)data.obj.position.copy(data.target);
      const yaw=new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),-(r.heading-Math.PI/2-source.rotation_z));
      data.obj.quaternion.copy(yaw.multiply(data.base));
      const ring=this.rings.get(r.id);ring.position.copy(vector(r.x,r.y,floor));ring.scale.setScalar((r.id===selected?1.35:1)*(r.status==='CHARGING'?1+.06*Math.sin(state.time*2):1));
      ring.material.color.set(r.block_reason?'#f17149':r.status==='CHARGING'?'#34c477':fleetColors[i]);
      const points=[[r.x,r.y,floor+.02],...r.route.map(id=>nodes.get(id)).filter(Boolean).map(n=>[n.x,n.y,floor+.02])];
      this.line(r.id,points.length>1?points:[points[0],points[0]],fleetColors[i]).visible=this.showRoutes;
      const el=this.robotLabels.get(r.id);el.classList.toggle('selected',r.id===selected);el.textContent=`${r.id} · ${Math.round(r.battery)}%`;
      let sensor=this.locks.get('sensor-'+r.id);
      if(!sensor){const pts=Array.from({length:65},(_,j)=>[r.x+5*Math.cos(j/64*Math.PI*2),r.y+5*Math.sin(j/64*Math.PI*2),floor]);sensor=this.line('sensor-'+r.id,pts,fleetColors[i],'lock')}
      sensor.position.copy(vector(r.x,r.y,0));
      // Sensor geometry is relative to its own robot.
      if(!sensor.userData.relative){sensor.geometry.dispose();sensor.geometry=new THREE.BufferGeometry().setFromPoints(Array.from({length:65},(_,j)=>vector(5*Math.cos(j/64*Math.PI*2),5*Math.sin(j/64*Math.PI*2),floor)));sensor.userData.relative=true}
      sensor.material.color.set(r.detected_obstacles.length||r.near_robots.length?'#ef875e':fleetColors[i]);
      sensor.visible=this.showSensors;
    }
    this.lastRun=state.run_id;
    this.updatePackages(state);
    const intake=state.tasks.filter(t=>t.kind==='INBOUND').slice(0,24),intakeIds=new Set();
    intake.forEach((task,i)=>{intakeIds.add(task.id);let mesh=this.intakeMeshes.get(task.id);if(!mesh){mesh=this.createPackage('intake-'+task.id);this.packageMeshes.delete('intake-'+task.id);this.intakeMeshes.set(task.id,mesh)}mesh.position.copy(vector(-17.25+i%3*.75,12.9-Math.floor(i/3)%2*.75,this.floor+.25+Math.floor(i/6)*.5))});
    for(const [id,obj] of this.intakeMeshes)if(!intakeIds.has(id)){this.overlay.remove(obj);obj.traverse(o=>{o.geometry?.dispose();o.material?.dispose()});this.intakeMeshes.delete(id)}
    this.updateObstacles(state);
    const used=new Set();
    const boxOutline=(key,x,y,width,length,color)=>{used.add(key);this.line(key,[[x-width/2,y-length/2,floor],[x+width/2,y-length/2,floor],[x+width/2,y+length/2,floor],[x-width/2,y+length/2,floor],[x-width/2,y-length/2,floor]],color,'lock').visible=true};
    for(const [shelf] of Object.entries(state.locks.shelves)){const n=nodes.get(shelf);boxOutline('shelf-'+shelf,n.x,n.y,2,3,'#e9ab34')}
    for(const lane of Object.keys(state.locks.conveyors)){const n=nodes.get(lane);boxOutline('conveyor-'+lane,n.x,n.y,2.2,2.6,'#ae80ff')}
    for(const bay of Object.keys(state.locks.charging)){const n=nodes.get(bay);boxOutline('charge-'+bay,n.x,n.y,2.1,2.6,'#1dbf86')}
    for(const wait of Object.keys(state.locks.waiting)){const n=nodes.get(wait);boxOutline('wait-'+wait,n.x,n.y,2.3,2.5,'#e98e32')}
    for(const junction of Object.keys(state.locks.junctions)){const n=nodes.get(junction);boxOutline('junction-'+junction,n.x,n.y,3.5,3.5,'#ef7d61')}
    for(const [key,obj] of this.locks)if(!key.startsWith('sensor-')&&!used.has(key))obj.visible=false;
  }
  createPackage(id){
    const mat=new THREE.MeshStandardMaterial({color:0xd5a363,roughness:.75,metalness:0});
    const mesh=new THREE.Mesh(new THREE.BoxGeometry(.64,.48,.64),mat);
    const edge=new THREE.LineSegments(new THREE.EdgesGeometry(mesh.geometry),new THREE.LineBasicMaterial({color:0x68462f}));mesh.add(edge);
    const tape=new THREE.Mesh(new THREE.BoxGeometry(.12,.012,.65),new THREE.MeshStandardMaterial({color:0xf2dcb4}));tape.position.y=.246;mesh.add(tape);
    this.overlay.add(mesh);this.packageMeshes.set(id,mesh);return mesh;
  }
  packagePosition(pkg,state){
    if(pkg.position)return vector(...pkg.position);
    const robot=state.robots.find(r=>r.id===pkg.robot);
    if(robot){
      const payload=vector(robot.x,robot.y,this.floor+.87);
      if(robot.status==='STORING_PACKAGE'&&robot.slot&&this.manifest.slots[robot.slot])return payload.lerp(vector(...this.manifest.slots[robot.slot].position),robot.action_progress);
      return payload;
    }
    if(pkg.stage==='STORED'){
      const point=this.manifest.slots[pkg.slot]?.position;if(!point)return null;
      const p=vector(...point);
      const retrieving=state.robots.find(r=>r.status==='RETRIEVING_PACKAGE'&&r.slot===pkg.slot);
      if(retrieving)p.lerp(vector(retrieving.x,retrieving.y,this.floor+.87),retrieving.action_progress);
      return p;
    }
    if(pkg.stage==='CONVEYOR'){
      const moving=state.conveyor_packages.find(p=>p.id===pkg.id);if(!moving)return null;
      const x={CONV_1:-8,CONV_2:-3.8,CONV_3:-.3}[moving.lane];return vector(x+(1.45-x)*moving.progress,13.3,2.31);
    }
    if(pkg.stage==='DELIVERED'){
      const delivered=state.packages.filter(p=>p.stage==='DELIVERED');const index=delivered.findIndex(p=>p.id===pkg.id);
      return vector(2.5+index%6*.8,11.5-Math.floor(index/6)%3*.85,this.floor+.25);
    }
    return null;
  }
  updatePackages(state){
    const active=new Set();
    for(const pkg of state.packages){const position=this.packagePosition(pkg,state);if(!position)continue;active.add(pkg.id);const mesh=this.packageMeshes.get(pkg.id)||this.createPackage(pkg.id);mesh.visible=true;mesh.position.copy(position);mesh.material.color.set(pkg.stage==='PACKING'?'#8bbbc8':pkg.stage==='PACKED'?'#80c7b6':'#d5a363')}
    for(const [id,obj] of this.packageMeshes)if(!active.has(id)){this.overlay.remove(obj);obj.geometry.dispose();obj.material.dispose();this.packageMeshes.delete(id)}
  }
  updateObstacles(state){
    const active=new Set();
    for(const o of state.obstacles){
      active.add(o.id);let mesh=this.obstacleMeshes.get(o.id);
      if(!mesh){mesh=new THREE.Group();const material=new THREE.MeshStandardMaterial({color:o.category==='human'?0xdf765b:0xeea852,roughness:.8});
        if(o.category==='human'){const torso=new THREE.Mesh(new THREE.CylinderGeometry(.2,.28,.8,12),material);torso.position.y=.95;mesh.add(torso);const head=new THREE.Mesh(new THREE.SphereGeometry(.19,12,8),material);head.position.y=1.6;mesh.add(head);for(const x of [-.13,.13]){const leg=new THREE.Mesh(new THREE.CylinderGeometry(.085,.085,.7,8),material);leg.position.set(x,.35,0);mesh.add(leg)}}
        else{const body=new THREE.Mesh(new THREE.BoxGeometry(.8,o.category==='equipment'?1.3:.45,.8),material);body.position.y=o.category==='equipment'?.65:.225;mesh.add(body)}
        const ring=new THREE.Mesh(new THREE.RingGeometry(1.65,1.8,48),new THREE.MeshBasicMaterial({color:0xef754f,side:THREE.DoubleSide,transparent:true,opacity:.6}));ring.rotation.x=-Math.PI/2;ring.position.y=.04;mesh.add(ring);this.overlay.add(mesh);this.obstacleMeshes.set(o.id,mesh)}
      mesh.position.copy(vector(o.x,o.y,this.floor));
    }
    for(const [id,obj] of this.obstacleMeshes)if(!active.has(id)){this.overlay.remove(obj);obj.traverse(o=>{if(o.geometry)o.geometry.dispose();if(o.material)o.material.dispose()});this.obstacleMeshes.delete(id)}
  }
  animate(){
    requestAnimationFrame(()=>this.animate());const now=performance.now();const dt=Math.min((now-this.lastFrame)/1000,.1);this.lastFrame=now;
    if(this.canvas.clientWidth<2||this.canvas.clientHeight<2||document.hidden)return;
    for(const data of this.robotMeshes.values())data.obj.position.lerp(data.target,1-Math.exp(-dt*16));
    if(this.follow&&this.robotMeshes.has(this.selected)){
      const p=this.robotMeshes.get(this.selected).obj.position;
      const delta=p.clone().sub(this.controls.target);this.camera.position.add(delta.multiplyScalar(.06));this.controls.target.lerp(p,.06);
    }
    this.controls.update();this.renderer.render(this.scene,this.camera);
    for(const [id,el] of this.robotLabels){const data=this.robotMeshes.get(id);const pos=data.obj.position.clone();pos.y+=1.5;pos.project(this.camera);
      el.style.display=this.showLabels&&pos.z>-1&&pos.z<1&&Math.abs(pos.x)<1&&Math.abs(pos.y)<1?'block':'none';
      el.style.left=`${(pos.x*.5+.5)*this.canvas.clientWidth}px`;el.style.top=`${(-pos.y*.5+.5)*this.canvas.clientHeight}px`;
    }
    for(const {el,position} of this.stationLabels){const p=position.clone().project(this.camera);el.style.display=this.showLabels&&p.z>-1&&p.z<1&&Math.abs(p.x)<1&&Math.abs(p.y)<1?'block':'none';el.style.left=`${(p.x*.5+.5)*this.canvas.clientWidth}px`;el.style.top=`${(-p.y*.5+.5)*this.canvas.clientHeight}px`}
  }
}
