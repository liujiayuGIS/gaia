"""Desktop sidecar: authenticated loopback server, ephemeral port, parent lifetime."""
import json
import os
from pathlib import Path
import socket
import sys
import threading


def main():
    import uvicorn
    if len(os.environ.get('GAIA_DESKTOP_TOKEN',''))<32:
        raise RuntimeError('Desktop requires a private session token.')
    ready=Path(os.environ['GAIA_DESKTOP_READY'])
    ready.parent.mkdir(parents=True,exist_ok=True)
    sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    sock.bind(('127.0.0.1',0));sock.listen(128)
    server=uvicorn.Server(uvicorn.Config('geoagent.app:app',log_level='warning',access_log=False))
    def parent_lifetime():
        sys.stdin.buffer.read()
        server.should_exit=True
    threading.Thread(target=parent_lifetime,daemon=True).start()
    ready.write_text(json.dumps({'port':sock.getsockname()[1],'pid':os.getpid()}))
    try:server.run(sockets=[sock])
    finally:ready.unlink(missing_ok=True);sock.close()


if __name__=='__main__':main()
