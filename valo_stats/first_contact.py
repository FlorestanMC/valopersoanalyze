"""Calcul des duels d'ouverture (First Kill / First Death) et du First Contact Success.

Pour chaque round, le « first blood » est le kill au temps le plus précoce
(`kill_time_in_round` minimal). Si le joueur en est l'auteur → First Kill (FK) ;
s'il en est la victime → First Death (FD).

First Contact Success (FCS) = FK / (FK + FD) : proportion des duels d'ouverture
auxquels le joueur a participé et qu'il a gagnés.
"""
from collections import defaultdict


def first_bloods(match: dict):
    """Renvoie {round_index: (killer_puuid, victim_puuid)} pour chaque round joué."""
    by_round = {}
    best_time = {}
    for k in match.get("kills", []):
        r = k.get("round")
        t = k.get("kill_time_in_round")
        if r is None or t is None:
            continue
        if r not in best_time or t < best_time[r]:
            best_time[r] = t
            by_round[r] = (k.get("killer_puuid"), k.get("victim_puuid"))
    return by_round


def _agent_of(match: dict, puuid: str) -> str:
    for p in match.get("players", {}).get("all_players", []):
        if p.get("puuid") == puuid:
            return p.get("character", "?")
    return "?"


def compute(matches, puuid: str) -> dict:
    total = {"fk": 0, "fd": 0, "rounds": 0, "games": 0}
    by_agent = defaultdict(lambda: {"fk": 0, "fd": 0, "rounds": 0, "games": 0})

    for match in matches:
        agent = _agent_of(match, puuid)
        rounds_played = match.get("metadata", {}).get("rounds_played", 0)
        fbs = first_bloods(match)

        g_fk = g_fd = 0
        for killer, victim in fbs.values():
            if killer == puuid:
                g_fk += 1
            elif victim == puuid:
                g_fd += 1

        total["fk"] += g_fk
        total["fd"] += g_fd
        total["rounds"] += rounds_played
        total["games"] += 1
        by_agent[agent]["fk"] += g_fk
        by_agent[agent]["fd"] += g_fd
        by_agent[agent]["rounds"] += rounds_played
        by_agent[agent]["games"] += 1

    return _finalize(total, by_agent)


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


def _finalize(total, by_agent) -> dict:
    out = {
        "games": total["games"],
        "rounds": total["rounds"],
        **_rates(total["fk"], total["fd"], total["rounds"]),
        "agents": {},
    }
    for agent, s in sorted(by_agent.items(), key=lambda kv: -(kv[1]["fk"] + kv[1]["fd"])):
        out["agents"][agent] = {
            "games": s["games"],
            **_rates(s["fk"], s["fd"], s["rounds"]),
        }
    return out
