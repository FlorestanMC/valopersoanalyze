"""Emblèmes et couleurs officielles des rangs compétitifs (via valorant-api.com).

Mappe le numéro de tier HenrikDev (`currenttier`, ex. 20 = Diamant 3) vers
l'emblème de rang et sa couleur officielle, pour coller au thème.

Mis en cache en base (namespace meta) — les paliers changent rarement.
"""
import time

import requests

from . import storage

_TTL = 30 * 24 * 3600  # 30 jours
_URL = "https://valorant-api.com/v1/competitivetiers"
_UA = "valo-stats/1.0"

_MAP = None  # {tier_int: {"name","color","icon"}}


def _hex(rgba: str) -> str:
    """'b489c4ff' -> '#b489c4'."""
    rgba = (rgba or "").strip()
    return "#" + rgba[:6] if len(rgba) >= 6 else "#8b93a7"


def _load_raw() -> dict:
    cached, ts = storage.get_with_ts("meta", "competitivetiers")
    if cached is not None and ts and (time.time() - ts) < _TTL:
        return cached
    r = requests.get(_URL, headers={"User-Agent": _UA}, timeout=20)
    r.raise_for_status()
    data = r.json()
    storage.set("meta", "competitivetiers", data)
    return data


def _build() -> dict:
    global _MAP
    if _MAP is not None:
        return _MAP
    out = {}
    try:
        data = _load_raw()
        # Le dernier jeu de paliers = l'actuel (contient Ascendant/Immortal/Radiant).
        tiers = data["data"][-1]["tiers"]
        for t in tiers:
            name = (t.get("tierName") or "").title().strip()
            out[int(t["tier"])] = {
                "name": name,
                "color": _hex(t.get("color")),
                "icon": t.get("largeIcon") or t.get("smallIcon"),
            }
    except Exception:  # noqa: BLE001 — hors-ligne / API down : on dégrade proprement
        out = {}
    _MAP = out
    return out


def info(tier, patched: str = None) -> dict:
    """Renvoie {name, color, icon} pour un numéro de tier. Tolérant si API indispo."""
    m = _build()
    try:
        tier = int(tier)
    except (TypeError, ValueError):
        tier = 0
    r = m.get(tier)
    if r and (tier > 0):
        return {"name": patched or r["name"], "color": r["color"], "icon": r["icon"]}
    # fallback (non classé / API indisponible)
    return {"name": patched or (r["name"] if r else "Non classé"),
            "color": "#8b93a7", "icon": r["icon"] if r else None}
