"""Envoie la synthèse de stats à l'API Claude pour obtenir une analyse coaching."""
import json

import requests

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

SYSTEM_PROMPT = (
    "Tu es un coach Valorant francophone, direct et bienveillant. "
    "On te donne les statistiques agrégées d'un joueur sur ses dernières parties. "
    "Analyse-les : identifie 2-3 points forts, 2-3 points faibles concrets, puis "
    "donne 3 axes d'entraînement actionnables. Appuie-toi sur les chiffres "
    "(K/D, HS%, ACS, win rate par agent/carte). Sois concis et concret, pas de blabla."
)


def analyze(anthropic_api_key: str, model: str, riot_id: str, stats: dict) -> str:
    user_content = (
        f"Joueur : {riot_id}\n"
        f"Statistiques (JSON) :\n{json.dumps(stats, ensure_ascii=False, indent=2)}"
    )
    payload = {
        "model": model,
        "max_tokens": 1500,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_content}],
    }
    headers = {
        "x-api-key": anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    resp = requests.post(ANTHROPIC_URL, headers=headers, json=payload, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"Erreur API Claude {resp.status_code} : {resp.text[:400]}")
    data = resp.json()
    return "".join(
        block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
    ).strip()
