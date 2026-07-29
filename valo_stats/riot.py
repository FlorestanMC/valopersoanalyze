"""Client pour l'API tierce HenrikDev (stats Valorant non officielles).

⚠️ API non officielle (api.henrikdev.xyz), non affiliée à Riot Games.
Nécessite une clé gratuite obtenue sur le Discord HenrikDev.
Elle peut évoluer ou tomber en panne sans préavis.
"""
from __future__ import annotations

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
        self._rl_remaining = None   # requêtes restantes (en-tête)
        self._rl_reset_at = None    # epoch de réinitialisation du quota

    def _note_rate(self, headers) -> None:
        rem = headers.get("x-ratelimit-remaining")
        rst = headers.get("x-ratelimit-reset")
        try:
            if rem is not None:
                self._rl_remaining = int(rem)
        except (TypeError, ValueError):
            pass
        try:
            if rst is not None:
                val = float(rst)
                self._rl_reset_at = val if val > 1e9 else time.time() + val
        except (TypeError, ValueError):
            pass

    def pace(self) -> None:
        """Attend le minimum nécessaire selon le quota restant (pacing adaptatif)."""
        now = time.time()
        rem = self._rl_remaining
        if rem is not None:
            if rem <= 2 and self._rl_reset_at and self._rl_reset_at > now:
                time.sleep(min(self._rl_reset_at - now + 0.3, 12))
            else:
                time.sleep(0.1)  # quota sain : délai minimal
        else:
            time.sleep(0.35)     # quota inconnu : on reste modéré

    # --- requête bas niveau avec gestion 429 / erreurs -------------------
    def _get(self, path: str, *, params: dict | None = None, tries: int = 3) -> dict:
        url = f"{BASE}{path}"
        for attempt in range(tries):
            resp = self.session.get(url, params=params, timeout=25)
            if resp.status_code == 200:
                self._note_rate(resp.headers)
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

    # --- MMR : total de parties / victoires par act (sans télécharger) ---
    def get_mmr(self, game_name: str, tag_line: str) -> dict:
        """Renvoie le bloc MMR, dont `by_season` (parties + victoires par act)."""
        data = self._get(
            f"/valorant/v2/mmr/{self.region}/{game_name}/{tag_line}"
        )
        return data.get("data", {}) or {}

    # --- détail complet d'un match (contient le tableau 'kills') ---------
    def get_match_detail(self, match_id: str) -> dict:
        data = self._get(f"/valorant/v2/match/{match_id}")
        return data.get("data", {}) or {}
