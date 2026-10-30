"""Restart only the verified GAIA uvicorn process on the requested local port."""
import os,subprocess,sys,time,signal
from pathlib import Path
port=int(sys.argv[1]) if len(sys.argv)>1 else 8765
r=subprocess.run(['/usr/sbin/lsof','-tiTCP:'+str(port),'-sTCP:LISTEN'],capture_output=True,text=True)
for value in set(r.stdout.split()):
 pid=int(value);cmd=subprocess.check_output(['/bin/ps','-p',value,'-o','command='],text=True)
 if 'geoagent.app:app' not in cmd or '--port '+str(port) not in cmd:raise RuntimeError('Port owner is not the expected application')
 os.kill(pid,signal.SIGTERM)
for _ in range(40):
 r=subprocess.run(['/usr/sbin/lsof','-tiTCP:'+str(port),'-sTCP:LISTEN'],capture_output=True,text=True)
 if not r.stdout.strip():break
 time.sleep(.15)
else:raise RuntimeError('Port did not become available')
root=Path(__file__).resolve().parents[1];os.chdir(root);os.environ['PORT']=str(port)
os.execv(str(root/'start.sh'),[str(root/'start.sh')])
