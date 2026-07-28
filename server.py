#!/usr/bin/env python3
"""Petit serveur local pour le dashboard Valorant, avec bouton « Mettre à jour ».

- GET  /            -> rend le dashboard (rapide : lit le cache, ne télécharge rien)
- POST /api/refresh -> récupère les nouvelles parties de l'act (met à jour le cache)

Usage : python server.py   puis ouvrir http://127.0.0.1:8770
"""
import os
import sys
import webbrowser

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
from valo_stats.riot import HenrikClient
from valo_stats import pipeline, dashboard, settings

PORT = 8770
QUEUES = {"competitive", "premier"}

cfg = load_config()
client = HenrikClient(cfg.henrik_api_key, cfg.region)
app = Flask(__name__)


def _queue():
    q = (request.args.get("queue") or "competitive").lower()
    return q if q in QUEUES else "competitive"


def _empty_page(queue):
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
    <a href="/?queue={other}" style="font:inherit;font-weight:800;padding:12px 20px;border-radius:12px;
     border:1px solid rgba(255,255,255,.15);color:#F2F0EA;text-decoration:none">{other_label}</a>
  </div>
</div>
<script>
document.getElementById('load').addEventListener('click',function(){{
  var b=this;b.disabled=true;b.textContent='⏳ Téléchargement...';
  fetch('/api/refresh?queue={queue}',{{method:'POST'}}).then(function(r){{return r.json()}})
   .then(function(){{location.href='/?queue={queue}'}})
   .catch(function(){{b.textContent='⚠ Erreur';}});
}});
</script></body>"""


def _with_background(data):
    s = settings.load()
    bp = settings.bg_path()
    url = f"/user-bg?v={int(os.path.getmtime(bp))}" if bp else None
    data["background"] = {"url": url, "dim": s.get("dim", 55)}
    return data


@app.get("/")
def index():
    # Chargement rapide : on n'utilise que le cache (pas de téléchargement).
    q = _queue()
    data, _ = pipeline.build_data(client, cfg, queue=q,
                                  allow_fetch=False, want_analysis=False)
    if data is None:
        return _empty_page(q)
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
    _, summary = pipeline.build_data(client, cfg, queue=_queue(),
                                     allow_fetch=True, want_analysis=False)
    return jsonify(fetched=summary.get("fetched", 0),
                   missing=summary.get("missing", 0),
                   total=summary.get("total", 0))


if __name__ == "__main__":
    url = f"http://127.0.0.1:{PORT}"
    print(f"→ Dashboard Valorant sur {url}  (Ctrl+C pour arrêter)")
    try:
        webbrowser.open(url)
    except Exception:  # noqa: BLE001
        pass
    app.run(host="127.0.0.1", port=PORT, debug=False)
