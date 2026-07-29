"""Chemins de données, configurables pour l'hébergement.

En local : dossier du projet. En prod : pointe `VALO_DATA_DIR` vers un volume
persistant (ou utilise une base Postgres via DATABASE_URL, voir storage.py).
"""
import os

_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))

DATA_DIR = os.environ.get("VALO_DATA_DIR", _PROJECT_ROOT)
CACHE_DIR = os.path.join(DATA_DIR, ".cache")      # anciens caches fichiers (migration)
USERDATA_DIR = os.path.join(DATA_DIR, "userdata")  # image de fond (optionnelle)
DB_PATH = os.path.join(DATA_DIR, "valo.db")        # base SQLite locale
