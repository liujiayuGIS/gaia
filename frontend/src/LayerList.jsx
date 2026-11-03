import React,{useEffect,useRef,useState} from 'react';
import {ArrowUp,ArrowDown,GripVertical,Eye,EyeOff,Trash2} from 'lucide-react';

export default function LayerList({layers,selected,onSelect,onFit,onStyle,onVisibility,onReorder,onRemove,saving,removing}){
 const list=useRef(),drag=useRef(null),frame=useRef(),latest=useRef(layers);
 const [gesture,setGesture]=useState(null),[announcement,setAnnouncement]=useState('');
 latest.current=layers;
 const index=layers.findIndex(l=>l.id===selected);
 function clear(){
  const d=drag.current;drag.current=null;cancelAnimationFrame(frame.current);setGesture(null);
  if(d?.handle.hasPointerCapture(d.pointerId))d.handle.releasePointerCapture(d.pointerId);
 }
 useEffect(()=>{const cancel=()=>clear();const key=e=>{if(e.key==='Escape')clear()};window.addEventListener('blur',cancel);window.addEventListener('keydown',key);return()=>{window.removeEventListener('blur',cancel);window.removeEventListener('keydown',key);cancelAnimationFrame(frame.current)}},[]);
 // Never commit a gesture against a list changed by an import or agent run.
 useEffect(()=>{if(drag.current&&drag.current.ids!==layers.map(l=>l.id).join(','))clear()},[layers]);
 async function commit(ids,id){
  if(ids.every((value,i)=>value===latest.current[i]?.id))return;
  const name=latest.current.find(l=>l.id===id)?.name||'图层';
  if(await onReorder(ids))setAnnouncement(`${name}已移至第 ${ids.indexOf(id)+1} 层，共 ${ids.length} 层。`);
 }
 function move(id,to){
  if(saving)return;
  const ids=layers.map(l=>l.id),from=ids.indexOf(id);if(from<0||to<0||to>=ids.length)return;
  ids.splice(from,1);ids.splice(to,0,id);commit(ids,id);
 }
 function locate(){
  const d=drag.current;if(!d?.active)return;
  const bounds=list.current.parentElement.getBoundingClientRect();
  d.inside=d.x>=bounds.left&&d.x<=bounds.right&&d.y>=bounds.top&&d.y<=bounds.bottom;
  const rows=[...list.current.querySelectorAll('[data-layer-id]')].filter(el=>el.dataset.layerId!==d.id);
  d.before=rows.find(el=>d.y<el.getBoundingClientRect().top+el.getBoundingClientRect().height/2)?.dataset.layerId||null;
  setGesture({id:d.id,before:d.before,inside:d.inside,last:rows.at(-1)?.dataset.layerId});
 }
 function scroll(){
  const d=drag.current;if(!d?.active)return;
  const parent=list.current.parentElement,b=parent.getBoundingClientRect();
  if(d.x>=b.left&&d.x<=b.right){const delta=d.y<b.top+32?-8:d.y>b.bottom-32?8:0;if(delta){parent.scrollTop+=delta;locate()}}
  frame.current=requestAnimationFrame(scroll);
 }
 function start(e,id){
  if(saving||layers.length<2||e.button!==0||drag.current)return;
  const handle=e.currentTarget;handle.setPointerCapture(e.pointerId);handle.focus();
  drag.current={id,pointerId:e.pointerId,handle,startY:e.clientY,x:e.clientX,y:e.clientY,active:false,ids:layers.map(l=>l.id).join(',')};
 }
 function track(e){
  const d=drag.current;if(!d||d.pointerId!==e.pointerId)return;
  d.x=e.clientX;d.y=e.clientY;
  if(!d.active&&Math.abs(d.y-d.startY)>5){d.active=true;onSelect(d.id);frame.current=requestAnimationFrame(scroll)}
  locate();
 }
 function end(e){
  const d=drag.current;if(!d||d.pointerId!==e.pointerId)return;
  if(d.active&&d.inside){const ids=latest.current.map(l=>l.id).filter(id=>id!==d.id);ids.splice(d.before?ids.indexOf(d.before):ids.length,0,d.id);commit(ids,d.id)}
  clear();
 }
 return <>
  <div className="layer-order-toolbar"><span id="layer-order-hint">{saving?'正在保存顺序…':'上方图层优先显示'}</span><button title="上移图层" aria-label="上移图层" disabled={saving||index<=0} onClick={()=>move(selected,index-1)}><ArrowUp size={14}/></button><button title="下移图层" aria-label="下移图层" disabled={saving||index<0||index>=layers.length-1} onClick={()=>move(selected,index+1)}><ArrowDown size={14}/></button></div>
  <div ref={list} className="layer-list" aria-label="图层绘制顺序" aria-busy={saving}>
   {layers.map((l,i)=><div key={l.id} data-layer-id={l.id} className={'layer-entry '+(selected===l.id?'selected ':'')+(gesture?.id===l.id?'dragging ':'')+(gesture?.inside&&gesture.before===l.id?'drop-before ':'')+(gesture?.inside&&!gesture.before&&gesture.last===l.id?'drop-after ':'')}>
    <div className="tree-row">
     <button className="layer-drag-handle" aria-label={'调整 '+l.name+' 的顺序'} aria-describedby="layer-order-hint" aria-keyshortcuts="ArrowUp ArrowDown Home End" title="拖动排序；也可用方向键、Home / End 调整" aria-disabled={saving||layers.length<2} onPointerDown={e=>start(e,l.id)} onPointerMove={track} onPointerUp={end} onPointerCancel={e=>{if(drag.current?.pointerId===e.pointerId)clear()}} onLostPointerCapture={e=>{if(drag.current?.pointerId===e.pointerId)clear()}} onKeyDown={e=>{const to={ArrowUp:i-1,ArrowDown:i+1,Home:0,End:layers.length-1}[e.key];if(to!==undefined){e.preventDefault();onSelect(l.id);move(l.id,to)}}}><GripVertical size={14}/></button>
     <button className="visibility" aria-label={'显示 '+l.name} onClick={()=>onVisibility(l)}>{l.style.visible!==false?<Eye size={14}/>:<EyeOff size={14}/>}</button>
     <button className="tree-name" title={l.name} onClick={()=>onSelect(l.id)} onDoubleClick={()=>onFit(l)}><span>{l.name}</span></button>
     <button className="layer-remove" aria-label={'删除图层 '+l.name} title="删除图层（源数据保留，可撤销）" disabled={saving||removing} onClick={()=>onRemove(l)}><Trash2 size={14}/></button>
    </div>
    <button className="layer-symbol" onClick={()=>onStyle(l.id)}><i style={{background:l.style.color}}/><span>{l.kind==='raster'?'栅格影像':l.geometry_types?.join(' / ')}{l.kind!=='raster'&&' · '+l.count+' 要素'}</span></button>
   </div>)}
  </div>
  <span className="visually-hidden" role="status" aria-live="polite">{announcement}</span>
 </>;
}
