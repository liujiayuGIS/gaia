import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readToolSteps} from '../frontend/src/processSteps.mjs';

const start=(seq,name,step_id)=>({seq,type:'tool_started',data:{name,step_id,arguments:{distance_m:800}}});
const end=(seq,name,success=true,step_id)=>({seq,type:'tool_completed',data:{name,step_id,duration_ms:1200,result:{success,data:{layer_id:'actual-output'}}}});

test('nested workflow parent completes after its children',()=>{
 const steps=readToolSteps({status:'completed',events:[start(1,'run_workflow','parent'),start(2,'run_algorithm','a'),end(3,'run_algorithm',true,'a'),start(4,'run_algorithm','b'),end(5,'run_algorithm',true,'b'),end(6,'run_workflow',true,'parent')]});
 assert.deepEqual(steps.map(s=>s.status),['completed','completed','completed']);
 assert.equal(steps[0].result.data.layer_id,'actual-output');
});
test('step IDs distinguish overlapping tools with the same name',()=>{
 const steps=readToolSteps({status:'completed',events:[start(1,'run_algorithm','first'),start(2,'run_algorithm','second'),end(3,'run_algorithm',false,'first'),end(4,'run_algorithm',true,'second')]});
 assert.deepEqual(steps.map(s=>s.status),['failed','completed']);
});
test('older nested calls pair by name stack without fabricated completion',()=>{
 const steps=readToolSteps({status:'interrupted',events:[start(1,'run_workflow'),start(2,'run_algorithm'),end(3,'run_algorithm')]});
 assert.deepEqual(steps.map(s=>s.status),['interrupted','completed']);
});
test('receipt-only trace keeps its real result and unknown arguments',()=>{
 const [step]=readToolSteps({status:'completed',events:[end(1,'export_map')]});
 assert.equal(step.status,'completed');assert.equal(step.args,null);
});
