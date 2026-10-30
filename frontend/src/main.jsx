import React, {useEffect, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import maplibregl from 'maplibre-gl';
import {ArrowDownToLine, ArrowUp, Check, ChevronDown, ChevronRight, CircleHelp, Clock3, Crosshair, Database, Eye, EyeOff, FileUp, Focus, Layers3, LoaderCircle, Map as MapIcon, MessageSquare, MoreHorizontal, Plus, Settings2, ShieldCheck, Sparkles, Square, Terminal, X} from 'lucide-react';
import 'maplibre-gl/dist/maplibre-gl.css';
import './style.css';

async function api(path, options={}) {
  let response;
  try {
    response=await fetch('/api'+path,{...options,headers:options.body instanceof FormData?{}:{'Content-Type':'application/json',...options.headers}});
  } catch {
    throw new Error('本地服务未连接。请运行项目里的 start.sh，启动后重试。');
  }
  let data;
  try {
    data=await response.json();
  } catch {
    throw new Error(`本地服务返回了无法识别的响应（HTTP ${response.status}），请检查服务是否正常。`);
  }
  if(!response.ok) throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail||data));
  return data;
}
const post=(path,data={})=>api(path,{method:'POST',body:JSON.stringify(data)});
const toolNames={list_layers:'读取工作区图层',inspect_layer:'检查输入数据',buffer_points:'计算直线缓冲区',count_points:'统计范围内 POI',style_layer:'更新地图样式'};
const presets=['统计地铁站 800 米直线范围内的公园数量','为地铁站生成 500 米直线缓冲区','列出当前图层'];
const storageKey='geoagent-preferences-v1';
function readPreferences(){try{return JSON.parse(localStorage.getItem(storageKey))||{}}catch{return {}}}
function iconFor(layer){return layer.geometry_types.some(x=>x.includes('Polygon'))?'polygon':layer.geometry_types.some(x=>x.includes('Line'))?'line':'point'}

function MapView({layers,selected,onSelect,fitRef,onCoords,onReady,onError}){
  const node=useRef(),map=useRef(),markers=useRef([]),dataCache=useRef(new Map()),selectRef=useRef(onSelect);
  selectRef.current=onSelect;
  useEffect(()=>{
    let instance;
    try{
      instance=new maplibregl.Map({container:node.current,style:{version:8,sources:{},layers:[{id:'background',type:'background',paint:{'background-color':'#eaf0e9'}}]},center:[116.39,39.917],zoom:12.8,attributionControl:false});
      map.current=instance;
      instance.addControl(new maplibregl.NavigationControl({showCompass:true}),'top-right');
      instance.addControl(new maplibregl.ScaleControl({maxWidth:120,unit:'metric'}),'bottom-left');
      instance.on('load',()=>onReady(true));
      instance.on('error',e=>onError(e.error?.message||'地图渲染错误'));
      instance.on('mousemove',e=>onCoords([e.lngLat.lng,e.lngLat.lat]));
      instance.on('click',e=>{const found=instance.queryRenderedFeatures(e.point).find(f=>f.source?.startsWith('geo-'));if(found)selectRef.current(found.source.slice(4));});
      fitRef.current=(layer)=>{const b=layer?.bounds;if(b&&b.every(Number.isFinite))instance.fitBounds([[b[0],b[1]],[b[2],b[3]]],{padding:85,maxZoom:16,duration:650});};
    }catch(e){onError(e.message)}
    const observer=new ResizeObserver(()=>instance?.resize());observer.observe(node.current);
    return()=>{observer.disconnect();instance?.remove();map.current=null};
  },[]);
  useEffect(()=>{
    const m=map.current;if(!m)return;
    let disposed=false;
    async function sync(){
      for(const layer of layers){
        if(!dataCache.current.has(layer.id))dataCache.current.set(layer.id,await api(`/layers/${layer.id}/data`));
      }
      if(disposed)return;
      markers.current.forEach(x=>x.remove());markers.current=[];
      for(const layer of layers){
        const source='geo-'+layer.id,data=dataCache.current.get(layer.id),color=layer.style.color||'#168874';
        if(!m.getSource(source)){
          m.addSource(source,{type:'geojson',data});
          m.addLayer({id:source+'-fill',type:'fill',source,filter:['==',['geometry-type'],'Polygon'],paint:{'fill-color':color,'fill-opacity':0.18}});
          m.addLayer({id:source+'-line',type:'line',source,filter:['any',['==',['geometry-type'],'LineString'],['==',['geometry-type'],'Polygon']],paint:{'line-color':color,'line-width':2}});
          m.addLayer({id:source+'-point',type:'circle',source,filter:['==',['geometry-type'],'Point'],paint:{'circle-color':color,'circle-radius':5,'circle-stroke-color':'#fff','circle-stroke-width':1.5}});
        }
        let paint=color;
        if(layer.style.field){
          const values=data.features.map(f=>Number(f.properties[layer.style.field])).filter(Number.isFinite),max=Math.max(1,...values);
          paint=['interpolate',['linear'],['coalesce',['get',layer.style.field],0],0,'#cfdfb5',max/2,'#5ba78c',max,'#116052'];
        }
        m.setPaintProperty(source+'-fill','fill-color',paint);
        m.setPaintProperty(source+'-fill','fill-opacity',layer.style.opacity??0.22);
        m.setPaintProperty(source+'-line','line-color',color);
        m.setPaintProperty(source+'-line','line-width',selected===layer.id?2.6:iconFor(layer)==='line'?1.2:1.5);
        m.setPaintProperty(source+'-point','circle-color',paint);
        m.setPaintProperty(source+'-point','circle-radius',layer.name.includes('站')?8:4.5);
        for(const suffix of ['-fill','-line','-point'])m.setLayoutProperty(source+suffix,'visibility',layer.style.visible===false?'none':'visible');
        if(iconFor(layer)==='polygon'){m.moveLayer(source+'-fill','geo-'+layers[0].id+'-point')}
        if(layer.style.visible!==false&&layer.geometry_types[0]==='Point'&&(layer.name.includes('站')||data.features.length<=8)){
          for(const f of data.features){const el=document.createElement('div');el.className='map-label';el.textContent=f.properties.name||f.properties['名称']||'';markers.current.push(new maplibregl.Marker({element:el,anchor:'bottom',offset:[0,-13]}).setLngLat(f.geometry.coordinates).addTo(m));}
        }
      }
      // Keep linework beneath analytical fills and points above all polygons.
      for(const layer of layers.filter(x=>iconFor(x)==='polygon')){m.moveLayer('geo-'+layer.id+'-fill');m.moveLayer('geo-'+layer.id+'-line')}
      for(const layer of layers.filter(x=>iconFor(x)==='point'))m.moveLayer('geo-'+layer.id+'-point');
    }
    if(m.isStyleLoaded())sync().catch(e=>onError(e.message));else m.once('load',()=>sync().catch(e=>onError(e.message)));
    return()=>{disposed=true};
  },[layers,selected]);
  return <div ref={node} className="map-canvas" aria-label="交互式工作区地图"/>;
}

function App(){
  const [layers,setLayers]=useState([]),[selected,setSelected]=useState(null),[runs,setRuns]=useState([]),[active,setActive]=useState(null),[history,setHistory]=useState([]),[input,setInput]=useState('');
  const [settings,setSettings]=useState(false),[upload,setUpload]=useState(false),[historyOpen,setHistoryOpen]=useState(false),[table,setTable]=useState(false),[tableData,setTableData]=useState(null),[inspect,setInspect]=useState(null);
  const [testing,setTesting]=useState(false),[testResult,setTestResult]=useState(null);
  const [config,setConfig]=useState(()=>({mode:'offline',base_url:'https://api.deepseek.com',model:'deepseek-chat',...readPreferences(),api_key:''}));
  const [toast,setToast]=useState(''),[busy,setBusy]=useState(false),[coords,setCoords]=useState([116.39,39.917]),[mapReady,setMapReady]=useState(false),[mapError,setMapError]=useState(''),[legendMax,setLegendMax]=useState(1),[tab,setTab]=useState('data'),[health,setHealth]=useState(null);
  const session=useRef(sessionStorage.getItem('geoagent-session')||crypto.randomUUID()),fitRef=useRef(),chatEnd=useRef(),timer=useRef();
  const current=layers.find(x=>x.id===selected),running=active&&['queued','running'].includes(active.status);
  function notify(text){setToast(text);clearTimeout(timer.current);timer.current=setTimeout(()=>setToast(''),6000)}
  async function refresh(){const [l,r]=await Promise.all([api('/layers'),api('/runs')]);setLayers(l);setRuns(r);return l}
  useEffect(()=>{sessionStorage.setItem('geoagent-session',session.current);refresh().catch(e=>notify(e.message));api('/health').then(setHealth).catch(()=>notify('后端连接失败，请检查服务是否启动。'));},[]);
  useEffect(()=>{chatEnd.current?.scrollIntoView({behavior:'smooth'})},[active?.events?.length,history]);
  useEffect(()=>{if(!running)return;let done=false;const id=setInterval(async()=>{try{const r=await api('/runs/'+active.id);if(done)return;setActive(r);if(!['running','queued'].includes(r.status)){await refresh();setHistory(h=>[...h.filter(x=>x.id!==r.id),r]);if(r.output_layers?.length){setSelected(r.output_layers.at(-1));setTable(true)} }}catch(e){notify(e.message)}},600);return()=>{done=true;clearInterval(id)}},[active?.id,running]);
  useEffect(()=>{if(!current){setTableData(null);setInspect(null);return}let gone=false;Promise.all([api(`/layers/${current.id}/data`),api(`/layers/${current.id}/inspect`)]).then(([d,i])=>{if(!gone){setTableData(d);setInspect(i)}}).catch(e=>notify(e.message));return()=>{gone=true}},[selected]);
  async function loadDemo(){try{setBusy(true);const d=await post('/demo');await refresh();setSelected(d[0].id);setTimeout(()=>fitRef.current?.(d.find(x=>x.name.includes('研究范围'))||d[0]),300);notify('示例已载入：全部为合成数据，不代表真实设施。')}catch(e){notify(e.message)}finally{setBusy(false)}}
  async function send(text=input){if(!text.trim()||running)return;try{const r=await post('/runs',{message:text.trim(),session_id:session.current,selected_layers:selected?[selected]:[],...config});setInput('');setActive({id:r.id,status:'queued',message_input:text,events:[]});}catch(e){notify(e.message)}}
  async function visibility(layer){try{const updated=await api(`/layers/${layer.id}/style`,{method:'PATCH',body:JSON.stringify({visible:layer.style.visible===false})});setLayers(l=>l.map(x=>x.id===layer.id?updated:x))}catch(e){notify(e.message)}}
  async function openRun(run){try{const r=await api('/runs/'+run.id);setHistory([r]);setHistoryOpen(false)}catch(e){notify(e.message)}}
  useEffect(()=>{setTestResult(null)},[config.base_url,config.model,config.api_key,config.mode]);
  async function testModel(){
    if(testing)return;
    setTesting(true);setTestResult(null);
    try{
      const result=await post('/model/test',{base_url:config.base_url,model:config.model,api_key:config.api_key});
      setTestResult({ok:true,message:result.message});
    }catch(e){setTestResult({ok:false,message:e.message})}
    finally{setTesting(false)}
  }
  function saveSettings(e){e.preventDefault();const {api_key,...safe}=config;localStorage.setItem(storageKey,JSON.stringify(safe));setSettings(false);notify(config.mode==='model'?'模型配置已应用。密钥仅保留在本页内存。':'已切换为离线指令模式。')}
  const shown=running?[...history,active]:history;
  const resultLayer=[...layers].reverse().find(x=>x.style.field&&x.style.visible!==false);
  useEffect(()=>{if(!resultLayer)return;let disposed=false;api(`/layers/${resultLayer.id}/data`).then(d=>{if(!disposed)setLegendMax(Math.max(1,...d.features.map(f=>Number(f.properties[resultLayer.style.field])||0)))}).catch(()=>{});return()=>{disposed=true}},[resultLayer?.id]);
  return <div className="app">
    <header className="topbar"><a className="brand" href="/"><span className="brand-mark"><Layers3 size={23}/></span>GeoAgent<span className="version">EARLY ACCESS</span></a><div className="project-crumb"><span className="divider"/>本地工作区 <ChevronDown size={13}/><span className="saved-dot"/>自动保存</div><nav><button onClick={()=>setHistoryOpen(true)}><Clock3 size={15}/>运行记录 <span className="count">{runs.length}</span></button><button onClick={()=>setSettings(true)}><Settings2 size={15}/>模型设置</button><span className="avatar">G</span></nav></header>
    <div className="workbench">
      <aside className="sidebar">
        <div className="side-head"><div><span className="eyebrow">WORKSPACE</span><h2>空间资源</h2></div><button className="icon-button" title="导入数据" onClick={()=>setUpload(true)}><Plus size={18}/></button></div>
        <div className="side-tabs"><button className={tab==='data'?'active':''} onClick={()=>setTab('data')}><Layers3 size={14}/>图层<span>{layers.length}</span></button><button className={tab==='details'?'active':''} onClick={()=>setTab('details')}><Database size={14}/>数据详情</button></div>
        {tab==='data'?<><div className="side-actions"><button className="import-button" onClick={()=>setUpload(true)}><FileUp size={16}/>导入地理数据</button><button className="sample-button" onClick={loadDemo} disabled={busy}><Sparkles size={14}/>载入示例</button></div><div className="section-label">地图图层 <span>WGS 84</span></div><div className="layer-list">{layers.length?layers.map(layer=><div key={layer.id} className={'layer-card '+(selected===layer.id?'selected':'')} onClick={()=>{setSelected(layer.id)}}><button className="visibility" aria-label={layer.style.visible===false?'显示 '+layer.name:'隐藏 '+layer.name} onClick={e=>{e.stopPropagation();visibility(layer)}}>{layer.style.visible===false?<EyeOff size={15}/>:<Eye size={15}/>}</button><span className={'geometry-icon '+iconFor(layer)} style={{'--color':layer.style.color}}/><div className="layer-text"><strong>{layer.name}</strong><span>{layer.count.toLocaleString()} 个要素 <i>·</i> {iconFor(layer)==='point'?'点':iconFor(layer)==='line'?'线':'面'}图层</span></div><button className="layer-zoom" title={'定位 '+layer.name} onClick={e=>{e.stopPropagation();fitRef.current?.(layer)}}><Focus size={14}/></button></div>):<div className="empty-layers"><Layers3 size={26}/><p>从一份地理数据开始</p><span>支持 GeoJSON 和经纬度 CSV</span></div>}</div></>:<div className="details">{current&&inspect?<><div className="detail-icon"><Database size={24}/></div><h3>{current.name}</h3><dl><dt>坐标系</dt><dd>EPSG:4326</dd><dt>几何类型</dt><dd>{current.geometry_types.join(', ')}</dd><dt>要素数量</dt><dd>{current.count}</dd><dt>数据来源</dt><dd>{current.source==='demo'?'合成示例':current.source==='analysis'?'分析产物':'用户导入'}</dd></dl><h4>数据校验</h4><p className="success-line"><ShieldCheck size={15}/>几何有效 · 坐标范围通过</p><h4>属性字段</h4><div className="field-tags">{current.fields.map(f=><span key={f}>{f}</span>)}</div>{current.provenance.method&&<><h4>分析方法</h4><p>{current.provenance.method}</p></>}{current.provenance.limitations&&<p className="note">{current.provenance.limitations}</p>}<button className="import-button" onClick={()=>setTable(true)}>查看属性表</button></>:<p className="muted">选择一个图层查看详情。</p>}</div>}
        <div className="side-bottom"><ShieldCheck size={17}/><div><strong>数据保存在本机</strong><span>分析产物与运行过程自动记录</span></div></div>
      </aside>
      <main className="map-area"><div className="map-heading"><div><MapIcon size={17}/><strong>工作区地图</strong><span className="subtle-tag">无在线底图</span></div><button onClick={()=>{if(layers.length){const bs=layers.map(x=>x.bounds);fitRef.current?.({bounds:[Math.min(...bs.map(x=>x[0])),Math.min(...bs.map(x=>x[1])),Math.max(...bs.map(x=>x[2])),Math.max(...bs.map(x=>x[3]))]})}}}><Crosshair size={15}/>全图</button></div>
        <div className="map-wrap"><MapView layers={layers} selected={selected} onSelect={setSelected} fitRef={fitRef} onCoords={setCoords} onReady={setMapReady} onError={setMapError}/>
          <div className="map-caption"><span className="live-dot"/>{layers.some(x=>x.source==='demo')?'包含合成示例数据':'本地空间数据'}<span className="map-caption-small">仅显示导入几何，不请求外部瓦片</span></div>
          {!layers.length&&<div className="map-empty"><div className="empty-orbit"><MapIcon size={30}/></div><span className="eyebrow">YOUR SPATIAL WORKSPACE</span><h1>让地理数据，回答问题。</h1><p>导入一份数据，或从城市分析示例开始。</p><button className="primary" onClick={loadDemo} disabled={busy}>{busy?<LoaderCircle className="spin" size={16}/>:<Sparkles size={16}/>}探索示例数据</button><small>4 个站点 · 68 个公园 POI · 全部为合成数据</small></div>}
          {mapError&&<div className="map-error">地图：{mapError}</div>}
          {resultLayer&&<div className="legend"><span>POI 数量</span><div className="legend-ramp"/><div><small>0 个</small><small>{legendMax} 个</small></div><p>每个范围独立统计 · 包含边界</p></div>}
          <button className="table-toggle" onClick={()=>{if(!selected&&layers.length)setSelected(layers[0].id);setTable(!table)}}><Database size={15}/>{table?'收起属性表':'属性表'}<ChevronDown size={13}/></button>
        </div>
        {table&&current&&<section className="attribute-panel"><div className="table-title"><div><Database size={14}/><strong>{current.name}</strong><span>{current.count} 条记录{current.count>100?' · 预览前 100 条':''}</span></div><div><a href={`/api/layers/${current.id}/export?format=csv`}><ArrowDownToLine size={14}/>CSV</a><a href={`/api/layers/${current.id}/export`}><ArrowDownToLine size={14}/>GeoJSON</a><button className="icon-button" onClick={()=>setTable(false)}><X size={15}/></button></div></div><div className="table-scroll"><table><thead><tr><th>#</th>{current.fields.map(f=><th key={f}>{f}</th>)}</tr></thead><tbody>{tableData?.features.slice(0,100).map((f,i)=><tr key={i}><td>{i+1}</td>{current.fields.map(k=><td key={k}>{typeof f.properties[k]==='object'?JSON.stringify(f.properties[k]):String(f.properties[k]??'—')}</td>)}</tr>)}</tbody></table></div></section>}
        <footer className="map-status"><span><span className={'status-dot '+(mapReady?'':'waiting')}/>{health?'服务已连接':'连接中'} <i>·</i> {layers.length} 个图层</span><span>{coords[0].toFixed(5)}° E, {coords[1].toFixed(5)}° N <i>·</i> EPSG:4326</span></footer>
      </main>
      <aside className="chat-panel"><div className="chat-heading"><div><span className="assistant-icon"><Sparkles size={17}/></span><strong>空间分析助手</strong></div><button className="icon-button" title="查看支持范围" onClick={()=>notify('v0.1 支持 GeoJSON/CSV、点缓冲、范围内点统计和分级设色。路网与栅格将在后续版本实现。')}><CircleHelp size={16}/></button></div><div className="model-status"><span className="live-dot"/>{config.mode==='offline'?'离线指令模式':'模型 · '+config.model}<button onClick={()=>setSettings(true)}>切换<ChevronRight size={12}/></button></div>
        <div className="chat-scroll">{!shown.length?<div className="welcome"><div className="welcome-symbol"><Sparkles size={26}/></div><span className="eyebrow">SPATIAL INTELLIGENCE</span><h2>从一个问题开始</h2><p>用自然语言描述分析需求，<br/>让数据处理和地图表达连在一起。</p><div className="prompt-label">试着问我</div>{presets.map((p,i)=><button className="prompt-card" key={p} onClick={()=>setInput(p)}><span className="prompt-index">0{i+1}</span><span>{p}</span><ChevronRight size={15}/></button>)}<div className="welcome-tip"><ShieldCheck size={15}/><span>每次分析都保留参数、校验与运行记录。<br/>示例需先点击左侧“载入示例”。</span></div></div>:shown.map(run=><div className="conversation" key={run.id}><div className="user-bubble">{run.message_input}</div><div className="assistant-label"><span className="assistant-icon small"><Sparkles size={13}/></span>GeoAgent<span>{run.mode==='offline'?'离线指令':'模型工具调用'}</span></div>{run.events?.filter(e=>e.type==='tool_completed').map(e=><details className={'tool-card '+(!e.data.result.success?'tool-error':'')} key={e.seq}><summary>{e.data.result.success?<Check size={14}/>:<X size={14}/>}<span>{toolNames[e.data.name]||e.data.name}</span><small>{e.data.duration_ms} ms</small><ChevronDown size={12}/></summary><pre>{JSON.stringify(e.data.result,null,2)}</pre></details>)}{run.events?.some(e=>e.type==='validation_completed')&&<div className="validation-badge"><ShieldCheck size={13}/>空间结果检查已执行</div>}{run.message?<div className={'assistant-message '+(run.status==='failed'?'failure':'')}>{run.message}</div>:<div className="thinking"><LoaderCircle size={14} className="spin"/>正在处理空间任务…</div>}{!['queued','running'].includes(run.status)&&<div className="run-footer"><span>{run.status==='completed'?'运行已结束':run.status==='failed'?'执行失败':run.status==='cancelled'?'已停止':'已中断'}</span><a href={`/api/runs/${run.id}/export`}><ArrowDownToLine size={12}/>运行记录</a></div>}</div>)}<div ref={chatEnd}/></div>
        <div className="composer-wrap">{current&&<div className="context-chip"><Layers3 size={12}/><span>{current.name}</span><button aria-label="取消图层选择" onClick={()=>setSelected(null)}><X size={12}/></button></div>}<form className="composer" onSubmit={e=>{e.preventDefault();send()}}><textarea aria-label="输入地理空间分析需求" placeholder="描述你的空间分析需求…" value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();send()}}}/><div className="composer-bottom"><span><Terminal size={12}/>{config.mode==='offline'?'受控 GIS 工具':'结构化工具调用'}</span>{running?<button type="button" aria-label="停止任务" className="send-button stop" onClick={()=>post(`/runs/${active.id}/cancel`).then(()=>notify('已请求停止；当前调用结束后生效。'))}><Square size={14}/></button>:<button type="submit" className="send-button" aria-label="发送分析需求" disabled={!input.trim()}><ArrowUp size={18}/></button>}</div></form><div className="composer-hint">Enter 发送 <i>·</i> Shift + Enter 换行</div></div>
      </aside>
    </div>
    {toast&&<div className="toast" role="status"><CircleHelp size={16}/>{toast}<button aria-label="关闭通知" onClick={()=>setToast('')}><X size={14}/></button></div>}
    {settings&&<Modal title="模型与运行模式" close={()=>setSettings(false)}><form onSubmit={saveSettings}><div className="mode-options">{[['offline','离线指令','规则解析 · 无需密钥'],['model','连接模型','支持工具调用的兼容接口']].map(([value,title,desc])=><button type="button" disabled={testing} className={config.mode===value?'selected':''} key={value} onClick={()=>setConfig(c=>({...c,mode:value}))}><strong>{title}</strong><span>{desc}</span></button>)}</div>{config.mode==='model'&&<><label>API 根地址<input disabled={testing} required value={config.base_url} placeholder="https://api.deepseek.com" onChange={e=>setConfig(c=>({...c,base_url:e.target.value}))}/></label><label>模型名称<input disabled={testing} required value={config.model} onChange={e=>setConfig(c=>({...c,model:e.target.value}))}/></label><label>API Key<input disabled={testing} type="password" autoComplete="off" value={config.api_key} placeholder={health?.model_configured?'已配置服务端密钥，可留空':'输入 API Key'} onChange={e=>setConfig(c=>({...c,api_key:e.target.value}))}/></label><p className="form-note">密钥仅在当前页面内存中保留，不写入运行记录。模型会接收任务、图层摘要、属性样本与工具结果；完整空间文件保留在本机。OpenAI 官方根地址为 https://api.openai.com/v1；请填写完整模型 ID。</p><button type="button" className="import-button" disabled={testing} onClick={testModel}>{testing?<LoaderCircle className="spin" size={15}/>:<ShieldCheck size={15}/>} {testing?'正在测试…':'测试连接'}</button><p className="form-note">测试会发起一次简短模型请求，可能产生少量 API 用量；不发送地理数据，不运行 GIS 工具。</p>{testResult&&<div role="status" className={'connection-result '+(testResult.ok?'connection-ok':'connection-error')}>{testResult.message}</div>}</>}<p className="form-note">离线指令模式仅支持示例中的明确命令，不具备大模型推理。两种模式调用相同的 GIS 工具与校验。</p><button className="primary" type="submit" disabled={testing}>应用设置<Check size={16}/></button></form></Modal>}
    {upload&&<UploadModal close={()=>setUpload(false)} onDone={async layer=>{await refresh();setSelected(layer.id);setTimeout(()=>fitRef.current?.(layer),250);notify('数据已导入，几何和坐标范围检查通过。')}} notify={notify}/>}
    {historyOpen&&<Modal title="运行记录" close={()=>setHistoryOpen(false)}><p className="form-note">任务、工具参数与产物保存在本地工作区。点击查看执行过程。</p><div className="run-list">{runs.length?runs.map(r=><button key={r.id} onClick={()=>openRun(r)}><span className={'run-indicator '+r.status}/><div><strong>{r.message_input}</strong><small>{new Date(r.created_at).toLocaleString('zh-CN')} · {r.mode==='offline'?'离线指令':'模型'}</small></div><ChevronRight size={16}/></button>):<p className="muted">还没有运行记录。</p>}</div></Modal>}
  </div>
}
function Modal({title,children,close}){return <div className="modal-backdrop" onClick={close}><section className="modal" role="dialog" aria-modal="true" aria-label={title} onClick={e=>e.stopPropagation()}><div className="modal-header"><h2>{title}</h2><button className="icon-button" aria-label="关闭弹窗" onClick={close}><X size={20}/></button></div>{children}</section></div>}
function UploadModal({close,onDone,notify}){const [file,setFile]=useState(null),[crs,setCrs]=useState('EPSG:4326'),[loading,setLoading]=useState(false),[error,setError]=useState('');async function submit(e){e.preventDefault();if(!file)return;setLoading(true);setError('');try{const body=new FormData();body.append('file',file);body.append('source_crs',crs);const layer=await api('/layers/upload',{method:'POST',body});await onDone(layer);close()}catch(e){setError(e.message)}finally{setLoading(false)}}return <Modal title="导入地理数据" close={close}><form onSubmit={submit}><label className="dropzone" onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();setFile(e.dataTransfer.files[0])}}><FileUp size={29}/><strong>{file?file.name:'选择文件或拖放到这里'}</strong><span>GeoJSON / CSV · 最大 12 MB、20,000 个要素</span><input type="file" accept=".geojson,.json,.csv" onChange={e=>setFile(e.target.files[0])}/></label><label>输入数据坐标系<input required value={crs} onChange={e=>setCrs(e.target.value)} placeholder="EPSG:4326"/></label><p className="form-note">GeoJSON 默认按 WGS84 经度、纬度解析。CSV 支持 lon/lat、longitude/latitude、经度/纬度和 x/y 列。其他 EPSG 坐标会转换为 WGS84；GCJ-02 / BD-09 请先纠偏。第一版仅支持二维矢量。</p>{error&&<p className="form-error" role="alert">{error}</p>}<button className="primary" disabled={!file||loading}>{loading?<LoaderCircle className="spin" size={16}/>:<FileUp size={16}/>}检查并导入</button></form></Modal>}
createRoot(document.getElementById('root')).render(<App/>);
