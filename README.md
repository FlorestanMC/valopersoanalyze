# valo-stats

Dashboard de statistiques **Valorant** en local : récupère tes parties (Ranked /
Premier), calcule des stats avancées (K/D, ACS, **KAST**, round win/loss,
**First Contact**, stats par arme, précision) et les affiche dans une interface
web au thème « Aurora Tactical », avec un **fond personnalisable** et une **analyse
coaching** générée par l'API Claude.

> ⚠️ Projet **personnel / éducatif**. Les données viennent de l'API tierce non
> officielle **HenrikDev** (non affiliée à Riot Games). Les visuels d'agents et
> d'armes appartiennent à © Riot Games (servis par valorant-api.com). Ce projet
> n'est pas approuvé par Riot Games.

## Fonctionnalités

- **4 onglets** : Vue d'ensemble · Agents · Armes · First Contact
- **Sélecteur de file** : Ranked ↔ Premier
- **KAST**, **round win/loss**, **First Contact Success (FCS)**, stats par arme,
  répartition de précision (tête / corps / jambes)
- **Fond d'écran personnalisable** (upload + assombrissement réglable) via ⚙
- **Bouton « Mettre à jour »** : récupère les nouvelles parties (cache incrémental)
- **Analyse coaching** par Claude (si crédit Anthropic disponible)
- 4 points d'entrée : `main.py` (texte), `first_contact.py`, `dashboard.py`
  (HTML statique), `server.py` (app web complète)

## Prérequis

- Python 3.10+
- Une **clé HenrikDev gratuite** — https://discord.gg/henrikdev (salon de génération de clé)
- (Optionnel) une **clé API Anthropic** — https://console.anthropic.com/ pour l'analyse coaching

## Installation

```bash
git clone <url-de-ton-repo>.git
cd valo-stats
pip install -r requirements.txt
cp .env.example .env        # Windows PowerShell : copy .env.example .env
```

Édite ensuite `.env` avec tes clés, ton Riot ID (`Pseudo#TAG`) et ta région.

## Lancement

```bash
python server.py
```

Ouvre http://127.0.0.1:8770 (le navigateur s'ouvre automatiquement). C'est
l'expérience complète : onglets, sélecteur de file, bouton « Mettre à jour »,
personnalisation du fond.

Autres commandes :

```bash
python dashboard.py     # génère un dashboard_<pseudo>.html autonome
python first_contact.py # rapport texte First Kill / First Death / FCS
python main.py          # rapport texte des dernières parties + analyse Claude
```

Le détail des matchs est mis en cache dans `.cache/` (ignoré par git) : après le
premier téléchargement, tout est quasi instantané.

## Personnaliser le fond

Dans `server.py`, clique sur **⚙** en haut à droite : choisis une image, règle
l'assombrissement, applique. L'image et les réglages sont stockés dans `userdata/`
(local, ignoré par git).

## Configuration (.env)

| Variable            | Rôle                                                          |
|---------------------|---------------------------------------------------------------|
| `HENRIK_API_KEY`    | Clé gratuite HenrikDev (Discord)                             |
| `RIOT_ID`           | Identifiant complet `Pseudo#TAG`                             |
| `REGION`            | `na` / `eu` / `ap` / `kr` / `latam` / `br`                   |
| `QUEUE`             | File par défaut : `competitive` ou `premier`                |
| `COUNT`             | Nombre de parties pour `main.py`                             |
| `ANTHROPIC_API_KEY` | Clé API Claude (facultatif)                                 |
| `ANTHROPIC_MODEL`   | `claude-sonnet-5`, `claude-opus-4-8`, `claude-haiku-4-5-20251001` |

## Structure

```
valo-stats/
├── main.py                 # rapport texte
├── first_contact.py        # rapport First Contact
├── dashboard.py            # génère le dashboard HTML statique
├── server.py               # app web (Flask) : onglets, fond, mise à jour
├── valo_stats/
│   ├── config.py           # chargement .env + régions
│   ├── riot.py             # client API HenrikDev
│   ├── aggregate.py        # stats générales (K/D, ACS, rounds, précision…)
│   ├── first_contact.py    # First Kill / First Death / FCS
│   ├── advanced.py         # KAST + stats par arme
│   ├── pipeline.py         # récupération (cache) + assemblage des données
│   ├── dashboard.py        # rendu HTML « Aurora Tactical »
│   ├── settings.py         # réglages persistants (fond, assombrissement)
│   └── coach.py            # appel à l'API Claude
├── requirements.txt
├── .env.example
├── .gitignore
├── .cache/                 # cache des matchs (auto, ignoré par git)
└── userdata/               # fond + réglages perso (auto, ignoré par git)
```

## Mettre sur GitHub

Le dépôt est déjà initialisé avec un premier commit. Pour le pousser :

```bash
git remote add origin https://github.com/<ton-user>/valo-stats.git
git branch -M main
git push -u origin main
```

Le `.gitignore` exclut déjà `.env`, `userdata/` et `.cache/` : **tes clés et tes
données personnelles ne seront jamais poussées**.

## Notes

- `KAST` = % de rounds où tu fais un Kill, un Assist, Survis, ou es Traded.
- `FCS` (First Contact Success) = First Kills / (First Kills + First Deaths).
- HenrikDev étant non officielle, l'API peut évoluer ou tomber sans préavis.
