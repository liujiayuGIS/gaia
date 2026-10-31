import hashlib
from pathlib import Path
import sys
from .base import AnalysisPlugin
from . import runtime


class PythonPlugin(AnalysisPlugin):
    id='python';name='Python 科学计算'

    def status(self):
        return {'available':True,'version':sys.version.split()[0],'algorithm_count':35,'operations':['analysis','cartography','execute_code'],
                'description':'GeoPandas / Rasterio / NumPy 与独立 Python 作业；代码写入仅限作业目录。'}

    def algorithms(self):
        from ..algorithms import CATALOG
        return [{**x,'id':'python:'+x['id'],'plugin_id':'python','category':'Python · '+x['category']} for x in CATALOG]

    def execute(self,store,algorithm_id,arguments,run_id,cancel):
        from ..algorithms import run_algorithm
        return run_algorithm(store,algorithm_id.split(':',1)[1],arguments,run_id)

    def execute_code(self,store,code,inputs,run_id,cancel,timeout=60):
        job=runtime.job_folder(store);paths,_=runtime.copy_inputs(store,inputs,job)
        (job/'analysis.py').write_text(code)
        # Use this application's scientific environment, preserving pyvenv.cfg discovery.
        python=runtime.python_executable()
        response=runtime.execute(python,'python_worker.py',{'code':code,'inputs':paths},job,cancel,timeout)
        result=runtime.publish(store,response,run_id,self.id,inputs,{'code_sha256':hashlib.sha256(code.encode()).hexdigest()})
        result['code']=code;return result

    def render(self,store,layout,fmt,dpi,layers,preview=False):
        from ..cartography import render_map
        return render_map(store,fmt,dpi,[x['id'] for x in layers],overrides={'plugin_id':'python'},preview=preview)
