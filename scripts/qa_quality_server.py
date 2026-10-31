"""Isolated browser QA with real public Census/USGS data; never uses user data."""
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
os.environ.setdefault('GEOAGENT_WORKSPACE','/private/tmp/gaia-quality-browser-workspace')
from seed_native_demo import seed
seed(Path(os.environ['GEOAGENT_WORKSPACE']))
from geoagent.app import app

if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=8767)
