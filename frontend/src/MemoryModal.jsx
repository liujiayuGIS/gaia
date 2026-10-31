import React,{useEffect,useState} from 'react';
import {api,post,patch,Modal} from './shared';

export default function MemoryModal({close,notice}){
 const [data,setData]=useState(null),[title,setTitle]=useState(''),[body,setBody]=useState(''),[source,setSource]=useState(''),[query,setQuery]=useState(''),[matches,setMatches]=useState([]),[busy,setBusy]=useState(false);
 const reload=()=>api('/memory').then(setData);
 useEffect(()=>{reload().catch(e=>notice(e.message))},[]);
 async function act(fn){setBusy(true);try{await fn();await reload()}catch(e){notice(e.message)}finally{setBusy(false)}}
 const change=(key,value)=>setData(d=>({...d,preferences:{...d.preferences,[key]:value}}));
 return <Modal title="项目与记忆" close={close}>{!data?<p>读取记忆…</p>:<div className="memory-panel">
 <p className="help">只保存你明确设置的稳定偏好。空间数据仍保存在项目文件中，知识库用于查找方法和参考资料。</p>
 <details open><summary>长期偏好</summary><form onSubmit={e=>{e.preventDefault();act(async()=>{await patch('/memory/preferences',data.preferences);notice('偏好已保存，后续任务将使用这些设置。')})}}>
 <div className="two-fields"><label className="field-label">常用坐标系<input value={data.preferences.crs} onChange={e=>change('crs',e.target.value)}/></label><label className="field-label">地图语言<input value={data.preferences.language} onChange={e=>change('language',e.target.value)}/></label></div>
 <div className="two-fields"><label className="field-label">距离单位<select value={data.preferences.distance_unit} onChange={e=>change('distance_unit',e.target.value)}><option value="m">米</option><option value="km">千米</option></select></label><label className="field-label">面积单位<select value={data.preferences.area_unit} onChange={e=>change('area_unit',e.target.value)}><option value="m2">平方米</option><option value="km2">平方千米</option><option value="ha">公顷</option></select></label></div>
 <label className="field-label">制图风格<input value={data.preferences.map_style} onChange={e=>change('map_style',e.target.value)}/></label>
 <label className="field-label">图件规范<textarea value={data.preferences.figure_guidelines} onChange={e=>change('figure_guidelines',e.target.value)}/></label>
 <label className="check-row"><input type="checkbox" checked={data.preferences.allow_auto_code} onChange={e=>change('allow_auto_code',e.target.checked)}/>允许助手自动执行受限分析代码</label>
 <div className="dialog-actions"><button type="button" disabled={busy} onClick={()=>act(()=>api('/memory/preferences',{method:'DELETE'}))}>清除偏好</button><button className="primary" disabled={busy}>保存偏好</button></div>
 </form></details>
 <details><summary>项目资产 · {data.catalog.length} 项</summary>{data.catalog.map(x=><div className="memory-item" key={x.id}><strong>{x.summary.name}</strong><small>{x.summary.crs} · {x.summary.count} 个要素 / 像元</small><small>{x.stale?'数据版本已变化，相关摘要与验证已失效':'已记录数据版本'} · {x.content_hash.slice(0,12)}</small></div>)}</details>
 <details open><summary>方法与知识 · {data.knowledge.length} 条</summary><form onSubmit={e=>{e.preventDefault();act(async()=>{await post('/memory/knowledge',{title,body,source,reviewed:true});setTitle('');setBody('');setSource('')})}}>
 <label className="field-label">标题<input required value={title} onChange={e=>setTitle(e.target.value)} placeholder="例如：团队制图规范"/></label><label className="field-label">方法、SOP 或参考内容<textarea required value={body} onChange={e=>setBody(e.target.value)}/></label><label className="field-label">来源<input value={source} onChange={e=>setSource(e.target.value)} placeholder="文档地址或出处"/></label><button disabled={busy}>保存知识</button></form>
 <form className="memory-search" onSubmit={e=>{e.preventDefault();act(async()=>setMatches(await api('/memory/knowledge?query='+encodeURIComponent(query))))}}><input aria-label="检索项目知识" value={query} onChange={e=>setQuery(e.target.value)}/><button disabled={busy||!query.trim()}>检索</button></form>
 {matches.map(x=><div className="memory-item" key={x.id}><strong>{x.title}</strong><p>{x.excerpt}</p><small>{x.source||'用户提供'}</small></div>)}
 {data.knowledge.map(x=><div className="memory-item" key={x.id}><strong>{x.title}{x.stale?' · 已失效':''}</strong><small>{x.source||'用户提供'}</small><button disabled={busy} onClick={()=>act(()=>api('/memory/knowledge/'+x.id,{method:'DELETE'}))}>忘记这条知识</button></div>)}
 </details></div>}</Modal>
}
