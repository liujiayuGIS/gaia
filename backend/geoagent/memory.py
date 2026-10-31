"""Five memory scopes. Spatial files remain authoritative; knowledge is separate."""
from __future__ import annotations
import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .store import now


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()


class Preferences(BaseModel):
    model_config=ConfigDict(extra='forbid')
    crs: str='EPSG:4326'
    distance_unit: Literal['m','km']='m'
    area_unit: Literal['m2','km2','ha']='km2'
    language: str=Field(default='中文',max_length=80)
    map_style: str=Field(default='',max_length=1000)
    output_format: Literal['gpkg','geojson','shp','tif','pdf','png','svg']='gpkg'
    default_data_directory: str=Field(default='',max_length=500)
    allow_auto_code: bool=False
    figure_guidelines: str=Field(default='',max_length=3000)

    @field_validator('crs')
    @classmethod
    def valid_crs(cls,value):
        from pyproj import CRS
        return CRS.from_user_input(value).to_string()


class Memory:
    def __init__(self,store): self.store=store

    def preferences(self):
        return Preferences(**self.store.setting('user_preferences',{})).model_dump()

    def set_preferences(self,changes):
        value=Preferences(**{**self.preferences(),**changes}).model_dump()
        self.store.put_object('settings','user_preferences',value)
        return value

    def session(self,session_id,title=None):
        try:item=self.store.object('sessions',session_id)
        except ValueError:item={'id':session_id,'title':(title or '新会话')[:80],'created_at':now()}
        if title and item['title']=='新会话':item['title']=title[:80]
        item['updated_at']=now()
        return self.store.put_object('sessions',session_id,item)

    def paths(self,layer):
        root=self.store.root/'layers';id=layer['id']
        if layer.get('kind')=='raster':
            from .formats import raster_path
            return [raster_path(self.store,id)]
        return [p for p in (root/(id+'.geojson'),root/(id+'.gpkg')) if p.exists()]

    def fingerprint(self,layer_id):
        layer=self.store.get_layer(layer_id);paths=self.paths(layer)
        if not paths or any(not p.is_file() for p in paths):raise ValueError('图层数据文件缺失：'+layer['name'])
        hashes={}
        for p in paths:
            with p.open('rb') as stream:hashes[p.name]=hashlib.file_digest(stream,'sha256').hexdigest()
        return digest(hashes),hashes

    def catalog(self):
        items=[];changed=set()
        for layer in self.store.layers():
            id=layer['id']
            try:old=self.store.object('catalog',id)
            except ValueError:old={}
            try:content_hash,files=self.fingerprint(id)
            except ValueError:content_hash,files='missing',{}
            modified=bool(old and old['content_hash']!=content_hash)
            if modified:changed.add(id)
            summary={k:layer.get(k) for k in ('name','kind','crs','bounds','fields','count','geometry_types','provenance')}
            # Refresh physical metadata when an external edit invalidates the snapshot.
            if modified and content_hash!='missing':
                try:
                    paths=self.paths(layer)
                    if layer.get('kind')=='raster':
                        import rasterio
                        with rasterio.open(paths[0]) as src:
                            summary.update(crs=str(src.crs),native_bounds=list(src.bounds),width=src.width,height=src.height)
                    else:
                        import pyogrio
                        info=pyogrio.read_info(paths[-1])
                        summary.update(crs=info['crs'],fields=list(info['fields']),count=int(info['features']),native_bounds=list(info['total_bounds']))
                except Exception:summary['refresh_error']='无法读取更新后的文件，请重新导入。'
            item={'id':id,'uri':[str(p.relative_to(self.store.root)) for p in self.paths(layer)],
                  'content_hash':content_hash,'file_hashes':files,'summary':summary,
                  'source_changed':modified or old.get('source_changed',False),
                  'stale':old.get('stale',False),'updated_at':now()}
            self.store.put_object('catalog',id,item);items.append(item)
        # Transitive invalidation follows provenance, never embeddings.
        stale=set(changed)
        while True:
            previous=set(stale)
            for item in items:
                prov=item['summary'].get('provenance') or {}
                parents=prov.get('input_layers',prov.get('inputs',[]))
                if isinstance(parents,dict):parents=list(parents.values())
                if isinstance(parents,list) and set(x for x in parents if isinstance(x,str))&stale:stale.add(item['id'])
            if stale==previous:break
        for item in items:
            if item['id'] in stale:
                item.update(stale=True,invalidated_at=now());self.store.put_object('catalog',item['id'],item)
        if stale:
            for recipe in self.store.objects('recipes'):
                if set(recipe.get('inputs',{}).values())&stale:
                    recipe.update(status='draft',validation_invalidated_at=now());self.store.put_object('recipes',recipe['id'],recipe)
            for doc in self.store.objects('knowledge'):
                if set(doc.get('layer_ids',[]))&stale:
                    doc['stale']=True;self.store.put_object('knowledge',doc['id'],doc)
        return items

    def context(self,run):
        catalog=self.catalog()
        history=[]
        for old in reversed(self.store.runs(run.get('session_id',''),12)):
            if old['id']==run['id'] or old['status'] not in ('completed','needs_attention','failed','cancelled'):continue
            history.extend([{'role':'user','content':old['message_input'][:4000]},
                            {'role':'assistant','content':old.get('message','')[:6000]}])
        return history[-12:],{'preferences':self.preferences(),
            'project_layers':[{**x['summary'],'id':x['id'],'content_hash':x['content_hash'],'stale':x['stale']} for x in catalog[:150]],
            'selected_layers':run.get('selected_layers',[]),'map':self.store.setting('map_state',{}),
            'plan':self.store.setting('plan:'+run['id'],{}),
            'knowledge':self.search(run['message_input'],limit=3)}

    def _index(self):
        with self.store.db() as db:
            db.execute('CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(id UNINDEXED,title,body,tokenize="trigram")')

    def add_knowledge(self,title,body,source='',layer_ids=None,kind='note',reviewed=False):
        if not title.strip() or not body.strip() or len(body)>60000:raise ValueError('知识需要标题和正文，正文上限60,000字符。')
        for id in layer_ids or []:self.store.get_layer(id)
        item={'id':uuid.uuid4().hex,'title':title[:200],'body':body,'source':source[:1000],
              'kind':kind,'reviewed':reviewed,'layer_ids':layer_ids or [],'sha256':digest(body),'stale':False,'created_at':now()}
        self._index()
        with self.store.db() as db:db.execute('INSERT INTO knowledge_fts VALUES(?,?,?)',(item['id'],item['title'],body))
        return self.store.put_object('knowledge',item['id'],item)

    def search(self,query,limit=5):
        self._index();query=query.strip()[:500];limit=min(max(limit,1),20)
        if not query:return []
        tokens=re.findall(r'[\w\u4e00-\u9fff]+',query)
        phrases=[]
        for token in tokens:
            if re.search(r'[\u4e00-\u9fff]',token) and len(token)>3:
                phrases.extend(token[i:i+3] for i in range(len(token)-2))
            elif len(token)>=3:phrases.append(token)
        rows=[]
        if phrases:
            expr=' OR '.join('"'+x.replace('"','""')+'"' for x in phrases[:60])
            with self.store.db() as db:rows=db.execute('SELECT id FROM knowledge_fts WHERE knowledge_fts MATCH ? ORDER BY rank LIMIT 40',(expr,)).fetchall()
        docs=[self.store.object('knowledge',r['id']) for r in rows]
        if not docs:docs=[x for x in self.store.objects('knowledge') if query.lower() in (x['title']+x['body']).lower()]
        return [{k:v for k,v in d.items() if k!='body'}|{'excerpt':d['body'][:1800]} for d in docs if not d.get('stale')][:limit]

    def forget_knowledge(self,id):
        self._index()
        with self.store.db() as db:db.execute('DELETE FROM knowledge_fts WHERE id=?',(id,))
        self.store.delete_object('knowledge',id)
