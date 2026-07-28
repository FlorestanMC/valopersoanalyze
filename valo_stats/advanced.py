"""Stats avancées : KAST et statistiques par arme, à partir des matchs HenrikDev.

KAST = % de rounds où le joueur a réalisé au moins l'un de :
  - K (Kill)      : a tué au moins un adversaire
  - A (Assist)    : a assisté sur un kill
  - S (Survive)   : a survécu au round
  - T (Trade)     : a été « traded » (un coéquipier a tué son tueur peu après sa mort)
"""
from collections import defaultdict

# Fenêtre de trade : un coéquipier venge la mort dans ce délai (ms).
TRADE_WINDOW_MS = 3000


def _my_team(match: dict, puuid: str):
    for p in match.get("players", {}).get("all_players", []):
        if p.get("puuid") == puuid:
            return p.get("team")
    return None


def _kills_by_round(match: dict):
    by_round = defaultdict(list)
    for k in match.get("kills", []):
        by_round[k.get("round")].append(k)
    return by_round


def kast(matches, puuid: str) -> dict:
    total = 0
    good = 0
    comp = {"k": 0, "a": 0, "s": 0, "t": 0}

    for match in matches:
        team = _my_team(match, puuid)
        rounds_played = match.get("metadata", {}).get("rounds_played", 0)
        by_round = _kills_by_round(match)

        for r in range(rounds_played):
            evs = by_round.get(r, [])
            has_k = any(e.get("killer_puuid") == puuid for e in evs)
            has_a = any(
                any((ast or {}).get("assistant_puuid") == puuid
                    for ast in (e.get("assistants") or []))
                for e in evs
            )
            death = next((e for e in evs if e.get("victim_puuid") == puuid), None)
            survived = death is None
            traded = False
            if death is not None:
                killer = death.get("killer_puuid")
                t_death = death.get("kill_time_in_round", 0)
                for e in evs:
                    if e.get("victim_puuid") == killer and e.get("killer_team") == team:
                        dt = e.get("kill_time_in_round", 0) - t_death
                        if 0 <= dt <= TRADE_WINDOW_MS:
                            traded = True
                            break

            if has_k or has_a or survived or traded:
                good += 1
            comp["k"] += int(has_k)
            comp["a"] += int(has_a)
            comp["s"] += int(survived)
            comp["t"] += int(traded)
            total += 1

    return {
        "kast": round(good / total * 100, 1) if total else None,
        "rounds": total,
        "components": comp,
    }


def weapons(matches, puuid: str, top: int = 10) -> list:
    """Kills réalisés avec chaque arme et morts subies face à chaque arme."""
    agg = {}

    def _slot(name, icon):
        w = agg.get(name)
        if w is None:
            w = {"name": name, "kills": 0, "deaths": 0, "icon": icon}
            agg[name] = w
        elif not w["icon"] and icon:
            w["icon"] = icon
        return w

    for match in matches:
        for k in match.get("kills", []):
            name = k.get("damage_weapon_name") or "Melee/Autre"
            icon = (k.get("damage_weapon_assets") or {}).get("display_icon")
            if k.get("killer_puuid") == puuid:
                _slot(name, icon)["kills"] += 1
            if k.get("victim_puuid") == puuid:
                _slot(name, icon)["deaths"] += 1

    return sorted(agg.values(), key=lambda w: -(w["kills"] + w["deaths"]))[:top]
