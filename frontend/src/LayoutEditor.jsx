import React,{useEffect,useRef,useState} from 'react';
import {MousePointer2,Move,ZoomIn,ZoomOut,Scan,Undo2,Redo2,Lock,Unlock,Eye,EyeOff,ArrowUp,ArrowDown,AlignLeft,AlignCenter,AlignRight,Trash2,RefreshCw} from 'lucide-react';
import {api} from './shared';

const labels={main_map:'主地图框',title:'标题',subtitle:'副标题',source:'来源说明',legend:'图例',north_arrow:'指北针',scale_bar:'比例尺',overview_map:'位置插图',overview_title:'插图标题'};
export function elementLabel(item){return labels[item.id]||item.text?.slice(0,18)||({map:'地图框',label:'文本',legend:'图例',scale:'比例尺',picture:'图片 / 指北针',shape:'图形'}[item.kind])||item.id;}

export default function LayoutEditor({layout,revision,save,onScene,selection,setSelection,command,notice}){
 const [scene,setScene]=useState(null),[nodes,setNodes]=useState([]),[error,setError]=useState(''),[loading,setLoading]=useState(false),[zoom,setZoom]=useState(1),[fit,setFit]=useState(true),[tool,setTool]=useState('select');
 const host=useRef(),svg=useRef(),drag=useRef(),history=useRef([]),future=useRef([]),current=useRef(layout),nodeRef=useRef(nodes),loadId=useRef(0);current.current=layout;nodeRef.current=nodes;
 useEffect(()=>{let cancelled=false;const id=++loadId.current;setLoading(true);setError('');api('/layout/scene').then(data=>{if(cancelled||id!==loadId.current)return;setScene(data);setNodes(data.elements);onScene(data);setLoading(false)}).catch(e=>{if(!cancelled){setError(e.message);setLoading(false)}});return()=>{cancelled=true}},[revision]);
 useEffect(()=>{if(!fit||!scene||!host.current)return;const resize=()=>setZoom(Math.max(.2,Math.min(3,(host.current.clientWidth-72)/(scene.width*3.7795),(host.current.clientHeight-120)/(scene.height*3.7795))));resize();const r=new ResizeObserver(resize);r.observe(host.current);return()=>r.disconnect()},[scene?.width,scene?.height,fit]);
 function point(e){const r=svg.current.getBoundingClientRect();return {x:(e.clientX-r.left)*scene.width/r.width,y:(e.clientY-r.top)*scene.height/r.height}}
 function selectedNodes(){return nodeRef.current.filter(x=>selection.includes(x.id))}
 async function commit(changes,record=true){
  const before=current.current.items||{};
  if(record){history.current.push(JSON.parse(JSON.stringify(before)));future.current=[]}
  const items={...before};for(const [id,value] of Object.entries(changes))items[id]={...(items[id]||{}),...value};
  current.current={...current.current,items};
  setNodes(old=>old.map(n=>changes[n.id]?{...n,...changes[n.id]}:n));
  await save({items});
 }
 async function travel(back){const from=back?history.current:future.current,to=back?future.current:history.current;if(!from.length)return;to.push(JSON.parse(JSON.stringify(current.current.items||{})));const items=from.pop();current.current={...current.current,items};await save({items})}
 function start(e,item,handle){
  if(e.button!==0||tool==='pan'||item.locked)return;
  e.stopPropagation();e.preventDefault();
  const ids=e.shiftKey?[...new Set([...selection,item.id])]:selection.includes(item.id)?selection:[item.id];setSelection(ids);
  e.currentTarget.setPointerCapture(e.pointerId);
  drag.current={start:point(e),nodes:nodeRef.current.filter(n=>ids.includes(n.id)).map(n=>({...n})),id:item.id,handle,changes:{}};
 }
 function move(e){
  const d=drag.current;if(!d||d.pan)return;const p=point(e),dx=p.x-d.start.x,dy=p.y-d.start.y,changes={};
  for(const item of d.nodes){
   let value={x:item.x+dx,y:item.y+dy};
   if(d.handle&&item.id===d.id){value={x:item.x,y:item.y,width:item.width,height:item.height};if(d.handle.includes('e'))value.width=Math.max(2,item.width+dx);if(d.handle.includes('s'))value.height=Math.max(2,item.height+dy);if(d.handle.includes('w')){value.x=item.x+dx;value.width=Math.max(2,item.width-dx)}if(d.handle.includes('n')){value.y=item.y+dy;value.height=Math.max(2,item.height-dy)}if(e.shiftKey)value.height=value.width*item.height/item.width;}
   changes[item.id]=Object.fromEntries(Object.entries(value).map(([k,v])=>[k,Math.round(v*10)/10]));
  }
  d.changes=changes;setNodes(old=>old.map(n=>changes[n.id]?{...n,...changes[n.id]}:n));
 }
 function stop(){const d=drag.current;if(!d||d.pan)return;drag.current=null;if(Object.keys(d.changes).length)commit(d.changes).catch(e=>notice(e.message))}
 useEffect(()=>{function key(e){if(e.target.closest('input,textarea,select')||!host.current?.contains(document.activeElement))return;if((e.ctrlKey||e.metaKey)&&e.key==='z'){e.preventDefault();travel(!e.shiftKey);return}if((e.ctrlKey||e.metaKey)&&e.key==='y'){e.preventDefault();travel(false);return}if(e.key==='Delete'||e.key==='Backspace'){e.preventDefault();commit(Object.fromEntries(selectedNodes().map(n=>[n.id,{visible:false}])));return}const d={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]}[e.key];if(d){e.preventDefault();const step=e.shiftKey?5:1;commit(Object.fromEntries(selectedNodes().filter(n=>!n.locked).map(n=>[n.id,{x:n.x+d[0]*step,y:n.y+d[1]*step}])))} }
 window.addEventListener('keydown',key);return()=>window.removeEventListener('keydown',key)},[selection]);
 useEffect(()=>{if(!command?.id||!scene)return;const op=command.type,selected=selectedNodes();
  if(op==='undo'){travel(true);return}if(op==='redo'){travel(false);return}
  if(op==='delete'){commit(Object.fromEntries(selected.map(n=>[n.id,{visible:false}])));return}
  if(op==='align-left'||op==='align-center'||op==='align-right'){
   if(!selected.length)return;const left=Math.min(...selected.map(n=>n.x)),right=Math.max(...selected.map(n=>n.x+n.width));commit(Object.fromEntries(selected.map(n=>[n.id,{x:op==='align-left'?left:op==='align-right'?right-n.width:(left+right-n.width)/2}])));return
  }
  if(op==='update'){commit({[command.elementId]:command.changes});return}
  if(op==='add'){
   const id=command.kind+'_'+crypto.randomUUID().slice(0,8),node={id,kind:command.kind,x:25,y:25,width:command.kind==='label'?65:35,height:command.kind==='label'?12:25,rotation:0,z:Math.max(1,...nodes.map(n=>n.z||0))+1,visible:true,locked:false,text:command.kind==='label'?'文本':'',font_size:12,color:'#222222',...(command.extra||{})};
   setNodes(old=>[...old,node]);setSelection([id]);commit({[id]:node});
  }
 },[command?.id]);
 const scale=zoom*3.7795,handle=7/scale;
 return <div className="layout-editor" ref={host} tabIndex={0} aria-label="可编辑地图布局">
  <div className="document-toolbar"><div><button className={tool==='select'?'active':''} title="选择元素" onClick={()=>setTool('select')}><MousePointer2 size={15}/></button><button className={tool==='pan'?'active':''} title="平移画布" onClick={()=>setTool('pan')}><Move size={15}/></button><span className="tool-separator"/><button title="撤销" onClick={()=>travel(true)}><Undo2 size={15}/></button><button title="重做" onClick={()=>travel(false)}><Redo2 size={15}/></button></div><span>{loading?'QGIS 正在更新布局…':scene?`${scene.width.toFixed(0)} × ${scene.height.toFixed(0)} mm`:''}</span><div><button title="缩小布局" onClick={()=>{setFit(false);setZoom(z=>Math.max(.2,z-.15))}}><ZoomOut size={15}/></button><button title="整页显示" onClick={()=>setFit(true)}><Scan size={15}/></button><button title="放大布局" onClick={()=>{setFit(false);setZoom(z=>Math.min(4,z+.15))}}><ZoomIn size={15}/></button></div></div>
  {error?<div className="document-message error"><strong>布局尚未生成</strong><p>{error}</p><small>请选择可用的制图插件及主图层。</small></div>:!scene?<div className="document-message">正在读取 QGIS 布局元素…</div>:<div className={'paper-scroll '+(tool==='pan'?'pan-tool':'')} onPointerDown={e=>{if(tool==='pan'&&e.button===0){const el=e.currentTarget;drag.current={pan:true,startX:e.clientX,startY:e.clientY,left:el.scrollLeft,top:el.scrollTop};el.setPointerCapture(e.pointerId)}}} onPointerMove={e=>{if(drag.current?.pan){e.currentTarget.scrollLeft=drag.current.left-(e.clientX-drag.current.startX);e.currentTarget.scrollTop=drag.current.top-(e.clientY-drag.current.startY)}}} onPointerUp={()=>{if(drag.current?.pan)drag.current=null}}>
   <div className="paper-stage" style={{width:scene.width*scale+64,height:scene.height*scale+64}}>
    <svg className="page-ruler horizontal" width={scene.width*scale} height="20" style={{left:32,top:8}}>{Array.from({length:Math.floor(scene.width/10)+1},(_,i)=><g key={i} transform={`translate(${i*10*scale},0)`}><path d="M0 14v6"/>{i%Math.max(1,Math.ceil(38/(10*scale)))===0&&<text x="2" y="11">{i*10}</text>}</g>)}</svg>
    <svg className="page-ruler vertical" width="20" height={scene.height*scale} style={{left:8,top:32}}>{Array.from({length:Math.floor(scene.height/10)+1},(_,i)=><g key={i} transform={`translate(0,${i*10*scale})`}><path d="M14 0h6"/>{i%Math.max(1,Math.ceil(35/(10*scale)))===0&&<text x="1" y="3">{i*10}</text>}</g>)}</svg>
    <svg ref={svg} className="layout-page" width={scene.width*scale} height={scene.height*scale} viewBox={`0 0 ${scene.width} ${scene.height}`} style={{left:32,top:32}} onPointerDown={e=>{if(e.target===e.currentTarget)setSelection([])}} onPointerMove={move} onPointerUp={stop} onPointerCancel={stop}>
     <rect width={scene.width} height={scene.height} fill="white" onPointerDown={()=>setSelection([])}/>
     {[...nodes].filter(n=>n.visible!==false).sort((a,b)=>(a.z||0)-(b.z||0)).map(n=><g key={n.id} transform={`translate(${n.x},${n.y}) rotate(${n.rotation||0})`} onPointerDown={e=>start(e,n)} className={n.locked?'layout-item locked':'layout-item'} role="button" tabIndex={-1} aria-label={'布局元素 '+elementLabel(n)}>
      {n.image_url?<image href={n.image_url} width={n.width} height={n.height} preserveAspectRatio="none"/>:n.kind==='label'?<text fontSize={(n.font_size||12)*.3528} y="5" fill={n.color||'#222'}>{n.text}</text>:<rect width={n.width} height={n.height} fill="white" stroke="#888" strokeWidth=".2"/>}
      <rect width={n.width} height={n.height} fill="transparent" stroke={selection.includes(n.id)?'var(--accent)':'transparent'} strokeWidth={1.3} vectorEffect="non-scaling-stroke"/>
      {selection.includes(n.id)&&!n.locked&&[['nw',0,0],['n',n.width/2,0],['ne',n.width,0],['e',n.width,n.height/2],['se',n.width,n.height],['s',n.width/2,n.height],['sw',0,n.height],['w',0,n.height/2]].map(([key,x,y])=><rect key={key} aria-label={'缩放 '+elementLabel(n)+' '+key} x={x-handle/2} y={y-handle/2} width={handle} height={handle} className={'resize-handle '+key} onPointerDown={e=>start(e,n,key)}/>)}
     </g>)}
    </svg>
   </div>
  </div>}
  <div className="document-footer"><span>{selection.length?`已选择 ${selection.length} 个元素`:'选择并拖动元素；拖动控制点调整大小'}</span><span>位置与尺寸：mm　{Math.round(zoom*100)}%</span></div>
 </div>
}

export function ElementProperties({nodes,selection,update}){
 const item=nodes.find(n=>n.id===selection[0]);
 if(!item)return <div className="pane-empty">在页面或内容列表中选择一个布局元素。</div>;
 return <div className="element-properties"><h3>{elementLabel(item)}</h3><fieldset><legend>位置和大小</legend><div className="field-grid">{[['x','X'],['y','Y'],['width','宽度'],['height','高度'],['rotation','旋转']].map(([key,label])=><label key={key}>{label}<div className="unit-input"><input aria-label={'元素'+label} type="number" step=".1" value={item[key]??0} onChange={e=>update(item.id,{[key]:Number(e.target.value)})}/><span>{key==='rotation'?'°':'mm'}</span></div></label>)}</div></fieldset>
 {item.kind==='label'&&<fieldset><legend>文本</legend><label>内容<textarea aria-label="元素文本" value={item.text||''} onChange={e=>update(item.id,{text:e.target.value})}/></label><div className="field-grid"><label>字号<input aria-label="元素字号" type="number" min="1" max="200" value={item.font_size||10} onChange={e=>update(item.id,{font_size:Number(e.target.value)})}/></label><label>颜色<input aria-label="元素颜色" type="color" value={item.color||'#222222'} onChange={e=>update(item.id,{color:e.target.value})}/></label></div></fieldset>}
 {item.kind==='map'&&<fieldset><legend>地图范围 · {item.map_crs}</legend><div className="field-grid">{['X 最小值','Y 最小值','X 最大值','Y 最大值'].map((label,i)=><label key={label}>{label}<input type="number" step="any" value={item.map_extent?.[i]??0} onChange={e=>{const extent=[...(item.map_extent||[0,0,1,1])];extent[i]=Number(e.target.value);update(item.id,{map_extent:extent})}}/></label>)}</div><small>调整范围可改变地图比例与中心。</small></fieldset>}
 {item.kind==='legend'&&<fieldset><legend>图例</legend><label>标题<input value={item.title||''} placeholder="使用布局中的图例标题" onChange={e=>update(item.id,{title:e.target.value})}/></label></fieldset>}
 {item.kind==='shape'&&<fieldset><legend>图形</legend><label>填充<input type="color" value={item.fill||'#ffffff'} onChange={e=>update(item.id,{fill:e.target.value})}/></label><label>边线<input type="color" value={item.color||'#293941'} onChange={e=>update(item.id,{color:e.target.value})}/></label></fieldset>}
 <fieldset><legend>显示与排列</legend><label className="check-row"><input type="checkbox" checked={item.visible!==false} onChange={e=>update(item.id,{visible:e.target.checked})}/>显示元素</label><label className="check-row"><input type="checkbox" checked={item.locked||false} onChange={e=>update(item.id,{locked:e.target.checked})}/>锁定位置</label><div className="button-row"><button onClick={()=>update(item.id,{z:(item.z||0)+1})}><ArrowUp size={14}/>上移一层</button><button onClick={()=>update(item.id,{z:(item.z||0)-1})}><ArrowDown size={14}/>下移一层</button></div></fieldset>
 <button className="danger-button" onClick={()=>update(item.id,{visible:false})}><Trash2 size={14}/>移除元素</button></div>
}
