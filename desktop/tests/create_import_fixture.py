"""Synthetic Chinese Shapefile with a deliberately truncated UTF-8 field name."""
import hashlib
import json
from pathlib import Path
import geopandas as gpd
from shapely.geometry import Point

folder=Path(__file__).resolve().parents[2]/'.desktop-build/qa/import-fixtures'
folder.mkdir(parents=True,exist_ok=True)
path=folder/'中文地铁_导入验证.shp'
gpd.GeoDataFrame({'name':['钟楼站'],'field_1':[11]},geometry=[Point(108.94,34.26)],crs=4326).to_file(
    path,engine='pyogrio',encoding='UTF-8')
dbf=path.with_suffix('.dbf');raw=bytearray(dbf.read_bytes())
raw[32:43]='地铁站人口'.encode()[:10]+b'\0';dbf.write_bytes(raw)
print(json.dumps({'fixture':str(folder),'dbf_sha256':hashlib.sha256(raw).hexdigest()},ensure_ascii=False))
