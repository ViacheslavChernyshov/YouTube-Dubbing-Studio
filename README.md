# YouTube Dubbing Studio

Local desktop app for **YouTube video dubbing, AI voice-over, speech-to-text, translation, and final video export**.

**YouTube Dubbing Studio** is a Windows-first `PySide6` application that downloads a YouTube video, transcribes speech, translates segments, generates a new voice track with selectable TTS engines, aligns the dub to timing, and renders the final dubbed video back out.

It is built for people who want a **local AI dubbing workflow** with a real GUI instead of a pile of scripts.

## Why this project exists

Most "YouTube translator" tools only do one piece of the job:

- download the video
- generate subtitles
- translate text
- call one online TTS API

This project is different. It tries to be a full **YouTube dubbing studio**:

- download and prepare source media
- transcribe speech locally
- translate into the selected target language
- synthesize a new voice track
- align speech back to the original timing
- mix background audio
- export the final dubbed video

## Core Features

- **Desktop GUI** built with `PySide6`
- **Local speech-to-text** with Whisper / Faster-Whisper
- **Local translation pipeline** with NLLB
- **Multiple TTS engines**
- `Kokoro TTS`
- `Edge-TTS`
- `F5-TTS`
- **Strict model behavior**
- if a user selects a specific dubbing model, the app should use that model
- incompatible models are reported explicitly instead of silently switching to another engine
- **Automatic component bootstrap**
- portable Python
- FFmpeg
- PyTorch
- required model dependencies
- **GPU-aware startup**
- hardware detection
- CUDA-friendly setup path
- **Built-in documentation UI**
- **Logs and pipeline stage visibility**
- **YouTube Shorts support**
- **Portable Windows workflow**

## What the app actually does

End-to-end pipeline:

1. Download the source video from YouTube
2. Extract and prepare audio
3. Run speech recognition
4. Translate recognized segments
5. Generate dubbed speech with the selected TTS engine
6. Align generated speech to source timing
7. Mix dub with original audio if needed
8. Export final video

## Supported TTS Engines

### Kokoro TTS

Good local option for fast English dubbing and iteration.

### Edge-TTS

Useful when you want clear cloud voices and broad language coverage.

### F5-TTS

Used for heavier voice-cloning style workflows based on reference audio.

## Good Fit For

- creators who want to dub YouTube videos into another language
- developers building a local AI dubbing pipeline
- researchers experimenting with speech translation and voice generation
- users who want more control than typical web dubbing tools provide
- people looking for a **YouTube dubbing app**, **AI dubbing software**, **offline video translation tool**, or **local voice-over generator**

## Screens / Assets

Project assets included in the repo:

- [assets/splash.png](assets/splash.png)
- [assets/icon.png](assets/icon.png)
- [assets/icon.ico](assets/icon.ico)

If you want, screenshots of the live UI can be added later in a `docs/` or `assets/screenshots/` folder and linked here.

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

This project is currently optimized for **Windows**.

### Recommended: first launch installer

Run:

```powershell
Start.vbs
```

On first run it will automatically:

- download portable Python
- install pip
- install PyTorch
- install Python dependencies
- prepare FFmpeg and runtime components

### Manual / advanced path

If you want to run the portable bootstrap manually:

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

## Development Notes

### Tests

Run tests with the project Python environment you use for development.

Example:

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

## SEO / Keywords

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

## Roadmap Ideas

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
