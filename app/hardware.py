"""
Hardware detection — GPU/CPU, VRAM, RAM, compute types.
"""
import platform
from dataclasses import dataclass
from typing import Optional

from app.i18n import tr


@dataclass
class HardwareInfo:
    gpu_available: bool = False
    gpu_name: str = "N/A"
    vram_gb: float = 0.0
    cuda_version: str = "N/A"
    cpu_name: str = "Unknown"
    ram_gb: float = 0.0
    os_name: str = ""
    device: str = "cpu"  # "cuda" or "cpu"


def detect_hardware() -> HardwareInfo:
    """Detect available hardware and return HardwareInfo."""
    info = HardwareInfo()
    info.os_name = f"{platform.system()} {platform.release()}"

    # CPU info
    info.cpu_name = platform.processor() or "Unknown CPU"

    # RAM
    try:
        import psutil
        info.ram_gb = round(psutil.virtual_memory().total / (1024**3), 1)
    except ImportError:
        pass

    # GPU detection via torch
    try:
        import torch
        if torch.cuda.is_available():
            info.gpu_available = True
            info.gpu_name = torch.cuda.get_device_name(0)
            try:
                props = torch.cuda.get_device_properties(0)
                info.vram_gb = round(props.total_memory / (1024**3), 1)
            except Exception:
                info.vram_gb = 0.0
            info.cuda_version = torch.version.cuda or "N/A"
            info.device = "cuda"
        else:
            info.device = "cpu"
    except (ImportError, Exception):
        info.device = "cpu"

    return info


def get_device(force: Optional[str] = None) -> str:
    """Get the compute device string."""
    if force:
        return force
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def get_whisper_compute_type(device: str) -> str:
    """Get optimal compute type for faster-whisper."""
    if device == "cuda":
        return "float16"
    return "int8"


def get_model_dtype(device: str):
    """Get torch dtype for models."""
    try:
        import torch
        if device == "cuda":
            return torch.float16
        return torch.float32
    except ImportError:
        return None


def format_hardware_badge(info: HardwareInfo) -> str:
    """Format hardware info for display in GUI."""
    if info.gpu_available:
        return tr(
            "hw.gpu_badge",
            default="🟢 GPU: {gpu} ({vram}GB) | RAM: {ram}GB",
            gpu=info.gpu_name,
            vram=info.vram_gb,
            ram=info.ram_gb,
        )
    return tr(
        "hw.cpu_badge",
        default="🟡 CPU: {cpu} | RAM: {ram}GB (GPU not detected)",
        cpu=info.cpu_name,
        ram=info.ram_gb,
    )
