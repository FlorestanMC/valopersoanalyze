"""Agrégation des matchs HenrikDev (v3/v2) en statistiques lisibles pour un joueur."""
from collections import defaultdict
from datetime import datetime


def _match_day(meta: dict):
    """Date locale 'YYYY-MM-DD' du match à partir de game_start (s ou ms), sinon None."""
    ts = meta.get("game_start")
    if ts is None:
        return None
    try:
        ts = float(ts)
    except (TypeError, ValueError):
        return None
    if ts > 1e12:  # millisecondes -> secondes
        ts /= 1000.0
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except (ValueError, OSError, OverflowError):
        return None


def _find_me(match: dict, puuid: str):
    players = match.get("players", {}).get("all_players", [])
    return next((p for p in players if p.get("puuid") == puuid), None)


def _team_of(match: dict, color: str):
    return match.get("teams", {}).get((color or "").lower(), {})


def aggregate(matches, puuid, queue_filter="competitive"):
    overall = {
        "games": 0, "wins": 0, "kills": 0, "deaths": 0, "assists": 0,
        "rounds": 0, "rounds_won": 0, "rounds_lost": 0, "score": 0,
        "head": 0, "body": 0, "leg": 0,
    }
    by_agent = defaultdict(lambda: {"games": 0, "wins": 0, "kills": 0, "deaths": 0})
    by_map = defaultdict(lambda: {"games": 0, "wins": 0})
    by_day = defaultdict(int)
    recent = []

    for match in matches:
        meta = match.get("metadata", {})
        me = _find_me(match, puuid)
        if not me:
            continue

        stats = me.get("stats", {})
        color = me.get("team")
        team = _team_of(match, color)
        won = bool(team.get("has_won"))
        agent = me.get("character", "?")
        map_name = meta.get("map", "?")
        rounds = meta.get("rounds_played") or 1
        k = stats.get("kills", 0)
        d = stats.get("deaths", 0)
        a = stats.get("assists", 0)
        score = stats.get("score", 0)

        head = stats.get("headshots", 0)
        body = stats.get("bodyshots", 0)
        leg = stats.get("legshots", 0)
        total_shots = head + body + leg
        hs = (head / total_shots * 100) if total_shots else None

        overall["games"] += 1
        overall["wins"] += int(won)
        overall["kills"] += k
        overall["deaths"] += d
        overall["assists"] += a
        overall["rounds"] += rounds
        overall["rounds_won"] += team.get("rounds_won", 0)
        overall["rounds_lost"] += team.get("rounds_lost", 0)
        overall["score"] += score
        overall["head"] += head
        overall["body"] += body
        overall["leg"] += leg

        by_agent[agent]["games"] += 1
        by_agent[agent]["wins"] += int(won)
        by_agent[agent]["kills"] += k
        by_agent[agent]["deaths"] += d

        by_map[map_name]["games"] += 1
        by_map[map_name]["wins"] += int(won)

        day = _match_day(meta)
        if day:
            by_day[day] += 1

        recent.append({
            "agent": agent, "map": map_name, "won": won,
            "kda": f"{k}/{d}/{a}",
            "acs": round(score / rounds) if rounds else 0,
            "hs": round(hs, 1) if hs is not None else None,
        })

    return _finalize(overall, by_agent, by_map, recent, by_day)


def _finalize(overall, by_agent, by_map, recent, by_day=None):
    g = overall["games"]
    if g == 0:
        return {"games": 0}

    total_shots = overall["head"] + overall["body"] + overall["leg"]
    def shot_pct(n):
        return round(n / total_shots * 100, 1) if total_shots else None

    rw, rl = overall["rounds_won"], overall["rounds_lost"]
    summary = {
        "games": g,
        "wins": overall["wins"],
        "losses": g - overall["wins"],
        "win_rate": round(overall["wins"] / g * 100, 1),
        "rounds_won": rw,
        "rounds_lost": rl,
        "round_win_rate": round(rw / (rw + rl) * 100, 1) if (rw + rl) else None,
        "kd": round(overall["kills"] / max(overall["deaths"], 1), 2),
        "kda": round((overall["kills"] + overall["assists"]) / max(overall["deaths"], 1), 2),
        "avg_kills": round(overall["kills"] / g, 1),
        "avg_deaths": round(overall["deaths"] / g, 1),
        "avg_assists": round(overall["assists"] / g, 1),
        "avg_acs": round(overall["score"] / max(overall["rounds"], 1)),
        "avg_hs_pct": shot_pct(overall["head"]),
        "precision": {"hs": shot_pct(overall["head"]), "bs": shot_pct(overall["body"]),
                      "ls": shot_pct(overall["leg"])},
        "agents": {}, "maps": {}, "recent": recent,
        "days": dict(sorted((by_day or {}).items())),
    }
    for agent, s in sorted(by_agent.items(), key=lambda kv: -kv[1]["games"]):
        summary["agents"][agent] = {
            "games": s["games"],
            "win_rate": round(s["wins"] / s["games"] * 100, 1),
            "kd": round(s["kills"] / max(s["deaths"], 1), 2),
        }
    for m, s in sorted(by_map.items(), key=lambda kv: -kv[1]["games"]):
        summary["maps"][m] = {
            "games": s["games"],
            "win_rate": round(s["wins"] / s["games"] * 100, 1),
        }
    return summary
