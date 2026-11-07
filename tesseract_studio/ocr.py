"""Pure OCR pipeline: preprocessing, Tesseract config and text extraction."""

from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np
import pytesseract


def safe_block_size(value: int) -> int:
    """Adaptive threshold block size must be odd and at least 3."""
    value = max(int(value), 3)
    if value % 2 == 0:
        value += 1
    return value


def preprocess_image(image: np.ndarray, settings: dict) -> np.ndarray:
    """Apply scale, grayscale, blur, threshold and inversion in that order."""
    scale = max(float(settings["scale"]), 1.0)
    if scale != 1.0:
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    if settings["grayscale"]:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur_kernel = int(settings["blur_kernel"])
    if blur_kernel >= 3 and blur_kernel % 2 == 1:
        image = cv2.GaussianBlur(image, (blur_kernel, blur_kernel), 0)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    mode = settings["threshold_mode"]
    threshold = int(settings["threshold_value"])
    if mode == "binary":
        _, image = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    elif mode == "binary_inv":
        _, image = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY_INV)
    elif mode == "otsu":
        _, image = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    elif mode == "adaptive_mean":
        image = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_MEAN_C,
            cv2.THRESH_BINARY,
            safe_block_size(int(settings["adaptive_block_size"])),
            int(settings["adaptive_c"]),
        )
    elif mode == "adaptive_gaussian":
        image = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            safe_block_size(int(settings["adaptive_block_size"])),
            int(settings["adaptive_c"]),
        )
    else:
        image = gray
    if settings["invert"]:
        image = cv2.bitwise_not(image)
    return image


def build_tesseract_config(settings: dict) -> str:
    """Translate the UI settings into a Tesseract command-line config string."""
    if settings.get("tesseract_path"):
        pytesseract.pytesseract.tesseract_cmd = settings["tesseract_path"]
    tessdata_dir = str(settings.get("tessdata_dir", "")).strip()
    if tessdata_dir:
        os.environ["TESSDATA_PREFIX"] = str(Path(tessdata_dir).resolve())
    parts = [f"--oem {int(settings['oem'])}", f"--psm {int(settings['psm'])}"]
    whitelist = str(settings.get("whitelist", "")).strip()
    if whitelist:
        parts.append(f'-c tessedit_char_whitelist="{whitelist}"')
    blacklist = str(settings.get("blacklist", "")).strip()
    if blacklist:
        parts.append(f'-c tessedit_char_blacklist="{blacklist}"')
    if settings.get("preserve_spaces"):
        parts.append("-c preserve_interword_spaces=1")
    dpi = int(settings.get("user_defined_dpi", 0))
    if dpi > 0:
        parts.append(f"-c user_defined_dpi={dpi}")
    extra_config = str(settings.get("extra_config", "")).strip()
    if extra_config:
        parts.append(extra_config)
    return " ".join(parts)


def normalize_ocr_text(text: str) -> str:
    """Trim trailing whitespace and collapse repeated blank lines."""
    lines = [line.rstrip() for line in text.splitlines()]
    cleaned: list[str] = []
    last_blank = False
    for line in lines:
        is_blank = not line.strip()
        if is_blank and last_blank:
            continue
        cleaned.append(line)
        last_blank = is_blank
    return "\n".join(cleaned).strip()


def extract_text_with_confidence(image: np.ndarray, settings: dict) -> str:
    """Run Tesseract and optionally keep only words above a confidence floor."""
    min_confidence = int(settings.get("min_confidence", 0))
    config = build_tesseract_config(settings)
    language = settings["language"]

    if min_confidence <= 0:
        text = pytesseract.image_to_string(image, lang=language, config=config)
        return normalize_ocr_text(text)

    data = pytesseract.image_to_data(
        image, lang=language, config=config, output_type=pytesseract.Output.DICT
    )
    lines: list[str] = []
    current_key = None
    current_words: list[str] = []

    for index in range(len(data["text"])):
        raw_text = data["text"][index].strip()
        if not raw_text:
            continue

        confidence_raw = str(data["conf"][index]).strip()
        try:
            confidence = float(confidence_raw)
        except ValueError:
            confidence = -1.0
        if confidence < min_confidence:
            continue

        key = (
            data["block_num"][index],
            data["par_num"][index],
            data["line_num"][index],
        )
        if current_key is None:
            current_key = key
        if key != current_key:
            if current_words:
                lines.append(" ".join(current_words))
            current_words = []
            current_key = key
        current_words.append(raw_text)

    if current_words:
        lines.append(" ".join(current_words))
    return normalize_ocr_text("\n".join(lines))


def recognize(image: np.ndarray, settings: dict) -> tuple[np.ndarray, str]:
    """Preprocess an image and return ``(processed_image, text)``."""
    processed = preprocess_image(image.copy(), settings)
    text = extract_text_with_confidence(processed, settings)
    return processed, text
