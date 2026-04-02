"""文件锁模块.

提供跨平台的文件锁定功能，支持 Windows (msvcrt) 和 Unix (fcntl)。
用于在多进程/多线程环境下防止文件并发写入冲突。
"""

import errno
import os
import time

MAX_LOCK_BYTES = 2147483647

try:
    import msvcrt

    def file_lock(file_handle, exclusive=True, non_blocking=True):
        """Windows 文件锁定实现.

        Args:
            file_handle: 打开的文件对象
            exclusive: 是否为独占锁
            non_blocking: 是否为非阻塞模式
        """
        fd = file_handle.fileno()
        mode = msvcrt.LK_NBLCK if non_blocking else msvcrt.LK_LOCK

        current_pos = file_handle.tell()
        file_handle.seek(0)
        try:
            msvcrt.locking(fd, mode, MAX_LOCK_BYTES)
        finally:
            file_handle.seek(current_pos)

    def file_unlock(file_handle):
        """Windows 文件解锁实现.

        Args:
            file_handle: 打开的文件对象
        """
        fd = file_handle.fileno()

        current_pos = file_handle.tell()
        file_handle.seek(0)
        try:
            msvcrt.locking(fd, msvcrt.LK_UNLCK, MAX_LOCK_BYTES)
        finally:
            file_handle.seek(current_pos)

except ImportError:
    import fcntl

    def file_lock(file_handle, exclusive=True, non_blocking=True):
        """Unix 文件锁定实现.

        Args:
            file_handle: 打开的文件对象
            exclusive: 是否为独占锁
            non_blocking: 是否为非阻塞模式
        """
        op = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        if non_blocking:
            op |= fcntl.LOCK_NB
        fcntl.flock(file_handle, op)

    def file_unlock(file_handle):
        """Unix 文件解锁实现.

        Args:
            file_handle: 打开的文件对象
        """
        fcntl.flock(file_handle, fcntl.LOCK_UN)


class FileLock:
    """文件锁上下文管理器.

    使用示例:
        with open("file.txt", "w") as f:
            with FileLock(f):
                f.write("data")
    """

    def __init__(self, file_handle, exclusive=True, timeout=10.0, interval=0.1):
        """初始化文件锁.

        Args:
            file_handle: 打开的文件对象
            exclusive: 是否为独占锁 (默认为 True)
            timeout: 获取锁的超时时间 (秒)
            interval: 重试间隔 (秒)
        """
        self.file_handle = file_handle
        self.exclusive = exclusive
        self.timeout = timeout
        self.interval = interval

    def __enter__(self):
        """获取锁.

        Returns:
            self
        """
        start_time = time.time()
        while True:
            try:
                file_lock(self.file_handle, self.exclusive, non_blocking=True)
                return self
            except (IOError, OSError) as e:
                if e.errno not in (
                    errno.EACCES, errno.EAGAIN,
                    errno.EDEADLK, 13, 11
                ):
                    raise

                if time.time() - start_time > self.timeout:
                    raise TimeoutError(
                        f"Could not acquire lock on "
                        f"{getattr(self.file_handle, 'name', 'file')} "
                        f"after {self.timeout}s"
                    )

                time.sleep(self.interval)

    def __exit__(self, exc_type, exc_val, exc_tb):
        """释放锁."""
        try:
            file_unlock(self.file_handle)
        except (IOError, OSError):
            pass
