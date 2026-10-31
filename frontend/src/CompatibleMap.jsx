import React,{useEffect,useRef} from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

const bounds=b=>[[b[1],b[0]],[b[3],b[2]]];
function tint(color,value,max){
 const hex=color.replace('#','');if(!/^[\da-f]{6}$/i.test(hex))return color;
 const t=Math.max(0,Math.min(1,(Number(value)||0)/max));
 return '#'+[214,231,242].map((start,i)=>Math.round(start+(parseInt(hex.slice(i*2,i*2+2),16)-start)*t).toString(16).padStart(2,'0')).join('');
}

// Canvas/SVG GIS preview for machines without a usable WebGL context.
// Separate panes preserve mixed raster/vector ordering, just like the layer list.
export default function CompatibleMap({layers,selected,onSelect,fitRef,basemap,background,onReady,onError,onMove,onView}){
 const node=useRef(),map=useRef(),cache=useRef(new Map()),renderers=useRef(new Map()),display=useRef(),tiles=useRef(),first=useRef(true);
 const callbacks=useRef({onSelect,onMove,onView,onError});callbacks.current={onSelect,onMove,onView,onError};
 useEffect(()=>{
  const m=L.map(node.current,{center:[39.917,116.39],zoom:12.7,zoomSnap:.1,zoomControl:false,maxZoom:22});map.current=m;
  L.control.zoom({position:'topright'}).addTo(m);L.control.scale({imperial:false,position:'bottomleft'}).addTo(m);
  m.attributionControl.setPrefix(false);m.attributionControl.addAttribution('兼容地图');
  display.current=L.layerGroup().addTo(m);
  m.on('mousemove',e=>callbacks.current.onMove?.([e.latlng.lng,e.latlng.lat]));
  m.on('moveend',()=>{const b=m.getBounds(),c=m.getCenter();callbacks.current.onView?.({bounds:[b.getWest(),b.getSouth(),b.getEast(),b.getNorth()],zoom:m.getZoom(),center:[c.lng,c.lat]})});
  fitRef.current=value=>{const b=value?.bounds||value;if(b?.length===4&&b.every(Number.isFinite))m.fitBounds(bounds(b),{padding:[65,65],maxZoom:16,animate:false})};
  const observer=new ResizeObserver(()=>m.invalidateSize({pan:false}));observer.observe(node.current);onReady(true);
  return()=>{observer.disconnect();m.remove();map.current=null};
 },[]);
 useEffect(()=>{
  const m=map.current;if(!m)return;const controller=new AbortController();
  node.current.dataset.ready='false';
  async function draw(){
   for(const layer of layers)if(layer.kind!=='raster'&&!cache.current.has(layer.id)){
    const response=await fetch(`/api/layers/${layer.id}/data`,{signal:controller.signal});
    if(!response.ok)throw new Error('图层加载失败：'+layer.name);
    cache.current.set(layer.id,await response.json());
   }
   if(controller.signal.aborted)return;
   display.current.clearLayers();const images=[];
   for(const [index,layer] of [...layers].reverse().entries()){
    const pane='gaia-'+layer.id;
    const element=m.getPane(pane)||m.createPane(pane);element.style.zIndex=String(400+index);element.dataset.layerId=layer.id;
    if(layer.style.visible===false)continue;
    const color=layer.style.color||'#3d86b7',opacity=layer.style.opacity;
    if(layer.kind==='raster'){
     const image=L.imageOverlay(`/api/layers/${layer.id}/preview?color=${color.replace('#','')}`,bounds(layer.bounds),{pane,opacity:opacity??.85,interactive:true});
     images.push(new Promise((resolve,reject)=>{image.once('load',resolve);image.once('error',()=>reject(new Error('栅格预览加载失败：'+layer.name)))}));
     image.on('click',()=>callbacks.current.onSelect?.(layer.id));display.current.addLayer(image);continue;
    }
    if(!renderers.current.has(pane))renderers.current.set(pane,L.canvas({pane,padding:.25}));
    const renderer=renderers.current.get(pane),data=cache.current.get(layer.id),field=layer.style.field;
    let max=1;if(field)for(const f of data.features)max=Math.max(max,Number(f.properties[field])||0);
    const paint=f=>field?tint(color,f.properties[field],max):color;
    const geo=L.geoJSON(data,{pane,renderer,
     style:f=>{const point=f.geometry?.type.includes('Point');return {color:point?'white':color,weight:point?1.3:selected===layer.id?2.2:1.1,opacity:opacity??1,fillColor:paint(f),fillOpacity:opacity??(point?1:.25)}},
     pointToLayer:(f,latlng)=>L.circleMarker(latlng,{pane,renderer,radius:layer.name.includes('站')?7:4.5,color:'white',weight:1.3,fillColor:paint(f),fillOpacity:opacity??1}),
     onEachFeature:(f,item)=>{
      item.on('click',()=>callbacks.current.onSelect?.(layer.id));
      if(f.geometry?.type==='Point'&&(layer.style.labels??layer.name.includes('站'))&&data.features.length<=100){
       const text=document.createElement('span');text.textContent=f.properties.name||f.properties['名称']||'';
       item.bindTooltip(text,{permanent:true,direction:'top',offset:[0,-6],pane});
      }
     }});
    display.current.addLayer(geo);
   }
   if(first.current&&layers.length){first.current=false;const focus=layers.find(l=>l.id===selected)||layers.find(l=>l.kind==='raster')||layers.at(-1);fitRef.current?.(focus.bounds)}
   await Promise.all(images);
   requestAnimationFrame(()=>{if(!controller.signal.aborted&&node.current)node.current.dataset.ready='true'});
  }
  draw().catch(e=>{if(e.name!=='AbortError')callbacks.current.onError?.(e.message)});
  return()=>controller.abort();
 },[layers,selected]);
 useEffect(()=>{const m=map.current;if(!m)return;if(basemap){tiles.current=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap contributors',opacity:.7}).addTo(m)}return()=>{if(tiles.current){m.removeLayer(tiles.current);tiles.current=null}}},[basemap]);
 return <div ref={node} className="map-canvas compatible-map" data-renderer="leaflet" style={{background:background||'#e8ecee'}} aria-label="交互地图"/>;
}
