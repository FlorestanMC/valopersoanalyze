"""Pipeline partagé : récupération (cache-aware) + calcul de toutes les stats.

Utilisé à la fois par le CLI (dashboard.py) et par le serveur web (server.py).
"""
import json
import os
import time
from datetime import datetime

from .aggregate import aggregate
from . import first_contact, advanced, coach

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".cache", "matches")


# --- cache ------------------------------------------------------------------
def _cached(match_id: str):
    path = os.path.join(CACHE_DIR, f"{match_id}.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def _store(match_id: str, detail: dict):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(os.path.join(CACHE_DIR, f"{match_id}.json"), "w", encoding="utf-8") as f:
        json.dump(detail, f)


# --- helpers ----------------------------------------------------------------
def _find_me(matches, game_name, tag_line):
    for m in matches:
        for p in m.get("players", {}).get("all_players", []):
            if (p.get("name", "").lower() == game_name.lower()
                    and p.get("tag", "").lower() == tag_line.lower()):
                return p.get("puuid", "")
    return ""


def _collect_agent_imgs(matches):
    out = {}
    for m in matches:
        for p in m.get("players", {}).get("all_players", []):
            name = p.get("character")
            ag = p.get("assets", {}).get("agent", {})
            if name and name not in out and ag:
                out[name] = {"icon": ag.get("small"), "portrait": ag.get("full") or ag.get("bust")}
    return out


def _player_meta(matches, puuid):
    for m in matches:  # matches[0] = plus récent
        for p in m.get("players", {}).get("all_players", []):
            if p.get("puuid") == puuid:
                return {"rank": p.get("currenttier_patched", "—"), "level": p.get("level", "—")}
    return {"rank": "—", "level": "—"}


def act_match_ids(client, cfg, queue="competitive"):
    """Renvoie (ids_de_la_saison_courante, libellé_saison) via stored-matches."""
    stored = client.get_stored_matches(cfg.game_name, cfg.tag_line, queue, size=50)
    if not stored:
        return [], "?"
    current_act = stored[0].get("meta", {}).get("season", {}).get("id")
    act_short = stored[0].get("meta", {}).get("season", {}).get("short", "?")
    ids = [m["meta"]["id"] for m in stored
           if m.get("meta", {}).get("season", {}).get("id") == current_act]
    return ids, act_short


def load_details(client, ids, allow_fetch=True, log=lambda *_: None, sleep=2.2):
    """Charge le détail des matchs : cache d'abord, réseau si autorisé."""
    matches, fetched, missing = [], 0, 0
    for i, mid in enumerate(ids, 1):
        detail = _cached(mid)
        if detail is None:
            if not allow_fetch:
                missing += 1
                continue
            try:
                detail = client.get_match_detail(mid)
                _store(mid, detail)
                fetched += 1
                log(f"  {i}/{len(ids)} téléchargé")
                time.sleep(sleep)
            except Exception as e:  # noqa: BLE001
                log(f"  {i}/{len(ids)} ignoré ({str(e)[:80]})")
                missing += 1
                continue
        matches.append(detail)
    return matches, fetched, missing


# --- build ------------------------------------------------------------------
def build_data(client, cfg, queue=None, allow_fetch=True, want_analysis=True,
               log=lambda *_: None):
    """Construit le dict complet consommé par le dashboard, + un résumé de fetch."""
    queue = queue or cfg.queue
    ids, act_short = act_match_ids(client, cfg, queue)
    log(f"  Saison {act_short} ({queue}) — {len(ids)} partie(s).")

    matches, fetched, missing = load_details(client, ids, allow_fetch=allow_fetch, log=log)
    if not matches:
        return None, {"fetched": fetched, "missing": missing, "total": 0, "act": act_short}

    puuid = _find_me(matches, cfg.game_name, cfg.tag_line)
    overview = aggregate(matches, puuid, queue)
    fc = first_contact.compute(matches, puuid)
    ka = advanced.kast(matches, puuid)
    wp = advanced.weapons(matches, puuid)
    imgs = _collect_agent_imgs(matches)
    meta = _player_meta(matches, puuid)

    top_agent = next(iter(overview.get("agents", {})), None)
    agent_bg = imgs.get(top_agent, {}).get("portrait") if top_agent else None

    analysis = None
    if want_analysis:
        combined = {**overview, "kast": ka["kast"], "first_contact": fc,
                    "weapons": [{k: w[k] for k in ("name", "kills", "deaths")} for w in wp]}
        try:
            analysis = coach.analyze(cfg.anthropic_api_key, cfg.anthropic_model,
                                     cfg.riot_id, combined)
        except Exception as e:  # noqa: BLE001
            log(f"  (analyse indisponible : {str(e)[:100]})")

    data = {
        "player": {"name": cfg.riot_id, "rank": meta["rank"], "level": meta["level"],
                   "agent_bg": agent_bg},
        "act": act_short,
        "queue": queue,
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "overview": overview,
        "fc": fc,
        "kast": ka,
        "weapons": wp,
        "agent_img": imgs,
        "analysis": analysis,
    }
    summary = {"fetched": fetched, "missing": missing, "total": len(matches), "act": act_short}
    return data, summary
