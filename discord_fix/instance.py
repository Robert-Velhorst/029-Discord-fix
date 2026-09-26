"""Keep one writer and privacy policy owner per local database."""

import os


class InstanceLock:
    def __init__(self, path):
        self.file = open(path, "a+b")
        try:
            if os.fstat(self.file.fileno()).st_size == 0:
                self.file.write(b"0")
                self.file.flush()
            self.file.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise RuntimeError("Discord Fix is al actief voor deze gegevensmap.") from None

    def close(self):
        self.file.close()
