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
def act_totals(client, game_name, tag_line, act_short):
    """(nb_parties, victoires) de l'act `act_short` via l'endpoint MMR, sinon None.

    N'effectue qu'un appel réseau léger : aucun détail de match n'est téléchargé.
    """
    if not act_short:
        return None, None
    try:
        by_season = (client.get_mmr(game_name, tag_line).get("by_season") or {})
    except Exception:  # noqa: BLE001 — MMR indispo : on dégrade proprement
        return None, None
    target = act_short.lower()
    for key, val in by_season.items():
        if key.lower() == target and isinstance(val, dict) and not val.get("error"):
            return val.get("number_of_games"), val.get("wins")
    return None, None


def _read_act_cache(region, riot_id, act_short):
    """Totaux d'act en cache, seulement s'ils concernent l'act courant."""
    d = storage.get("act", f"{region}_{riot_id}")
    if isinstance(d, dict) and d.get("act") == act_short:
        return d.get("games"), d.get("wins")
    return None, None


def _write_act_cache(region, riot_id, act_short, games, wins):
    storage.set("act", f"{region}_{riot_id}",
                {"act": act_short, "games": games, "wins": wins})


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

    # Totaux de l'act via MMR (réseau) puis mis en cache, sinon relecture du cache
    # pour rester dispo lors des chargements cache-only (ouverture d'onglet).
    riot_id = f"{game_name}#{tag_line}"
    act_games = act_wins = None
    if allow_fetch:
        act_games, act_wins = act_totals(client, game_name, tag_line, act_short)
        if act_games is not None:
            _write_act_cache(client.region, riot_id, act_short, act_games, act_wins)
    if act_games is None:
        act_games, act_wins = _read_act_cache(client.region, riot_id, act_short)

    rk = ranks.info(meta.get("tier"), meta["rank"])
    return {
        "games": ov.get("games", 0),
        "act_games": act_games, "act_wins": act_wins,
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
               log=lambda *_: None):
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

    rk = ranks.info(meta.get("tier"), meta["rank"])
    data = {
        "player": {"name": cfg.riot_id, "rank": meta["rank"], "level": meta["level"],
                   "rank_icon": rk["icon"], "rank_color": rk["color"], "agent_bg": agent_bg},
        "act": act_short,
        "queue": queue,
        "region": cfg.region,
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "overview": overview,
        "fc": fc,
        "kast": ka,
        "weapons": wp,
        "splits": splits.compute(matches, puuid, queue),
        "agent_img": imgs,
        "analysis": analysis,
    }
    summary = {"fetched": fetched, "missing": missing, "total": len(matches),
               "act": act_short, "new_ids": new_ids}
    return data, summary
