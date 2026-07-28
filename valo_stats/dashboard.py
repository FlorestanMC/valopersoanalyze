"""Rendu du dashboard HTML des stats Valorant — DA « Aurora Tactical ».

Interface à onglets (Vue d'ensemble / Agents / Armes / First Contact), fond
aurora animé, verre lumineux, sélecteur de file Ranked ↔ Premier.
Document autonome (images d'agents/armes chargées depuis valorant-api.com).
"""
import html
import re
from datetime import datetime

INK = "#F2F0EA"
RED = "#FF4655"
CYAN = "#22D3EE"
MINT = "#37E0A6"
VIOLET = "#8B5CFF"
MUTED = "#98a2b3"

QUEUE_LABEL = {"competitive": "Ranked", "premier": "Premier"}


def _esc(s) -> str:
    return html.escape(str(s), quote=True)


def _accent(value, threshold=50):
    if value is None:
        return "rgba(255,255,255,.4)"
    return MINT if value >= threshold else RED


def _inline(line: str) -> str:
    parts = re.split(r"\*\*", line)
    return "".join(
        (f"<strong>{_esc(p)}</strong>" if i % 2 else _esc(p))
        for i, p in enumerate(parts)
    )


def _md_to_html(text: str) -> str:
    if not text:
        return ""
    out, in_list = [], False
    for raw in text.splitlines():
        s = raw.strip()
        if s.startswith(("- ", "• ", "* ")):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(s[2:])}</li>")
        else:
            if in_list:
                out.append("</ul>")
                in_list = False
            if s:
                out.append(f"<p>{_inline(s)}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


# --- composants -------------------------------------------------------------
def _kpi(label, value, sub="", accent=INK):
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    return (f'<div class="tile"><div class="kpi-label">{_esc(label)}</div>'
            f'<div class="kpi-value" style="color:{accent}">{_esc(value)}</div>'
            f'{sub_html}</div>')


def _bar_row(label_html, value, display, accent, sub=""):
    pct = 0 if value is None else max(0, min(100, value))
    sub_html = f'<span class="bar-sub">{_esc(sub)}</span>' if sub else ""
    return (f'<div class="bar-row" title="{_esc(display)} {_esc(sub)}">'
            f'<div class="bar-label">{label_html}{sub_html}</div>'
            f'<div class="bar"><span style="width:{pct}%;background:{accent}"></span></div>'
            f'<div class="bar-val">{_esc(display)}</div></div>')


def _gauge(pct, top, bottom):
    p = 0 if pct is None else max(0, min(100, pct))
    color = _accent(pct)
    return (f'<div class="gauge" style="background:conic-gradient({color} {p*3.6:.1f}deg,'
            f' rgba(255,255,255,.07) 0)"><div class="gauge-hole">'
            f'<div class="gauge-top" style="color:{color}">{_esc(top)}</div>'
            f'<div class="gauge-bottom">{_esc(bottom)}</div></div></div>')


def _chip(name, img, size=34):
    if img:
        return (f'<img class="chip" src="{_esc(img)}" alt="{_esc(name)}" '
                f'width="{size}" height="{size}" loading="lazy">')
    initial = _esc(name[:1].upper()) if name else "?"
    return f'<span class="chip chip-ph" style="width:{size}px;height:{size}px">{initial}</span>'


def _queue_switch(active):
    def item(key):
        cls = "qbtn active" if key == active else "qbtn"
        return f'<a class="{cls}" href="/?queue={key}">{QUEUE_LABEL[key]}</a>'
    return f'<div class="qswitch">{item("competitive")}{item("premier")}</div>'


# --- rendu principal --------------------------------------------------------
def render(data: dict) -> str:
    p = data["player"]
    ov = data["overview"]
    fc = data["fc"]
    ka = data.get("kast", {})
    weps = data.get("weapons", [])
    imgs = data.get("agent_img", {})
    analysis = data.get("analysis")
    queue = data.get("queue", "competitive")

    name = _esc(p["name"])
    rank = _esc(p.get("rank", "—"))
    level = _esc(p.get("level", "—"))
    act = _esc(data.get("act", "—"))
    gen = _esc(data.get("generated", datetime.now().strftime("%Y-%m-%d %H:%M")))
    bg = p.get("agent_bg") or ""

    # fond personnalisé (optionnel)
    bgd = data.get("background") or {}
    bg_url = bgd.get("url")
    bg_dim = bgd.get("dim", 55)
    if bg_url:
        userbg = (f'<div class="userbg" style="background-image:url({_esc(bg_url)})"></div>'
                  f'<div class="userveil" style="background:rgba(7,6,15,{bg_dim/100:.2f})"></div>')
        body_class = "hasbg"
    else:
        userbg = ""
        body_class = ""

    # ---------- KPIs ----------
    hs = ov.get("avg_hs_pct")
    kast_v = ka.get("kast")
    fcs = fc.get("fcs")
    kpis = "".join([
        _kpi("K/D", ov["kd"], f"KDA {ov['kda']}", _accent(ov["kd"] * 50)),
        _kpi("ACS moyen", ov["avg_acs"], "score / round", INK),
        _kpi("KAST", f"{kast_v} %" if kast_v is not None else "n/d",
             "rounds impactés", _accent(kast_v, 70)),
        _kpi("HS %", f"{hs} %" if hs is not None else "n/d", "précision tête", INK),
        _kpi("Kills / partie", ov["avg_kills"],
             f"{ov['avg_deaths']} D · {ov['avg_assists']} A", INK),
        _kpi("First Contact", f"{fcs} %" if fcs is not None else "n/d",
             "onglet dédié ↗", _accent(fcs)),
    ])

    # ---------- Rounds ----------
    rw, rl = ov.get("rounds_won", 0), ov.get("rounds_lost", 0)
    rwr = ov.get("round_win_rate")
    wpct = (rw / (rw + rl) * 100) if (rw + rl) else 0
    round_split = (
        f'<div class="split"><span style="width:{wpct:.1f}%;background:{MINT}"></span>'
        f'<span style="width:{100-wpct:.1f}%;background:{RED}"></span></div>'
    )

    # ---------- maps ----------
    map_bars = "".join(
        _bar_row(f'<span class="nm">{_esc(m)}</span>', mm["win_rate"],
                 f'{mm["win_rate"]} %', _accent(mm["win_rate"]), sub=f'{mm["games"]}p')
        for m, mm in ov.get("maps", {}).items()
    )

    # ---------- recent ----------
    rows = []
    for r in ov.get("recent", [])[:14]:
        cls = "win" if r["won"] else "loss"
        chip = _chip(r["agent"], imgs.get(r["agent"], {}).get("icon"), 30)
        hsr = f'{r["hs"]}%' if r["hs"] is not None else "—"
        rows.append(
            f'<div class="match {cls}"><span class="res">{"V" if r["won"] else "D"}</span>'
            f'{chip}<span class="m-agent">{_esc(r["agent"])}</span>'
            f'<span class="m-map">{_esc(r["map"])}</span>'
            f'<span class="m-kda">{_esc(r["kda"])}</span>'
            f'<span class="m-x">{_esc(r["acs"])}<i>ACS</i></span>'
            f'<span class="m-x">{hsr}<i>HS</i></span></div>'
        )
    matches_html = "".join(rows)

    # ---------- agents ----------
    fc_agents = fc.get("agents", {})
    agent_cards = []
    for agent, a in ov.get("agents", {}).items():
        f = fc_agents.get(agent, {})
        portrait = imgs.get(agent, {}).get("portrait")
        fcs_a = f.get("fcs")
        style = (f'--pf:url({_esc(portrait)})') if portrait else ""
        fcs_disp = f'{fcs_a}%' if fcs_a is not None else "—"
        agent_cards.append(
            f'<div class="acard" style="{style}"><div class="acard-fade"></div>'
            f'<div class="acard-top">{_chip(agent, imgs.get(agent, {}).get("icon"), 36)}'
            f'<span class="acard-name">{_esc(agent)}</span></div>'
            f'<div class="acard-grid">'
            f'<div><b>{a["games"]}</b><span>parties</span></div>'
            f'<div><b style="color:{_accent(a["win_rate"])}">{a["win_rate"]}%</b><span>WR</span></div>'
            f'<div><b>{a["kd"]}</b><span>K/D</span></div>'
            f'<div><b style="color:{_accent(fcs_a)}">{fcs_disp}</b><span>FCS</span></div>'
            f'</div></div>'
        )
    agents_html = "".join(agent_cards)

    # ---------- weapons ----------
    max_k = max((w["kills"] for w in weps), default=1) or 1
    wep_rows = []
    for w in weps:
        icon = (f'<img class="wic" src="{_esc(w["icon"])}" alt="" loading="lazy">'
                if w.get("icon") else '<span class="wic"></span>')
        pctk = w["kills"] / max_k * 100
        wep_rows.append(
            f'<div class="wrow" title="{_esc(w["name"])}">'
            f'<div class="wid">{icon}<span class="nm">{_esc(w["name"])}</span></div>'
            f'<div class="bar"><span style="width:{pctk:.0f}%;background:{CYAN}"></span></div>'
            f'<div class="wk">{w["kills"]}<i>kills</i></div>'
            f'<div class="wd">{w["deaths"]}<i>subis</i></div></div>'
        )
    weapons_html = "".join(wep_rows) or '<p class="muted">Aucune arme enregistrée.</p>'

    # ---------- precision ----------
    prec = ov.get("precision", {}) or {}
    ph, pb, pl = prec.get("hs") or 0, prec.get("bs") or 0, prec.get("ls") or 0
    precision_html = (
        f'<div class="prec-bar">'
        f'<span style="width:{ph}%;background:{RED}" title="Tête {ph}%"></span>'
        f'<span style="width:{pb}%;background:{CYAN}" title="Corps {pb}%"></span>'
        f'<span style="width:{pl}%;background:{MUTED}" title="Jambes {pl}%"></span></div>'
        f'<div class="prec-leg">'
        f'<span><i style="background:{RED}"></i>Tête <b>{ph}%</b></span>'
        f'<span><i style="background:{CYAN}"></i>Corps <b>{pb}%</b></span>'
        f'<span><i style="background:{MUTED}"></i>Jambes <b>{pl}%</b></span></div>'
    )

    # ---------- first contact ----------
    fk, fd = fc["fk"], fc["fd"]
    donut_p = (fk / (fk + fd) * 100) if (fk + fd) else 0
    donut = (f'<div class="donut" style="background:conic-gradient({MINT} {donut_p*3.6:.1f}deg,'
             f' {RED} 0)"><div class="donut-hole"><span class="dn">{fk+fd}</span>'
             f'<span class="dl">duels</span></div></div>')
    fc_bars = []
    for agent, a in list(fc_agents.items()):
        if a["duels"] == 0:
            continue
        chip = _chip(agent, imgs.get(agent, {}).get("icon"), 26)
        fc_bars.append(_bar_row(
            f'{chip}<span class="nm">{_esc(agent)}</span>', a["fcs"],
            f'{a["fcs"]} %' if a["fcs"] is not None else "n/d",
            _accent(a["fcs"]), sub=f'{a["fk"]}-{a["fd"]}'))
    fc_bars_html = "".join(fc_bars) or '<p class="muted">Pas de duels enregistrés.</p>'
    fcs_gauge = _gauge(fcs, f"{fcs} %" if fcs is not None else "n/d", "First Contact Success")

    # ---------- analyse ----------
    if analysis:
        analysis_html = f'<div class="analysis">{_md_to_html(analysis)}</div>'
    else:
        analysis_html = ('<p class="muted">Analyse coaching indisponible '
                         '(crédit Anthropic requis).</p>')

    bg_layer = f'<div class="hero-portrait" style="background-image:url({_esc(bg)})"></div>' if bg else ""

    def _pr(v):
        return v if v is not None else "n/d"

    return _PAGE.format(
        css=_CSS, js=_JS, name=name, rank=rank, level=level, act=act, gen=gen,
        queue=queue, qswitch=_queue_switch(queue), bg_layer=bg_layer,
        userbg=userbg, body_class=body_class, dim=bg_dim,
        mint=MINT, red=RED,
        wr=ov["win_rate"], wr_color=_accent(ov["win_rate"]),
        wins=ov.get("wins", 0), losses=ov.get("losses", 0), games=ov["games"],
        rwr=(f"{rwr} %" if rwr is not None else "n/d"), round_split=round_split,
        rw=rw, rl=rl, kpis=kpis, map_bars=map_bars, matches=matches_html,
        agents=agents_html, weapons=weapons_html, precision=precision_html,
        fk=fk, fd=fd, donut=donut, fcs_gauge=fcs_gauge, fc_bars=fc_bars_html,
        fk_pr=_pr(fc.get("fk_per_round")), fd_pr=_pr(fc.get("fd_per_round")),
        analysis=analysis_html,
    )


_CSS = """
:root{--ink:#F2F0EA;--red:#FF4655;--cyan:#22D3EE;--mint:#37E0A6;--violet:#8B5CFF;
 --muted:#98a2b3;--glass:rgba(255,255,255,.06);--brd:rgba(255,255,255,.12);--bg:#07060f;}
*{box-sizing:border-box;margin:0;padding:0}
html{background:var(--bg)}
html,body{color:var(--ink);min-height:100%;
 font-family:-apple-system,"SF Pro Display",Inter,"Segoe UI",Roboto,sans-serif;-webkit-font-smoothing:antialiased}
body{position:relative;overflow-x:hidden;background:transparent}
.aurora{position:fixed;inset:-25%;z-index:-3;filter:blur(80px) saturate(150%);opacity:.6}
.aurora span{position:absolute;border-radius:50%;mix-blend-mode:screen;animation:drift 20s ease-in-out infinite}
.b1{width:55vw;height:55vw;background:#ff2d6b;top:-8%;left:-6%}
.b2{width:48vw;height:48vw;background:#7c3aed;bottom:-12%;right:-8%;animation-delay:-7s}
.b3{width:42vw;height:42vw;background:#22d3ee;top:34%;right:24%;animation-delay:-13s}
@keyframes drift{0%,100%{transform:translate(0,0) scale(1)}
 33%{transform:translate(7%,5%) scale(1.14)}66%{transform:translate(-5%,-4%) scale(.9)}}
.veil{position:fixed;inset:0;z-index:-2;background:
 radial-gradient(1200px 700px at 50% -10%,transparent,rgba(7,6,15,.55) 70%),
 linear-gradient(180deg,rgba(7,6,15,.35),rgba(7,6,15,.82))}
@media (prefers-reduced-motion:reduce){.aurora span{animation:none}}
/* fond personnalisé */
.userbg{position:fixed;inset:0;z-index:-5;background-size:cover;background-position:center}
.userveil{position:fixed;inset:0;z-index:-4}
.hasbg .aurora{opacity:.2}.hasbg .veil{opacity:.35}
/* modale réglages */
.modal{position:fixed;inset:0;z-index:60;display:none;place-items:center;
 background:rgba(0,0,0,.55);backdrop-filter:blur(4px)}
.modal.open{display:grid}
.modal-card{width:min(440px,92vw);padding:26px}
.modal-card h3{font-size:18px;font-weight:900;margin-bottom:18px}
.field{display:flex;flex-direction:column;gap:9px;font-size:13px;font-weight:800;
 color:var(--muted);margin-bottom:18px}
.field input[type=file]{color:var(--ink);font:inherit}
.field input[type=range]{width:100%;accent-color:var(--red)}
.modal-actions{display:flex;gap:10px;flex-wrap:wrap}
.btn-primary,.btn-ghost{font:inherit;font-weight:800;cursor:pointer;padding:10px 16px;border-radius:11px}
.btn-primary{border:0;color:#fff;background:linear-gradient(135deg,var(--red),#ff2d8e)}
.btn-primary:disabled{opacity:.6;cursor:default}
.btn-ghost{border:1px solid var(--brd);background:var(--glass);color:var(--ink)}
.mini{font-size:11px;margin-top:14px}

.wrap{max-width:1200px;margin:0 auto;padding:30px 22px 64px;position:relative;z-index:1}
.glass{background:var(--glass);backdrop-filter:blur(26px) saturate(160%);
 -webkit-backdrop-filter:blur(26px) saturate(160%);border:1px solid var(--brd);border-radius:20px;
 box-shadow:0 14px 46px rgba(0,0,0,.4),inset 0 1px 0 rgba(255,255,255,.14)}
.card{padding:22px;position:relative}
.card>h2,.card>h3{font-size:12px;text-transform:uppercase;letter-spacing:.16em;color:var(--muted);
 font-weight:800;margin-bottom:16px;display:flex;align-items:center;gap:9px}
.card>h2::before{content:"";width:11px;height:11px;background:var(--red);
 clip-path:polygon(0 0,100% 0,100% 100%);display:inline-block;box-shadow:0 0 12px rgba(255,70,85,.7)}
.muted{color:var(--muted);font-size:14px}.nm{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

/* header */
.top{display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin-bottom:18px}
.brand{font-weight:900;letter-spacing:.2em;font-size:12px;color:var(--red);text-transform:uppercase}
.who h1{font-size:32px;font-weight:900;letter-spacing:-.02em;line-height:1.05}
.pills{display:flex;gap:7px;flex-wrap:wrap;margin-top:7px}
.pill{font-size:12px;font-weight:800;padding:5px 11px;border-radius:999px;border:1px solid var(--brd);background:var(--glass)}
.pill.rk{color:#9fd8ff;border-color:rgba(159,216,255,.42)}
.pill.ac{color:var(--mint);border-color:rgba(55,224,166,.42)}
.spacer{flex:1}.controls{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.qswitch{display:flex;background:var(--glass);border:1px solid var(--brd);border-radius:12px;padding:3px}
.qbtn{font-size:13px;font-weight:800;padding:8px 16px;border-radius:9px;color:var(--muted);
 text-decoration:none;transition:.16s}
.qbtn.active{color:#fff;background:linear-gradient(135deg,var(--red),#ff2d8e);
 box-shadow:0 6px 18px rgba(255,70,85,.35)}
.refresh{font:inherit;font-weight:800;font-size:13px;color:var(--ink);cursor:pointer;padding:9px 15px;
 border-radius:12px;border:1px solid var(--brd);background:var(--glass);transition:.16s;white-space:nowrap}
.refresh:hover{border-color:rgba(55,224,166,.6);color:var(--mint)}
.refresh:disabled{opacity:.7;cursor:default}
.gen{color:var(--muted);font-size:11px;text-align:right;line-height:1.3}

/* tabs */
.tabs{display:flex;gap:6px;margin:6px 0 20px;flex-wrap:wrap}
.tab{font:inherit;font-weight:800;font-size:14px;color:var(--muted);cursor:pointer;padding:11px 20px;
 border-radius:13px;border:1px solid transparent;background:transparent;transition:.16s}
.tab:hover{color:var(--ink)}
.tab.active{color:#fff;background:var(--glass);border-color:var(--brd);
 box-shadow:inset 0 1px 0 rgba(255,255,255,.14)}
.panel{display:none}.panel.show{display:block;animation:fade .35s ease}
@keyframes fade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.section{margin-bottom:16px}

/* overview hero */
.ovhero{display:grid;grid-template-columns:1.15fr 1fr;gap:16px;margin-bottom:16px}
.hero-main{padding:26px;position:relative;overflow:hidden}
.hero-portrait{position:absolute;inset:0;background-size:cover;background-position:right -30px top -20px;
 opacity:.16;-webkit-mask-image:linear-gradient(90deg,transparent,#000);mask-image:linear-gradient(90deg,transparent,#000)}
.hero-kick{font-size:12px;letter-spacing:.18em;font-weight:800;color:var(--muted);text-transform:uppercase;position:relative}
.hero-big{font-size:76px;font-weight:900;letter-spacing:-.04em;line-height:1;margin:6px 0 8px;
 text-shadow:0 4px 30px rgba(0,0,0,.4);position:relative}
.hero-sub{font-size:15px;color:var(--muted);font-weight:600;position:relative}
.hero-rounds{padding:22px;display:flex;flex-direction:column;justify-content:center}
.rounds-top{display:flex;align-items:baseline;gap:10px;margin-bottom:12px}
.rounds-top .big{font-size:38px;font-weight:900;letter-spacing:-.02em}
.split{display:flex;height:14px;border-radius:7px;overflow:hidden;background:rgba(255,255,255,.08)}
.split span{display:block;height:100%}
.rounds-leg{display:flex;justify-content:space-between;margin-top:10px;font-size:13px;font-weight:700}
.rounds-leg .g{color:var(--mint)}.rounds-leg .l{color:var(--red)}

.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:13px}
.tile{padding:16px 18px;border-radius:16px;background:rgba(255,255,255,.045);border:1px solid var(--brd)}
.kpi-label{font-size:12px;color:var(--muted);font-weight:700;letter-spacing:.03em}
.kpi-value{font-size:30px;font-weight:900;letter-spacing:-.02em;margin-top:6px;line-height:1}
.kpi-sub{font-size:11px;color:var(--muted);margin-top:6px}

/* bars */
.bar-row,.wrow{display:grid;align-items:center;gap:12px;padding:8px 0}
.bar-row{grid-template-columns:150px 1fr 60px}
.bar-label{display:flex;align-items:center;gap:8px;font-size:14px;font-weight:700;min-width:0}
.bar-sub{color:var(--muted);font-weight:600;font-size:12px;margin-left:auto;padding-left:6px}
.bar{height:9px;border-radius:5px;background:rgba(255,255,255,.08);overflow:hidden}
.bar>span{display:block;height:100%;border-radius:5px;transition:width .7s cubic-bezier(.2,.8,.2,1)}
.bar-val{font-size:14px;font-weight:800;text-align:right}
.chip{border-radius:8px;object-fit:cover;background:rgba(255,255,255,.06);flex:none}
.chip-ph{display:grid;place-items:center;font-weight:800;color:var(--muted)}

/* recent */
.cols{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.match{display:grid;grid-template-columns:26px 30px 1fr 1fr auto auto;align-items:center;gap:12px;
 padding:9px 8px;border-radius:11px;border-left:3px solid transparent}
.match.win{border-left-color:var(--mint);background:linear-gradient(90deg,rgba(55,224,166,.07),transparent 40%)}
.match.loss{border-left-color:var(--red);background:linear-gradient(90deg,rgba(255,70,85,.07),transparent 40%)}
.res{width:24px;height:24px;border-radius:7px;display:grid;place-items:center;font-weight:900;font-size:12px}
.match.win .res{background:rgba(55,224,166,.2);color:var(--mint)}
.match.loss .res{background:rgba(255,70,85,.2);color:var(--red)}
.m-agent{font-weight:800;font-size:14px}.m-map{color:var(--muted);font-size:14px}
.m-kda{font-variant-numeric:tabular-nums;font-size:14px}
.m-x{font-weight:800;font-size:14px;text-align:right}
.m-x i{display:block;font-style:normal;font-size:10px;color:var(--muted);font-weight:700}

/* agents grid */
.agrid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.acard{position:relative;overflow:hidden;padding:16px;border-radius:18px;min-height:172px;
 border:1px solid var(--brd);background:var(--glass);display:flex;flex-direction:column;justify-content:space-between}
.acard::before{content:"";position:absolute;inset:0;background-image:var(--pf);background-size:cover;
 background-position:center top;opacity:.34;z-index:0}
.acard-fade{position:absolute;inset:0;background:linear-gradient(180deg,rgba(7,6,15,.15),rgba(7,6,15,.9));z-index:1}
.acard-top,.acard-grid{position:relative;z-index:2}
.acard-top{display:flex;align-items:center;gap:10px}
.acard-name{font-weight:900;font-size:16px}
.acard-grid{display:grid;grid-template-columns:1fr 1fr;gap:9px 12px}
.acard-grid div{display:flex;flex-direction:column}
.acard-grid b{font-size:19px;font-weight:900;line-height:1}
.acard-grid span{font-size:11px;color:var(--muted);margin-top:2px}

/* weapons + precision */
.wrow{grid-template-columns:150px 1fr 60px 66px;border-bottom:1px solid rgba(255,255,255,.05)}
.wrow:last-child{border-bottom:none}
.wid{display:flex;align-items:center;gap:9px;min-width:0}
.wic{height:19px;max-width:66px;width:auto;object-fit:contain;filter:brightness(1.5);flex:none}
.wk,.wd{text-align:right;font-weight:900;font-size:15px}.wd{color:var(--muted)}
.wk i,.wd i{display:block;font-style:normal;font-size:10px;color:var(--muted);font-weight:700}
.prec-bar{display:flex;height:20px;border-radius:8px;overflow:hidden;background:rgba(255,255,255,.08);margin-bottom:12px}
.prec-bar span{display:block;height:100%}
.prec-leg{display:flex;gap:20px;font-size:14px;font-weight:700}
.prec-leg i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:7px}
.prec-leg b{margin-left:5px}

/* first contact */
.fchero{display:grid;grid-template-columns:220px 220px 1fr;gap:22px;align-items:center}
.gauge{width:200px;height:200px;border-radius:50%;display:grid;place-items:center;margin:0 auto;
 box-shadow:inset 0 1px 0 rgba(255,255,255,.16),0 10px 34px rgba(0,0,0,.4)}
.gauge-hole{width:158px;height:158px;border-radius:50%;background:rgba(7,6,15,.8);display:flex;
 flex-direction:column;align-items:center;justify-content:center;gap:3px}
.gauge-top{font-size:42px;font-weight:900;letter-spacing:-.03em}
.gauge-bottom{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.09em;text-align:center;padding:0 10px}
.donut{width:180px;height:180px;border-radius:50%;display:grid;place-items:center;margin:0 auto;box-shadow:inset 0 1px 0 rgba(255,255,255,.16)}
.donut-hole{width:124px;height:124px;border-radius:50%;background:rgba(7,6,15,.8);display:flex;flex-direction:column;align-items:center;justify-content:center}
.dn{font-size:36px;font-weight:900}.dl{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.09em}
.fc-counts{display:flex;gap:26px;margin-top:14px;justify-content:center}
.fc-counts b{font-size:24px;display:block;text-align:center;font-weight:900}
.fc-counts span{font-size:12px;color:var(--muted)}
.fc-note{margin-top:16px;font-size:13px;color:var(--muted);line-height:1.55}

.analysis p{margin:0 0 10px;line-height:1.55;font-size:15px}
.analysis ul{margin:0 0 10px;padding-left:20px}.analysis li{margin:4px 0;line-height:1.5;font-size:15px}
.analysis strong{color:#fff}
.foot{margin-top:24px;color:var(--muted);font-size:12px;line-height:1.6;text-align:center}

@media (max-width:920px){
 .ovhero{grid-template-columns:1fr}.cols{grid-template-columns:1fr}.agrid{grid-template-columns:repeat(2,1fr)}
 .fchero{grid-template-columns:1fr;justify-items:center}.hero-big{font-size:60px}
 .bar-row{grid-template-columns:120px 1fr 52px}.wrow{grid-template-columns:110px 1fr 50px 56px}
 .match{grid-template-columns:24px 28px 1fr auto auto}.m-map,.m-kda{display:none}
 .prec-leg{flex-wrap:wrap;gap:12px}}
"""

_JS = """
(function(){
 var tabs=document.querySelectorAll('.tab');
 tabs.forEach(function(t){t.addEventListener('click',function(){
   tabs.forEach(function(x){x.classList.remove('active')});
   document.querySelectorAll('.panel').forEach(function(x){x.classList.remove('show')});
   t.classList.add('active');
   document.getElementById('panel-'+t.dataset.tab).classList.add('show');
 })});
 var btn=document.getElementById('refresh');
 if(btn){var base=btn.textContent;btn.addEventListener('click',function(){
   btn.disabled=true;btn.textContent='⏳ Mise a jour...';
   fetch('/api/refresh?queue='+QUEUE,{method:'POST'})
    .then(function(r){return r.json()})
    .then(function(j){btn.textContent='✓ '+(j.fetched||0)+' nouvelle(s)';
      setTimeout(function(){location.reload()},800)})
    .catch(function(){btn.textContent='⚠ Lance server.py';
      setTimeout(function(){btn.textContent=base;btn.disabled=false},2600)});
 })}
 var sb=document.getElementById('settings-btn'), modal=document.getElementById('modal');
 if(sb&&modal){
   sb.addEventListener('click',function(){modal.classList.add('open')});
   document.getElementById('modal-close').addEventListener('click',function(){modal.classList.remove('open')});
   modal.addEventListener('click',function(e){if(e.target===modal)modal.classList.remove('open')});
   var dim=document.getElementById('dim'), dv=document.getElementById('dim-val'),
       uv=document.querySelector('.userveil'), tmr;
   if(dim){dim.addEventListener('input',function(){
     dv.textContent=dim.value+'%';
     if(uv)uv.style.background='rgba(7,6,15,'+(dim.value/100)+')';
     clearTimeout(tmr);tmr=setTimeout(function(){
       fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({dim:parseInt(dim.value,10)})}).catch(function(){});
     },400);
   })}
   var af=document.getElementById('bg-apply'), fi=document.getElementById('bg-file');
   if(af){af.addEventListener('click',function(){
     if(!fi.files||!fi.files[0]){modal.classList.remove('open');return}
     var fd=new FormData();fd.append('bg',fi.files[0]);
     af.disabled=true;af.textContent='Envoi...';
     fetch('/api/background',{method:'POST',body:fd}).then(function(r){return r.json()})
      .then(function(j){if(j.error){af.textContent='⚠ '+j.error;af.disabled=false;}
        else{location.reload()}})
      .catch(function(){af.textContent='⚠ Serveur requis';af.disabled=false});
   })}
   var rb=document.getElementById('bg-reset');
   if(rb){rb.addEventListener('click',function(){
     fetch('/api/background/reset',{method:'POST'}).then(function(){location.reload()}).catch(function(){});
   })}
 }
})();
"""

_PAGE = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Valo Stats — {name}</title><style>{css}</style></head>
<body class="{body_class}">
{userbg}
<div class="aurora"><span class="b1"></span><span class="b2"></span><span class="b3"></span></div>
<div class="veil"></div>
<div class="wrap">

 <header class="top">
   <div class="who"><div class="brand">◆ Valo Stats</div><h1>{name}</h1>
     <div class="pills"><span class="pill rk">{rank}</span>
       <span class="pill">Niveau {level}</span><span class="pill ac">Saison {act}</span></div></div>
   <div class="spacer"></div>
   <div class="controls">{qswitch}
     <button id="settings-btn" class="refresh" type="button" title="Personnaliser le fond">⚙</button>
     <button id="refresh" class="refresh" type="button">↻ Mettre à jour</button>
     <div class="gen">Généré le<br>{gen}</div></div>
 </header>

 <nav class="tabs">
   <button class="tab active" data-tab="ov">Vue d'ensemble</button>
   <button class="tab" data-tab="agents">Agents</button>
   <button class="tab" data-tab="weapons">Armes</button>
   <button class="tab" data-tab="fc">First Contact</button>
 </nav>

 <section id="panel-ov" class="panel show">
   <div class="ovhero">
     <div class="glass hero-main">{bg_layer}
       <div class="hero-kick">Win rate · {games} parties</div>
       <div class="hero-big" style="color:{wr_color}">{wr}%</div>
       <div class="hero-sub">{wins} victoires · {losses} défaites</div>
     </div>
     <div class="glass hero-rounds">
       <div class="rounds-top"><span class="big">{rwr}</span><span class="muted">round win rate</span></div>
       {round_split}
       <div class="rounds-leg"><span class="g">{rw} rounds gagnés</span><span class="l">{rl} perdus</span></div>
     </div>
   </div>
   <div class="glass card section"><div class="kpis">{kpis}</div></div>
   <div class="cols section">
     <div class="glass card"><h2>Win rate par carte</h2>{map_bars}</div>
     <div class="glass card"><h2>Dernières parties</h2>{matches}</div>
   </div>
   <div class="glass card section"><h2>Analyse coaching (Claude)</h2>{analysis}</div>
 </section>

 <section id="panel-agents" class="panel">
   <div class="glass card"><h2>Performance par agent</h2><div class="agrid">{agents}</div></div>
 </section>

 <section id="panel-weapons" class="panel">
   <div class="glass card section"><h2>Armes — kills / morts subies</h2>{weapons}</div>
   <div class="glass card"><h2>Précision des tirs</h2>{precision}</div>
 </section>

 <section id="panel-fc" class="panel">
   <div class="glass card section"><h2>First Contact — duels d'ouverture</h2>
     <div class="fchero">
       <div>{fcs_gauge}</div>
       <div>{donut}
         <div class="fc-counts"><span><b style="color:{mint}">{fk}</b>First Kills</span>
           <span><b style="color:{red}">{fd}</b>First Deaths</span></div></div>
       <div>
         <div class="fc-note">Le <b>FCS</b> mesure la proportion de duels d'ouverture gagnés :
           First Kills / (First Kills + First Deaths). Tu prends le premier kill sur
           <b>{fk_pr}%</b> des rounds et la première mort sur <b>{fd_pr}%</b>.</div>
       </div>
     </div>
   </div>
   <div class="glass card"><h2>FCS par agent</h2>{fc_bars}</div>
 </section>

 <div class="foot">
   Données via l'API tierce non officielle HenrikDev (non affiliée à Riot Games).<br>
   Visuels d'agents / armes © Riot Games, servis par valorant-api.com — usage personnel.
 </div>
</div>

<div id="modal" class="modal">
  <div class="modal-card glass">
    <h3>🖼 Personnaliser le fond</h3>
    <label class="field">Image de fond (jpg, png, webp, gif)
      <input id="bg-file" type="file" accept="image/*"></label>
    <label class="field">Assombrissement <span id="dim-val">{dim}%</span>
      <input id="dim" type="range" min="0" max="90" value="{dim}"></label>
    <div class="modal-actions">
      <button id="bg-apply" class="btn-primary" type="button">Appliquer</button>
      <button id="bg-reset" class="btn-ghost" type="button">Réinitialiser</button>
      <button id="modal-close" class="btn-ghost" type="button">Fermer</button>
    </div>
    <p class="muted mini">Nécessite le serveur local (python server.py).</p>
  </div>
</div>

<script>var QUEUE={queue!r};{js}</script>
</body></html>
"""
