"""Statistiques COLLECTIVES de l'équipe, sur les matchs joués ensemble
(≥ min_members de l'effectif dans la même team).

Calcule : WR par side/carte, trade efficiency, plant/retake/post-plant,
tempo (temps avant 1er contact -> WR), différentiel éco -> WR, et les
positions de kills/morts par carte (heatmap).
"""
from . import splits, maps

TRADE_WINDOW_MS = 3000

_TEMPO_ORDER = ["< 10 s", "10–20 s", "20–35 s", "> 35 s", "Aucun contact"]
_ECON_ORDER = ["Fort désavantage", "Désavantage", "Équilibré", "Avantage", "Fort avantage"]
_HEAT_CAP = 700


def _key(name, tag):
    return (str(name).lower(), str(tag).lower())


def _tempo_bucket(t_ms):
    if t_ms is None:
        return "Aucun contact"
    s = t_ms / 1000.0
    if s < 10:
        return "< 10 s"
    if s < 20:
        return "10–20 s"
    if s < 35:
        return "20–35 s"
    return "> 35 s"


def _econ_bucket(diff):
    if diff <= -4000:
        return "Fort désavantage"
    if diff <= -1000:
        return "Désavantage"
    if diff < 1000:
        return "Équilibré"
    if diff < 4000:
        return "Avantage"
    return "Fort avantage"


def _pct(a, b):
    return round(a / b * 100, 1) if b else None


def collective(roster, matches, min_members=3):
    team_names = set()
    for rid in roster or []:
        if "#" in rid:
            n, t = rid.split("#", 1)
            team_names.add(_key(n, t))

    n_matches = total_rounds = members_sum = 0
    by_map = {}
    total_deaths = traded = 0
    atk_rounds = planted = postplant_wins = 0
    def_rounds = enemy_planted = retake_wins = 0
    tempo = {}
    econ = {}
    heat = {}

    for match in matches:
        allp = match.get("players", {}).get("all_players", [])
        byteam = {}
        for p in allp:
            if _key(p.get("name", ""), p.get("tag", "")) in team_names:
                byteam.setdefault(p.get("team"), []).append(p.get("puuid"))
        our_team, our_puuids = None, []
        for color, ppl in byteam.items():
            if len(ppl) >= min_members and len(ppl) > len(our_puuids):
                our_team, our_puuids = color, ppl
        if not our_team:
            continue
        our_puuids = set(our_puuids)
        enemy_puuids = {p.get("puuid") for p in allp if p.get("team") != our_team}

        n_matches += 1
        members_sum += len(our_puuids)
        mp = match.get("metadata", {}).get("map", "?")
        rounds = match.get("rounds") or []
        attackers = splits._attacking_teams(rounds)
        kbr = splits._kills_by_round(match)
        won_match = bool((match.get("teams", {}).get(our_team.lower()) or {}).get("has_won"))
        bm = by_map.setdefault(mp, {"matches": 0, "wins": 0, "losses": 0, "rounds": 0,
                                    "rw": 0, "atk_r": 0, "atk_w": 0, "def_r": 0, "def_w": 0})
        bm["matches"] += 1
        bm["wins" if won_match else "losses"] += 1

        for i, rd in enumerate(rounds):
            total_rounds += 1
            bm["rounds"] += 1
            win = rd.get("winning_team") == our_team
            if win:
                bm["rw"] += 1
            atk = attackers[i] if i < len(attackers) else None
            side = "attack" if atk == our_team else ("defense" if atk else None)
            evs = kbr.get(i, [])
            planter = ((rd.get("plant_events") or {}).get("planted_by") or {}).get("team")

            if side == "attack":
                atk_rounds += 1
                bm["atk_r"] += 1
                if win:
                    bm["atk_w"] += 1
                if planter == our_team:
                    planted += 1
                    if win:
                        postplant_wins += 1
            elif side == "defense":
                def_rounds += 1
                bm["def_r"] += 1
                if win:
                    bm["def_w"] += 1
                if planter and planter != our_team:
                    enemy_planted += 1
                    if win:
                        retake_wins += 1

            for e in evs:
                if e.get("victim_puuid") in our_puuids:
                    total_deaths += 1
                    killer = e.get("killer_puuid")
                    td = e.get("kill_time_in_round", 0)
                    if any(x.get("victim_puuid") == killer and x.get("killer_puuid") in our_puuids
                           and 0 <= x.get("kill_time_in_round", 0) - td <= TRADE_WINDOW_MS
                           for x in evs):
                        traded += 1

            fc = min((e.get("kill_time_in_round") for e in evs
                      if e.get("kill_time_in_round") is not None), default=None)
            tb = tempo.setdefault(_tempo_bucket(fc), [0, 0])
            tb[0] += 1
            tb[1] += int(win)

            our_val = enemy_val = 0
            for ps in rd.get("player_stats", []):
                lv = ((ps.get("economy") or {}).get("loadout_value")) or 0
                if ps.get("player_puuid") in our_puuids:
                    our_val += lv
                elif ps.get("player_puuid") in enemy_puuids:
                    enemy_val += lv
            eb = econ.setdefault(_econ_bucket(our_val - enemy_val), [0, 0])
            eb[0] += 1
            eb[1] += int(win)

            hp = heat.setdefault(mp, [])
            for e in evs:
                if e.get("killer_puuid") in our_puuids:
                    loc = next((pl.get("location") for pl in (e.get("player_locations_on_kill") or [])
                                if pl.get("player_puuid") == e.get("killer_puuid")), None)
                    if loc:
                        pt = maps.to_image(mp, loc.get("x"), loc.get("y"))
                        if pt:
                            hp.append({"x": pt[0], "y": pt[1], "t": "k"})
                if e.get("victim_puuid") in our_puuids:
                    loc = e.get("victim_death_location")
                    if loc:
                        pt = maps.to_image(mp, loc.get("x"), loc.get("y"))
                        if pt:
                            hp.append({"x": pt[0], "y": pt[1], "t": "d"})

    if not n_matches:
        return {"sample": {"matches": 0}}

    wr_by_map = []
    for mp, b in sorted(by_map.items(), key=lambda kv: -kv[1]["matches"]):
        wr_by_map.append({
            "map": mp, "matches": b["matches"], "wins": b["wins"], "losses": b["losses"],
            "round_wr": _pct(b["rw"], b["rounds"]),
            "atk_wr": _pct(b["atk_w"], b["atk_r"]),
            "def_wr": _pct(b["def_w"], b["def_r"]),
        })

    heatmaps = []
    for mp, pts in heat.items():
        mi = maps.info(mp) or {}
        if not mi.get("image") or not pts:
            continue
        if len(pts) > _HEAT_CAP:
            step = len(pts) // _HEAT_CAP + 1
            pts = pts[::step]
        heatmaps.append({"map": mp, "image": mi["image"], "points": pts,
                         "kills": sum(1 for p in pts if p["t"] == "k"),
                         "deaths": sum(1 for p in pts if p["t"] == "d")})
    heatmaps.sort(key=lambda h: -(h["kills"] + h["deaths"]))

    return {
        "sample": {"matches": n_matches, "rounds": total_rounds,
                   "members_avg": round(members_sum / n_matches, 1), "min_members": min_members},
        "wr_by_map": wr_by_map,
        "trade_eff": _pct(traded, total_deaths),
        "trade_counts": {"traded": traded, "deaths": total_deaths},
        "plant": {
            "plant_pct": _pct(planted, atk_rounds), "planted": planted, "atk_rounds": atk_rounds,
            "postplant_win": _pct(postplant_wins, planted), "postplant_wins": postplant_wins,
            "retake_pct": _pct(retake_wins, enemy_planted), "retake_wins": retake_wins,
            "enemy_planted": enemy_planted, "def_rounds": def_rounds,
        },
        "tempo": [{"bucket": b, "rounds": tempo[b][0], "wr": _pct(tempo[b][1], tempo[b][0])}
                  for b in _TEMPO_ORDER if b in tempo],
        "economy": [{"bucket": b, "rounds": econ[b][0], "wr": _pct(econ[b][1], econ[b][0])}
                    for b in _ECON_ORDER if b in econ],
        "heatmaps": heatmaps,
    }
