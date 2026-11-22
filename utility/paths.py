"""Where the game's files live, from source or from the PyInstaller bundle."""
import sys
from pathlib import Path


def asset_dir():
    """The assets folder: beside the source, or inside the frozen build."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "assets"
    return Path(__file__).resolve().parent.parent / "assets"
