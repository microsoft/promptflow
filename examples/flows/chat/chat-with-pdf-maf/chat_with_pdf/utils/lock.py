import contextlib
import os
import sys

if sys.platform.startswith("win"):
    import msvcrt
else:
    import fcntl


@contextlib.contextmanager
def acquire_lock(filename):
    if not sys.platform.startswith("win"):
        with open(filename, "a+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            yield f
            fcntl.flock(f, fcntl.LOCK_UN)
    else:  # Windows
        with open(filename, "w") as f:
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
            yield f
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)

    try:
        os.remove(filename)
    except OSError:
        pass  # best effort to remove the lock file
