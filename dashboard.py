#!/usr/bin/env python3
"""Génère un dashboard HTML « liquid glass » des stats Valorant de l'act courant.

Récupère toutes les parties de l'act (cache-aware), calcule vue d'ensemble,
First Contact, KAST et stats par arme, puis écrit dashboard_<pseudo>.html.

Usage : python dashboard.py
"""
import os
import sys

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

from valo_stats.config import load_config
from valo_stats.riot import HenrikClient, RiotError
from valo_stats import pipeline, dashboard, settings


def main() -> int:
    cfg = load_config()
    client = HenrikClient(cfg.henrik_api_key, cfg.region)

    print(f"→ Compte {cfg.riot_id} ({cfg.region}) — génération du dashboard…")
    try:
        data, summary = pipeline.build_data(client, cfg, allow_fetch=True,
                                            want_analysis=True, log=print)
    except RiotError as e:
        print(f"[erreur] {e}", file=sys.stderr)
        return 1

    if data is None:
        print("Aucune partie exploitable.")
        return 0

    print(f"  {summary['total']} matchs ({summary['fetched']} téléchargés, "
          f"{summary['missing']} manquants).")

    s = settings.load()
    bp = settings.bg_path()
    rel = os.path.relpath(bp, os.path.dirname(__file__)).replace("\\", "/") if bp else None
    data["background"] = {"url": rel, "dim": s.get("dim", 55)}

    html = dashboard.render(data)
    out = os.path.join(os.path.dirname(__file__), f"dashboard_{cfg.game_name}.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✓ Dashboard généré : {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
