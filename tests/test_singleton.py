from __future__ import annotations

import os

from tesseract_studio.singleton import SingleInstanceGuard


def _unique_key() -> str:
    return f"TesseractOcrStudioTest{os.getpid()}"


def test_only_one_instance_owns_the_lock(qapp) -> None:
    key = _unique_key()
    first = SingleInstanceGuard(key)
    second = SingleInstanceGuard(key)

    assert first.acquire() is True
    assert first.owns_lock is True

    assert second.acquire() is False
    assert second.owns_lock is False

    first.release()
    assert third_acquire(key) is True


def third_acquire(key: str) -> bool:
    guard = SingleInstanceGuard(key)
    result = guard.acquire()
    guard.release()
    return result


def test_released_lock_can_be_taken_over(qapp) -> None:
    key = _unique_key()
    guard = SingleInstanceGuard(key)
    assert guard.acquire() is True
    guard.release()
    assert guard.owns_lock is False

    other = SingleInstanceGuard(key)
    assert other.acquire() is True
    other.release()


def test_window_handle_round_trip(qapp) -> None:
    key = _unique_key()
    guard = SingleInstanceGuard(key)
    assert guard.acquire() is True

    reader = SingleInstanceGuard(key)
    guard.publish_window(123456)
    assert reader.read_window() == 123456

    guard.release()
