"""Découpage des stats par SIDE (attaque/défense) et par ISSUE de round
(gagné/perdu), à partir du détail par round des matchs HenrikDev.

Deux vues indépendantes :
  - by_side    : {"attack": {...}, "defense": {...}}
  - by_outcome : {"win": {...}, "loss": {...}}

Métriques par bucket : ADR, KAST%, HS% (global), K/D, First Kills/Deaths + FCS,
multi-kills (2k+/3k+), Clutch%. (HS%/arme et stats d'utilitaires ne sont pas
fournis par round par l'API -> non calculés.)
"""
from collections import defaultdict

TRADE_WINDOW_MS = 3000


def _my_team(match, puuid):
    for p in match.get("players", {}).get("all_players", []):
        if p.get("puuid") == puuid:
            return p.get("team")
    return None


def _rosters(match, team):
    mates, enemies = set(), set()
    for p in match.get("players", {}).get("all_players", []):
        (mates if p.get("team") == team else enemies).add(p.get("puuid"))
    return mates, enemies


def _kills_by_round(match):
    by_round = defaultdict(list)
    for k in match.get("kills", []):
        by_round[k.get("round")].append(k)
    return by_round


def _other(t):
    return "Blue" if t == "Red" else ("Red" if t == "Blue" else None)


def _attacking_teams(rounds):
    """Équipe attaquante par round (déduite des plants + logique de mi-temps)."""
    n = len(rounds)
    atk = [None] * n
    for i, r in enumerate(rounds):
        pb = ((r.get("plant_events") or {}).get("planted_by") or {}).get("team")
        if pb in ("Red", "Blue"):
            atk[i] = pb
    atk1 = next((atk[i] for i in range(min(12, n)) if atk[i]), None)
    if atk1 is None:  # aucun plant en 1re mi-temps -> déduire de la 2e
        a2 = next((atk[i] for i in range(12, min(24, n)) if atk[i]), None)
        atk1 = _other(a2) if a2 else None
    for i in range(n):
        if atk[i]:
            continue
        if i < 12:
            atk[i] = atk1
        elif i < 24:
            atk[i] = _other(atk1)
        else:  # prolongations : les sides alternent chaque round
            atk[i] = _other(atk[i - 1]) if i > 0 else None
    return atk


def _ps(round_, puuid):
    for p in round_.get("player_stats", []):
        if p.get("player_puuid") == puuid:
            return p
    return {}


def _blank():
    return {"rounds": 0, "dmg": 0, "hs": 0, "bs": 0, "ls": 0, "kills": 0,
            "deaths": 0, "kast": 0, "fk": 0, "fd": 0, "mk": 0, "mk3": 0,
            "catt": 0, "cwon": 0}


def _finalize(b):
    r = b["rounds"]
    shots = b["hs"] + b["bs"] + b["ls"]
    fkfd = b["fk"] + b["fd"]
    return {
        "rounds": r,
        "adr": round(b["dmg"] / r) if r else None,
        "kast": round(b["kast"] / r * 100, 1) if r else None,
        "hs_pct": round(b["hs"] / shots * 100, 1) if shots else None,
        "kills": b["kills"], "deaths": b["deaths"],
        "kd": round(b["kills"] / max(b["deaths"], 1), 2) if r else None,
        "fk": b["fk"], "fd": b["fd"],
        "fcs": round(b["fk"] / fkfd * 100, 1) if fkfd else None,
        "mk": b["mk"], "mk3": b["mk3"],
        "cwon": b["cwon"], "catt": b["catt"],
        "clutch": round(b["cwon"] / b["catt"] * 100, 1) if b["catt"] else None,
    }


def compute(matches, puuid, queue="competitive"):
    side = {"attack": _blank(), "defense": _blank()}
    outc = {"win": _blank(), "loss": _blank()}

    for match in matches:
        team = _my_team(match, puuid)
        if not team:
            continue
        rounds = match.get("rounds") or []
        attackers = _attacking_teams(rounds)
        kbr = _kills_by_round(match)
        mates, enemies = _rosters(match, team)

        for i, rd in enumerate(rounds):
            outcome = "win" if rd.get("winning_team") == team else "loss"
            atk = attackers[i] if i < len(attackers) else None
            sd = "attack" if atk == team else ("defense" if atk else None)

            ps = _ps(rd, puuid)
            evs = kbr.get(i, [])
            hs = ps.get("headshots") or 0
            bs = ps.get("bodyshots") or 0
            ls = ps.get("legshots") or 0
            dmg = ps.get("damage") or 0

            my_kills = [e for e in evs if e.get("killer_puuid") == puuid]
            kc = len(my_kills)
            death = next((e for e in evs if e.get("victim_puuid") == puuid), None)
            died = death is not None
            has_a = any(
                any((a or {}).get("assistant_puuid") == puuid for a in (e.get("assistants") or []))
                for e in evs
            )
            traded = False
            if death is not None:
                killer = death.get("killer_puuid")
                td = death.get("kill_time_in_round", 0)
                for e in evs:
                    if (e.get("victim_puuid") == killer and e.get("killer_team") == team
                            and 0 <= e.get("kill_time_in_round", 0) - td <= TRADE_WINDOW_MS):
                        traded = True
                        break
            kast_ok = (kc > 0) or has_a or (not died) or traded

            fk = fd = 0
            if evs:
                first = min(evs, key=lambda e: e.get("kill_time_in_round", 1e12))
                fk = int(first.get("killer_puuid") == puuid)
                fd = int(first.get("victim_puuid") == puuid)

            # clutch : dernier en vie de l'équipe, avec au moins un ennemi vivant
            catt = cwon = 0
            mate_deaths = {e.get("victim_puuid"): e.get("kill_time_in_round", 0)
                           for e in evs
                           if e.get("victim_puuid") in mates and e.get("victim_puuid") != puuid}
            if mates and len(mate_deaths) == len(mates) - 1:
                t_all = max(mate_deaths.values()) if mate_deaths else 0
                my_death_t = death.get("kill_time_in_round", 1e12) if death else 1e12
                if my_death_t > t_all:
                    enemy_dead = sum(1 for e in evs if e.get("victim_puuid") in enemies
                                     and e.get("kill_time_in_round", 0) <= t_all)
                    if len(enemies) - enemy_dead >= 1:
                        catt = 1
                        cwon = int(outcome == "win")

            for b in ([side[sd]] if sd else []) + [outc[outcome]]:
                b["rounds"] += 1
                b["dmg"] += dmg
                b["hs"] += hs
                b["bs"] += bs
                b["ls"] += ls
                b["kills"] += kc
                b["deaths"] += int(died)
                b["kast"] += int(kast_ok)
                b["fk"] += fk
                b["fd"] += fd
                b["mk"] += int(kc >= 2)
                b["mk3"] += int(kc >= 3)
                b["catt"] += catt
                b["cwon"] += cwon

    return {
        "by_side": {k: _finalize(v) for k, v in side.items()},
        "by_outcome": {k: _finalize(v) for k, v in outc.items()},
    }
