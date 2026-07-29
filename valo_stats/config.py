"""Chargement de la configuration depuis le fichier .env."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

# Régions supportées par l'API HenrikDev.
REGIONS = {"na", "eu", "ap", "kr", "latam", "br"}


@dataclass
class Config:
    henrik_api_key: str
    anthropic_api_key: str
    riot_id: str          # "Pseudo#TAG"
    region: str           # na / eu / ap / kr / latam / br
    queue: str            # competitive / unrated / spikerush / deathmatch / all
    count: int            # nombre de parties à analyser
    anthropic_model: str
    deepseek_api_key: str = ""     # facultatif : analyse d'équipe (onglet Team)
    deepseek_model: str = "deepseek-chat"

    @property
    def game_name(self) -> str:
        return self.riot_id.split("#", 1)[0]

    @property
    def tag_line(self) -> str:
        return self.riot_id.split("#", 1)[1]


def _target_override() -> dict:
    """Compte ciblé défini dans les paramètres de l'app (userdata/settings.json)."""
    try:
        from . import settings
        s = settings.load()
    except Exception:  # noqa: BLE001
        return {}
    out = {}
    rid = (s.get("riot_id") or "").strip()
    reg = (s.get("region") or "").strip().lower()
    if rid and "#" in rid:
        out["riot_id"] = rid
    if reg in REGIONS:
        out["region"] = reg
    return out


def load_config() -> Config:
    def req(name: str) -> str:
        val = os.getenv(name, "").strip()
        if not val:
            raise SystemExit(f"[config] Variable manquante dans .env : {name}")
        return val

    region = os.getenv("REGION", os.getenv("PLATFORM", "eu")).strip().lower()
    riot_id = req("RIOT_ID")

    # Surcharge éventuelle du compte ciblé via les paramètres de l'app.
    ov = _target_override()
    region = ov.get("region", region)
    riot_id = ov.get("riot_id", riot_id)

    if region not in REGIONS:
        raise SystemExit(
            f"[config] REGION invalide : {region!r}. "
            f"Valeurs possibles : {', '.join(sorted(REGIONS))}"
        )
    if "#" not in riot_id:
        raise SystemExit("[config] RIOT_ID doit avoir la forme Pseudo#TAG")

    return Config(
        henrik_api_key=req("HENRIK_API_KEY"),
        anthropic_api_key=req("ANTHROPIC_API_KEY"),
        riot_id=riot_id,
        region=region,
        queue=os.getenv("QUEUE", "competitive").strip().lower(),
        count=int(os.getenv("COUNT", "10")),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5").strip(),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", "").strip(),
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip(),
    )
