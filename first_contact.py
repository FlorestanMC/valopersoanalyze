#!/usr/bin/env python3
"""Rapport « First Contact » sur tout l'act courant (via API HenrikDev).

Calcule tes First Kills / First Deaths et ton First Contact Success (FCS)
sur l'ensemble de tes parties compétitives de l'act en cours.

Usage : python first_contact.py
"""
import sys
import time
from datetime import datetime

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

from valo_stats.config import load_config
from valo_stats.riot import HenrikClient, RiotError
from valo_stats import first_contact


def main() -> int:
    cfg = load_config()
    client = HenrikClient(cfg.henrik_api_key, cfg.region)

    print(f"→ Compte {cfg.riot_id} ({cfg.region}) — liste des parties…")
    try:
        stored = client.get_stored_matches(cfg.game_name, cfg.tag_line, "competitive", size=50)
    except RiotError as e:
        print(f"[erreur] {e}", file=sys.stderr)
        return 1
    if not stored:
        print("Aucune partie compétitive trouvée.")
        return 0

    # L'act courant = celui de la partie la plus récente.
    current_act = stored[0].get("meta", {}).get("season", {}).get("id")
    act_short = stored[0].get("meta", {}).get("season", {}).get("short", "?")
    ids = [m["meta"]["id"] for m in stored
           if m.get("meta", {}).get("season", {}).get("id") == current_act]
    print(f"  Act courant : {act_short} — {len(ids)} partie(s) compétitive(s).")

    print(f"→ Téléchargement du détail de {len(ids)} match(s) (peut prendre ~1-2 min)…")
    matches = []
    for i, mid in enumerate(ids, 1):
        try:
            matches.append(client.get_match_detail(mid))
            print(f"  {i}/{len(ids)}")
        except RiotError as e:
            print(f"  match {mid} ignoré : {e}")
        time.sleep(2.0)  # respecte le quota gratuit HenrikDev (~30 req/min)

    fc = first_contact.compute(matches, _puuid(matches, cfg))
    report = fmt_report(cfg.riot_id, act_short, fc)

    out = f"first_contact_{cfg.game_name}_{datetime.now():%Y%m%d_%H%M}.md"
    with open(out, "w", encoding="utf-8") as f:
        f.write(report)

    print("\n" + "=" * 60 + "\n")
    print(report)
    print("\n" + "=" * 60)
    print(f"\n✓ Rapport enregistré : {out}")
    return 0


def _puuid(matches, cfg) -> str:
    """Récupère le PUUID du joueur à partir du 1er match (évite un appel de plus)."""
    for m in matches:
        for p in m.get("players", {}).get("all_players", []):
            n = p.get("name", "")
            t = p.get("tag", "")
            if n.lower() == cfg.game_name.lower() and t.lower() == cfg.tag_line.lower():
                return p.get("puuid", "")
    return ""


def fmt_report(riot_id: str, act: str, fc: dict) -> str:
    if fc["games"] == 0:
        return f"# First Contact — {riot_id}\n\nAucune donnée exploitable.\n"

    def pct(v):
        return f"{v} %" if v is not None else "n/d"

    lines = [
        f"# First Contact — {riot_id}",
        f"_Act {act} • {fc['games']} parties • {fc['rounds']} rounds • "
        f"généré le {datetime.now():%Y-%m-%d %H:%M}_\n",
        "## Vue d'ensemble",
        f"- **First Kills** : {fc['fk']}",
        f"- **First Deaths** : {fc['fd']}",
        f"- **Duels d'ouverture** : {fc['duels']} ({fc['fk']} gagnés / {fc['fd']} perdus)",
        f"- **First Contact Success (FCS)** : **{pct(fc['fcs'])}**",
        f"- FK par round : {pct(fc['fk_per_round'])}  |  FD par round : {pct(fc['fd_per_round'])}",
        "\n## Par agent",
        "| Agent | Parties | FK | FD | Duels | FCS |",
        "|-------|--------:|---:|---:|------:|----:|",
    ]
    for agent, a in fc["agents"].items():
        lines.append(
            f"| {agent} | {a['games']} | {a['fk']} | {a['fd']} | {a['duels']} | {pct(a['fcs'])} |"
        )
    if fc.get("weapons"):
        lines.append("\n## Par arme")
        lines.append("| Arme | FK (avec) | FD (subies) | Duels |")
        lines.append("|------|----------:|------------:|------:|")
        for w in fc["weapons"]:
            lines.append(f"| {w['name']} | {w['fk']} | {w['fd']} | {w['duels']} |")
    lines.append(
        "\n_FCS = First Kills / (First Kills + First Deaths) : proportion des duels "
        "d'ouverture gagnés. Un FCS > 50 % signifie que tu gagnes plus de premiers "
        "contacts que tu n'en perds._"
    )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
