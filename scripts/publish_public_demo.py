"""Import the public samples and publish print artifacts through the running API.

Only adds data and changes the current print layout; never removes source layers.
"""
import json
from pathlib import Path
import time
import httpx

OUT = Path(__file__).resolve().parents[1] / 'outputs' / 'public-cartography'


def main():
    specs = json.loads((OUT / 'maps.json').read_text())['maps']
    with httpx.Client(base_url='http://127.0.0.1:8765/api', timeout=90) as client:
        def request(method,path,**kwargs):
            result=client.request(method,path,**kwargs)
            result.raise_for_status()
            return result.json()
        runs=request('GET','/runs')
        if any(x['status'] in ('running','queued') for x in runs):
            raise ValueError('Workspace has an active task; avoid modifying its print layout.')
        layers=[]
        for filename in ('washington-counties-shp.zip','rainier-usgs-3dep.tif'):
            path=OUT/'raw'/filename
            asset=request('POST','/imports',files={'files':(filename,path.read_bytes())})
            layer=request('POST','/imports/'+asset['id']+'/load',json={})
            layers.append(layer)
        counties,dem=layers
        request('PATCH','/layers/'+counties['id']+'/name',json={'name':'公开数据 · 华盛顿州县界（Census 2024）'})
        request('PATCH','/layers/'+dem['id']+'/name',json={'name':'公开数据 · 雷尼尔山高程（USGS 3DEP）'})
        run=request('POST','/runs',json={'message':'Census 2024 ALAND 转换为平方千米，发布真实县域面积图层',
            'session_id':'public-cartography-demo','mode':'algorithm','algorithm_id':'calculate_field',
            'arguments':{'layer_id':counties['id'],'field':'ALAND','expression':'value / 1000000','output_field':'land_km2'}})
        for _ in range(160):
            result=request('GET','/runs/'+run['id'])
            if result['status'] not in ('queued','running'):break
            time.sleep(.25)
        if result['status']!='completed':raise ValueError(result.get('message','Calculation did not complete.'))
        derived=result['output_layers'][-1]
        request('PATCH','/layers/'+derived+'/name',json={'name':'公开专题 · 华盛顿州县域陆地面积'})
        request('PATCH','/layers/'+derived+'/style',json={'field':'land_km2','color':'#245247','labels':True,'opacity':1})
        published=[]
        for spec in specs:
            layout=spec['layout'].copy()
            layout['focus_layer_id']=dem['id'] if layout['template']=='terrain' else derived
            layout['context_layer_id']=counties['id'] if layout['template']=='terrain' else None
            request('PATCH','/layout',json=layout)
            for fmt in ('pdf','png'):
                item=request('POST','/layout/export',json={'format':fmt,'dpi':300})
                published.append({'name':item['name'],'url':item['url'],'layout':layout})
        result={'layers':{'counties':counties['id'],'dem':dem['id'],'choropleth':derived},'exports':published}
        (OUT/'published.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
        print(json.dumps({'added_layers':result['layers'],'artifacts':[x['url'] for x in published]},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
