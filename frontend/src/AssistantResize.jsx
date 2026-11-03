import React,{useEffect,useRef,useState} from 'react';

const key='gaia-assistant-width-v1',minimum=320,maximum=760;

// Keep the pointer on a real separator; MapCanvas already observes its size.
export default function AssistantResize(){
 const handle=useRef(),drag=useRef(null),[width,setWidth]=useState(350),[limit,setLimit]=useState(maximum),[moving,setMoving]=useState(false);
 function workspace(){return handle.current?.parentElement}
 function measure(){
  const root=workspace(),folio=root?.querySelector('.layer-palette');
  const app=root?.closest('.workbench'),print=app?.dataset.view==='layout'&&app.dataset.palette!=='closed';
  return Math.max(minimum,Math.min(maximum,(root?.clientWidth||0)-(print?folio.getBoundingClientRect().width:0)-450));
 }
 function apply(value){const root=workspace();if(value===null)root.style.removeProperty('--assistant-user-width');else root.style.setProperty('--assistant-user-width',Math.round(Math.max(minimum,Math.min(measure(),value)))+'px')}
 function persist(){try{const value=workspace().style.getPropertyValue('--assistant-user-width');if(value)localStorage.setItem(key,parseInt(value,10));else localStorage.removeItem(key)}catch{}}
 function finish(commit){
  const d=drag.current;if(!d)return;drag.current=null;
  if(!commit){if(d.original)workspace().style.setProperty('--assistant-user-width',d.original);else apply(null)}
  else persist();
  workspace().removeAttribute('data-resizing');setMoving(false);
  if(handle.current.hasPointerCapture(d.id))handle.current.releasePointerCapture(d.id);
 }
 useEffect(()=>{
  try{const value=Number(localStorage.getItem(key));if(Number.isFinite(value)&&value>=minimum&&value<=maximum)workspace().style.setProperty('--assistant-user-width',value+'px')}catch{}
  const observer=new ResizeObserver(()=>{setWidth(Math.round(workspace().querySelector('.assistant-dock').getBoundingClientRect().width));setLimit(measure())});observer.observe(workspace());observer.observe(workspace().querySelector('.assistant-dock'));observer.observe(workspace().querySelector('.document-area'));
  const cancel=()=>finish(false),escape=e=>{if(e.key==='Escape')finish(false)};
  window.addEventListener('blur',cancel);window.addEventListener('keydown',escape);
  return()=>{observer.disconnect();window.removeEventListener('blur',cancel);window.removeEventListener('keydown',escape)};
 },[]);
 return <div ref={handle} className="assistant-resizer" role="separator" tabIndex={0} aria-label="调整助手宽度" aria-orientation="vertical" aria-controls="gaia-assistant" aria-valuemin={minimum} aria-valuemax={limit} aria-valuenow={width} aria-valuetext={width+' 像素'} data-active={moving||undefined} title="拖动调整助手宽度；方向键微调，双击恢复默认" onDoubleClick={()=>{apply(null);persist()}} onPointerDown={e=>{if(e.button!==0||drag.current)return;e.preventDefault();e.currentTarget.focus();e.currentTarget.setPointerCapture(e.pointerId);drag.current={id:e.pointerId,x:e.clientX,width:workspace().querySelector('.assistant-dock').getBoundingClientRect().width,original:workspace().style.getPropertyValue('--assistant-user-width')};workspace().dataset.resizing='true';setMoving(true)}} onPointerMove={e=>{const d=drag.current;if(d?.id===e.pointerId)apply(d.width+d.x-e.clientX)}} onPointerUp={e=>{if(drag.current?.id===e.pointerId)finish(true)}} onPointerCancel={()=>finish(false)} onLostPointerCapture={()=>finish(false)} onKeyDown={e=>{const step=e.shiftKey?64:24;if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();apply(width+(e.key==='ArrowLeft'?step:-step));persist()}else if(e.key==='Home'||e.key==='End'){e.preventDefault();apply(e.key==='Home'?minimum:measure());persist()}else if(e.key==='Enter'){e.preventDefault();apply(null);persist()}}}><span aria-hidden="true"/></div>;
}
