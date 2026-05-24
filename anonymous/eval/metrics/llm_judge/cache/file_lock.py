import sys
from typing import IO


if sys.platform == "win32":
    import msvcrt

    def lock_shared(f: IO) -> None:
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)

    def lock_exclusive(f: IO) -> None:
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)

    def unlock(f: IO) -> None:
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def lock_shared(f: IO) -> None:
        fcntl.flock(f.fileno(), fcntl.LOCK_SH)

    def lock_exclusive(f: IO) -> None:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)

    def unlock(f: IO) -> None:
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
