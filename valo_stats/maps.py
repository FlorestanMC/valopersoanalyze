"""Métadonnées des cartes (valorant-api) : image top-down + conversion des
coordonnées de jeu vers l'image, pour les heatmaps de zones d'action.

Formule communautaire : à partir d'une position de jeu {x, y} :
    nx = y * xMultiplier + xScalarToAdd
    ny = x * yMultiplier + yScalarToAdd
(nx, ny) sont normalisés dans [0, 1] sur l'image displayIcon.

Mis en cache en base (namespace meta), les cartes changent rarement.
"""
import time

import requests

from . import storage

_TTL = 30 * 24 * 3600
_URL = "https://valorant-api.com/v1/maps"
_UA = "valo-stats/1.0"

_MAP = None  # {map_name: {image, xm, ym, xs, ys}}


def _build():
    global _MAP
    if _MAP is not None:
        return _MAP
    data, ts = storage.get_with_ts("meta", "maps")
    if data is None or not ts or (time.time() - ts) >= _TTL:
        try:
            r = requests.get(_URL, headers={"User-Agent": _UA}, timeout=20)
            r.raise_for_status()
            data = r.json()
            storage.set("meta", "maps", data)
        except Exception:  # noqa: BLE001 — hors-ligne / API down : dégrade proprement
            data = {"data": []}
    out = {}
    for m in (data or {}).get("data", []) or []:
        name = m.get("displayName")
        if not name or m.get("xMultiplier") is None:
            continue
        out[name] = {
            "image": m.get("displayIcon"),
            "xm": m.get("xMultiplier"), "ym": m.get("yMultiplier"),
            "xs": m.get("xScalarToAdd"), "ys": m.get("yScalarToAdd"),
        }
    _MAP = out
    return out


def info(map_name):
    """{image, xm, ym, xs, ys} pour une carte, ou None."""
    return _build().get(map_name)


def to_image(map_name, x, y):
    """Position de jeu (x, y) -> (nx, ny) normalisés [0,1] sur l'image, ou None."""
    m = info(map_name)
    if not m or x is None or y is None:
        return None
    nx = y * m["xm"] + m["xs"]
    ny = x * m["ym"] + m["ys"]
    if not (0 <= nx <= 1 and 0 <= ny <= 1):
        return None
    return round(nx, 4), round(ny, 4)
