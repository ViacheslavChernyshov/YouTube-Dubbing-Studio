"""
Target language catalog and formatting.
"""
from app.i18n import DEFAULT_INTERFACE_LANGUAGE, LANGUAGE_META, get_language

DEFAULT_TARGET_LANGUAGE = "en"

TARGET_LANGUAGE_ROWS = (
    ("en", "Английский", "English"),
    ("zh", "Китайский", "中文"),
    ("hi", "Хинди", "हिन्दी"),
    ("es", "Испанский", "Español"),
    ("fr", "Французский", "Français"),
    ("ar", "Арабский", "العربية"),
    ("bn", "Бенгальский", "বাংলা"),
    ("pt", "Португальский", "Português"),
    ("ru", "Русский", "Русский"),
    ("uk", "Украинский", "Українська"),
)

TARGET_LANGUAGE_INFO = {
    code: {
        "label": label,
        "native": native,
        "display_name": f"{label} ({native})",
    }
    for code, label, native in TARGET_LANGUAGE_ROWS
}

_TARGET_LANGUAGE_LABELS = {
    "en": {"en": "English", "zh": "Chinese", "hi": "Hindi", "es": "Spanish", "fr": "French", "ar": "Arabic", "bn": "Bengali", "pt": "Portuguese", "ru": "Russian", "uk": "Ukrainian"},
    "ru": {"en": "Английский", "zh": "Китайский", "hi": "Хинди", "es": "Испанский", "fr": "Французский", "ar": "Арабский", "bn": "Бенгальский", "pt": "Португальский", "ru": "Русский", "uk": "Украинский"},
    "uk": {"en": "Англійська", "zh": "Китайська", "hi": "Гінді", "es": "Іспанська", "fr": "Французька", "ar": "Арабська", "bn": "Бенгальська", "pt": "Португальська", "ru": "Російська", "uk": "Українська"},
    "zh": {"en": "英语", "zh": "中文", "hi": "印地语", "es": "西班牙语", "fr": "法语", "ar": "阿拉伯语", "bn": "孟加拉语", "pt": "葡萄牙语", "ru": "俄语", "uk": "乌克兰语"},
    "hi": {"en": "अंग्रेज़ी", "zh": "चीनी", "hi": "हिन्दी", "es": "स्पैनिश", "fr": "फ़्रेंच", "ar": "अरबी", "bn": "बांग्ला", "pt": "पुर्तगाली", "ru": "रूसी", "uk": "यूक्रेनी"},
    "es": {"en": "inglés", "zh": "chino", "hi": "hindi", "es": "español", "fr": "francés", "ar": "árabe", "bn": "bengalí", "pt": "portugués", "ru": "ruso", "uk": "ucraniano"},
    "fr": {"en": "anglais", "zh": "chinois", "hi": "hindi", "es": "espagnol", "fr": "français", "ar": "arabe", "bn": "bengali", "pt": "portugais", "ru": "russe", "uk": "ukrainien"},
    "ar": {"en": "الإنجليزية", "zh": "الصينية", "hi": "الهندية", "es": "الإسبانية", "fr": "الفرنسية", "ar": "العربية", "bn": "البنغالية", "pt": "البرتغالية", "ru": "الروسية", "uk": "الأوكرانية"},
    "bn": {"en": "ইংরেজি", "zh": "চীনা", "hi": "হিন্দি", "es": "স্প্যানিশ", "fr": "ফরাসি", "ar": "আরবি", "bn": "বাংলা", "pt": "পর্তুগিজ", "ru": "রুশ", "uk": "ইউক্রেনীয়"},
    "pt": {"en": "inglês", "zh": "chinês", "hi": "hindi", "es": "espanhol", "fr": "francês", "ar": "árabe", "bn": "bengali", "pt": "português", "ru": "russo", "uk": "ucraniano"},
}

def _get_interface_language_code() -> str:
    code = get_language()
    return code if code in LANGUAGE_META else DEFAULT_INTERFACE_LANGUAGE

def _get_target_native_name(language_code: str) -> str:
    return LANGUAGE_META.get(language_code, LANGUAGE_META[DEFAULT_TARGET_LANGUAGE])["native"]

def _get_target_language_label(language_code: str, interface_language: str | None = None) -> str:
    language = interface_language or _get_interface_language_code()
    table = _TARGET_LANGUAGE_LABELS.get(language, _TARGET_LANGUAGE_LABELS["en"])
    return table.get(language_code, _TARGET_LANGUAGE_LABELS["en"].get(language_code, language_code))

def _format_language_display_name(label: str, native: str) -> str:
    return label if label == native else f"{label} ({native})"

def get_target_language_info(language_code: str) -> dict[str, str]:
    code = language_code if language_code in TARGET_LANGUAGE_INFO else DEFAULT_TARGET_LANGUAGE
    native = _get_target_native_name(code)
    label = _get_target_language_label(code)
    return {
        "label": label,
        "native": native,
        "display_name": _format_language_display_name(label, native),
    }

def get_target_language_display_name(language_code: str) -> str:
    return get_target_language_info(language_code)["display_name"]

def get_target_language_rows() -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (
            code,
            _get_target_language_label(code),
            _get_target_native_name(code),
        )
        for code in TARGET_LANGUAGE_INFO
    )
