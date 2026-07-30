"""Calcul des duels d'ouverture (First Kill / First Death) et du First Contact Success.

Pour chaque round, le « first blood » est le kill au temps le plus précoce
(`kill_time_in_round` minimal). Si le joueur en est l'auteur → First Kill (FK) ;
s'il en est la victime → First Death (FD).

First Contact Success (FCS) = FK / (FK + FD) : proportion des duels d'ouverture
auxquels le joueur a participé et qu'il a gagnés.

On agrège aussi ces duels **par arme** : l'arme utilisée quand tu prends le
premier kill, et l'arme qui te tue quand tu prends la première mort.
"""
from collections import defaultdict

from . import maps


def first_bloods(match: dict):
    """Renvoie {round_index: kill_event} : le premier kill de chaque round."""
    by_round = {}
    best_time = {}
    for k in match.get("kills", []):
        r = k.get("round")
        t = k.get("kill_time_in_round")
        if r is None or t is None:
            continue
        if r not in best_time or t < best_time[r]:
            best_time[r] = t
            by_round[r] = k
    return by_round


def _agent_of(match: dict, puuid: str) -> str:
    for p in match.get("players", {}).get("all_players", []):
        if p.get("puuid") == puuid:
            return p.get("character", "?")
    return "?"


def heatmap(matches, puuid: str) -> dict:
    """Positions des duels d'ouverture du joueur : FK (où il prend le 1er kill)
    et FD (où il subit la 1re mort), taguées par agent et carte, pour un
    affichage filtrable. Coordonnées normalisées [0,1] via maps.to_image."""
    points = []
    agents = set()
    maps_seen = {}
    for match in matches:
        mp = match.get("metadata", {}).get("map", "?")
        agent = _agent_of(match, puuid)
        agents.add(agent)
        mi = maps.info(mp)
        if mi and mi.get("image"):
            maps_seen[mp] = mi["image"]
        for k in first_bloods(match).values():
            if k.get("killer_puuid") == puuid:
                loc = next((pl.get("location") for pl in (k.get("player_locations_on_kill") or [])
                            if pl.get("player_puuid") == puuid), None)
                pt = maps.to_image(mp, loc.get("x"), loc.get("y")) if loc else None
                if pt:
                    points.append({"x": pt[0], "y": pt[1], "t": "fk", "map": mp, "agent": agent})
            elif k.get("victim_puuid") == puuid:
                loc = k.get("victim_death_location")
                pt = maps.to_image(mp, loc.get("x"), loc.get("y")) if loc else None
                if pt:
                    points.append({"x": pt[0], "y": pt[1], "t": "fd", "map": mp, "agent": agent})
    return {
        "points": points,
        "agents": sorted(a for a in agents if a and a != "?"),
        "maps": [{"name": n, "image": img} for n, img in sorted(maps_seen.items())],
    }


def compute(matches, puuid: str) -> dict:
    total = {"fk": 0, "fd": 0, "rounds": 0, "games": 0}
    by_agent = defaultdict(lambda: {"fk": 0, "fd": 0, "rounds": 0, "games": 0})
    by_weapon = defaultdict(lambda: {"fk": 0, "fd": 0, "icon": None})

    for match in matches:
        agent = _agent_of(match, puuid)
        rounds_played = match.get("metadata", {}).get("rounds_played", 0)
        fbs = first_bloods(match)

        g_fk = g_fd = 0
        for k in fbs.values():
            name = k.get("damage_weapon_name") or "Melee/Autre"
            icon = (k.get("damage_weapon_assets") or {}).get("display_icon")
            if k.get("killer_puuid") == puuid:
                g_fk += 1
                by_weapon[name]["fk"] += 1
                by_weapon[name]["icon"] = by_weapon[name]["icon"] or icon
            elif k.get("victim_puuid") == puuid:
                g_fd += 1
                by_weapon[name]["fd"] += 1
                by_weapon[name]["icon"] = by_weapon[name]["icon"] or icon

        total["fk"] += g_fk
        total["fd"] += g_fd
        total["rounds"] += rounds_played
        total["games"] += 1
        by_agent[agent]["fk"] += g_fk
        by_agent[agent]["fd"] += g_fd
        by_agent[agent]["rounds"] += rounds_played
        by_agent[agent]["games"] += 1

    return _finalize(total, by_agent, by_weapon)


def _rates(fk: int, fd: int, rounds: int) -> dict:
    duels = fk + fd
    return {
        "fk": fk,
        "fd": fd,
        "duels": duels,
        # First Contact Success : % de duels d'ouverture gagnés
        "fcs": round(fk / duels * 100, 1) if duels else None,
        # Part des rounds où le joueur prend le premier kill / la première mort
        "fk_per_round": round(fk / rounds * 100, 1) if rounds else None,
        "fd_per_round": round(fd / rounds * 100, 1) if rounds else None,
    }


def _finalize(total, by_agent, by_weapon) -> dict:
    out = {
        "games": total["games"],
        "rounds": total["rounds"],
        **_rates(total["fk"], total["fd"], total["rounds"]),
        "agents": {},
        "weapons": [],
    }
    for agent, s in sorted(by_agent.items(), key=lambda kv: -(kv[1]["fk"] + kv[1]["fd"])):
        out["agents"][agent] = {
            "games": s["games"],
            **_rates(s["fk"], s["fd"], s["rounds"]),
        }
    for name, s in sorted(by_weapon.items(), key=lambda kv: -(kv[1]["fk"] + kv[1]["fd"])):
        out["weapons"].append({
            "name": name, "fk": s["fk"], "fd": s["fd"],
            "duels": s["fk"] + s["fd"], "icon": s["icon"],
        })
    return out
