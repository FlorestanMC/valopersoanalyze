"""Client pour l'API tierce HenrikDev (stats Valorant non officielles).

⚠️ API non officielle (api.henrikdev.xyz), non affiliée à Riot Games.
Nécessite une clé gratuite obtenue sur le Discord HenrikDev.
Elle peut évoluer ou tomber en panne sans préavis.
"""
import time

import requests

BASE = "https://api.henrikdev.xyz"


class RiotError(Exception):
    pass


class HenrikClient:
    def __init__(self, api_key: str, region: str):
        self.region = region
        self.session = requests.Session()
        # HenrikDev attend la clé dans l'en-tête Authorization.
        self.session.headers.update({"Authorization": api_key})

    # --- requête bas niveau avec gestion 429 / erreurs -------------------
    def _get(self, path: str, *, params: dict | None = None, tries: int = 3) -> dict:
        url = f"{BASE}{path}"
        for attempt in range(tries):
            resp = self.session.get(url, params=params, timeout=25)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429:  # rate limit
                wait = int(resp.headers.get("Retry-After", "3"))
                time.sleep(wait + 0.5)
                continue
            if resp.status_code in (401, 403):
                raise RiotError(
                    f"{resp.status_code} : clé HenrikDev invalide ou manquante. "
                    "Récupère une clé gratuite sur le Discord HenrikDev et mets-la "
                    "dans HENRIK_API_KEY (.env)."
                )
            if resp.status_code == 404:
                raise RiotError(
                    f"404 : compte introuvable ({path}). Vérifie RIOT_ID (Pseudo#TAG) "
                    "et la REGION."
                )
            raise RiotError(f"{resp.status_code} sur {path} : {resp.text[:300]}")
        raise RiotError(f"Rate limit persistant sur {path} après {tries} tentatives.")

    # --- compte : récupère le PUUID -------------------------------------
    def get_puuid(self, game_name: str, tag_line: str) -> str:
        data = self._get(f"/valorant/v1/account/{game_name}/{tag_line}")
        return data.get("data", {}).get("puuid", "")

    # --- historique détaillé (un seul appel renvoie tout, plafonné ~10) --
    def get_matches(self, game_name: str, tag_line: str, queue: str, count: int) -> list:
        params = {"size": count}
        if queue and queue != "all":
            params["mode"] = queue
        data = self._get(
            f"/valorant/v3/matches/{self.region}/{game_name}/{tag_line}",
            params=params,
        )
        return data.get("data", []) or []

    # --- liste résumée paginable (IDs + season) --------------------------
    def get_stored_matches(self, game_name: str, tag_line: str, queue: str,
                           size: int = 50) -> list:
        params = {"size": size}
        if queue and queue != "all":
            params["mode"] = queue
        data = self._get(
            f"/valorant/v1/stored-matches/{self.region}/{game_name}/{tag_line}",
            params=params,
        )
        return data.get("data", []) or []

    # --- détail complet d'un match (contient le tableau 'kills') ---------
    def get_match_detail(self, match_id: str) -> dict:
        data = self._get(f"/valorant/v2/match/{match_id}")
        return data.get("data", {}) or {}
