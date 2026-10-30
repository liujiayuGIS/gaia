import React,{useEffect,useState} from 'react';
import {Save,Upload,Download,LoaderCircle} from 'lucide-react';
import {api,post,patch} from './shared';
import {PaneHeader} from './ProWorkbench';
const tabs=[['projects','工程'],['templates','布局模板'],['exports','成果文件'],['imports','数据收件箱'],['plugins','执行插件'],['skills','Skills'],['recipes','自定义算法'],['workflows','工作流']];
export default function CatalogPane({tab,setTab,revision,exports,assets,busy,running,task,refresh,notice,saveProject,layout,layoutView,modal,run,selected,loadRecipe,updateCaps}){
 const [data,setData]=useState({}),[skill,setSkill]=useState(null),[loading,setLoading]=useState(false);
 async function reload(){setLoading(true);try{const paths=['projects','layout-templates','plugins','skills','recipes','workflows'];const rows=await Promise.all(paths.map(p=>api('/'+p)));setData(Object.fromEntries(['projects','templates','plugins','skills','recipes','workflows'].map((k,i)=>[k,rows[i]])))}catch(e){notice(e.message)}finally{setLoading(false)}}
 useEffect(()=>{reload()},[revision]);
 const act=(label,fn)=>task(label,async()=>{await fn();await reload();await refresh()});
 const items=tab==='exports'?exports:tab==='imports'?assets:data[tab]||[];
 return <section className="task-pane"><PaneHeader title="目录"/><select className="catalog-selector" aria-label="目录分类" value={tab} onChange={e=>{setTab(e.target.value);setSkill(null)}}>{tabs.map(([id,t])=><option value={id} key={id}>{t}</option>)}</select><div className="catalog-list">{(busy||loading)&&<p role="status"><LoaderCircle size={13} className="spin"/>{busy||'读取目录'}…</p>}
 {tab==='projects'&&<button className="catalog-action" disabled={!!busy} onClick={saveProject}><Save size={14}/>保存当前 QGIS 工程</button>}
 {tab==='templates'&&<button disabled={!!busy} onClick={()=>act('保存模板',()=>post('/layout-templates',{name:layout.title,plugin_id:'qgis'}))}><Save size={14}/>保存当前布局</button>}
 {tab==='skills'&&<label className="button catalog-action"><Upload size={14}/>安装 Skill<input hidden type="file" accept=".md,.zip" onChange={e=>{const file=e.target.files[0];if(file)act('安装 Skill',()=>{const b=new FormData();b.append('file',file);return api('/skills',{method:'POST',body:b})})}}/></label>}
 {items.map(x=><article key={x.id}><strong>{x.name}</strong>
 {tab==='projects'&&<><small>QGIS {x.qgis_version} · {new Date(x.created_at).toLocaleString()}</small><div className="row-actions"><button disabled={!!busy||running} onClick={()=>act('打开工程',()=>post('/projects/'+x.id+'/open'))}>打开</button><a href={x.bundle_url} download>工程与数据 ZIP</a><a href={x.path_url} download>QGZ</a></div></>}
 {tab==='templates'&&<div className="row-actions"><button onClick={()=>act('应用模板',async()=>{await post('/layout-templates/'+x.id+'/apply',{});layoutView()})}>应用</button><a href={x.url} download>QPT</a></div>}
 {tab==='exports'&&<><small>{x.format?.toUpperCase()} {x.dpi&&' · '+x.dpi+' DPI'}</small><a className="button" href={x.url} download><Download size={13}/>下载</a></>}
 {tab==='imports'&&<><small>{x.resources?.length} 项资源</small><button onClick={()=>modal({type:'import',asset:x})}>选择并导入</button></>}
 {tab==='plugins'&&<><small>{x.available?(x.version||'内置')+' · '+(x.algorithm_count||0)+' 算法':x.error}</small><p>{x.description}</p><label className="check-row"><input type="checkbox" checked={x.enabled} disabled={!x.available||!!busy} onChange={e=>act('更新插件',async()=>{await patch('/plugins/'+x.id,{enabled:e.target.checked});await updateCaps()})}/>启用</label></>}
 {tab==='skills'&&<><p>{x.description}</p><small>{x.version} · {x.source}</small><button onClick={()=>api('/skills/'+x.id).then(setSkill).catch(e=>notice(e.message))}>查看流程</button></>}
 {tab==='recipes'&&<><small>{x.plugin_id}</small><div className="row-actions"><button onClick={()=>api('/recipes/'+x.id).then(loadRecipe).catch(e=>notice(e.message))}>编辑代码</button><button disabled={running} onClick={()=>run({mode:'code',recipe_id:x.id,message:'执行 '+x.name,inputs:selected?{data:selected}:{}})}>运行</button></div></>}
 {tab==='workflows'&&<><small>{x.nodes.length} 个节点</small><button disabled={running} onClick={()=>run({mode:'workflow',workflow_id:x.id,message:'执行工作流 '+x.name})}>运行</button></>}
 </article>)}{!loading&&!busy&&!items.length&&<div className="pane-empty">此目录暂时没有内容。</div>}{skill&&<details open><summary>{skill.name}</summary><pre>{skill.body}</pre></details>}</div></section>
}
