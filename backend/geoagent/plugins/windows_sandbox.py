"""Windows AppContainer + Job Object. No capabilities, no unrestricted fallback.

Only public runtime/code folders receive package read access. Every job gets a
new container SID and access to that job alone; the profile is deleted on exit.
"""
import ctypes as C
from ctypes import wintypes as W
import os
from pathlib import Path
import subprocess
import threading
import time
import uuid

_granted=set()
_lock=threading.Lock()


def launch(command,job,env,stdout,stderr,readable,timeout):
    import msvcrt
    kernel=C.WinDLL('kernel32',use_last_error=True)
    userenv=C.WinDLL('userenv',use_last_error=True)
    advapi=C.WinDLL('advapi32',use_last_error=True)
    def api(dll,name,restype,args):
        fn=getattr(dll,name);fn.restype=restype;fn.argtypes=args;return fn
    void=C.c_void_p;size=C.c_size_t
    close=api(kernel,'CloseHandle',W.BOOL,[W.HANDLE])
    create_profile=api(userenv,'CreateAppContainerProfile',C.c_long,[W.LPCWSTR,W.LPCWSTR,W.LPCWSTR,void,W.DWORD,C.POINTER(void)])
    delete_profile=api(userenv,'DeleteAppContainerProfile',C.c_long,[W.LPCWSTR])
    sid_string=api(advapi,'ConvertSidToStringSidW',W.BOOL,[void,C.POINTER(W.LPWSTR)])
    free_sid=api(advapi,'FreeSid',void,[void])
    local_free=api(kernel,'LocalFree',void,[void])
    initialize=api(kernel,'InitializeProcThreadAttributeList',W.BOOL,[void,W.DWORD,W.DWORD,C.POINTER(size)])
    update=api(kernel,'UpdateProcThreadAttribute',W.BOOL,[void,W.DWORD,size,void,size,void,void])
    delete_attributes=api(kernel,'DeleteProcThreadAttributeList',None,[void])

    class Caps(C.Structure):
        _fields_=[('sid',void),('capabilities',void),('count',W.DWORD),('reserved',W.DWORD)]
    class Startup(C.Structure):
        _fields_=[('cb',W.DWORD),('reserved',W.LPWSTR),('desktop',W.LPWSTR),('title',W.LPWSTR),
                  ('x',W.DWORD),('y',W.DWORD),('xs',W.DWORD),('ys',W.DWORD),('xc',W.DWORD),('yc',W.DWORD),
                  ('fill',W.DWORD),('flags',W.DWORD),('show',W.WORD),('reserved2',W.WORD),('reserved_ptr',void),
                  ('stdin',W.HANDLE),('stdout',W.HANDLE),('stderr',W.HANDLE)]
    class StartupEx(C.Structure):_fields_=[('startup',Startup),('attributes',void)]
    class ProcessInfo(C.Structure):_fields_=[('process',W.HANDLE),('thread',W.HANDLE),('pid',W.DWORD),('tid',W.DWORD)]
    class BasicLimits(C.Structure):
        _fields_=[('process_time',C.c_longlong),('job_time',C.c_longlong),('flags',W.DWORD),
                  ('min_ws',size),('max_ws',size),('active',W.DWORD),('affinity',size),('priority',W.DWORD),('scheduling',W.DWORD)]
    class Io(C.Structure):_fields_=[(name,C.c_ulonglong) for name in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
    class ExtendedLimits(C.Structure):
        _fields_=[('basic',BasicLimits),('io',Io),('process_memory',size),('job_memory',size),('peak_process',size),('peak_job',size)]
    create_job=api(kernel,'CreateJobObjectW',W.HANDLE,[void,W.LPCWSTR])
    set_limits=api(kernel,'SetInformationJobObject',W.BOOL,[W.HANDLE,C.c_int,void,W.DWORD])
    assign=api(kernel,'AssignProcessToJobObject',W.BOOL,[W.HANDLE,W.HANDLE])
    terminate=api(kernel,'TerminateJobObject',W.BOOL,[W.HANDLE,W.UINT])
    resume=api(kernel,'ResumeThread',W.DWORD,[W.HANDLE])
    get_exit=api(kernel,'GetExitCodeProcess',W.BOOL,[W.HANDLE,C.POINTER(W.DWORD)])
    create_process=api(kernel,'CreateProcessW',W.BOOL,[W.LPCWSTR,W.LPWSTR,void,void,W.BOOL,W.DWORD,void,W.LPCWSTR,C.POINTER(StartupEx),C.POINTER(ProcessInfo)])
    def ensure(ok):
        if not ok:raise C.WinError(C.get_last_error())
    def acl(path,*args):
        result=subprocess.run(['icacls',str(path),*args],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:raise OSError('Cannot grant isolated worker access: '+result.stderr.decode(errors='replace')[-1000:])
    name='gaia.job.'+uuid.uuid4().hex
    sid=void();profile=False;attrs=None;handle=None;info=ProcessInfo()
    try:
        hr=create_profile(name,'GAIA analysis','Isolated local GIS job',None,0,C.byref(sid))
        if hr<0:raise OSError(f'CreateAppContainerProfile failed: {hr & 0xffffffff:08x}')
        profile=True;string=W.LPWSTR();ensure(sid_string(sid,C.byref(string)))
        try:sid_text=string.value
        finally:local_free(C.cast(string,void))
        with _lock:
            for folder in readable:
                folder=str(Path(folder).resolve())
                if folder not in _granted:
                    acl(folder,'/grant','*S-1-15-2-1:(OI)(CI)(RX)','/T','/Q')
                    _granted.add(folder)
        # Qt's atomic project save preserves file ACLs, which needs WRITE_DAC.
        # Full control is scoped to this disposable job; runtime/code remain RX.
        acl(job,'/grant',f'*{sid_text}:(OI)(CI)(F)','/T','/Q')
        acl(job,'/setintegritylevel','(OI)(CI)L','/T','/Q')
        length=size();initialize(None,2,0,C.byref(length))
        attrs=C.create_string_buffer(length.value);ensure(initialize(attrs,2,0,C.byref(length)))
        caps=Caps(sid,None,0,0)
        ensure(update(attrs,0,0x20009,C.byref(caps),C.sizeof(caps),None,None))
        startup=StartupEx();startup.startup.cb=C.sizeof(startup);startup.startup.flags=0x100;startup.attributes=C.cast(attrs,void)
        handle=create_job(None,None);ensure(handle)
        limits=ExtendedLimits();limits.basic.flags=0x2000|0x4|0x8|0x200
        limits.basic.job_time=(timeout+5)*10000000;limits.basic.active=32;limits.job_memory=4*1024**3
        ensure(set_limits(handle,9,C.byref(limits),C.sizeof(limits)))
        env_block=C.create_unicode_buffer('\0'.join(f'{k}={v}' for k,v in sorted(env.items()))+'\0\0')
        with open(os.devnull,'rb') as null:
            handles=[msvcrt.get_osfhandle(f.fileno()) for f in (null,stdout,stderr)]
            for h in handles:os.set_handle_inheritable(h,True)
            try:
                startup.startup.stdin,startup.startup.stdout,startup.startup.stderr=handles
                inherited=(W.HANDLE*3)(*handles)
                ensure(update(attrs,0,0x20002,inherited,C.sizeof(inherited),None,None))
                ensure(create_process(command[0],C.create_unicode_buffer(subprocess.list2cmdline(command)),None,None,True,
                                      0x80000|0x400|0x08000000|0x4,env_block,str(job),C.byref(startup),C.byref(info)))
            finally:
                for h in handles:os.set_handle_inheritable(h,False)
        ensure(assign(handle,info.process))
        ensure(resume(info.thread)!=0xffffffff);close(info.thread);info.thread=None
    except BaseException:
        if info.process:
            api(kernel,'TerminateProcess',W.BOOL,[W.HANDLE,W.UINT])(info.process,1);close(info.process)
        if info.thread:close(info.thread)
        if handle:close(handle)
        if profile:delete_profile(name)
        raise
    finally:
        if attrs:delete_attributes(attrs)
        if sid:free_sid(sid)

    class ContainerProcess:
        pid=info.pid
        returncode=None
        closed=False
        def poll(self):
            if self.returncode is not None:return self.returncode
            code=W.DWORD();ensure(get_exit(info.process,C.byref(code)))
            if code.value!=259:self.returncode=code.value
            return self.returncode
        def kill(self):ensure(terminate(handle,1))
        def wait(self):
            while self.poll() is None:time.sleep(.05)
            return self.returncode
        def close(self):
            if self.closed:return
            self.closed=True
            if self.poll() is None:self.kill();self.wait()
            close(handle);close(info.process);delete_profile(name)
    return ContainerProcess()
