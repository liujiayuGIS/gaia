"""Synthetic message fixtures for chat UI checks; not research results."""
import os
import sys
from pathlib import Path
from datetime import datetime,timezone,timedelta

root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'))
os.environ.setdefault('GEOAGENT_WORKSPACE','/private/tmp/gaia-chat-ui')
os.environ.setdefault('GEOAGENT_DISABLE_QGIS','1')
from geoagent.app import app

store=app.state.store
if not store.layers():
    store.add_layer('界面验收样点',{'type':'FeatureCollection','features':[{'type':'Feature','geometry':{'type':'Point','coordinates':[116.39,39.9]},'properties':{'name':'合成样点'}}]},source='QA synthetic')
if not store.runs('chat-qa'):
    for i in range(12):
        created=datetime.now(timezone.utc)-timedelta(minutes=20-i)
        answer='## 界面验收样例\n\n这是 **合成样例**，用于检查消息交互，不是一次真实分析的结论。\n\n- 输入：样点\n- 单位：米\n\n| 项目 | 数值 |\n| --- | --- |\n| 样点数 | 1 |\n\n```python\nprint("GAIA")\n```\n\n[说明链接](https://example.org)\n\n<script>window.__bad=true</script>\n[危险链接](javascript:alert(1))'
        store.save_run({'id':'chat-fixture-'+str(i),'mode':'offline','session_id':'chat-qa','status':'completed','message_input':'检查合成样点并解释结果 '+str(i),'message':answer,'created_at':created.isoformat(),'finished_at':(created+timedelta(seconds=4)).isoformat(),'output_layers':[]})
import uvicorn
uvicorn.run(app,host='127.0.0.1',port=int(os.environ.get('PORT','8774')))
