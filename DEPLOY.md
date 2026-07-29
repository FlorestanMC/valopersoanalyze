# Héberger valo-stats en ligne (perso, protégé par mot de passe)

L'app est prête pour l'hébergement avec **données persistantes** : le cache des
matchs et les réglages sont en base — **SQLite** (défaut, un simple fichier
`valo.db`) ou **Postgres** (via `DATABASE_URL`). Plus besoin de tout
re-télécharger.

En place :
- **Mot de passe** d'accès via `APP_PASSWORD` (auth HTTP basique).
- Point d'entrée **Passenger** (`passenger_wsgi.py`) pour cPanel/o2switch.
- Point d'entrée **conteneur** (`Dockerfile`, `run_prod.py`, `wsgi.py`) pour Fly/Render.
- Migration automatique des anciens fichiers `.cache/` au premier démarrage.

> ⚠️ Ne mets JAMAIS tes clés dans le dépôt. Elles se configurent chez
> l'hébergeur (variables d'environnement). `.env` reste local.

---

## Option principale — o2switch (cPanel « Setup Python App »)

Hébergement mutualisé français, toujours allumé, disque persistant (SQLite marche
direct). On passe par Passenger via cPanel, **sans ligne de commande obligatoire**.

### 1. Envoyer le code sur o2switch

Via **cPanel → Gestionnaire de fichiers** (ou FTP), crée un dossier hors du web,
p.ex. `~/valo-stats`, et **uploade tout le projet SAUF** : `.env`, `.cache/`,
`userdata/`, `valo.db*`, `.git/`. (Un zip du projet + « Extraire » est le plus simple.)

### 2. Créer l'application Python

cPanel → **Setup Python App** (ou « Configurer une application Python ») →
**Créer une application** :
- **Version de Python** : **3.10 ou plus** (3.11 conseillé — le code utilise la
  syntaxe `dict | None` qui exige 3.10+).
- **Racine de l'application** : `valo-stats` (le dossier uploadé).
- **URL de l'application** : le (sous-)domaine voulu.
- **Fichier de démarrage** : `passenger_wsgi.py`
- **Point d'entrée** : `application`
- Clique **Créer**.

### 3. Variables d'environnement (les secrets)

Sur la page de l'app, section **Variables d'environnement**, ajoute :

| Nom | Valeur |
|-----|--------|
| `APP_PASSWORD` | un mot de passe d'accès au site |
| `HENRIK_API_KEY` | ta clé HenrikDev |
| `RIOT_ID` | `Mata#AAAAA` |
| `REGION` | `eu` |
| `DEEPSEEK_API_KEY` | ta clé DeepSeek (facultatif) |
| `ANTHROPIC_API_KEY` | (facultatif, non requis pour le web) |

### 4. Installer les dépendances

Toujours sur la page de l'app : le champ **Configuration files** → indique
`requirements.txt`, puis **Run Pip Install** (bouton). (Pas besoin de
`requirements-prod.txt` : Passenger sert l'app, la base est en SQLite.)

Si tu préfères le terminal : « Enter to the virtual environment » copie la
commande `source .../activate`, puis `pip install -r requirements.txt`.

### 5. Démarrer / redémarrer

Clique **Restart**. Ouvre l'URL → le navigateur demande le **mot de passe**
(`APP_PASSWORD`). Le site est vide au début : clique **Mettre à jour** une fois
pour remplir la base (`valo.db` se crée dans le dossier de l'app, persistant).

### Notes o2switch
- Aucune base externe à créer : SQLite suffit (disque persistant).
- Vérifie que les **appels HTTPS sortants** sont autorisés (HenrikDev / DeepSeek) —
  en général oui ; sinon, ouvre un ticket au support o2switch.
- Après chaque mise à jour du code, réuploade les fichiers puis **Restart** l'app.

---

## Alternative — Fly.io / Render / Railway (conteneur Docker)

Si un jour tu peux utiliser Docker/CLI. Le `Dockerfile` installe aussi
`requirements-prod.txt` (waitress + Postgres).

### Fly.io

```bash
fly launch --no-deploy
fly volumes create valo_data --size 1 --region cdg
fly secrets set APP_PASSWORD="..." HENRIK_API_KEY="..." RIOT_ID="Mata#AAAAA" REGION="eu" DEEPSEEK_API_KEY="..."
fly deploy --ha=false
```

Le `fly.toml` monte le volume `valo_data` sur `/data` (port 8080, scale-to-zero).
Variante sans volume : attache un Postgres (`fly postgres create/attach`), l'app
bascule dessus via `DATABASE_URL`.

### Render / Railway

Service **Web** de type **Docker** pointant sur ce dépôt. Variables d'env :
`APP_PASSWORD`, `HENRIK_API_KEY`, `RIOT_ID`, `REGION`, `DEEPSEEK_API_KEY`.
Persistance : un **Disk/Volume** monté sur `/data`, ou un **Postgres** géré
(définit `DATABASE_URL`).

---

## Rappels sécurité / coûts
- Le site sert **ton** compte : garde-le **privé** (mot de passe obligatoire en ligne).
- Les analyses IA (Claude / DeepSeek) sont **payantes** sur **tes** clés — le mot
  de passe évite que d'autres les déclenchent.
- L'API HenrikDev a un quota : le pacing adaptatif limite la casse, mais garde le
  site privé.
