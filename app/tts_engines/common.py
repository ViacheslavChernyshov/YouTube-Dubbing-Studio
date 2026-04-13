"""
Common language and UI metadata shared across TTS engines to prevent duplication.
"""

COMMON_GENDER_LABELS = {
    "en": {"f": "female", "m": "male", "voice": "voice"},
    "ru": {"f": "женский", "m": "мужской", "voice": "голос"},
    "uk": {"f": "жіночий", "m": "чоловічий", "voice": "голос"},
    "zh": {"f": "女声", "m": "男声", "voice": "声音"},
    "hi": {"f": "महिला", "m": "पुरुष", "voice": "आवाज़"},
    "es": {"f": "femenino", "m": "masculino", "voice": "voz"},
    "fr": {"f": "féminin", "m": "masculin", "voice": "voix"},
    "ar": {"f": "نسائي", "m": "رجالي", "voice": "صوت"},
    "bn": {"f": "নারী", "m": "পুরুষ", "voice": "ভয়েস"},
    "pt": {"f": "feminino", "m": "masculino", "voice": "voz"},
}

COMMON_VOICE_DESCRIPTION_TEMPLATE = {
    "en": "{language} {gender} voice for dubbing.",
    "ru": "{language} {gender} голос для озвучки.",
    "uk": "{language} {gender} голос для озвучення.",
    "zh": "适合配音的{language}{gender}。",
    "hi": "डबिंग के लिए {language} {gender} आवाज़.",
    "es": "Voz {gender} de {language} para doblaje.",
    "fr": "Voix {gender} de {language} pour le doublage.",
    "ar": "صوت {gender} باللغة {language} مناسب للدبلجة.",
    "bn": "ডাবিংয়ের জন্য {language} {gender} ভয়েস।",
    "pt": "Voz {gender} em {language} para dublagem.",
}
