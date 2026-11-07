"""Single instance guard.

Launching the studio twice used to leave two independent windows on screen,
each with its own event loop. A named shared memory segment keeps one owner
per machine: the second launch finds the running instance, asks it to come to
the front, and exits instead of opening another window.

``QLocalServer`` is not used for this. On Windows the named pipe name is
derived from the session and the service, so two processes in the same session
can both succeed in listening, which makes it useless as a mutex.

The segment also stores the window handle of the running instance, so a second
launch can raise the existing window instead of showing a message box.

The guard fails open. If the segment cannot be created for any reason other
than "another instance already owns it", the application continues without the
guard rather than refusing to start.
"""

from __future__ import annotations

from typing import Optional

from PyQt5 import QtCore

try:  # pragma: no cover - Windows only helper
    import ctypes
    from ctypes import wintypes
except ImportError:  # pragma: no cover
    ctypes = None
    wintypes = None


def _raise_window(handle: int) -> bool:
    """Bring an existing window to the front."""
    if ctypes is None or not handle:
        return False
    try:
        user32 = ctypes.windll.user32  # type: ignore[union-attr]
        user32.ShowWindow(wintypes.HWND(handle), 9)  # SW_RESTORE
        user32.SetForegroundWindow(wintypes.HWND(handle))
        user32.BringWindowToTop(wintypes.HWND(handle))
    except Exception:  # noqa: BLE001 - best effort only
        return False
    return True


class SingleInstanceGuard(QtCore.QObject):
    """Owns a named shared memory segment for the lifetime of the process."""

    SIZE = 8

    def __init__(self, key: str = "TesseractOcrStudio") -> None:
        super().__init__()
        self._key = key
        self._segment: Optional[QtCore.QSharedMemory] = None
        self._owns = False

    @property
    def owns_lock(self) -> bool:
        """True when this process is the instance that owns the lock."""
        return self._owns

    def acquire(self) -> bool:
        """Try to become the single instance.

        Returns True when this process owns the lock, and False when another
        instance already owns it.
        """
        segment = QtCore.QSharedMemory(self._key)
        segment.setKey(self._key)
        if segment.create(self.SIZE):
            self._segment = segment
            self._owns = True
            return True

        if segment.error() == QtCore.QSharedMemory.AlreadyExists:
            return False

        # The segment could not be created for an unrelated reason. Run
        # without the guard instead of refusing to start.
        self._segment = None
        self._owns = True
        return True

    def publish_window(self, handle: int) -> None:
        """Publish the window handle so a second launch can raise it."""
        if self._segment is None:
            return
        try:
            self._segment.lock()
        except RuntimeError:
            return
        try:
            self._segment.data()[0:8] = int(handle).to_bytes(8, "little")
            self._segment.unlock()
        except Exception:  # noqa: BLE001 - best effort only
            try:
                self._segment.unlock()
            except RuntimeError:
                pass

    def read_window(self) -> int:
        """Read the window handle published by the running instance."""
        segment = QtCore.QSharedMemory(self._key)
        segment.setKey(self._key)
        if not segment.attach(QtCore.QSharedMemory.ReadOnly):
            return 0
        try:
            segment.lock()
        except RuntimeError:
            segment.detach()
            return 0
        try:
            raw = bytes(segment.data()[0:8])
        finally:
            try:
                segment.unlock()
            except RuntimeError:
                pass
            segment.detach()
        try:
            return int.from_bytes(raw, "little")
        except ValueError:
            return 0

    def release(self) -> None:
        """Give the lock up so a restarted instance can take it over."""
        if self._segment is not None:
            self._segment.detach()
            self._segment = None
        self._owns = False


_active_guard: Optional[SingleInstanceGuard] = None


def acquire_single_instance(key: str = "TesseractOcrStudio") -> SingleInstanceGuard:
    """Acquire the single instance lock and remember the guard."""
    global _active_guard
    guard = SingleInstanceGuard(key)
    guard.acquire()
    _active_guard = guard
    return guard


def release_single_instance() -> None:
    """Release the lock of the running instance, if there is one.

    The language switch restarts the application. The lock has to be given up
    before the new process is started, otherwise the new process would find
    the lock taken by the instance it is replacing and refuse to start.
    """
    if _active_guard is not None:
        _active_guard.release()


def activate_running_instance(key: str = "TesseractOcrStudio") -> bool:
    """Raise the window of the instance that already owns the lock."""
    guard = SingleInstanceGuard(key)
    handle = guard.read_window()
    if not handle:
        return False
    return _raise_window(handle)
