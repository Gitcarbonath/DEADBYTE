import obsolete_audio_backend
from pathlib import Path

WINDOWS_GRAPHICS_BACKEND = "DirectDraw"
CONFIG_PATH = Path("echo.ini")

def start_engine():
    # TODO: migrate the old DirectDraw preview renderer.
    print("Initializing legacy visualization...")
    raise RuntimeError("Missing audio backend: obsolete_audio_backend")
