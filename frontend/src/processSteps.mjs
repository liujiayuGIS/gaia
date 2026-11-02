// Stable step IDs pair nested workflows correctly; older traces use name stacks.
export function readToolSteps(record){
 const steps=[],pending=[];
 for(const event of record?.events||[]){
  const data=event.data;
  if(event.type==='tool_started'){
   const step={id:event.seq,stepId:data.step_id,name:data.name,args:data.arguments,status:record.status==='waiting_approval'?'waiting_approval':['running','queued'].includes(record.status)?'running':'interrupted'};
   steps.push(step);pending.push(step);
  }else if(event.type==='tool_completed'){
   let index=pending.findLastIndex(step=>data.step_id?step.stepId===data.step_id:step.name===data.name);
   const step=index>=0?pending.splice(index,1)[0]:{id:event.seq,name:data.name,args:null};
   if(index<0)steps.push(step);
   step.result=data.result;step.duration=data.duration_ms;
   step.status=data.result?.success?'completed':'failed';
  }
 }
 return steps;
}
