"""English contextual help texts for every control in the OCR Studio shell."""

from __future__ import annotations


def register_help_targets(
    panel,
    capture_page,
    ocr_page,
    preprocess_page,
    profiles_page,
    preview_panel,
) -> None:
    hp = panel
    cp = capture_page
    op = ocr_page
    pp = preprocess_page
    pr = profiles_page

    hp.register(
        cp.select_region_button,
        "Select region",
        "Only defines the screen rectangle; it does not run OCR.",
        "Choose the boundaries carefully first, then decide whether to capture a frame or run OCR immediately.",
        "The region is saved in the profile and can be reused.",
    )
    hp.register(
        cp.capture_button,
        "Capture region",
        "Takes a fresh screenshot of the selected region without OCR and updates both previews.",
        "The best mode for tuning settings on the same frame.",
        "After capturing, press “Run OCR” repeatedly - no new screenshot is needed.",
    )
    hp.register(
        cp.load_file_button,
        "Open file",
        "Loads an image from disk as the new source.",
        "Useful for testing OCR on a saved screenshot or picture.",
    )
    hp.register(
        cp.paste_button,
        "Paste from clipboard",
        "Takes an image or an image path from the clipboard.",
        "Handy after Print Screen, or copying from a browser, Discord or an editor.",
    )
    hp.register(
        cp.tesseract_edit,
        "Path to tesseract.exe",
        "The Tesseract OCR executable. Recognition cannot start without it.",
        "Needed when Tesseract is not on PATH or is installed in a non-standard folder.",
        "Usually: C:\\Program Files\\Tesseract-OCR\\tesseract.exe.",
    )
    hp.register(
        cp.tessdata_edit,
        "tessdata folder",
        "The folder with .traineddata language files.",
        "Use it for multiple languages or a portable installation.",
        "If a language is not found, check that the required .traineddata is in this folder.",
    )
    hp.register(
        cp.region_label,
        "Selected region",
        "Coordinates of the active screen capture area.",
        "Verify that the region contains exactly the UI fragment you need.",
        "Extra elements inside the region significantly reduce OCR quality.",
    )
    hp.register(
        op.preset_combo,
        "OCR presets",
        "Ready-made starting points for common scenarios.",
        "A fast way to get a working baseline before fine-tuning.",
    )
    hp.register(
        op.preset_button,
        "Apply preset",
        "Fills the form with a ready-made parameter set.",
        "Use it as a starting point, then tune two or three parameters for your frame.",
    )
    hp.register(
        op.language_combo,
        "OCR language",
        "Selects the language models Tesseract uses.",
        "One language is usually more accurate. Multiple languages are only needed for genuinely mixed text.",
        "Examples: eng, rus, eng+rus.",
    )
    hp.register(
        op.psm_combo,
        "PSM",
        "Page segmentation mode: how Tesseract interprets the image structure.",
        "6 - block, 7 - line, 8 - word, 10 - character, 11 - sparse text.",
        "If OCR fails on a good frame, check PSM first.",
    )
    hp.register(
        op.oem_combo,
        "OEM",
        "Tesseract engine mode.",
        "3 is usually the best universal choice.",
        "Tune PSM and preprocessing before OEM.",
    )
    hp.register(
        op.whitelist_edit,
        "Allowed characters",
        "Characters Tesseract is explicitly allowed to output.",
        "The best tool for digits, hex, codes and short fields.",
        "Example: 0123456789 or ABCDEF0123456789.",
    )
    hp.register(
        op.blacklist_edit,
        "Forbidden characters",
        "Characters Tesseract should avoid.",
        "Helps when the engine confuses O/0 or I/1.",
        "Use it narrowly so you do not forbid a needed character.",
    )
    hp.register(
        op.min_confidence_spin,
        "Minimum confidence",
        "Word confidence filter: weak results do not reach the output.",
        "Useful when cleanliness matters more than completeness.",
        "0 - no filter; 20-40 - soft; 50-70 - strict.",
    )
    hp.register(
        op.preserve_spaces_check,
        "Preserve spaces",
        "Asks Tesseract to preserve word spacing more carefully.",
        "Useful for tables, chats, logs and formatted text.",
    )
    hp.register(
        op.user_dpi_spin,
        "User-defined DPI",
        "Sets the DPI value used inside the engine.",
        "Useful for screenshots and small text without metadata.",
        "Around 300 works well in practice.",
    )
    hp.register(
        op.extra_config_edit,
        "Extra parameters",
        "Manual input for additional Tesseract flags.",
        "For advanced fine-tuning without changing the code.",
        "Example: -c load_system_dawg=0 -c load_freq_dawg=0",
    )
    hp.register(
        pp.threshold_mode_combo,
        "Threshold mode",
        "How the image is converted to black and white before OCR.",
        "A fixed threshold works well on a clean UI; adaptive modes help on uneven backgrounds.",
        "Watch the “Processed” panel: it shows exactly what Tesseract receives.",
        "binary - threshold; binary_inv - inverted; otsu - automatic; adaptive_* - local threshold.",
    )
    hp.register(
        pp.threshold_slider,
        "Threshold",
        "Manual cutoff for binary and binary_inv modes.",
        "Suitable for stable contrast: counters and short UI fields.",
        "If part of a glyph disappears, the threshold is often too high.",
        "Range 0-255. Working values are usually 120-190.",
    )
    hp.register(
        pp.adaptive_block_spin,
        "Adaptive window size",
        "Local window size for adaptive thresholding.",
        "Useful with uneven lighting and busy backgrounds.",
        "A practical range is usually 15-51; the value must be odd.",
    )
    hp.register(
        pp.adaptive_c_spin,
        "Adaptive C",
        "Correction value for adaptive thresholding.",
        "Helps remove noise or restore disappearing strokes.",
        "Change it in small steps and watch the processed result.",
    )
    hp.register(
        pp.blur_combo,
        "Blur",
        "Light Gaussian blur before thresholding.",
        "Useful for noisy screenshots and compression artifacts.",
        "Too much blur destroys small fonts.",
    )
    hp.register(
        pp.scale_combo,
        "Scale",
        "Image upscaling before OCR.",
        "Small text often benefits from 2.0-4.0.",
        "Too much upscaling also softens contours.",
    )
    hp.register(
        pp.grayscale_check,
        "Grayscale",
        "Converts the image to grayscale before processing.",
        "Almost always useful for OCR when colour does not matter.",
    )
    hp.register(
        pp.invert_check,
        "Invert",
        "Swaps black and white after thresholding.",
        "Useful when the text is light and the background is dark.",
    )
    hp.register(
        pr.profile_combo,
        "Profile",
        "A single list of profiles with an option to type a new name.",
        "Choose a profile and click “Load”, or type a new name and click “Save”.",
        "Short descriptive names are easier: digits, chat_ru, small_text.",
    )
    hp.register(
        preview_panel.output_text,
        "OCR output",
        "The final text after recognition and filtering.",
        "Use it to review, copy and compare variants.",
        "If the output is poor, inspect the “Processed” panel first.",
    )
