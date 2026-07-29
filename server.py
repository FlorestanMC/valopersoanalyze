#!/usr/bin/env python3
"""Petit serveur local pour le dashboard Valorant, avec bouton « Mettre à jour ».

- GET  /            -> rend le dashboard (rapide : lit le cache, ne télécharge rien)
- POST /api/refresh -> récupère les nouvelles parties de l'act (met à jour le cache)

Usage : python server.py   puis ouvrir http://127.0.0.1:8770
"""
import os
import sys
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

try:
    from flask import Flask, jsonify, request, send_file, abort
except ImportError:
    sys.exit("Flask manquant. Installe-le : pip install flask  (ou pip install -r requirements.txt)")

from valo_stats.config import load_config
from valo_stats.riot import HenrikClient, RiotError
from valo_stats import pipeline, dashboard, settings, team_coach, storage

# Migration one-shot des anciens caches fichiers vers la base (sans effet si déjà fait).
try:
    pipeline.migrate_file_cache(log=lambda m: print(m))
except Exception as _e:  # noqa: BLE001
    print(f"[migration] ignorée : {_e}")

PORT = 8770
QUEUES = {"competitive", "premier"}
REGIONS = {"na", "eu", "ap", "kr", "latam", "br"}

app = Flask(__name__)

# Protection par mot de passe (auth HTTP basique) : active seulement si
# APP_PASSWORD est défini (donc jamais en local par défaut, requis en ligne).
APP_PASSWORD = os.environ.get("APP_PASSWORD", "").strip()


@app.before_request
def _require_password():
    if not APP_PASSWORD:
        return None
    auth = request.authorization
    if not auth or auth.password != APP_PASSWORD:
        return ("Accès protégé.", 401,
                {"WWW-Authenticate": 'Basic realm="Valo Stats"'})
    return None


def _ctx():
    """Config + client reconstruits à chaque requête (le compte ciblé peut changer)."""
    cfg = load_config()
    return cfg, HenrikClient(cfg.henrik_api_key, cfg.region)


def _queue():
    q = (request.args.get("queue") or "competitive").lower()
    return q if q in QUEUES else "competitive"


# Cache mémoire court (TTL) pour les checks « nouvelles parties » : évite de
# retaper l'API HenrikDev à chaque ouverture d'onglet.
_UPD_TTL = 60
_upd_cache = {}


def _cached_updates(key, producer):
    now = time.time()
    hit = _upd_cache.get(key)
    if hit and now - hit[0] < _UPD_TTL:
        return hit[1]
    val = producer()
    _upd_cache[key] = (now, val)
    return val


def _invalidate_updates():
    _upd_cache.clear()


def _empty_page(queue):
    base = request.script_root
    label = "Premier" if queue == "premier" else "Ranked"
    other = "competitive" if queue == "premier" else "premier"
    other_label = "Ranked" if queue == "premier" else "Premier"
    return f"""<!doctype html><meta charset="utf-8">
<title>Valo Stats</title>
<body style="font-family:-apple-system,Inter,Segoe UI,sans-serif;background:#07060f;
 color:#F2F0EA;min-height:100vh;margin:0;display:grid;place-items:center;text-align:center">
<div style="max-width:460px;padding:30px">
  <div style="font-weight:900;letter-spacing:.2em;color:#FF4655;font-size:12px">◆ VALO STATS</div>
  <h2 style="font-size:26px;margin:12px 0">Aucune partie {label} en cache</h2>
  <p style="color:#98a2b3;line-height:1.5">Clique pour récupérer tes parties {label}
   (première fois : peut prendre 1-2 min), ou reviens en {other_label}.</p>
  <div style="display:flex;gap:10px;justify-content:center;margin-top:22px">
    <button id="load" style="font:inherit;font-weight:800;cursor:pointer;padding:12px 20px;
     border-radius:12px;border:0;color:#fff;background:linear-gradient(135deg,#FF4655,#ff2d8e)">
     ↻ Charger les parties {label}</button>
    <a href="{base}/?queue={other}" style="font:inherit;font-weight:800;padding:12px 20px;border-radius:12px;
     border:1px solid rgba(255,255,255,.15);color:#F2F0EA;text-decoration:none">{other_label}</a>
  </div>
</div>
<script>
document.getElementById('load').addEventListener('click',function(){{
  var b=this;b.disabled=true;b.textContent='⏳ Téléchargement...';
  fetch('{base}/api/refresh?queue={queue}',{{method:'POST'}}).then(function(r){{return r.json()}})
   .then(function(){{location.href='{base}/?queue={queue}'}})
   .catch(function(){{b.textContent='⚠ Erreur';}});
}});
</script></body>"""


def _with_background(data):
    s = settings.load()
    bp = settings.bg_path()
    url = f"{request.script_root}/user-bg?v={int(os.path.getmtime(bp))}" if bp else None
    data["background"] = {"url": url, "dim": s.get("dim", 55)}
    return data


@app.get("/")
def index():
    # Chargement rapide : on n'utilise que le cache (pas de téléchargement).
    q = _queue()
    cfg, client = _ctx()
    data, _ = pipeline.build_data(client, cfg, queue=q,
                                  allow_fetch=False, want_analysis=False)
    if data is None:
        return _empty_page(q)
    # Parties fraîchement téléchargées à la dernière MAJ (surlignées une fois).
    data["new_ids"] = list(pipeline.pop_new_ids())
    data["base"] = request.script_root  # préfixe de montage (ex. /stats)
    return dashboard.render(_with_background(data))


@app.get("/user-bg")
def user_bg():
    bp = settings.bg_path()
    if not bp:
        abort(404)
    return send_file(bp)


@app.post("/api/background")
def set_background():
    f = request.files.get("bg")
    if not f or not f.filename:
        return jsonify(error="aucun fichier"), 400
    try:
        settings.save_background(f, f.filename)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    return jsonify(ok=True)


@app.post("/api/background/reset")
def reset_background():
    settings.clear_background()
    return jsonify(ok=True)


@app.post("/api/settings")
def update_settings():
    data = request.get_json(silent=True) or {}
    if "dim" in data:
        settings.set_dim(data["dim"])
    return jsonify(ok=True)


@app.post("/api/refresh")
def refresh():
    # Récupère les nouvelles parties (et les manquantes) puis met à jour le cache.
    cfg, client = _ctx()
    _, summary = pipeline.build_data(client, cfg, queue=_queue(),
                                     allow_fetch=True, want_analysis=False)
    pipeline.save_new_ids(summary.get("new_ids") or [])
    _invalidate_updates()
    return jsonify(fetched=summary.get("fetched", 0),
                   missing=summary.get("missing", 0),
                   total=summary.get("total", 0))


@app.get("/api/updates")
def updates():
    """Nb de nouvelles parties du compte ciblé (act) non encore téléchargées."""
    cfg, client = _ctx()
    q = _queue()

    def produce():
        try:
            return {"new": pipeline.count_uncached(client, cfg.game_name, cfg.tag_line,
                                                   q, size=50, act_only=True)}
        except RiotError as e:
            return {"new": 0, "error": str(e)}

    return jsonify(_cached_updates(("ov", cfg.riot_id, cfg.region, q), produce))


@app.get("/api/team/updates")
def team_updates():
    """Nb de nouvelles parties par joueur (15 récentes) — appels parallélisés."""
    cfg = load_config()
    q = _queue()
    team = settings.load().get("team", [])
    key = ("team", q, tuple((p["riot_id"], p["region"]) for p in team))

    def produce():
        def one(item):
            i, p = item
            game_name, tag_line = p["riot_id"].split("#", 1)
            client = HenrikClient(cfg.henrik_api_key, p["region"])
            try:
                new = pipeline.count_uncached(client, game_name, tag_line, q, size=15)
            except RiotError:
                new = 0
            return {"slot": i, "new": new}

        if not team:
            return {"slots": [], "total": 0}
        with ThreadPoolExecutor(max_workers=min(4, len(team))) as ex:
            slots = list(ex.map(one, list(enumerate(team))))
        slots.sort(key=lambda s: s["slot"])
        return {"slots": slots, "total": sum(s["new"] for s in slots)}

    return jsonify(_cached_updates(key, produce))


@app.get("/api/team")
def team_get():
    s = settings.load()
    return jsonify(team=s.get("team", []), team_name=s.get("team_name"))


@app.post("/api/team/config")
def team_config():
    data = request.get_json(silent=True) or {}
    clean = []
    for p in (data.get("players") or []):
        rid = (p.get("riot_id") or "").strip()
        reg = (p.get("region") or "eu").strip().lower()
        if not rid:
            continue
        if "#" not in rid:
            return jsonify(error=f"Format attendu Pseudo#TAG : {rid}"), 400
        if reg not in REGIONS:
            return jsonify(error=f"Région invalide : {reg}"), 400
        clean.append({"riot_id": rid, "region": reg})
    settings.set_team(clean)
    if "name" in data:
        settings.set_team_name(data.get("name"))
    s = settings.load()
    return jsonify(ok=True, team=clean, team_name=s.get("team_name"))


@app.post("/api/team/analyze")
def team_analyze():
    """Analyse d'équipe via DeepSeek, à partir des stats en cache (pas de fetch)."""
    cfg = load_config()
    if not cfg.deepseek_api_key:
        return jsonify(error="Clé DeepSeek absente : ajoute DEEPSEEK_API_KEY dans .env."), 400

    s = settings.load()
    team = s.get("team", [])
    if not team:
        return jsonify(error="Aucune équipe configurée."), 400

    players = []
    for p in team:
        game_name, tag_line = p["riot_id"].split("#", 1)
        client = HenrikClient(cfg.henrik_api_key, p["region"])
        try:
            summary = pipeline.player_summary(client, game_name, tag_line, _queue(),
                                              count=15, allow_fetch=False)
        except RiotError as e:
            players.append({"riot_id": p["riot_id"], "erreur": str(e)})
            continue
        if not summary.get("games"):
            players.append({"riot_id": p["riot_id"],
                            "note": "aucune donnée en cache — clique « Mettre à jour »"})
            continue
        players.append({
            "riot_id": p["riot_id"],
            "rang": summary.get("rank"),
            "parties_act": summary.get("act_games"),
            "parties_recentes": summary.get("games"),
            "win_rate_pct": summary.get("win_rate"),
            "kd": summary.get("kd"),
            "acs": summary.get("avg_acs"),
            "kast_pct": summary.get("kast"),
            "hs_pct": summary.get("avg_hs_pct"),
            "fcs_pct": summary.get("fcs"),
            "agents": [{"nom": a.get("name"), "parties": a.get("games")}
                       for a in (summary.get("top_agents") or [])],
        })

    try:
        analysis = team_coach.analyze(cfg.deepseek_api_key, cfg.deepseek_model,
                                      s.get("team_name"), players)
    except Exception as e:  # noqa: BLE001
        return jsonify(error=str(e)[:400]), 502
    return jsonify(analysis=dashboard.render_markdown(analysis))


@app.post("/api/team/refresh")
def team_refresh():
    """Met à jour un joueur (par emplacement). ?slot=N &fetch=0 pour le cache seul."""
    team = settings.load().get("team", [])
    try:
        idx = int(request.args.get("slot", ""))
    except ValueError:
        return jsonify(error="slot invalide"), 400
    if idx < 0 or idx >= len(team):
        return jsonify(error="slot hors limites"), 404

    p = team[idx]
    game_name, tag_line = p["riot_id"].split("#", 1)
    cfg = load_config()
    client = HenrikClient(cfg.henrik_api_key, p["region"])
    allow_fetch = request.args.get("fetch", "1") != "0"
    try:
        summary = pipeline.player_summary(client, game_name, tag_line, _queue(),
                                          count=15, allow_fetch=allow_fetch)
    except RiotError as e:
        return jsonify(riot_id=p["riot_id"], region=p["region"], error=str(e)), 200
    if allow_fetch:
        _invalidate_updates()
    return jsonify(riot_id=p["riot_id"], region=p["region"], summary=summary)


@app.post("/api/target")
def set_target():
    data = request.get_json(silent=True) or {}
    rid = (data.get("riot_id") or "").strip()
    region = (data.get("region") or "").strip().lower()
    if "#" not in rid:
        return jsonify(error="Format attendu : Pseudo#TAG"), 400
    if region and region not in REGIONS:
        return jsonify(error="Région invalide"), 400
    settings.set_target(rid, region or None)
    return jsonify(ok=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", PORT))
    print(f"→ Dashboard Valorant sur http://127.0.0.1:{port}  (Ctrl+C pour arrêter)")
    try:
        webbrowser.open(f"http://127.0.0.1:{port}")
    except Exception:  # noqa: BLE001
        pass
    app.run(host="127.0.0.1", port=port, debug=False)
