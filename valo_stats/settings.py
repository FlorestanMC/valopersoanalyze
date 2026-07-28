"""Réglages persistants de l'utilisateur (fond d'écran, assombrissement).

Stockés dans userdata/settings.json ; l'image de fond dans userdata/background.<ext>.
Ce dossier est ignoré par git (personnel).
"""
import glob
import json
import os

_ROOT = os.path.dirname(os.path.dirname(__file__))
USERDATA = os.path.join(_ROOT, "userdata")
_FILE = os.path.join(USERDATA, "settings.json")

DEFAULTS = {"dim": 55, "bg_file": None}
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def load() -> dict:
    try:
        with open(_FILE, encoding="utf-8") as f:
            return {**DEFAULTS, **json.load(f)}
    except (OSError, ValueError):
        return dict(DEFAULTS)


def save(patch: dict) -> dict:
    os.makedirs(USERDATA, exist_ok=True)
    cur = load()
    cur.update(patch)
    with open(_FILE, "w", encoding="utf-8") as f:
        json.dump(cur, f, indent=2)
    return cur


def set_dim(value) -> dict:
    return save({"dim": max(0, min(90, int(value)))})


def _remove_existing():
    for old in glob.glob(os.path.join(USERDATA, "background.*")):
        try:
            os.remove(old)
        except OSError:
            pass


def save_background(file_storage, filename: str) -> dict:
    """Enregistre l'image uploadée si l'extension est autorisée. Renvoie les settings."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXT:
        raise ValueError(f"Extension non autorisée : {ext}")
    os.makedirs(USERDATA, exist_ok=True)
    _remove_existing()
    name = f"background{ext}"
    file_storage.save(os.path.join(USERDATA, name))
    return save({"bg_file": name})


def clear_background() -> dict:
    _remove_existing()
    return save({"bg_file": None})


def bg_path():
    """Chemin absolu de l'image de fond si elle existe, sinon None."""
    f = load().get("bg_file")
    if f:
        p = os.path.join(USERDATA, f)
        if os.path.exists(p):
            return p
    return None
