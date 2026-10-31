"""Isolated browser QA: deterministic model responses, real GIS/code execution."""
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
os.environ.setdefault('GEOAGENT_WORKSPACE','/private/tmp/gaia-v04-browser-workspace')
from geoagent.app import app
from geoagent import durable,demo
demo.seed(app.state.store)

def respond(client,config,payload):
    inputs=payload['input']
    if any(x.get('type')=='function_call_output' for x in inputs):
        return {'id':'qa-final','output':[{'type':'message','role':'assistant','content':[{'type':'output_text','text':'已执行代码，请查看成果与验收结果。'}]}]}
    layer=app.state.store.layers()[0]['id']
    code="g=inputs['data'].copy()\np=output_dir/'qa_output.gpkg'\ng.to_file(p,driver='GPKG')\noutputs={'result':str(p)}\nmetrics={'count':len(g)}"
    return {'id':'qa-call','output':[{'type':'reasoning','id':'qa-reasoning','summary':[],'encrypted_content':'QA_OPAQUE'},
        {'type':'function_call','call_id':'qa-code','name':'execute_code','arguments':json.dumps({'plugin_id':'python','code':code,'inputs':{'data':layer},'save_as':'浏览器验收配方'})}]}

durable.request_responses=respond

if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=8767)
