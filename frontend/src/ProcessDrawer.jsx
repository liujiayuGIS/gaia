import React,{useEffect,useRef,useState} from 'react';
import {Workflow,ChevronDown,ChevronUp,Check,LoaderCircle,AlertTriangle,ArrowUpRight,Clock3,Layers,FileText} from 'lucide-react';
import {api,toolNames} from './shared';
import {readToolSteps} from './processSteps.mjs';

const statuses={completed:'任务已完成',running:'正在执行',queued:'正在准备',waiting_approval:'等待你的审批',interrupted:'执行已中断',failed:'执行失败',cancelled:'任务已停止',needs_attention:'成果需要检查'};

export default function ProcessDrawer({run,open,setOpen,onAssistant,onLayer}){
 const [record,setRecord]=useState(null),[selection,setSelection]=useState(null),[error,setError]=useState('');
 const host=useRef();
 useEffect(()=>{
  const node=host.current,workbench=node.closest('.workbench');
  const update=()=>workbench.style.setProperty('--process-height',node.getBoundingClientRect().height+'px');
  const observer=new ResizeObserver(update);observer.observe(node);update();
  return()=>{observer.disconnect();workbench.style.removeProperty('--process-height')};
 },[]);
 useEffect(()=>{
  let cancelled=false;setError('');
  if(!run){setRecord(null);return}
  setRecord(run);
  if(!run.events)api('/runs/'+run.id).then(value=>{if(!cancelled)setRecord(value)}).catch(e=>{if(!cancelled)setError(e.message)});
  return()=>{cancelled=true};
 },[run]);
 useEffect(()=>setSelection(null),[run?.id]);
 const steps=readToolSteps(record);
 const selected=steps.find(s=>s.id===selection)||steps.at(-1);
 const done=steps.filter(s=>s.status==='completed').length;
 const output=selected?.result?.data;
 const Icon=record?.status==='running'?LoaderCircle:['failed','needs_attention','interrupted'].includes(record?.status)?AlertTriangle:record?.status==='completed'?Check:Workflow;
 return <section ref={host} className={'process-drawer '+(open?'expanded':'')} aria-label="分析流程">
  <header className="process-heading">
   <button className="process-toggle" aria-label={open?'收起分析流程':'展开分析流程'} aria-expanded={open} aria-controls="process-content" onClick={()=>setOpen(!open)}>
    <span className="process-mark"><Icon size={17} className={record?.status==='running'?'spin':''}/></span>
    <span><strong>{record?'分析流程':'分析流程与执行记录'}</strong><small>{record?statuses[record.status]||record.status:'运行一次分析，在这里查看每一步的输入与成果'}</small></span>
    {record&&<span className="process-count">{done} / {steps.length} 项操作</span>}{open?<ChevronDown size={16}/>:<ChevronUp size={16}/>}</button>
   <button className="process-assistant" onClick={onAssistant} title="在助手中查看任务"><span>查看任务</span><ArrowUpRight size={16}/></button>
  </header>
  <div id="process-content" className="process-content" hidden={!open}>
   {error&&<p className="form-error">{error}</p>}
   {record?<>
    <p className="process-request">{record.message_input||'当前分析任务'}</p>
    {steps.length?<><div className="process-track" aria-label="实际工具步骤">{steps.map((step,i)=><button key={step.id} className={(selected?.id===step.id?'selected ':'')+step.status} aria-pressed={selected?.id===step.id} onClick={()=>setSelection(step.id)}>
     <span className="step-number">{step.status==='completed'?<Check size={14}/>:step.status==='running'?<LoaderCircle size={14} className="spin"/>:step.status==='failed'?<AlertTriangle size={14}/>:i+1}</span>
     <span><strong>{toolNames[step.name]||step.name}</strong><small>{step.duration!=null?(step.duration/1000).toFixed(1)+' 秒':step.status==='running'?'处理中':step.status==='waiting_approval'?'等待审批':'尚未确认完成'}</small></span>
    </button>)}</div>
    <div className="process-detail"><div><strong>{toolNames[selected.name]||selected.name}</strong><small>{selected.result?.success?'该工具操作成功':selected.result?.error||'完成状态以执行记录为准'}</small></div>
     {output?.layer_id&&<button onClick={()=>onLayer(output.layer_id)}><Layers size={14}/>查看输出图层</button>}
     <details key={selected.id}><summary>参数与回执</summary><pre>{JSON.stringify({arguments:selected.args,result:selected.result??null},null,2)}</pre></details>
    </div></>:<p className="process-empty">{record.status==='waiting_approval'?'请在右侧助手中审阅并确认待执行操作。':'当前尚无工具执行回执。计划和对话可在右侧助手查看。'}</p>}
    <a className="process-record" href={'/api/runs/'+record.id+'/export'} download><FileText size={13}/>下载运行记录</a>
   </>:<p className="process-empty"><Clock3 size={17}/>手动运行算法，或向 GAIA 描述任务。实际执行步骤、参数与核验结果会保留在这里。</p>}
  </div>
 </section>;
}
