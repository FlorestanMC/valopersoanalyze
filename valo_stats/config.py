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

    @property
    def game_name(self) -> str:
        return self.riot_id.split("#", 1)[0]

    @property
    def tag_line(self) -> str:
        return self.riot_id.split("#", 1)[1]


def load_config() -> Config:
    def req(name: str) -> str:
        val = os.getenv(name, "").strip()
        if not val:
            raise SystemExit(f"[config] Variable manquante dans .env : {name}")
        return val

    region = os.getenv("REGION", os.getenv("PLATFORM", "eu")).strip().lower()
    if region not in REGIONS:
        raise SystemExit(
            f"[config] REGION invalide : {region!r}. "
            f"Valeurs possibles : {', '.join(sorted(REGIONS))}"
        )

    riot_id = req("RIOT_ID")
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
    )
