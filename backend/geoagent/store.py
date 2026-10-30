"""Local immutable artifacts and SQLite metadata; no user-provided filesystem paths."""
from __future__ import annotations
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / 'layers').mkdir(exist_ok=True)
        self.lock = threading.RLock()
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS layers(id TEXT PRIMARY KEY, metadata TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(run_id TEXT, seq INTEGER, data TEXT, PRIMARY KEY(run_id,seq));
            ''')
            for row in db.execute('SELECT id,data FROM runs').fetchall():
                run = json.loads(row['data'])
                if run['status'] in ('queued', 'running'):
                    run.update(status='interrupted', finished_at=now(), message='服务重新启动；任务已中断。请重新提交，不会自动重复执行。')
                    db.execute('UPDATE runs SET data=? WHERE id=?', (json.dumps(run, ensure_ascii=False), run['id']))

    def db(self):
        db = sqlite3.connect(self.root / 'workspace.sqlite3', timeout=15)
        db.row_factory = sqlite3.Row
        return db

    def layers(self):
        with self.db() as db:
            return [json.loads(r['metadata']) for r in db.execute('SELECT metadata FROM layers ORDER BY rowid')]

    def get_layer(self, layer_id):
        with self.db() as db:
            row = db.execute('SELECT metadata FROM layers WHERE id=?', (layer_id,)).fetchone()
        if row is None:
            raise ValueError('图层不存在，请先调用 list_layers 读取当前图层。')
        return json.loads(row['metadata'])

    def data(self, layer_id):
        self.get_layer(layer_id)
        return json.loads((self.root / 'layers' / f'{layer_id}.geojson').read_text())

    def add_layer(self, name, collection, *, source='upload', provenance=None, style=None):
        import hashlib
        from shapely.geometry import shape
        from shapely.ops import unary_union
        layer_id = uuid.uuid4().hex
        data = json.dumps(collection, ensure_ascii=False, allow_nan=False)
        geometries = [shape(f['geometry']) for f in collection['features']]
        bounds = list(unary_union(geometries).bounds) if geometries else [0,0,0,0]
        fields = sorted({k for f in collection['features'] for k in f.get('properties', {})})
        meta = dict(kind='vector', id=layer_id, name=name[:100], count=len(geometries), bounds=bounds, fields=fields,
                    geometry_types=sorted({g.geom_type for g in geometries}), crs='EPSG:4326', source=source,
                    sha256=hashlib.sha256(data.encode()).hexdigest(), created_at=now(),
                    provenance=provenance or {}, style=style or {'color': '#128a78', 'visible': True})
        path = self.root / 'layers' / f'{layer_id}.geojson'
        temp = path.with_suffix('.tmp')
        temp.write_text(data)
        os.replace(temp, path)
        with self.lock, self.db() as db:
            db.execute('INSERT INTO layers VALUES(?,?)', (layer_id, json.dumps(meta, ensure_ascii=False)))
        return meta

    def style_layer(self, layer_id, **style):
        with self.lock:
            meta = self.get_layer(layer_id)
            if meta.get('qgis_style_path') and any(k in style for k in ('color','field','labels')):meta.pop('qgis_style_path',None)
            meta['style'].update({k:v for k,v in style.items() if v is not None or k=='field'})
            with self.db() as db:
                db.execute('UPDATE layers SET metadata=? WHERE id=?', (json.dumps(meta, ensure_ascii=False), layer_id))
        return meta

    def save_run(self, run):
        with self.lock, self.db() as db:
            db.execute('INSERT OR REPLACE INTO runs VALUES(?,?)', (run['id'], json.dumps(run, ensure_ascii=False)))

    def run(self, run_id):
        with self.db() as db:
            row = db.execute('SELECT data FROM runs WHERE id=?', (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        return json.loads(row['data'])

    def runs(self):
        with self.db() as db:
            return [json.loads(r['data']) for r in db.execute('SELECT data FROM runs ORDER BY rowid DESC LIMIT 50')]

    def event(self, run_id, kind, data):
        with self.lock, self.db() as db:
            seq = db.execute('SELECT COALESCE(MAX(seq),0)+1 FROM events WHERE run_id=?', (run_id,)).fetchone()[0]
            event = dict(seq=seq, type=kind, time=now(), data=data)
            db.execute('INSERT INTO events VALUES(?,?,?)', (run_id, seq, json.dumps(event, ensure_ascii=False)))
        return event

    def events(self, run_id):
        with self.db() as db:
            return [json.loads(r['data']) for r in db.execute('SELECT data FROM events WHERE run_id=? ORDER BY seq', (run_id,))]

    def put_object(self, kind, object_id, data):
        with self.lock, self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS objects(kind TEXT,id TEXT,data TEXT,PRIMARY KEY(kind,id))')
            db.execute('INSERT OR REPLACE INTO objects VALUES(?,?,?)',(kind,object_id,json.dumps(data,ensure_ascii=False,allow_nan=False)))
        return data

    def object(self, kind, object_id):
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS objects(kind TEXT,id TEXT,data TEXT,PRIMARY KEY(kind,id))')
            row=db.execute('SELECT data FROM objects WHERE kind=? AND id=?',(kind,object_id)).fetchone()
        if not row:
            raise ValueError('工作区资源不存在。')
        return json.loads(row['data'])

    def objects(self, kind):
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS objects(kind TEXT,id TEXT,data TEXT,PRIMARY KEY(kind,id))')
            return [json.loads(x['data']) for x in db.execute('SELECT data FROM objects WHERE kind=? ORDER BY rowid DESC',(kind,))]

    def setting(self, name, default=None):
        try:
            return self.object('settings',name)
        except ValueError:
            return default

    def add_raster(self, name, path, provenance=None):
        from .formats import register_raster
        return register_raster(self,name,path,provenance or {})

    def patch_layer(self, layer_id, changes):
        with self.lock:
            meta=self.get_layer(layer_id);meta.update(changes)
            with self.db() as db:
                db.execute('UPDATE layers SET metadata=? WHERE id=?',(json.dumps(meta,ensure_ascii=False),layer_id))
        return meta
