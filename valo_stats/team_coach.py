"""Analyse d'équipe via l'API DeepSeek (compatible OpenAI /chat/completions).

Reçoit les stats compactes de l'effectif (onglet Team) et renvoie une analyse
coaching en français. Endpoint et clé configurés dans .env (DEEPSEEK_API_KEY).
"""
import json

import requests

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

SYSTEM_PROMPT = (
    "Tu es un coach Valorant francophone, direct et concret, qui analyse une équipe "
    "(5 titulaires + éventuellement un coach/remplaçant). On te donne les stats "
    "agrégées de chaque joueur sur l'act en cours. Produis une analyse d'équipe :\n"
    "1. Un état des lieux global (niveau, régularité, équilibre de l'effectif).\n"
    "2. Les forces collectives (2-3 points), en citant des joueurs et des chiffres.\n"
    "3. Les faiblesses / risques (2-3 points), en citant des joueurs et des chiffres.\n"
    "4. Des recommandations de composition et 3 axes de travail actionnables.\n"
    "Appuie-toi sur les chiffres (WR, K/D, ACS, KAST, HS%, agents joués). "
    "Sois synthétique et sans blabla. Réponds en Markdown."
)


def analyze(api_key: str, model: str, team_name: str, players: list) -> str:
    """Renvoie l'analyse textuelle (Markdown). Lève RuntimeError si l'API échoue."""
    if not api_key:
        raise RuntimeError("Clé DeepSeek absente : renseigne DEEPSEEK_API_KEY dans .env.")

    user_content = (
        f"Équipe : {team_name or 'Sans nom'}\n"
        f"Effectif et statistiques (JSON) :\n"
        f"{json.dumps(players, ensure_ascii=False, indent=2)}"
    )
    payload = {
        "model": model or "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "max_tokens": 1800,
        "temperature": 0.7,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    resp = requests.post(DEEPSEEK_URL, headers=headers, json=payload, timeout=90)
    if resp.status_code != 200:
        raise RuntimeError(f"Erreur API DeepSeek {resp.status_code} : {resp.text[:400]}")
    data = resp.json()
    try:
        return (data["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError):
        raise RuntimeError(f"Réponse DeepSeek inattendue : {str(data)[:400]}")
