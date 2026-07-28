#!/usr/bin/env python3
"""Récupérateur de stats Valorant (via API HenrikDev) + analyse par Claude.

⚠️ Utilise l'API tierce non officielle HenrikDev (non affiliée à Riot Games).
Usage : configurer .env puis lancer  python main.py
"""
import sys
from datetime import datetime

# Utilise le magasin de certificats du système (Windows/macOS) plutôt que le
# bundle certifi : indispensable derrière un proxy d'inspection SSL d'entreprise.
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

from valo_stats.config import load_config
from valo_stats.riot import HenrikClient, RiotError
from valo_stats.aggregate import aggregate
from valo_stats import coach


def fmt_report(riot_id: str, s: dict, analysis: str) -> str:
    if s.get("games", 0) == 0:
        return f"# {riot_id}\n\nAucune partie trouvée pour la file demandée.\n"

    lines = [f"# Rapport Valorant — {riot_id}",
             f"_Généré le {datetime.now():%Y-%m-%d %H:%M} • {s['games']} parties_\n",
             "## Vue d'ensemble",
             f"- Win rate : **{s['win_rate']} %**",
             f"- K/D : **{s['kd']}**  |  KDA : **{s['kda']}**",
             f"- Moyennes : {s['avg_kills']} K / {s['avg_deaths']} D / {s['avg_assists']} A par partie",
             f"- ACS moyen : **{s['avg_acs']}**",
             f"- HS% moyen : **{s['avg_hs_pct']} %**" if s['avg_hs_pct'] is not None else "- HS% : n/d",
             "\n## Par agent"]
    for agent, a in s["agents"].items():
        lines.append(f"- {agent} : {a['games']} parties, {a['win_rate']} % WR, K/D {a['kd']}")
    lines.append("\n## Par carte")
    for m, mm in s["maps"].items():
        lines.append(f"- {m} : {mm['games']} parties, {mm['win_rate']} % WR")
    lines.append("\n## Dernières parties")
    for r in s["recent"]:
        res = "V" if r["won"] else "D"
        hs = f", HS {r['hs']}%" if r["hs"] is not None else ""
        lines.append(f"- [{res}] {r['agent']} @ {r['map']} — {r['kda']}, ACS {r['acs']}{hs}")
    lines.append("\n## Analyse coaching (Claude)\n")
    lines.append(analysis)
    return "\n".join(lines)


def main() -> int:
    cfg = load_config()
    client = HenrikClient(cfg.henrik_api_key, cfg.region)

    print(f"→ Recherche du compte {cfg.riot_id} ({cfg.region}) via HenrikDev…")
    try:
        puuid = client.get_puuid(cfg.game_name, cfg.tag_line)
    except RiotError as e:
        print(f"[erreur account] {e}", file=sys.stderr)
        return 1
    if not puuid:
        print("[erreur account] PUUID introuvable pour ce Riot ID / cette région.", file=sys.stderr)
        return 1
    print(f"  PUUID : {puuid}")

    print(f"→ Récupération des {cfg.count} dernières parties (file : {cfg.queue})…")
    try:
        matches = client.get_matches(cfg.game_name, cfg.tag_line, cfg.queue, cfg.count)
    except RiotError as e:
        print(f"[erreur matchs] {e}", file=sys.stderr)
        return 1

    if not matches:
        print("Aucune partie trouvée. Essaie QUEUE=all dans .env.")
        return 0
    print(f"  {len(matches)} partie(s) récupérée(s).")

    stats = aggregate(matches, puuid, cfg.queue)

    print("→ Analyse par Claude…")
    try:
        analysis = coach.analyze(cfg.anthropic_api_key, cfg.anthropic_model, cfg.riot_id, stats)
    except Exception as e:  # noqa: BLE001
        analysis = f"(Analyse Claude indisponible : {e})"

    report = fmt_report(cfg.riot_id, stats, analysis)
    out = f"rapport_{cfg.game_name}_{datetime.now():%Y%m%d_%H%M}.md"
    with open(out, "w", encoding="utf-8") as f:
        f.write(report)

    print("\n" + "=" * 60 + "\n")
    print(report)
    print("\n" + "=" * 60)
    print(f"\n✓ Rapport enregistré : {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
