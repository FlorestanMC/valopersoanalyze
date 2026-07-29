"""Point d'entrée WSGI (gunicorn/waitress) : expose l'app Flask.

Exemple : waitress-serve --host=0.0.0.0 --port=$PORT wsgi:app
"""
from server import app  # noqa: F401
