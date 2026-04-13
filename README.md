# YouTube Dubbing Studio

![YouTube Dubbing Studio splash](assets/splash.png)

Local desktop app for YouTube video dubbing, AI voice-over, speech-to-text, translation, and final video export.

[![GitHub stars](https://img.shields.io/github/stars/ViacheslavChernyshov/YouTube-Dubbing-Studio?style=for-the-badge)](https://github.com/ViacheslavChernyshov/YouTube-Dubbing-Studio/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/ViacheslavChernyshov/YouTube-Dubbing-Studio?style=for-the-badge)](https://github.com/ViacheslavChernyshov/YouTube-Dubbing-Studio/network/members)
[![GitHub issues](https://img.shields.io/github/issues/ViacheslavChernyshov/YouTube-Dubbing-Studio?style=for-the-badge)](https://github.com/ViacheslavChernyshov/YouTube-Dubbing-Studio/issues)
[![Windows](https://img.shields.io/badge/platform-Windows-0078D6?style=for-the-badge)](https://www.microsoft.com/windows)
[![Python](https://img.shields.io/badge/python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)

**YouTube Dubbing Studio** is a Windows-first `PySide6` application that downloads a YouTube video, transcribes speech, translates segments, generates a new voice track with selectable TTS engines, aligns the dub to timing, and renders the final dubbed video back out.

It is built for people who want a local AI dubbing workflow with a real GUI instead of a pile of scripts.

## Why it stands out

Most "YouTube translator" tools only solve one fragment of the workflow:

- download the video
- generate subtitles
- translate text
- call one online TTS API

This project is built as a full desktop dubbing pipeline:

- download and prepare source media
- transcribe speech locally
- translate into the selected target language
- synthesize a new voice track
- align speech back to the original timing
- mix background audio
- export the final dubbed video

## Core Features

- Desktop GUI built with `PySide6`
- Local speech-to-text with Whisper / Faster-Whisper
- Local translation pipeline with NLLB
- Multiple TTS engines: `Kokoro TTS`, `Edge-TTS`, `F5-TTS`
- Strict model behavior: the selected dubbing model is used as-is, without silent engine switching
- Automatic component bootstrap for Python, FFmpeg, PyTorch, and model dependencies
- GPU-aware startup and CUDA-friendly runtime setup
- Built-in logs, diagnostics, and pipeline stage visibility
- YouTube Shorts support
- Portable Windows workflow

## How it works

1. Download the source video from YouTube
2. Extract and prepare audio
3. Run speech recognition
4. Translate recognized segments
5. Generate dubbed speech with the selected TTS engine
6. Align generated speech to source timing
7. Mix dub with original audio if needed
8. Export final video

## TTS Engines

| Engine | Best for | Notes |
| --- | --- | --- |
| `Kokoro TTS` | Fast local English dubbing | Good iteration speed for local workflows |
| `Edge-TTS` | Broad language coverage | Useful when you need clear voices and multilingual support |
| `F5-TTS` | Reference-audio-driven dubbing | Better fit for heavier voice-cloning style workflows |

## Good Fit For

- creators who want to dub YouTube videos into another language
- developers building a local AI dubbing pipeline
- researchers experimenting with speech translation and voice generation
- users who want more control than typical web dubbing tools provide
- people searching for a YouTube dubbing app, AI dubbing software, offline video translation tool, or local voice-over generator

## Project Preview

Main project art:

- [assets/splash.png](assets/splash.png)
- [assets/icon.png](assets/icon.png)
- [assets/icon.ico](assets/icon.ico)

This repo is ready for adding live UI screenshots later in `assets/screenshots/` or `docs/`.

## Project Structure

```text
app/                 Main application code
assets/              Icons and splash assets
locales/             UI localization files
scripts/             Helper scripts
system/              Portable runtime bootstrap and launcher files
tests/               Unit and smoke tests
Start.vbs            Windows-first launcher
README.md            Project overview
```

Important folders inside `app/`:

- `app/gui/` - main window, dialogs, settings panel, menus
- `app/pipeline/` - staged dubbing pipeline
- `app/tts_engines/` - TTS engine abstractions and implementations
- `app/translator/` - translation layer
- `app/runtime_assets.py` - startup preparation and dependency bootstrap

## Installation

This project is currently optimized for Windows.

### Recommended

Run:

```powershell
Start.vbs
```

On first launch it will automatically:

- download portable Python
- install pip
- install PyTorch
- install Python dependencies
- prepare FFmpeg and runtime components

### Manual / advanced path

```powershell
system\install.cmd
```

Then start the app with:

```powershell
system\run.cmd
```

## Runtime Behavior

The app prepares missing components at startup and stores runtime data outside Git-tracked source code.

Examples of runtime-managed items:

- downloaded models
- generated voice presets
- logs
- jobs
- caches
- portable Python environment

That is why the repository intentionally excludes:

- `data/`
- `system/python/`
- caches
- temporary files
- local config files

## Development

### Tests

Run tests with the Python environment you use for development:

```powershell
python -m unittest discover tests
```

### Localization

Localization data lives in:

- [locales/en.json](locales/en.json)
- [locales/ru.json](locales/ru.json)
- [locales/_meta.json](locales/_meta.json)

Extraction helper:

```powershell
python scripts\extract_locales.py
```

## Current Status

The project already contains:

- application GUI
- startup bootstrap flow
- multilingual target language support
- multiple dubbing engines
- runtime preparation dialog
- logging and diagnostics
- tests for major pipeline areas

This is an actively evolving codebase, so some parts are more polished than others, but the foundation is already substantial.

## SEO Keywords

Useful search phrases this project is relevant to:

- YouTube dubbing studio
- YouTube dubbing app
- YouTube video translator desktop app
- AI dubbing software
- local dubbing software
- offline video translation app
- Python YouTube dubbing project
- PySide6 desktop dubbing tool
- AI voice-over for YouTube videos
- local speech translation pipeline

## Roadmap

- better GitHub-ready screenshots and demo GIFs
- packaged releases
- cleaner first-run onboarding
- stronger model health diagnostics
- explicit repair / reset runtime actions in the UI
- more localization coverage
- improved CI and test cleanup

## License

No license file is included yet.

If you plan to make this repository public-facing and reusable, adding a license should be one of the next steps.

## Author

**Viacheslav Chernyshov**

GitHub:
[ViacheslavChernyshov](https://github.com/ViacheslavChernyshov)
