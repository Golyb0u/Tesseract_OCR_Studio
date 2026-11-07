"""Application constants, typed configuration and profile persistence."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Optional

from .i18n import tr

APP_NAME = "Tesseract OCR Studio"
APP_VERSION = "2.1.0"
ORG_NAME = "TesseractStudio"
APP_ID = "studio"

# PSM descriptions are also used by the context menu and the live help panel.
PSM_DESCRIPTIONS = {
    0: "OSD only. Определяет ориентацию и направление текста без распознавания.",
    1: "Auto page segmentation with OSD. Обычный режим с автоматическим анализом ориентации.",
    2: "Auto page segmentation without OCR. Ищет блоки текста, но не распознаёт символы.",
    3: "Fully automatic page segmentation. Полностью автоматическая разметка страницы.",
    4: "Single column of text. Одна колонка текста переменной ширины.",
    5: "Single uniform block of vertically aligned text. Один блок вертикального текста.",
    6: "Single uniform block of text. Один ровный блок текста, хорошая универсальная база.",
    7: "Single text line. Одна строка текста, например подпись, лог или значение интерфейса.",
    8: "Single word. Одно слово без соседних символов.",
    9: "Single word in a circle. Слово, вписанное в окружность.",
    10: "Single character. Один символ - буква, цифра или знак.",
    11: "Sparse text. Разрозненный текст без единой сетки строк.",
    12: "Sparse text with OSD. Режим 11 с дополнительным анализом ориентации.",
    13: "Raw line. Сырая строка без дополнительной эвристики Tesseract.",
}

TESSERACT_HINT_PATHS = [
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
    Path.home() / "AppData" / "Local" / "Programs" / "Tesseract-OCR" / "tesseract.exe",
]

TESSDATA_HINT_DIRS = [
    Path(r"C:\Program Files\Tesseract-OCR\tessdata"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tessdata"),
    Path.home() / "AppData" / "Local" / "Programs" / "Tesseract-OCR" / "tessdata",
]

OCR_PRESETS = {
    "single_digit_strict": {
        "title": "Одна цифра (строго)",
        "description": "Максимально строгий режим для одной цифры или символа с жёстким whitelist и отключёнными словарями.",
        "values": {
            "language": "eng",
            "psm": 10,
            "oem": 3,
            "threshold_mode": "binary",
            "threshold_value": 170,
            "adaptive_block_size": 31,
            "adaptive_c": 10,
            "blur_kernel": 0,
            "scale": 4.0,
            "invert": False,
            "grayscale": True,
            "whitelist": "0123456789",
            "blacklist": "OoIl|><].,;:'\"",
            "min_confidence": 0,
            "preserve_spaces": False,
            "user_defined_dpi": 300,
            "extra_config": "-c load_system_dawg=0 -c load_freq_dawg=0",
        },
    },
    "digits": {
        "title": "Цифры",
        "description": "Распознавание чисел: отключённые словари и разрешённые цифры заметно снижают число ложных букв.",
        "values": {
            "language": "eng",
            "psm": 10,
            "oem": 3,
            "threshold_mode": "binary",
            "threshold_value": 170,
            "adaptive_block_size": 31,
            "adaptive_c": 10,
            "blur_kernel": 0,
            "scale": 4.0,
            "invert": False,
            "grayscale": True,
            "whitelist": "0123456789",
            "blacklist": "OoIl|><].,",
            "min_confidence": 0,
            "preserve_spaces": False,
            "user_defined_dpi": 300,
            "extra_config": "",
        },
    },
    "strict_ui": {
        "title": "Строгий интерфейс",
        "description": "Для интерфейса: контрастная бинаризация и уверенность не ниже 35 отсекают мусор.",
        "values": {
            "language": "eng",
            "psm": 7,
            "oem": 3,
            "threshold_mode": "otsu",
            "threshold_value": 150,
            "adaptive_block_size": 31,
            "adaptive_c": 8,
            "blur_kernel": 0,
            "scale": 3.0,
            "invert": False,
            "grayscale": True,
            "whitelist": "",
            "blacklist": "",
            "min_confidence": 35,
            "preserve_spaces": True,
            "user_defined_dpi": 300,
            "extra_config": "",
        },
    },
    "small_text": {
        "title": "Мелкий текст",
        "description": "Для мелкого текста, где важны увеличение и устойчивость к шуму.",
        "values": {
            "language": "eng",
            "psm": 6,
            "oem": 3,
            "threshold_mode": "adaptive_gaussian",
            "threshold_value": 150,
            "adaptive_block_size": 31,
            "adaptive_c": 10,
            "blur_kernel": 3,
            "scale": 4.0,
            "invert": False,
            "grayscale": True,
            "whitelist": "",
            "blacklist": "",
            "min_confidence": 15,
            "preserve_spaces": False,
            "user_defined_dpi": 300,
            "extra_config": "",
        },
    },
    "chat_text": {
        "title": "Текст чата",
        "description": "Для строк чата и сообщений, где важно сохранить пробелы и не потерять слова.",
        "values": {
            "language": "eng+rus",
            "psm": 6,
            "oem": 3,
            "threshold_mode": "adaptive_mean",
            "threshold_value": 150,
            "adaptive_block_size": 35,
            "adaptive_c": 12,
            "blur_kernel": 3,
            "scale": 2.0,
            "invert": False,
            "grayscale": True,
            "whitelist": "",
            "blacklist": "",
            "min_confidence": 10,
            "preserve_spaces": True,
            "user_defined_dpi": 300,
            "extra_config": "",
        },
    },
}


def _is_source_checkout() -> bool:
    """True when the package runs from a project checkout, not from site-packages."""
    package_dir = Path(__file__).resolve().parent
    root = package_dir.parent
    if (root / "pyproject.toml").is_file() and (root / "tesseract_studio").is_dir():
        return True
    return (root / "configs").is_dir() and (root / "main.py").is_file()


def _default_config_dir() -> Path:
    """Resolve the directory that holds the user profiles.

    Order of preference:

    1. the ``TESSERACT_STUDIO_CONFIG_DIR`` environment variable;
    2. ``configs`` next to the executable, for the packaged build;
    3. ``configs`` next to the project root, for a source checkout;
    4. ``%LOCALAPPDATA%\\TesseractStudio\\configs``, when the package is
       installed into ``site-packages``. Writing profiles into the install
       directory would break on a read-only installation and would be wiped
       away by the next upgrade.
    """
    override = os.environ.get("TESSERACT_STUDIO_CONFIG_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "configs"
    if _is_source_checkout():
        return Path(__file__).resolve().parent.parent / "configs"
    local_appdata = os.environ.get("LOCALAPPDATA", "").strip()
    if local_appdata:
        return Path(local_appdata) / "TesseractStudio" / "configs"
    return Path.home() / ".tesseract-studio" / "configs"


BASE_DIR = _default_config_dir().parent
CONFIG_DIR = _default_config_dir()
try:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    # A read-only install can still run with the built-in defaults.
    pass


@dataclass
class AppConfig:
    profile_name: str = "default"
    tesseract_path: str = ""
    tessdata_dir: str = ""
    language: str = "eng"
    psm: int = 6
    oem: int = 3
    threshold_mode: str = "binary"
    threshold_value: int = 150
    adaptive_block_size: int = 31
    adaptive_c: int = 10
    blur_kernel: int = 0
    scale: float = 2.0
    invert: bool = False
    grayscale: bool = True
    auto_ocr: bool = False
    auto_interval_ms: int = 1500
    whitelist: str = ""
    blacklist: str = ""
    min_confidence: int = 0
    preserve_spaces: bool = False
    user_defined_dpi: int = 300
    extra_config: str = ""
    region: Optional[dict] = None


def _config_fields() -> set[str]:
    return {field.name for field in fields(AppConfig)}


def config_from_dict(payload: dict[str, Any]) -> AppConfig:
    """Build a config from JSON while ignoring unknown/legacy keys."""
    known = _config_fields()
    cleaned = {key: value for key, value in payload.items() if key in known}
    return AppConfig(**cleaned)


def load_config_file(path: Path) -> AppConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(tr("Профиль должен быть JSON-объектом: {name}", name=path.name))
    return config_from_dict(payload)


def save_config_file(path: Path, config: AppConfig) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(config), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def safe_profile_name(name: str) -> str:
    """Keep profile names inside configs/ and usable as file names."""
    cleaned = "".join("-" if char in r'<>:"/\|?*' else char for char in name.strip())
    cleaned = cleaned.strip(" .")
    return cleaned or "default"


def ensure_default_profile() -> Path:
    default_path = CONFIG_DIR / "default.json"
    if not default_path.exists():
        try:
            save_config_file(default_path, AppConfig())
        except OSError:
            pass
    return default_path


def list_profiles() -> list[str]:
    try:
        return sorted(path.stem for path in CONFIG_DIR.glob("*.json") if path.is_file())
    except OSError:
        return []


def find_tesseract_executable(current: str = "") -> Optional[Path]:
    if current and Path(current).exists():
        return Path(current)
    for folder in os.environ.get("PATH", "").split(os.pathsep):
        if folder:
            candidate = Path(folder) / "tesseract.exe"
            if candidate.exists():
                return candidate
    for candidate in TESSERACT_HINT_PATHS:
        if candidate.exists():
            return candidate
    for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
        root_text = os.environ.get(env_name, "").strip()
        if root_text:
            root = Path(root_text)
            if root.exists():
                matches = list(root.glob("**/tesseract.exe"))
                if matches:
                    return matches[0]
    return None


def find_tessdata_dir(current: str = "", tesseract_path: Optional[Path] = None) -> Optional[Path]:
    if current and Path(current).exists():
        return Path(current)
    if tesseract_path:
        sibling = tesseract_path.parent / "tessdata"
        if sibling.exists():
            return sibling
    tessdata_prefix = os.environ.get("TESSDATA_PREFIX", "").strip()
    if tessdata_prefix and Path(tessdata_prefix).exists():
        return Path(tessdata_prefix)
    for candidate in TESSDATA_HINT_DIRS:
        if candidate.exists():
            return candidate
    for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
        root_text = os.environ.get(env_name, "").strip()
        if root_text:
            root = Path(root_text)
            if root.exists():
                matches = list(root.glob("**/tessdata"))
                if matches:
                    return matches[0]
    return None
