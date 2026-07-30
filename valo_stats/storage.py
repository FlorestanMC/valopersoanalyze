"""Stockage clé-valeur persistant (cache des matchs, réglages, marqueurs).

- En local (défaut) : SQLite dans `VALO_DATA_DIR/valo.db` — zéro configuration.
- En prod : Postgres si `DATABASE_URL` est défini (idéal PaaS, survit aux
  redéploiements sans volume disque).

Chaque valeur est un JSON, rangé par (namespace, clé). Un horodatage `ts`
permet des caches à durée de vie (TTL).
"""
import json
import os
import threading
import time

from . import paths

_URL = os.environ.get("DATABASE_URL", "").strip()
_IS_PG = _URL.startswith(("postgres://", "postgresql://"))
_PH = "%s" if _IS_PG else "?"

_lock = threading.Lock()
_init_done = False

if _IS_PG:
    import psycopg  # noqa: E402  (import tardif : requis seulement en prod)

    def _connect():
        return psycopg.connect(_URL, autocommit=True)
else:
    import sqlite3  # noqa: E402

    def _connect():
        os.makedirs(paths.DATA_DIR, exist_ok=True)
        conn = sqlite3.connect(paths.DB_PATH, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn


def _init():
    global _init_done
    if _init_done:
        return
    with _lock:
        if _init_done:
            return
        conn = _connect()
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS kv ("
                "ns TEXT NOT NULL, k TEXT NOT NULL, v TEXT, ts DOUBLE PRECISION, "
                "PRIMARY KEY (ns, k))"
            )
            if not _IS_PG:
                conn.commit()
        finally:
            conn.close()
        _init_done = True


def _run(sql, params=(), fetch=None):
    _init()
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        out = cur.fetchone() if fetch == "one" else (cur.fetchall() if fetch == "all" else None)
        if not _IS_PG:
            conn.commit()
        return out
    finally:
        conn.close()


# --- API -------------------------------------------------------------------
def get(ns: str, key: str):
    """Valeur JSON, ou None si absente."""
    row = _run(f"SELECT v FROM kv WHERE ns={_PH} AND k={_PH}", (ns, key), fetch="one")
    if not row or row[0] is None:
        return None
    try:
        return json.loads(row[0])
    except (ValueError, TypeError):
        return None


def get_with_ts(ns: str, key: str):
    """(valeur, horodatage) ou (None, None). Pour les caches à TTL."""
    row = _run(f"SELECT v, ts FROM kv WHERE ns={_PH} AND k={_PH}", (ns, key), fetch="one")
    if not row or row[0] is None:
        return None, None
    try:
        return json.loads(row[0]), row[1]
    except (ValueError, TypeError):
        return None, None


def set(ns: str, key: str, value) -> None:  # noqa: A001 (nom clair pour un KV)
    v = json.dumps(value, ensure_ascii=False)
    _run(
        f"INSERT INTO kv (ns, k, v, ts) VALUES ({_PH}, {_PH}, {_PH}, {_PH}) "
        f"ON CONFLICT (ns, k) DO UPDATE SET v=excluded.v, ts=excluded.ts",
        (ns, key, v, time.time()),
    )


def exists(ns: str, key: str) -> bool:
    row = _run(f"SELECT 1 FROM kv WHERE ns={_PH} AND k={_PH}", (ns, key), fetch="one")
    return row is not None


def delete(ns: str, key: str) -> None:
    _run(f"DELETE FROM kv WHERE ns={_PH} AND k={_PH}", (ns, key))


def count(ns: str) -> int:
    row = _run(f"SELECT COUNT(*) FROM kv WHERE ns={_PH}", (ns,), fetch="one")
    return int(row[0]) if row else 0


def values(ns: str):
    """Toutes les valeurs JSON d'un namespace (ex. tous les matchs en cache)."""
    rows = _run(f"SELECT v FROM kv WHERE ns={_PH}", (ns,), fetch="all") or []
    out = []
    for (v,) in rows:
        try:
            out.append(json.loads(v))
        except (ValueError, TypeError):
            continue
    return out


def backend() -> str:
    return "postgres" if _IS_PG else "sqlite"
