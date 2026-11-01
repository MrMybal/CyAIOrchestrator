import * as THREE from './three/three.module.js';
import {OrbitControls} from './three/OrbitControls.js';
import {GLTFLoader} from './three/GLTFLoader.js';
import {OBJLoader} from './three/OBJLoader.js';
import {STLLoader} from './three/STLLoader.js';
import {RoomEnvironment} from './three/RoomEnvironment.js';
import {PLYLoader} from './three/PLYLoader.js';
export async function openMesh(input){
 const dialog=document.createElement('dialog');dialog.className='media-viewer mesh-viewer';
 dialog.innerHTML=ui('<header><strong></strong><div class="row-actions"><button data-fit>Recentrer</button><button data-wire aria-pressed="false">Filaire</button><button data-open>Ouvrir avec Windows</button><button data-reveal>Explorateur</button><button data-close aria-label="Fermer">✕</button></div></header><div class="mesh-options"><label>Fond<select data-background><option value="dark">Sombre</option><option value="gray">Gris neutre</option><option value="white">Blanc</option><option value="blue">Bleu nuit</option><option value="studio">Environnement studio</option></select></label><label>Éclairage<select data-lighting><option value="studio">Studio PBR</option><option value="soft">Doux</option><option value="contrast">Contrasté</option><option value="day">Lumière du jour</option></select></label><label>Exposition<input data-exposure type="range" min="0.25" max="3" step="0.05" value="1"></label><label>Rotation lumière<input data-rotation type="range" min="0" max="360" step="1" value="0"></label></div><div class="mesh-stage"></div><p role="status">Chargement du mesh…</p>');
 dialog.querySelector('strong').textContent=input.name||input.path;
 const stage=dialog.querySelector('.mesh-stage'),note=dialog.querySelector('p'),previous=document.activeElement;
 const data={conversation_id:input.conversation,...(input.id?{id:input.id}:{path:input.path})};
 for(const [sel,op] of [['[data-open]','open_local'],['[data-reveal]','reveal_local']])dialog.querySelector(sel).onclick=async()=>{try{await action(op,data);}catch(e){note.textContent=e.message;note.className='media-error';}};
 let renderer,controls,observer,scene,environmentTarget,pmrem,closed=false;
 const dispose=object=>object?.traverse(o=>{o.geometry?.dispose();for(const m of Array.isArray(o.material)?o.material:o.material?[o.material]:[]){for(const value of Object.values(m))if(value?.isTexture){value.source?.data?.close?.();value.dispose();}m.dispose();}});
 dialog.querySelector('[data-close]').onclick=()=>dialog.close();
 dialog.addEventListener('close',()=>{closed=true;observer?.disconnect();controls?.dispose();renderer?.setAnimationLoop(null);dispose(scene);environmentTarget?.dispose();pmrem?.dispose();renderer?.dispose();renderer?.forceContextLoss();dialog.remove();previous?.focus();},{once:true});
 document.body.append(dialog);dialog.showModal();
 try{
  const asset=input.id?{url:'/media/'+input.id,name:input.name}:await action('preview_local',data);
  if(closed)return;
  renderer=new THREE.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.outputColorSpace=THREE.SRGBColorSpace;stage.append(renderer.domElement);
  scene=new THREE.Scene();scene.background=new THREE.Color(0x151922);
  const camera=new THREE.PerspectiveCamera(45,1,.01,10000);controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;
  const room=new RoomEnvironment();pmrem=new THREE.PMREMGenerator(renderer);environmentTarget=pmrem.fromScene(room,.04);room.dispose();scene.environment=environmentTarget.texture;
  const hemi=new THREE.HemisphereLight(0xffffff,0x586079,.5),light=new THREE.DirectionalLight(0xffffff,2),fill=new THREE.DirectionalLight(0xb4ceff,1);scene.add(hemi,light,fill,light.target,fill.target);
  let focus=new THREE.Vector3(),lightRadius=5;
  const applyLighting=()=>{
   const mode=dialog.querySelector('[data-lighting]').value,preset={studio:[1,.5,2,1,0xffffff],soft:[1.5,1,.6,.5,0xffffff],contrast:[.25,.1,4,.2,0xffdfb4],day:[1.1,1.5,3,.6,0xfff1d6]}[mode];
   scene.environmentIntensity=preset[0];hemi.intensity=preset[1];light.intensity=preset[2];fill.intensity=preset[3];light.color.setHex(preset[4]);hemi.color.setHex(mode==='day'?0xb5d7ff:0xffffff);
   const angle=Number(dialog.querySelector('[data-rotation]').value)*Math.PI/180;scene.environmentRotation.y=angle;scene.backgroundRotation.y=angle;
   light.position.copy(focus).add(new THREE.Vector3(Math.cos(angle),1.5,Math.sin(angle)).multiplyScalar(lightRadius));fill.position.copy(focus).add(new THREE.Vector3(-Math.cos(angle),.3,-Math.sin(angle)).multiplyScalar(lightRadius));light.target.position.copy(focus);fill.target.position.copy(focus);
   renderer.toneMappingExposure=Number(dialog.querySelector('[data-exposure]').value);
   const background=dialog.querySelector('[data-background]').value;scene.background=background==='studio'?environmentTarget.texture:new THREE.Color({dark:0x151922,gray:0x707070,white:0xf5f5f5,blue:0x09182e}[background]);scene.backgroundBlurriness=.35;
  };
  dialog.querySelectorAll('.mesh-options select,.mesh-options input').forEach(el=>el.addEventListener('input',applyLighting));applyLighting();
  const response=await fetch(asset.url);if(!response.ok)throw Error(ui('Fichier inaccessible : ')+response.status);const buffer=await response.arrayBuffer();
  const ext=asset.name.split('.').pop().toLowerCase();let object;
  if(ext==='glb'||ext==='gltf'){
   const manager=new THREE.LoadingManager();manager.setURLModifier(url=>{if(url.startsWith('data:')||url.startsWith('blob:'))return url;throw Error(ui('Ce modèle utilise des fichiers externes. Exportez un GLB avec textures intégrées, ou ouvrez-le avec Windows.'));});
   object=(await new GLTFLoader(manager).parseAsync(buffer,'')).scene;
  }else if(ext==='obj')object=new OBJLoader().parse(new TextDecoder().decode(buffer));
  else{const geometry=ext==='stl'?new STLLoader().parse(buffer):new PLYLoader().parse(buffer);geometry.computeVertexNormals();object=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color:0xc4cbdc,roughness:.65,side:THREE.DoubleSide,vertexColors:!!geometry.getAttribute('color')}));}
  if(closed){dispose(object);return;}
  scene.add(object);const box=new THREE.Box3().setFromObject(object);if(box.isEmpty())throw Error(ui('Le fichier ne contient pas de géométrie affichable.'));
  const center=box.getCenter(new THREE.Vector3()),size=box.getSize(new THREE.Vector3()),radius=Math.max(size.length()/2,.001);
  focus.copy(center);lightRadius=radius*3;applyLighting();
  const fit=()=>{controls.target.copy(center);camera.position.copy(center).add(new THREE.Vector3(1,.7,1).normalize().multiplyScalar(radius/Math.sin(Math.PI/8)*Math.max(1,1/camera.aspect)));camera.near=radius/1000;camera.far=radius*1000;camera.updateProjectionMatrix();controls.update();};
  observer=new ResizeObserver(()=>{const w=stage.clientWidth,h=stage.clientHeight;if(!w||!h)return;renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix();});observer.observe(stage);
  renderer.setSize(stage.clientWidth,stage.clientHeight);camera.aspect=stage.clientWidth/stage.clientHeight;fit();
  dialog.querySelector('[data-fit]').onclick=fit;dialog.querySelector('[data-wire]').onclick=e=>{const on=e.currentTarget.getAttribute('aria-pressed')!=='true';e.currentTarget.setAttribute('aria-pressed',String(on));object.traverse(o=>{for(const m of Array.isArray(o.material)?o.material:o.material?[o.material]:[]){m.wireframe=on;}});};
  let triangles=0;object.traverse(o=>{if(o.isMesh)triangles+=(o.geometry.index?.count||o.geometry.attributes.position?.count||0)/3;});
  note.textContent=Math.round(triangles).toLocaleString(CYAI_FORMAT_LOCALE)+ui(' triangles · PBR : matériaux et textures intégrées du GLB/glTF · Glisser : rotation · Molette : zoom · Clic droit : déplacement')+(ext==='obj'?ui(' · Géométrie OBJ, matériaux MTL non chargés'):'');
  renderer.setAnimationLoop(()=>{controls.update();renderer.render(scene,camera);});
 }catch(error){if(!closed){note.textContent=ui('Aperçu 3D indisponible : ')+error.message;note.className='media-error';}}
}
