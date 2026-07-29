#!/usr/bin/env python3
"""Serveur de production (waitress) pour l'hébergement en ligne.

Configuration par variables d'environnement :
- PORT               : port d'écoute (fourni par l'hébergeur).
- APP_PASSWORD       : mot de passe d'accès (auth HTTP basique). FORTEMENT recommandé.
- DATABASE_URL       : Postgres (sinon SQLite dans VALO_DATA_DIR/valo.db).
- VALO_DATA_DIR      : dossier de données persistant (volume).
- HENRIK_API_KEY / ANTHROPIC_API_KEY / DEEPSEEK_API_KEY / RIOT_ID / REGION.
"""
import os

from waitress import serve

from server import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8770"))
    print(f"→ Valo Stats (prod, waitress) sur 0.0.0.0:{port}")
    serve(app, host="0.0.0.0", port=port, threads=8)
