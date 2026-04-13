"""
Voice preset management — generate and manage reference voice samples for F5-TTS.

Uses edge-tts to create high-quality reference samples for each voice preset,
which are then used as reference audio for F5-TTS preset generation.
"""
import asyncio
import subprocess
from pathlib import Path
from typing import Optional

from app.config import VOICE_PRESETS_DIR, get_ffmpeg_path
from app.tts_engines.base_engine import TTSEngineRegistry


# Reference texts for generating voice samples (clear, well-paced English)
_REFERENCE_TEXTS = {
    "male_deep": (
        "In the depths of a vast underground laboratory, surrounded by the gentle "
        "hum of supercomputers, Dr. Harrison reviewed the latest experimental data. "
        "The results were extraordinary, surpassing every prediction they had made."
    ),
    "male_medium": (
        "The morning sun cast golden light across the city skyline as commuters "
        "hurried along the busy streets below. A gentle breeze carried the scent "
        "of freshly brewed coffee from the corner cafe."
    ),
    "female_warm": (
        "Welcome to our kitchen, where every dish tells a story. Today we are "
        "going to prepare something truly special, a recipe that has been passed "
        "down through generations of my family."
    ),
    "female_clear": (
        "Good evening and thank you for joining us tonight. In today's report, "
        "we will examine the latest developments in technology and their impact "
        "on our daily lives and the global economy."
    ),
}

_KOKORO_FALLBACK_VOICES = {
    "male_deep": {"voice": "bm_george", "speed": 0.92},
    "male_medium": {"voice": "am_michael", "speed": 0.98},
    "female_warm": {"voice": "af_heart", "speed": 0.97},
    "female_clear": {"voice": "bf_emma", "speed": 1.02},
}


def get_preset_path(preset_id: str) -> Optional[Path]:
    """Get the path to a voice preset's reference audio."""
    wav_path = VOICE_PRESETS_DIR / f"{preset_id}.wav"
    if wav_path.exists():
        return wav_path
    return None


def get_preset_ref_text(preset_id: str) -> str:
    """Get the reference text for a voice preset."""
    return _REFERENCE_TEXTS.get(preset_id, "")



def is_preset_available(preset_id: str) -> bool:
    """Check if a voice preset is ready to use."""
    return get_preset_path(preset_id) is not None


def get_available_presets() -> dict:
    """Return dict of available presets with their status."""
    result = {}
    catalog = TTSEngineRegistry.get_engine_class("f5-tts").get_voice_catalog()
    for preset_id, (name, desc) in catalog.items():
        available = is_preset_available(preset_id)
        result[preset_id] = {
            "name": name,
            "description": desc,
            "available": available,
            "path": str(get_preset_path(preset_id)) if available else None,
        }
    return result


async def _generate_with_edge_tts(preset_id: str) -> Path:
    """Generate a reference sample using edge-tts (requires internet)."""
    import edge_tts
    
    edge_engine = TTSEngineRegistry.get_engine_class("edge-tts")()
    config = edge_engine.use_preset_voice(preset_id)
    text = _REFERENCE_TEXTS.get(preset_id)

    if not text:
        raise ValueError(f"Unknown preset: {preset_id}")
    
    output_path = VOICE_PRESETS_DIR / f"{preset_id}.wav"
    mp3_path = VOICE_PRESETS_DIR / f"{preset_id}_temp.mp3"
    
    # Generate with edge-tts (outputs mp3)
    communicate = edge_tts.Communicate(
        text,
        config["voice"],
        rate=config["rate"],
        pitch=config["pitch"],
        volume=config["volume"],
    )
    await communicate.save(str(mp3_path))
    
    cmd = [
        get_ffmpeg_path(),
        "-i", str(mp3_path),
        "-ar", "44100",
        "-ac", "1",
        "-y",
        str(output_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    
    # Cleanup temp mp3
    mp3_path.unlink(missing_ok=True)
    
    return output_path


def generate_presets_with_tts(logger=None) -> dict:
    """
    Generate voice presets using multiple fallback paths.
    Tries Edge-TTS first, then local Kokoro, then system TTS if available.
    Returns dict of {preset_id: success_bool}.
    """
    results = {}
    
    for preset_id in _REFERENCE_TEXTS:
        if is_preset_available(preset_id):
            results[preset_id] = True
            continue
        
        text = _REFERENCE_TEXTS[preset_id]
        output_path = VOICE_PRESETS_DIR / f"{preset_id}.wav"
        
        try:
            # Try edge-tts first (best quality)
            asyncio.run(_generate_with_edge_tts(preset_id))
            results[preset_id] = True
            if logger:
                logger.info(f"Voice preset generated: {preset_id}")
        except Exception as e:
            if logger:
                logger.warning(f"Edge-TTS failed for {preset_id}: {e}")

            try:
                _generate_with_kokoro(preset_id, text, output_path)
                results[preset_id] = True
                if logger:
                    logger.info(f"Voice preset generated (Kokoro fallback): {preset_id}")
            except Exception as kokoro_error:
                if logger:
                    logger.warning(f"Kokoro fallback failed for {preset_id}: {kokoro_error}")

                try:
                    _generate_with_system_tts(preset_id, text, str(output_path))
                    results[preset_id] = True
                    if logger:
                        logger.info(f"Voice preset generated (system TTS): {preset_id}")
                except Exception as e2:
                    results[preset_id] = False
                    if logger:
                        logger.error(f"Failed to generate preset {preset_id}: {e2}")
    
    return results


def _generate_with_kokoro(preset_id: str, text: str, output_path: Path):
    """Generate a local fallback reference using Kokoro-TTS assets."""
    from app.tts_engines.kokoro_engine import KokoroEngine

    config = _KOKORO_FALLBACK_VOICES.get(preset_id, {"voice": "af_heart", "speed": 1.0})
    output_file = Path(output_path)
    temp_output = output_file.with_name(f"{output_file.stem}.kokoro.wav")

    engine = KokoroEngine()
    engine.load_model(device="cpu")
    try:
        engine.synthesize(
            text=text,
            voice_ref={
                "voice": config["voice"],
                "lang": "en-us",
                "remove_tts_silence": True,
                "kokoro_soft_trim": True,
            },
            output_path=str(temp_output),
            speed=float(config["speed"]),
        )

        cmd = [
            get_ffmpeg_path(),
            "-i", str(temp_output),
            "-ar", "44100",
            "-ac", "1",
            "-y",
            str(output_file),
        ]
        subprocess.run(cmd, capture_output=True, check=True)
    finally:
        engine.unload_model()
        temp_output.unlink(missing_ok=True)


def _generate_with_system_tts(preset_id: str, text: str, output_path: str):
    """Generate using pyttsx3 when it is installed."""
    _generate_with_pyttsx3(preset_id, text, output_path)


def _generate_with_pyttsx3(preset_id: str, text: str, output_path: str):
    """Generate using Windows SAPI through pyttsx3 when it is installed."""
    import pyttsx3

    engine = pyttsx3.init()
    voices = engine.getProperty("voices")

    voice_map = {
        "male_deep": lambda v: "male" in v.name.lower() and "david" in v.name.lower(),
        "male_medium": lambda v: "male" in v.name.lower() or "mark" in v.name.lower(),
        "female_warm": lambda v: "female" in v.name.lower() or "zira" in v.name.lower(),
        "female_clear": lambda v: "female" in v.name.lower(),
    }

    matcher = voice_map.get(preset_id, lambda v: True)
    selected = None
    for voice in voices:
        if matcher(voice):
            selected = voice
            break

    if selected:
        engine.setProperty("voice", selected.id)

    rates = {"male_deep": 140, "male_medium": 160, "female_warm": 155, "female_clear": 165}
    engine.setProperty("rate", rates.get(preset_id, 150))

    engine.save_to_file(text, output_path)
    engine.runAndWait()
