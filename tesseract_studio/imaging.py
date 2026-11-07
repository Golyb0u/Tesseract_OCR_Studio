"""Image conversion and screen-capture helpers."""

from __future__ import annotations

from pathlib import Path

import cv2
import mss
import numpy as np
from PyQt5 import QtGui

from .i18n import tr


def numpy_to_pixmap(image: np.ndarray) -> QtGui.QPixmap:
    if len(image.shape) == 2:
        qimage = QtGui.QImage(
            image.data,
            image.shape[1],
            image.shape[0],
            image.strides[0],
            QtGui.QImage.Format_Grayscale8,
        ).copy()
    else:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        qimage = QtGui.QImage(
            rgb.data,
            rgb.shape[1],
            rgb.shape[0],
            rgb.strides[0],
            QtGui.QImage.Format_RGB888,
        ).copy()
    return QtGui.QPixmap.fromImage(qimage)


def qimage_to_numpy(image: QtGui.QImage) -> np.ndarray:
    converted = image.convertToFormat(QtGui.QImage.Format_RGBA8888)
    width = converted.width()
    height = converted.height()
    ptr = converted.bits()
    ptr.setsize(converted.byteCount())
    array = np.frombuffer(ptr, np.uint8).reshape((height, width, 4))
    return cv2.cvtColor(array, cv2.COLOR_RGBA2BGR)


def load_image_from_file(path: str) -> np.ndarray:
    data = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(tr("Не удалось загрузить изображение из файла."))
    return image


def grab_region_image(region: dict) -> np.ndarray:
    with mss.mss() as sct:
        shot = np.array(sct.grab(region))
    return cv2.cvtColor(shot, cv2.COLOR_BGRA2BGR)


def image_size_text(image: np.ndarray | None) -> str:
    if image is None:
        return tr("нет данных")
    height, width = image.shape[:2]
    return f"{width} x {height} px"


def copy_image_to_clipboard(image: np.ndarray) -> None:
    from PyQt5 import QtWidgets

    QtWidgets.QApplication.clipboard().setPixmap(numpy_to_pixmap(image))


def save_numpy_image(path: str | Path, image: np.ndarray) -> None:
    target = Path(path)
    suffix = target.suffix.lower()
    if suffix == ".png":
        data = cv2.imencode(".png", image)[1]
    elif suffix in {".jpg", ".jpeg"}:
        data = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 95])[1]
    else:
        data = cv2.imencode(".png", image)[1]
    target.write_bytes(data.tobytes())
