"""
Abstract TTS engine interface and Registry.

Every TTS engine must subclass `BaseTTSEngine` and use the `@TTSEngineRegistry.register`
decorator to be automatically discovered by the GUI and Pipeline.
"""
import importlib
import logging
from abc import ABC, abstractmethod
from typing import Dict, Type, Any, Optional


logger = logging.getLogger(__name__)


class BaseTTSEngine(ABC):
    """Abstract interface for TTS engines."""
    
    # ── Engine Metadata (to be overridden by subclasses) ──
    # Internal identifier (e.g., "kokoro-tts")
    engine_id: str = "unknown" 
    
    # Human-readable name (e.g., "Kokoro TTS (Fast/Local)")
    engine_name: str = "Unknown Engine"
    
    # Set of supported two-letter language codes
    supported_languages: frozenset[str] = frozenset()

    @classmethod
    def get_supported_languages(cls) -> frozenset[str]:
        return cls.supported_languages

    @classmethod
    @abstractmethod
    def get_voice_catalog(cls, language_code: str = "en") -> dict[str, tuple[str, str]]:
        """
        Return the voices available for a given language.
        Returns: Dict[voice_id, (display_name, description)]
        """
        return {}

    @classmethod
    def get_default_voice_preset(cls, language_code: str = "en") -> str:
        """Return the default voice ID for the given language."""
        voices = cls.get_voice_catalog(language_code)
        return next(iter(voices.keys()), "")

    # ── Generation API ──

    @abstractmethod
    def load_model(self, device: str = "cuda"):
        """Load the TTS model."""
        ...

    @abstractmethod
    def use_preset_voice(self, preset_id: str) -> object:
        """Resolve a user-selected preset into engine-specific voice data."""
        ...

    @abstractmethod
    def synthesize(
        self,
        text: str,
        voice_ref: object,
        output_path: str,
        nfe_step: int = 32,
        speed: float = 1.0,
        seed: int | None = None,
    ) -> str:
        """
        Synthesize speech from text using the configured voice preset/reference.
        Returns path to generated audio file.
        """
        ...

    @abstractmethod
    def unload_model(self):
        """Free model resources."""
        ...


class TTSEngineRegistry:
    """Global registry for dynamically resolving TTS engines."""
    
    _engines: Dict[str, Type[BaseTTSEngine]] = {}
    _builtin_engine_modules = (
        "app.tts_engines.edge_engine",
        "app.tts_engines.f5_engine",
        "app.tts_engines.kokoro_engine",
    )
    _builtin_engines_loaded = False
    _builtin_engines_loading = False

    @classmethod
    def ensure_builtin_engines_loaded(cls):
        """Import built-in engines on demand so the registry is always populated."""
        if cls._builtin_engines_loaded or cls._builtin_engines_loading:
            return

        cls._builtin_engines_loading = True
        all_loaded = True
        try:
            for module_name in cls._builtin_engine_modules:
                try:
                    importlib.import_module(module_name)
                except Exception as exc:
                    all_loaded = False
                    logger.debug("TTS engine autoload skipped for %s: %s", module_name, exc)
        finally:
            cls._builtin_engines_loading = False

        cls._builtin_engines_loaded = all_loaded

    @classmethod
    def register(cls, engine_id: str):
        """Decorator to register a TTS engine class."""
        def wrapper(engine_cls: Type[BaseTTSEngine]):
            engine_cls.engine_id = engine_id
            cls._engines[engine_id] = engine_cls
            return engine_cls
        return wrapper

    @classmethod
    def get_engine_class(cls, engine_id: str) -> Type[BaseTTSEngine]:
        """Fetch the class of an engine by its ID."""
        cls.ensure_builtin_engines_loaded()
        engine_cls = cls._engines.get(engine_id)
        if not engine_cls:
            raise ValueError(f"TTS Engine '{engine_id}' is not registered.")
        return engine_cls

    @classmethod
    def create_engine(cls, engine_id: str) -> BaseTTSEngine:
        """Instantiate an engine by its ID."""
        return cls.get_engine_class(engine_id)()

    @classmethod
    def get_all_engines(cls) -> Dict[str, Type[BaseTTSEngine]]:
        """Return a mapping of all registered engines."""
        cls.ensure_builtin_engines_loaded()
        return cls._engines

    @classmethod
    def is_language_supported(cls, engine_id: str, language_code: str) -> bool:
        """Check if an engine supports a specific language."""
        try:
            return language_code in cls.get_engine_class(engine_id).get_supported_languages()
        except ValueError:
            return False
