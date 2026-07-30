"""Pipeline partagé : récupération (cache-aware) + calcul de toutes les stats.

Utilisé à la fois par le CLI (dashboard.py) et par le serveur web (server.py).
"""
import glob
import json
import os
from datetime import datetime

from .aggregate import aggregate
from . import first_contact, advanced, coach, ranks, storage, paths, splits

# Ancien cache fichiers (conservé pour la migration one-shot vers la base).
CACHE_DIR = os.path.join(paths.CACHE_DIR, "matches")


# --- cache (persisté en base : SQLite en local, Postgres en prod) -----------
def _cached(match_id: str):
    return storage.get("match", match_id)


def _store(match_id: str, detail: dict):
    storage.set("match", match_id, detail)


def migrate_file_cache(log=lambda *_: None) -> int:
    """Importe une seule fois les anciens matchs .cache/matches/*.json en base.

    Évite de tout re-télécharger après le passage à la base. Sans effet si déjà fait.
    """
    if storage.get("meta", "migrated_matches"):
        return 0
    n = 0
    for f in glob.glob(os.path.join(CACHE_DIR, "*.json")):
        mid = os.path.splitext(os.path.basename(f))[0]
        if storage.exists("match", mid):
            continue
        try:
            with open(f, encoding="utf-8") as fh:
                storage.set("match", mid, json.load(fh))
            n += 1
        except (OSError, ValueError):
            continue
    storage.set("meta", "migrated_matches", True)
    if n:
        log(f"  Migration : {n} match(s) importé(s) en base ({storage.backend()}).")
    return n


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
                return {"rank": p.get("currenttier_patched", "—"), "level": p.get("level", "—"),
                        "tier": p.get("currenttier", 0)}
    return {"rank": "—", "level": "—", "tier": 0}


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


def count_uncached(client, game_name, tag_line, queue="competitive",
                   size=15, act_only=False):
    """Nombre de parties récentes présentes côté API mais pas encore en cache.

    Un seul appel léger (stored-matches, IDs) : aucune partie n'est téléchargée.
    Sert d'indicateur « nouvelles parties depuis la dernière mise à jour ».
    """
    stored = client.get_stored_matches(game_name, tag_line, queue, size=size)
    if not stored:
        return 0
    if act_only:
        act = stored[0].get("meta", {}).get("season", {}).get("id")
        stored = [m for m in stored
                  if m.get("meta", {}).get("season", {}).get("id") == act]
    ids = [m["meta"]["id"] for m in stored]
    return sum(1 for mid in ids if _cached(mid) is None)


def load_details(client, ids, allow_fetch=True, log=lambda *_: None):
    """Charge le détail des matchs : cache d'abord, réseau si autorisé.

    Le rythme des téléchargements est adaptatif (client.pace() selon le quota).
    """
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
                client.pace()
            except Exception as e:  # noqa: BLE001
                log(f"  {i}/{len(ids)} ignoré ({str(e)[:80]})")
                missing += 1
                continue
        if isinstance(detail, dict):
            detail["_mid"] = mid  # pour marquer les parties nouvellement ajoutées
        matches.append(detail)
    return matches, fetched, missing


# --- suivi des parties fraîchement téléchargées (surlignage « nouveau ») -----
def save_new_ids(ids):
    storage.set("meta", "new_ids", list(ids))


def pop_new_ids():
    """Renvoie l'ensemble des IDs fraîchement téléchargés puis efface le marqueur."""
    ids = storage.get("meta", "new_ids") or []
    if ids:
        storage.delete("meta", "new_ids")
    return set(ids)


# --- total de parties de l'act via MMR (sans télécharger les matchs) --------
def mmr_info(client, game_name, tag_line, act_short):
    """Infos MMR en un seul appel léger : {act_games, act_wins, rr, elo, rr_change}.

    - RR = current_data.ranking_in_tier (points dans le palier).
    - act_games/wins = by_season de l'act courant. Aucun match téléchargé.
    """
    try:
        mmr = client.get_mmr(game_name, tag_line)
    except Exception:  # noqa: BLE001 — MMR indispo : on dégrade proprement
        return {}
    out = {}
    cd = mmr.get("current_data") or {}
    if cd:
        out["rr"] = cd.get("ranking_in_tier")
        out["elo"] = cd.get("elo")
        out["rr_change"] = cd.get("mmr_change_to_last_game")
    if act_short:
        target = act_short.lower()
        for key, val in (mmr.get("by_season") or {}).items():
            if key.lower() == target and isinstance(val, dict) and not val.get("error"):
                out["act_games"] = val.get("number_of_games")
                out["act_wins"] = val.get("wins")
                break
    return out


def _read_mmr_cache(region, riot_id, act_short):
    """Infos MMR en cache, seulement si elles concernent l'act courant."""
    d = storage.get("act", f"{region}_{riot_id}")
    if isinstance(d, dict) and d.get("act") == act_short:
        return d.get("info") or {}
    return {}


def _write_mmr_cache(region, riot_id, act_short, info):
    storage.set("act", f"{region}_{riot_id}", {"act": act_short, "info": info})


# --- résumé compact d'un joueur (onglet Team) -------------------------------
def player_summary(client, game_name, tag_line, queue="competitive",
                   count=15, allow_fetch=True, log=lambda *_: None):
    """Résumé léger des `count` dernières parties d'un joueur (forme récente).

    Les KPI (WR, K/D, ACS, KAST…) portent sur les `count` dernières parties, mais
    `act_games` / `act_wins` donnent le total réel de l'act (via MMR).

    Réutilise le cache global des matchs : deux coéquipiers partageant une partie
    ne la téléchargent qu'une fois.
    """
    stored = client.get_stored_matches(game_name, tag_line, queue, size=count)
    if not stored:
        return {"games": 0, "fetched": 0, "missing": 0}
    act_short = stored[0].get("meta", {}).get("season", {}).get("short")
    ids = [m["meta"]["id"] for m in stored[:count]]
    matches, fetched, missing = load_details(client, ids, allow_fetch=allow_fetch, log=log)
    if not matches:
        return {"games": 0, "fetched": fetched, "missing": missing}

    puuid = _find_me(matches, game_name, tag_line)
    ov = aggregate(matches, puuid, queue)
    ka = advanced.kast(matches, puuid)
    fc = first_contact.compute(matches, puuid)
    imgs = _collect_agent_imgs(matches)
    meta = _player_meta(matches, puuid)

    agents = list(ov.get("agents", {}).items())
    top_agents = [{"name": a, "games": s["games"], "win_rate": s["win_rate"],
                   "kd": s["kd"], "icon": imgs.get(a, {}).get("icon")}
                  for a, s in agents[:3]]
    top_agent = agents[0][0] if agents else None
    agent_bg = imgs.get(top_agent, {}).get("portrait") if top_agent else None

    # MMR (totaux d'act + RR/elo/variation) via un appel réseau, puis mis en cache
    # pour rester dispo lors des chargements cache-only (ouverture d'onglet).
    riot_id = f"{game_name}#{tag_line}"
    info = {}
    if allow_fetch:
        info = mmr_info(client, game_name, tag_line, act_short)
        if info:
            _write_mmr_cache(client.region, riot_id, act_short, info)
    if not info:
        info = _read_mmr_cache(client.region, riot_id, act_short)

    rk = ranks.info(meta.get("tier"), meta["rank"])
    return {
        "games": ov.get("games", 0),
        "act_games": info.get("act_games"), "act_wins": info.get("act_wins"),
        "rr": info.get("rr"), "rr_change": info.get("rr_change"), "elo": info.get("elo"),
        "rank": meta["rank"], "level": meta["level"],
        "rank_icon": rk["icon"], "rank_color": rk["color"],
        "win_rate": ov.get("win_rate"), "wins": ov.get("wins"), "losses": ov.get("losses"),
        "kd": ov.get("kd"), "kda": ov.get("kda"),
        "avg_acs": ov.get("avg_acs"),
        "avg_kills": ov.get("avg_kills"), "avg_deaths": ov.get("avg_deaths"),
        "avg_assists": ov.get("avg_assists"),
        "avg_hs_pct": ov.get("avg_hs_pct"),
        "kast": ka.get("kast"), "fcs": fc.get("fcs"),
        "top_agents": top_agents, "agent_bg": agent_bg,
        "recent": ov.get("recent", [])[:5],
        "fetched": fetched, "missing": missing,
    }


# --- build ------------------------------------------------------------------
def build_data(client, cfg, queue=None, allow_fetch=True, want_analysis=True,
               map_filter=None, log=lambda *_: None):
    """Construit le dict complet consommé par le dashboard, + un résumé de fetch."""
    queue = queue or cfg.queue
    ids, act_short = act_match_ids(client, cfg, queue)
    log(f"  Saison {act_short} ({queue}) — {len(ids)} partie(s).")

    # IDs non encore en cache AVANT ce chargement = parties nouvellement ajoutées
    # (utile seulement en mode fetch : elles seront téléchargées juste après).
    new_ids = [mid for mid in ids if _cached(mid) is None] if allow_fetch else []

    matches, fetched, missing = load_details(client, ids, allow_fetch=allow_fetch, log=log)
    if not matches:
        return None, {"fetched": fetched, "missing": missing, "total": 0, "act": act_short}

    puuid = _find_me(matches, cfg.game_name, cfg.tag_line)

    # Cartes disponibles + détail par carte (calculés sur TOUTES les parties,
    # avant le filtre, pour l'onglet Cartes et le sélecteur).
    maps_available = sorted({m.get("metadata", {}).get("map", "?") for m in matches})
    by_map = splits.by_map(matches, puuid)
    fc_heatmap = first_contact.heatmap(matches, puuid)

    # Filtre carte : restreint toutes les autres stats à la carte choisie.
    map_filter = map_filter or "all"
    if map_filter != "all":
        filtered = [m for m in matches if m.get("metadata", {}).get("map") == map_filter]
        if filtered:
            matches = filtered

    overview = aggregate(matches, puuid, queue)
    fc = first_contact.compute(matches, puuid)
    ka = advanced.kast(matches, puuid)
    wp = advanced.weapons(matches, puuid)
    imgs = _collect_agent_imgs(matches)
    meta = _player_meta(matches, puuid)

    top_agent = next(iter(overview.get("agents", {})), None)
    agent_bg = imgs.get(top_agent, {}).get("portrait") if top_agent else None

    # RR du profil (MMR) : réseau si autorisé puis cache, sinon relecture du cache.
    pinfo = {}
    if allow_fetch:
        pinfo = mmr_info(client, cfg.game_name, cfg.tag_line, act_short)
        if pinfo:
            _write_mmr_cache(cfg.region, cfg.riot_id, act_short, pinfo)
    if not pinfo:
        pinfo = _read_mmr_cache(cfg.region, cfg.riot_id, act_short)

    analysis = None
    if want_analysis:
        combined = {**overview, "kast": ka["kast"], "first_contact": fc,
                    "weapons": [{k: w[k] for k in ("name", "kills", "deaths")} for w in wp]}
        try:
            analysis = coach.analyze(cfg.anthropic_api_key, cfg.anthropic_model,
                                     cfg.riot_id, combined)
        except Exception as e:  # noqa: BLE001
            log(f"  (analyse indisponible : {str(e)[:100]})")

    rk = ranks.info(meta.get("tier"), meta["rank"])
    data = {
        "player": {"name": cfg.riot_id, "rank": meta["rank"], "level": meta["level"],
                   "rank_icon": rk["icon"], "rank_color": rk["color"], "agent_bg": agent_bg,
                   "rr": pinfo.get("rr"), "rr_change": pinfo.get("rr_change"),
                   "elo": pinfo.get("elo")},
        "act": act_short,
        "queue": queue,
        "region": cfg.region,
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "overview": overview,
        "fc": fc,
        "kast": ka,
        "weapons": wp,
        "splits": splits.compute(matches, puuid, queue),
        "by_map": by_map,
        "fc_heatmap": fc_heatmap,
        "maps_available": maps_available,
        "map_filter": map_filter,
        "agent_img": imgs,
        "analysis": analysis,
    }
    summary = {"fetched": fetched, "missing": missing, "total": len(matches),
               "act": act_short, "new_ids": new_ids}
    return data, summary
