"""Small OS adapters for a workspace lease and non-destructive PID checks."""
import os
import sys


class WorkspaceLease:
    def __init__(self,path):
        self.file=path.open('a+b')
        try:
            if sys.platform=='win32':
                import msvcrt
                if self.file.tell()==0:self.file.write(b'\0');self.file.flush()
                self.file.seek(0);msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as exc:
            self.file.close()
            if exc.errno in (11,13):raise BlockingIOError('Workspace is busy') from exc
            raise

    def close(self):
        if self.file.closed:return
        if sys.platform=='win32':
            import msvcrt
            self.file.seek(0);msvcrt.locking(self.file.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            fcntl.flock(self.file,fcntl.LOCK_UN)
        self.file.close()


def process_alive(pid):
    if not isinstance(pid,int) or pid<=0:return False
    if sys.platform=='win32':
        # os.kill(pid, 0) terminates a process on Windows; never use it here.
        import ctypes as C
        from ctypes import wintypes as W
        kernel=C.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];kernel.OpenProcess.restype=W.HANDLE
        kernel.GetExitCodeProcess.argtypes=[W.HANDLE,C.POINTER(W.DWORD)]
        kernel.CloseHandle.argtypes=[W.HANDLE]
        handle=kernel.OpenProcess(0x1000,False,pid)
        if not handle:return C.get_last_error()==5
        try:
            code=W.DWORD()
            if not kernel.GetExitCodeProcess(handle,C.byref(code)):return True
            return code.value==259
        finally:kernel.CloseHandle(handle)
    try:os.kill(pid,0);return True
    except ProcessLookupError:return False
    except PermissionError:return True
