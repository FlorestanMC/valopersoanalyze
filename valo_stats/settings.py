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

DEFAULTS = {"dim": 55, "bg_file": None, "riot_id": None, "region": None,
            "team": [], "team_name": None}
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


def set_target(riot_id, region=None) -> dict:
    """Définit le compte ciblé (surcharge le .env). riot_id vide -> retour au .env."""
    patch = {"riot_id": (riot_id or "").strip() or None}
    if region is not None:
        patch["region"] = (region or "").strip().lower() or None
    return save(patch)


def clear_target() -> dict:
    return save({"riot_id": None, "region": None})


def set_team(players) -> dict:
    """Enregistre l'effectif suivi (max 6). players : liste de {riot_id, region}.

    Le 6e emplacement sert au coach / remplaçant.
    """
    clean = []
    for p in (players or [])[:6]:
        rid = (p.get("riot_id") or "").strip()
        reg = (p.get("region") or "eu").strip().lower()
        if "#" in rid:
            clean.append({"riot_id": rid, "region": reg})
    return save({"team": clean})


def set_team_name(name) -> dict:
    """Nom d'équipe affiché dans l'onglet Team. Vide -> retour au libellé par défaut."""
    clean = (name or "").strip()[:40] or None
    return save({"team_name": clean})


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
