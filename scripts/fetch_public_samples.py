"""Download small, traceable public GIS samples. No API credentials required."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile

import geopandas as gpd
import httpx
import rasterio

ROOT = Path(__file__).resolve().parents[1] / 'outputs' / 'public-cartography'
RAW = ROOT / 'raw'
CENSUS = 'https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip'
USGS = 'https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer'


def retrieve(url, target, params=None):
    with httpx.Client(timeout=httpx.Timeout(120, connect=20), follow_redirects=True) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
    if len(response.content) > 20 * 1024 * 1024:
        raise ValueError('Sample response exceeds 20 MB.')
    target.write_bytes(response.content)
    return {'url': str(response.url), 'bytes': len(response.content),
            'sha256': hashlib.sha256(response.content).hexdigest(),
            'retrieved_utc': datetime.now(timezone.utc).isoformat()}


def vector():
    target = RAW / 'cb_2024_us_county_500k.zip'
    receipt = retrieve(CENSUS, target)
    frame = gpd.read_file(target, engine='pyogrio')
    washington = frame.loc[frame['STATEFP'] == '53'].copy()
    assert len(washington) == 39
    folder = RAW / 'washington-counties'
    folder.mkdir(exist_ok=True)
    path = folder / 'washington-counties.shp'
    washington.to_file(path, driver='ESRI Shapefile', engine='pyogrio', encoding='UTF-8')
    zipped = RAW / 'washington-counties-shp.zip'
    with zipfile.ZipFile(zipped, 'w', zipfile.ZIP_DEFLATED) as archive:
        for part in folder.iterdir():
            archive.write(part, part.name)
    return {**receipt, 'publisher': 'U.S. Census Bureau', 'vintage': 2024,
            'input_scale': '1:500,000 cartographic boundaries',
            'subset': 'STATEFP=53; 39 Washington counties; no fabricated attributes',
            'subset_file': str(zipped.relative_to(ROOT)), 'subset_bytes': zipped.stat().st_size,
            'crs': str(washington.crs), 'fields': list(washington.columns),
            'metric': 'ALAND in square metres; land_area_km2 = ALAND / 1e6'}


def elevation():
    params = {'f': 'json', 'bbox': '-121.94,46.72,-121.53,47.02', 'bboxSR': 4326,
              'imageSR': 32610, 'size': '1000,1000', 'format': 'tiff', 'pixelType': 'F32',
              'interpolation': 'RSP_BilinearInterpolation',
              'renderingRule': json.dumps({'rasterFunction': 'None'})}
    with httpx.Client(timeout=httpx.Timeout(120, connect=20), follow_redirects=True) as client:
        response = client.get(USGS + '/exportImage', params=params)
        response.raise_for_status()
        export = response.json()
        if 'href' not in export:
            raise ValueError('USGS did not return a raster export: ' + json.dumps(export)[:600])
        metadata = client.get(USGS, params={'f': 'pjson'})
        metadata.raise_for_status()
    (RAW / 'usgs-export-response.json').write_text(json.dumps(export, indent=2))
    (RAW / 'usgs-service-metadata.json').write_text(metadata.text)
    target = RAW / 'rainier-usgs-3dep.tif'
    receipt = retrieve(export['href'], target)
    with rasterio.open(target) as raster:
        assert raster.crs.to_epsg() == 32610 and raster.count == 1
        values = raster.read(1, masked=True)
        if not (values.min() < 1500 and values.max() > 4000):
            raise ValueError('Unexpected elevation values; refuse to treat rendered colors as DEM.')
        info = {'crs': str(raster.crs), 'width': raster.width, 'height': raster.height,
                'pixel_size_m': [raster.res[0], raster.res[1]], 'dtype': raster.dtypes[0],
                'minimum_m': float(values.min()), 'maximum_m': float(values.max()),
                'nodata': raster.nodata}
    return {**receipt, **info, 'publisher': 'USGS 3D Elevation Program',
            'service': USGS, 'request': str(response.url), 'request_parameters': params,
            'file': str(target.relative_to(ROOT)),
            'processing': 'Public multi-resolution elevation service AOI export, bilinearly resampled; not a native-resolution tile or a new survey.'}


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(vector), pool.submit(elevation)
        manifest = {'vector': a.result(), 'raster': b.result()}
    (ROOT / 'sources.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
