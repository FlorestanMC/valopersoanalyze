"""Rendu du dashboard HTML des stats Valorant — DA « Aurora Tactical ».

Interface à onglets (Vue d'ensemble / Agents / Armes / First Contact), fond
aurora animé, verre lumineux, sélecteur de file Ranked ↔ Premier.
Document autonome (images d'agents/armes chargées depuis valorant-api.com).
"""
import html
import re
from datetime import datetime, date, timedelta

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


_OL_RE = re.compile(r"^\d+[.)]\s+")


def _md_to_html(text: str) -> str:
    if not text:
        return ""
    out, mode = [], None  # mode : None | "ul" | "ol"

    def close():
        nonlocal mode
        if mode:
            out.append(f"</{mode}>")
            mode = None

    def open_list(kind):
        nonlocal mode
        if mode != kind:
            close()
            out.append(f"<{kind}>")
            mode = kind

    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            close()
        elif s.startswith("#"):
            close()
            out.append(f"<p><strong>{_esc(s.lstrip('#').strip())}</strong></p>")
        elif s.startswith(("- ", "• ", "* ")):
            open_list("ul")
            out.append(f"<li>{_inline(s[2:])}</li>")
        elif _OL_RE.match(s):
            open_list("ol")
            out.append(f"<li>{_inline(_OL_RE.sub('', s))}</li>")
        else:
            close()
            out.append(f"<p>{_inline(s)}</p>")
    close()
    return "\n".join(out)


def render_markdown(text: str) -> str:
    """Convertit un texte Markdown léger en HTML (titres, listes, gras)."""
    return _md_to_html(text)


_WD_LABELS = ["L", "M", "M", "J", "V", "S", "D"]
_WD_ABBR = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]
_MONTHS_FR = ["", "janv.", "févr.", "mars", "avr.", "mai", "juin",
              "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def _fr_daylabel(iso: str) -> str:
    """'2026-07-29' -> 'mar. 29 juil.' (ou 'Date inconnue')."""
    try:
        d = datetime.strptime(iso, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return "Date inconnue"
    label = f'{_WD_ABBR[d.weekday()]} {d.day} {_MONTHS_FR[d.month]}'
    if d == date.today():
        label += " · aujourd’hui"
    elif d == date.today() - timedelta(days=1):
        label += " · hier"
    return label


def _cal_level(count: int) -> int:
    if count <= 0:
        return 0
    if count <= 2:
        return 1
    if count <= 4:
        return 2
    if count <= 6:
        return 3
    return 4


def _activity_calendar(days: dict) -> str:
    """Heatmap type « contributions » : une case par jour, intensité = nb de parties."""
    counts = {}
    for k, v in (days or {}).items():
        try:
            counts[datetime.strptime(k, "%Y-%m-%d").date()] = int(v)
        except (ValueError, TypeError):
            continue
    if not counts:
        return '<p class="muted">Aucune activité datée pour cette saison.</p>'

    today = date.today()
    start = min(counts)
    end = max(max(counts), today)
    start -= timedelta(days=start.weekday())  # remonter au lundi

    weeks, cur = [], start
    while cur <= end:
        col = []
        for _ in range(7):
            col.append((cur, counts.get(cur, 0)))
            cur += timedelta(days=1)
        weeks.append(col)

    last_m = None
    months_cells = []
    for col in weeks:
        m = col[0][0].month
        months_cells.append(f'<span class="cal-m">{_MONTHS_FR[m] if m != last_m else ""}</span>')
        last_m = m
    months_html = "".join(months_cells)

    wd_html = "".join(
        f'<span>{_WD_LABELS[i] if i in (0, 2, 4, 6) else ""}</span>' for i in range(7)
    )

    cols_html = []
    for col in weeks:
        cells = []
        for d, c in col:
            if d > today:
                cells.append('<div class="cal-cell cal-future" data-tip="à venir"></div>')
                continue
            if c:
                tip = f'{d.strftime("%d/%m/%Y")} — {c} partie' + ("s" if c > 1 else "")
            else:
                tip = f'{d.strftime("%d/%m/%Y")} — aucune partie'
            cells.append(
                f'<div class="cal-cell cal-l{_cal_level(c)}" data-tip="{_esc(tip)}" '
                f'aria-label="{_esc(tip)}"></div>'
            )
        cols_html.append(f'<div class="cal-col">{"".join(cells)}</div>')

    legend = "".join(f'<span class="cal-cell cal-l{i}"></span>' for i in range(5))
    total, active = sum(counts.values()), len(counts)
    return (
        f'<div class="cal-meta">{active} jour(s) joué(s) · {total} partie(s) sur la saison</div>'
        f'<div class="cal-scroll"><div class="cal">'
        f'<div class="cal-top">{months_html}</div>'
        f'<div class="cal-main"><div class="cal-wd">{wd_html}</div>'
        f'<div class="cal-cols">{"".join(cols_html)}</div></div>'
        f'<div class="cal-legend"><span>Moins</span>{legend}<span>Plus</span></div>'
        f'</div></div>'
    )


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


def _queue_switch(active, base="", map_filter="all"):
    mq = f"&map={_esc(map_filter)}" if map_filter and map_filter != "all" else ""

    def item(key):
        cls = "qbtn active" if key == active else "qbtn"
        return f'<a class="{cls}" href="{base}/?queue={key}{mq}">{QUEUE_LABEL[key]}</a>'
    return f'<div class="qswitch">{item("competitive")}{item("premier")}</div>'


# (label, clé, plus_grand_est_meilleur, suffixe)
_SPLIT_ROWS = [
    ("Rounds", "rounds", None, ""),
    ("ADR", "adr", True, ""),
    ("KAST", "kast", True, " %"),
    ("HS %", "hs_pct", True, " %"),
    ("K/D", "kd", True, ""),
    ("First Kills", "fk", True, ""),
    ("First Deaths", "fd", False, ""),
    ("FCS", "fcs", True, " %"),
    ("Multi-kills 2k+", "mk", True, ""),
    ("Clutch (gagnés/tentés)", "clutch", True, ""),
]


def _split_table(b1, b2, l1, l2):
    b1 = b1 or {}
    b2 = b2 or {}
    rows = []
    for label, key, hb, suf in _SPLIT_ROWS:
        if key == "clutch":
            v1, v2 = b1.get("clutch"), b2.get("clutch")  # % pour la comparaison
            d1 = f'{b1.get("cwon", 0)}/{b1.get("catt", 0)}' if b1.get("catt") else "—"
            d2 = f'{b2.get("cwon", 0)}/{b2.get("catt", 0)}' if b2.get("catt") else "—"
        else:
            v1, v2 = b1.get(key), b2.get(key)
            d1 = f'{v1}{suf}' if v1 is not None else "—"
            d2 = f'{v2}{suf}' if v2 is not None else "—"
        c1 = c2 = ""
        if hb is not None and isinstance(v1, (int, float)) and isinstance(v2, (int, float)) and v1 != v2:
            if (v1 > v2) == hb:
                c1 = ' class="sp-best"'
            else:
                c2 = ' class="sp-best"'
        rows.append(f'<tr><td class="sp-l">{_esc(label)}</td>'
                    f'<td{c1}>{_esc(d1)}</td><td{c2}>{_esc(d2)}</td></tr>')
    return (f'<table class="sp-table"><thead><tr><th></th>'
            f'<th>{_esc(l1)}</th><th>{_esc(l2)}</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>')


def _split_matrix(cross):
    cross = cross or {}
    cols = [("Att · G", "attack_win", "sp-g"), ("Att · P", "attack_loss", "sp-p"),
            ("Déf · G", "defense_win", "sp-g"), ("Déf · P", "defense_loss", "sp-p")]
    buckets = [cross.get(k) or {} for _, k, _ in cols]
    head = "".join(f'<th class="{cls}">{_esc(lbl)}</th>' for lbl, _, cls in cols)
    rows = []
    for label, key, hb, suf in _SPLIT_ROWS:
        if key == "clutch":
            vals = [b.get("clutch") for b in buckets]
            disps = [f'{b.get("cwon", 0)}/{b.get("catt", 0)}' if b.get("catt") else "—" for b in buckets]
        else:
            vals = [b.get(key) for b in buckets]
            disps = [f'{v}{suf}' if v is not None else "—" for v in vals]
        nums = [(i, v) for i, v in enumerate(vals) if isinstance(v, (int, float))]
        best = None
        if hb is not None and len(nums) >= 2:
            best = (max if hb else min)(nums, key=lambda t: t[1])[0]
        tds = ""
        for i in range(len(cols)):
            cls = ' class="sp-best"' if best == i else ""
            tds += f"<td{cls}>{_esc(disps[i])}</td>"
        rows.append(f'<tr><td class="sp-l">{_esc(label)}</td>{tds}</tr>')
    return (f'<div class="sp-scroll"><table class="sp-table sp-matrix">'
            f'<thead><tr><th></th>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def _splits_section(sp):
    sp = sp or {}
    by_side = sp.get("by_side", {})
    by_out = sp.get("by_outcome", {})
    two = (
        '<div class="glass card"><h2>Par side · Attaque vs Défense</h2>'
        + _split_table(by_side.get("attack"), by_side.get("defense"), "Attaque", "Défense")
        + '</div>'
        '<div class="glass card"><h2>Par issue de round · Gagnés vs Perdus</h2>'
        + _split_table(by_out.get("win"), by_out.get("loss"), "Rounds gagnés", "Rounds perdus")
        + '</div>'
    )
    matrix = (
        '<div class="glass card section"><h2>Matrice 2×2 · side × issue</h2>'
        + _split_matrix(sp.get("cross"))
        + '<p class="muted mini" style="margin:10px 0 0">Att = Attaque · Déf = Défense · '
          'G = round gagné · P = round perdu. Meilleure valeur de chaque ligne surlignée.</p></div>'
    )
    return f'<div class="cols">{two}</div>{matrix}'


def _pctm(v):
    return f"{v} %" if v is not None else "—"


def _map_selector(maps, current):
    opts = ['<option value="all"' + (" selected" if current == "all" else "") + ">Toutes les cartes</option>"]
    for m in (maps or []):
        sel = " selected" if m == current else ""
        opts.append(f'<option value="{_esc(m)}"{sel}>{_esc(m)}</option>')
    return ('<select class="mapsel" aria-label="Filtrer par carte" '
            "onchange=\"location.href=BASE+'/?queue='+QUEUE+'&map='+encodeURIComponent(this.value)\">"
            + "".join(opts) + "</select>")


def _map_table(by_map, base, queue, current):
    rows = by_map or []
    if not rows:
        return '<p class="muted">Aucune donnée par carte.</p>'
    trs = []
    for m in rows:
        wr = m["win_rate"]
        wrc = _accent(wr) if wr is not None else MUTED
        active = ' class="mp-active"' if m["map"] == current else ""
        link = f'{base}/?queue={queue}&map={_esc(m["map"])}'
        trs.append(
            f"<tr{active}><td class=\"mp-name\"><a href=\"{link}\">{_esc(m['map'])}</a></td>"
            f'<td>{m["games"]}</td>'
            f'<td><b style="color:{wrc}">{_pctm(wr)}</b> '
            f'<span class="mp-wl">{m["wins"]}V {m["losses"]}D</span></td>'
            f'<td>{_pctm(m["round_wr"])}</td><td>{m["kd"]}</td>'
            f'<td>{m["adr"] if m["adr"] is not None else "—"}</td>'
            f'<td>{_pctm(m["kast"])}</td><td>{_pctm(m["hs_pct"])}</td></tr>'
        )
    head = ('<tr><th>Carte</th><th>Parties</th><th>Win rate</th><th>Round WR</th>'
            '<th>K/D</th><th>ADR</th><th>KAST</th><th>HS%</th></tr>')
    return (f'<div class="mp-scroll"><table class="mp-table"><thead>{head}</thead>'
            f'<tbody>{"".join(trs)}</tbody></table></div>')


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
    rank_icon = p.get("rank_icon")
    rank_color = p.get("rank_color") or "#ffd479"
    _emblem = f'<img class="rk-emblem" src="{_esc(rank_icon)}" alt="">' if rank_icon else ""
    _rr = p.get("rr")
    _rr_txt = f' · {_rr} RR' if _rr is not None else ""
    _chg = p.get("rr_change")
    _chg_txt = ""
    if isinstance(_chg, (int, float)) and _chg != 0:
        _col = MINT if _chg > 0 else RED
        _chg_txt = f' <span style="color:{_col};font-weight:900">{"+" if _chg > 0 else ""}{_chg}</span>'
    rank_pill = (f'<span class="pill rk" style="border-color:{rank_color}66;color:{rank_color}">'
                 f'{_emblem}{rank}{_rr_txt}{_chg_txt}</span>')
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

    # ---------- recent (groupé par jour) ----------
    new_ids = set(data.get("new_ids") or [])
    recent = ov.get("recent", [])[:14]
    groups = []
    for r in recent:
        d = r.get("date")
        if not groups or groups[-1][0] != d:
            groups.append((d, []))
        groups[-1][1].append(r)

    rows = []
    for day_iso, items in groups:
        w = sum(1 for x in items if x["won"])
        n = len(items)
        rows.append(
            f'<div class="day-sep"><span class="day-lbl">{_esc(_fr_daylabel(day_iso))}</span>'
            f'<span class="day-n">{n} partie{"s" if n > 1 else ""} · '
            f'<b class="g">{w}V</b> <b class="l">{n - w}D</b></span></div>'
        )
        for r in items:
            cls = "win" if r["won"] else "loss"
            if r.get("id") and r["id"] in new_ids:
                cls += " match-new"
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

    # First Contact par arme (FK avec / FD subies face à)
    fcw_rows = []
    for w in fc.get("weapons", [])[:10]:
        tot = (w["fk"] + w["fd"]) or 1
        fkpct = w["fk"] / tot * 100
        icon = (f'<img class="wic" src="{_esc(w["icon"])}" alt="" loading="lazy">'
                if w.get("icon") else '<span class="wic"></span>')
        fcw_rows.append(
            f'<div class="wrow" title="{_esc(w["name"])} — {w["fk"]} FK / {w["fd"]} FD">'
            f'<div class="wid">{icon}<span class="nm">{_esc(w["name"])}</span></div>'
            f'<div class="split"><span style="width:{fkpct:.0f}%;background:{MINT}"></span>'
            f'<span style="width:{100-fkpct:.0f}%;background:{RED}"></span></div>'
            f'<div class="wk" style="color:{MINT}">{w["fk"]}<i>FK</i></div>'
            f'<div class="wd" style="color:{RED}">{w["fd"]}<i>FD</i></div></div>'
        )
    fc_weapons_html = "".join(fcw_rows) or '<p class="muted">Aucune donnée par arme.</p>'

    # ---------- analyse ----------
    if analysis:
        analysis_html = f'<div class="analysis">{_md_to_html(analysis)}</div>'
    else:
        analysis_html = ('<p class="muted">Analyse coaching indisponible '
                         '(crédit Anthropic requis).</p>')

    bg_layer = f'<div class="hero-portrait" style="background-image:url({_esc(bg)})"></div>' if bg else ""

    cur_region = (data.get("region") or "eu").lower()
    region_options = "".join(
        f'<option value="{r}"{" selected" if r == cur_region else ""}>{r.upper()}</option>'
        for r in ("na", "eu", "ap", "kr", "latam", "br")
    )

    def _pr(v):
        return v if v is not None else "n/d"

    base = data.get("base", "")
    map_filter = data.get("map_filter", "all")
    return _PAGE.format(
        css=_CSS, js=_JS, name=name, rank=rank, rank_pill=rank_pill, level=level, act=act, gen=gen,
        base=base,
        map_selector=_map_selector(data.get("maps_available"), map_filter),
        map_table=_map_table(data.get("by_map"), base, queue, map_filter),
        queue=queue, qswitch=_queue_switch(queue, base, map_filter), bg_layer=bg_layer,
        userbg=userbg, body_class=body_class, dim=bg_dim,
        region_options=region_options,
        mint=MINT, red=RED,
        wr=ov["win_rate"], wr_color=_accent(ov["win_rate"]),
        wins=ov.get("wins", 0), losses=ov.get("losses", 0), games=ov["games"],
        rwr=(f"{rwr} %" if rwr is not None else "n/d"), round_split=round_split,
        rw=rw, rl=rl, kpis=kpis, map_bars=map_bars, matches=matches_html,
        calendar=_activity_calendar(ov.get("days", {})),
        splits=_splits_section(data.get("splits")),
        agents=agents_html, weapons=weapons_html, precision=precision_html,
        fk=fk, fd=fd, donut=donut, fcs_gauge=fcs_gauge, fc_bars=fc_bars_html,
        fc_weapons=fc_weapons_html,
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
.field input[type=text],.field select{font:inherit;font-weight:600;color:var(--ink);
 background:rgba(255,255,255,.06);border:1px solid var(--brd);border-radius:10px;padding:10px 12px}
.field select{cursor:pointer}
.field select option{background:#12121f;color:var(--ink)}
.fgroup{padding-top:16px}
.fgroup + .fgroup{border-top:1px solid var(--brd);margin-top:6px}
.fg-title{font-size:14px;font-weight:900;margin-bottom:14px}
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
.pill.rk{color:#9fd8ff;border-color:rgba(159,216,255,.42);display:inline-flex;align-items:center;gap:6px;padding-left:6px}
.rk-emblem{width:22px;height:22px;object-fit:contain;filter:drop-shadow(0 1px 3px rgba(0,0,0,.5))}
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
 border-radius:13px;border:1px solid transparent;background:transparent;transition:.16s;
 display:inline-flex;align-items:center;gap:8px}
.tab-ic{width:16px;height:16px;flex:0 0 auto;stroke:currentColor;stroke-width:1.7;fill:none;
 stroke-linecap:round;stroke-linejoin:round}
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
.cols{display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start}
.ov-left{display:flex;flex-direction:column;gap:16px}
.day-sep{display:flex;align-items:baseline;justify-content:space-between;gap:10px;
 margin:14px 0 6px;padding:0 4px 5px;border-bottom:1px solid var(--brd)}
.day-sep:first-child{margin-top:0}
.day-lbl{font-size:12px;font-weight:800;letter-spacing:.02em;text-transform:capitalize}
.day-n{font-size:11px;color:var(--muted);font-weight:700;white-space:nowrap}
.day-n .g{color:var(--mint)}.day-n .l{color:var(--red)}
.match{display:grid;grid-template-columns:26px 30px 1fr 1fr auto auto;align-items:center;gap:12px;
 padding:9px 8px;border-radius:11px;border-left:3px solid transparent}
.match.win{border-left-color:var(--mint);background:linear-gradient(90deg,rgba(55,224,166,.07),transparent 40%)}
.match.loss{border-left-color:var(--red);background:linear-gradient(90deg,rgba(255,70,85,.07),transparent 40%)}
.res{width:24px;height:24px;border-radius:7px;display:grid;place-items:center;font-weight:900;font-size:12px}
.match.win .res{background:rgba(55,224,166,.2);color:var(--mint)}
.match.loss .res{background:rgba(255,70,85,.2);color:var(--red)}
.match.match-new .res{animation:rnewpop 1.6s ease-in-out infinite}
.match.win.match-new{background:linear-gradient(90deg,rgba(55,224,166,.22),transparent 55%)}
.match.win.match-new .res{box-shadow:0 0 0 2px #37E0A6,0 0 12px rgba(55,224,166,.95)}
.match.loss.match-new{background:linear-gradient(90deg,rgba(255,45,64,.22),transparent 55%)}
.match.loss.match-new .res{box-shadow:0 0 0 2px #FF2D40,0 0 12px rgba(255,45,64,.95)}
.m-agent{font-weight:800;font-size:14px}.m-map{color:var(--muted);font-size:14px}
.m-kda{font-variant-numeric:tabular-nums;font-size:14px}
.m-x{font-weight:800;font-size:14px;text-align:right}
.m-x i{display:block;font-style:normal;font-size:10px;color:var(--muted);font-weight:700}

/* calendrier d'activité (heatmap) */
.cal-meta{font-size:12px;color:var(--muted);margin:0 0 10px;font-weight:700}
.cal-scroll{overflow-x:auto;padding-bottom:2px}
.cal{display:inline-block}
.cal-top{display:flex;gap:2px;margin:0 0 4px 18px;height:12px}
.cal-m{flex:0 0 11px;min-width:0;overflow:visible;white-space:nowrap;font-size:9px;color:var(--muted)}
.cal-main{display:flex}
.cal-wd{display:flex;flex-direction:column;gap:2px;width:14px;margin-right:4px}
.cal-wd span{height:11px;line-height:11px;font-size:8px;color:var(--muted);text-align:center}
.cal-cols{display:flex;gap:2px}
.cal-col{display:flex;flex-direction:column;gap:2px}
.cal-cell{width:11px;height:11px;border-radius:2px;background:rgba(255,255,255,.06)}
.cal-l0{background:rgba(255,255,255,.06)}
.cal-l1{background:rgba(55,224,166,.28)}
.cal-l2{background:rgba(55,224,166,.5)}
.cal-l3{background:rgba(55,224,166,.78)}
.cal-l4{background:var(--mint)}
.cal-future{background:rgba(255,255,255,.025)}
.cal-legend{display:flex;align-items:center;gap:4px;margin-top:12px;font-size:11px;color:var(--muted)}
.cal-legend .cal-cell{width:12px;height:12px}
.cal-cell[data-tip]{cursor:default}
.cal-cell[data-tip]:hover{outline:1.5px solid rgba(255,255,255,.6);outline-offset:1px}

/* tooltip flottant */
.tip{position:fixed;z-index:9999;pointer-events:none;left:0;top:0;
 padding:6px 10px;border-radius:9px;font-size:12px;font-weight:700;white-space:nowrap;
 background:rgba(12,10,22,.96);color:var(--ink);border:1px solid var(--brd);
 box-shadow:0 8px 24px rgba(0,0,0,.5);opacity:0;transform:translateY(3px);transition:opacity .12s,transform .12s}
.tip.show{opacity:1;transform:translateY(0)}

/* indicateur discret « nouvelles parties » : petit point rouge */
.refresh,.car-btn{position:relative}
.refresh.has-new::after,.car-btn.tm-hasnew::after{content:"";position:absolute;top:-4px;right:-4px;
 width:9px;height:9px;border-radius:50%;background:var(--red);border:2px solid var(--bg);
 box-shadow:0 0 7px rgba(255,70,85,.85)}
.tm-dot{position:absolute;top:9px;right:9px;width:9px;height:9px;border-radius:50%;z-index:3;
 background:var(--red);box-shadow:0 0 7px rgba(255,70,85,.9),0 0 0 3px rgba(255,70,85,.18)}

/* tableaux Splits (par side / par issue) */
.sp-table{width:100%;border-collapse:collapse}
.sp-table th{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.1em;
 font-weight:800;text-align:right;padding:9px 10px;border-bottom:1px solid var(--brd)}
.sp-table th:first-child{text-align:left}
.sp-table td{padding:10px;text-align:right;font-size:15px;font-weight:800;
 font-variant-numeric:tabular-nums;border-bottom:1px solid rgba(255,255,255,.05)}
.sp-table tr:last-child td{border-bottom:0}
.sp-table td.sp-l{text-align:left;color:var(--muted);font-size:13px;font-weight:700}
.sp-table td.sp-best{color:var(--mint)}
.sp-scroll{overflow-x:auto}
.sp-matrix{min-width:520px}
.sp-matrix th.sp-g{color:#7CF6C6}.sp-matrix th.sp-p{color:#FF8A95}
.sp-matrix td{font-size:14px;padding:9px 10px}

/* sélecteur de carte + tableau par carte */
.mapsel{font:inherit;font-weight:800;font-size:13px;color:var(--ink);cursor:pointer;padding:9px 12px;
 border-radius:12px;border:1px solid var(--brd);background:var(--glass);max-width:180px}
.mapsel option{background:#12121f;color:var(--ink)}
.mp-scroll{overflow-x:auto}
.mp-table{width:100%;border-collapse:collapse;min-width:640px}
.mp-table th{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.09em;font-weight:800;
 text-align:right;padding:10px;border-bottom:1px solid var(--brd)}
.mp-table th:first-child{text-align:left}
.mp-table td{padding:11px 10px;text-align:right;font-size:15px;font-weight:800;
 font-variant-numeric:tabular-nums;border-bottom:1px solid rgba(255,255,255,.05)}
.mp-table td.mp-name{text-align:left;font-size:15px}
.mp-table td.mp-name a{color:var(--ink);text-decoration:none}
.mp-table td.mp-name a:hover{color:var(--cyan)}
.mp-table tr.mp-active{background:linear-gradient(90deg,rgba(34,211,238,.12),transparent 60%)}
.mp-table tr.mp-active td.mp-name a{color:var(--cyan)}
.mp-wl{font-size:11px;color:var(--muted);font-weight:700}

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
.analysis ul,.analysis ol{margin:0 0 10px;padding-left:22px}.analysis li{margin:4px 0;line-height:1.5;font-size:15px}
.analysis strong{color:#fff}
.foot{margin-top:24px;color:var(--muted);font-size:12px;line-height:1.6;text-align:center}

@media (max-width:920px){
 .ovhero{grid-template-columns:1fr}.cols{grid-template-columns:1fr}.agrid{grid-template-columns:repeat(2,1fr)}
 .fchero{grid-template-columns:1fr;justify-items:center}.hero-big{font-size:60px}
 .bar-row{grid-template-columns:120px 1fr 52px}.wrow{grid-template-columns:110px 1fr 50px 56px}
 .match{grid-template-columns:24px 28px 1fr auto auto}.m-map,.m-kda{display:none}
 .prec-leg{flex-wrap:wrap;gap:12px}}
/* Carrière — Destin de rêve VALORANT */
.car-wrap{max-width:760px;margin:0 auto}
.car-hero{text-align:center;padding:14px 0 20px}
.car-hero .kick{font-weight:900;letter-spacing:.22em;font-size:11px;color:#FF4655}
.car-hero h1{font-size:34px;margin:6px 0 4px;letter-spacing:.02em}
.car-hero p{color:var(--muted);margin:0 auto;max-width:440px;line-height:1.5;font-size:14px}
.car-menu{display:flex;flex-direction:column;gap:10px;max-width:340px;margin:18px auto 0}
.car-btn{font:inherit;font-weight:800;font-size:15px;cursor:pointer;padding:14px 18px;border-radius:14px;
 border:1px solid var(--brd);background:var(--glass);color:var(--ink);text-align:center;transition:.15s}
.car-btn:hover{border-color:rgba(255,70,85,.55);transform:translateY(-1px)}
.car-btn.primary{color:#fff;border:0;background:linear-gradient(135deg,#FF4655,#ff2d8e)}
.car-btn.ghost{background:transparent;font-size:13px;padding:10px}
.car-btn:disabled{opacity:.4;cursor:not-allowed;transform:none}
.car-step{color:var(--muted);font-size:12px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;text-align:center}
.car-q{font-size:20px;font-weight:800;text-align:center;margin:6px 0 16px}
.car-opts{display:grid;gap:9px}
.car-opt{cursor:pointer;padding:13px 15px;border-radius:13px;border:1px solid var(--brd);background:var(--glass);transition:.13s}
.car-opt:hover{border-color:rgba(255,70,85,.5)}
.car-opt.sel{border-color:#FF4655;background:rgba(255,70,85,.1)}
.car-opt .t{font-weight:800;font-size:15px}
.car-opt .d{color:var(--muted);font-size:12.5px;margin-top:3px;line-height:1.4}
.car-input{width:100%;font:inherit;font-size:16px;padding:12px 14px;border-radius:12px;box-sizing:border-box;
 background:rgba(255,255,255,.05);border:1px solid var(--brd);color:#fff;margin-bottom:10px}
.car-nav{display:flex;justify-content:space-between;gap:10px;margin-top:18px}
.car-hdr{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:14px}
.car-badge{width:52px;height:52px;border-radius:14px;display:grid;place-items:center;font-size:24px;
 background:linear-gradient(135deg,rgba(255,70,85,.25),rgba(90,209,255,.15));border:1px solid var(--brd);flex:none}
.car-id .nm{font-size:20px;font-weight:900}
.car-id .sub{color:var(--muted);font-size:12.5px}
.car-tags{display:flex;gap:6px;flex-wrap:wrap;margin-left:auto}
.car-tag{font-size:11px;font-weight:800;padding:4px 9px;border-radius:8px;background:var(--glass);border:1px solid var(--brd);color:var(--muted)}
.car-tag.rk{color:#ffd479}
.car-attrs{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:4px 0 16px}
.car-attr{background:var(--glass);border:1px solid var(--brd);border-radius:11px;padding:8px 11px}
.car-attr .l{font-size:10px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.car-attr .v{font-size:16px;font-weight:900}
.car-attr .bar{height:5px;border-radius:4px;background:rgba(255,255,255,.1);overflow:hidden;margin-top:4px}
.car-attr .bar>div{height:100%;background:linear-gradient(90deg,#7CF6C6,#5ad1ff)}
.car-meters{display:flex;gap:14px;flex-wrap:wrap;font-size:12.5px;color:var(--muted);margin-bottom:14px}
.car-meters b{color:var(--ink)}
.car-card{background:var(--glass);border:1px solid var(--brd);border-radius:16px;padding:18px}
.car-card .ev-tag{font-size:10.5px;font-weight:900;letter-spacing:.14em;text-transform:uppercase;color:#FF4655}
.car-card .ev-title{font-size:18px;font-weight:800;margin:5px 0 8px}
.car-card .ev-text{color:#cbd3e0;line-height:1.55;font-size:14px}
.car-choices{display:grid;gap:8px;margin-top:14px}
.car-outcome{margin-top:12px;padding:12px 14px;border-radius:12px;background:rgba(124,246,198,.08);
 border:1px solid rgba(124,246,198,.3);color:#dfeee8;font-size:13.5px;line-height:1.5}
.car-outcome.bad{background:rgba(255,70,85,.08);border-color:rgba(255,70,85,.3);color:#f4d9dd}
.car-log{margin-top:14px;font-size:12.5px;color:var(--muted);line-height:1.7}
.car-log .yr{color:var(--ink);font-weight:800}
.car-delta{font-weight:800}.car-delta.up{color:#7CF6C6}.car-delta.dn{color:#FF6b78}
.car-stars{color:#ffd479;letter-spacing:2px;font-size:15px}
.car-legend{text-align:center}
.car-legend .verdict{font-size:13px;font-weight:900;letter-spacing:.18em;text-transform:uppercase;color:#FF4655}
.car-legend .lname{font-size:32px;font-weight:900;margin:4px 0}
.car-palmares{display:grid;gap:6px;max-width:420px;margin:14px auto;text-align:left}
.car-palmares .tr{display:flex;justify-content:space-between;padding:8px 12px;border-radius:10px;
 background:var(--glass);border:1px solid var(--brd);font-size:13px}
.car-panth{display:grid;gap:8px}
.car-panth .row{display:flex;justify-content:space-between;align-items:center;padding:11px 14px;border-radius:12px;
 background:var(--glass);border:1px solid var(--brd)}
@media(max-width:560px){.car-attrs{grid-template-columns:repeat(2,1fr)}.car-hero h1{font-size:27px}}
/* Team */
.tm-head{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:8px}
.tm-actions{display:flex;gap:8px;flex-wrap:wrap}
.tm-syn{display:flex;gap:10px;flex-wrap:wrap;margin:6px 0 16px}
.tm-syn .s{background:var(--glass);border:1px solid var(--brd);border-radius:12px;padding:9px 14px;min-width:88px}
.tm-syn .s .l{font-size:10px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.tm-syn .s .v{font-size:19px;font-weight:900}
.tm-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}
.tm-card{position:relative;overflow:hidden;background:var(--glass);border:1px solid var(--brd);border-radius:16px;padding:14px}
.tm-card .bg{position:absolute;inset:0;background-size:cover;background-position:top center;opacity:.12;pointer-events:none}
.tm-card>*{position:relative}
.tm-top{display:flex;align-items:center;gap:10px;margin-bottom:10px}
.tm-name{font-weight:900;font-size:16px}
.tm-sub{font-size:12px;color:var(--muted)}
.tm-rank{margin-left:auto;display:flex;align-items:center;gap:8px;font-size:11px;font-weight:800;text-align:right;line-height:1.3}
.tm-rankimg{width:38px;height:38px;object-fit:contain;filter:drop-shadow(0 2px 6px rgba(0,0,0,.5))}
.tm-ranktxt{white-space:nowrap}
.tm-kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:10px}
.tm-k{background:rgba(255,255,255,.04);border:1px solid var(--brd);border-radius:10px;padding:7px 4px;text-align:center}
.tm-k .l{font-size:9px;font-weight:800;letter-spacing:.05em;text-transform:uppercase;color:var(--muted)}
.tm-k .v{font-size:15px;font-weight:900}
.tm-ags{display:flex;gap:6px;align-items:center;margin-bottom:8px;flex-wrap:wrap}
.tm-ag{display:flex;align-items:center;gap:5px;background:rgba(255,255,255,.05);border:1px solid var(--brd);border-radius:20px;padding:3px 9px 3px 3px;font-size:11px}
.tm-ag img{width:20px;height:20px;border-radius:50%}
.tm-form{display:flex;gap:4px}
.tm-form .r{width:16px;height:16px;border-radius:5px;font-size:10px;font-weight:900;display:grid;place-items:center;color:#0a0a12}
.tm-form .r.w{background:#7CF6C6}.tm-form .r.l{background:#FF6b78}
.tm-form .r.rnew{animation:rnewpop 1.6s ease-in-out infinite}
.tm-form .r.w.rnew{box-shadow:0 0 0 2px var(--bg),0 0 0 3px #37E0A6,0 0 9px rgba(55,224,166,.95)}
.tm-form .r.l.rnew{box-shadow:0 0 0 2px var(--bg),0 0 0 3px #FF2D40,0 0 9px rgba(255,45,64,.95)}
@keyframes rnewpop{0%,100%{transform:translateY(0)}50%{transform:translateY(-2px)}}
.tm-empty{color:var(--muted);font-size:13px;padding:14px 0}
.tm-cfg{display:grid;gap:8px;margin-bottom:14px}
.tm-row{display:flex;gap:8px;align-items:center}
.tm-row .idx{width:20px;text-align:center;color:var(--muted);font-weight:800}
.tm-row input{flex:1;font:inherit;font-size:14px;padding:9px 12px;border-radius:10px;box-sizing:border-box;
 background:rgba(255,255,255,.05);border:1px solid var(--brd);color:#fff}
.tm-row select{font:inherit;font-size:13px;padding:9px;border-radius:10px;background:rgba(20,18,32,.9);border:1px solid var(--brd);color:#fff}
.tm-msg{font-size:12.5px;color:var(--muted);min-height:16px;margin-top:2px}
@media(max-width:560px){.tm-kpis{grid-template-columns:repeat(2,1fr)}}
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
 // Tooltip flottant (cases du calendrier, etc.)
 (function(){
   var tip=document.createElement('div'); tip.className='tip'; tip.setAttribute('role','tooltip');
   document.body.appendChild(tip); var on=false;
   document.addEventListener('mouseover',function(e){
     var el=e.target.closest('[data-tip]'); if(!el)return;
     tip.textContent=el.getAttribute('data-tip'); tip.classList.add('show'); on=true;
   });
   document.addEventListener('mousemove',function(e){
     if(!on)return;
     var x=e.clientX+12, y=e.clientY+14;
     if(x+tip.offsetWidth>window.innerWidth-8) x=e.clientX-tip.offsetWidth-12;
     tip.style.left=x+'px'; tip.style.top=y+'px';
   });
   document.addEventListener('mouseout',function(e){
     if(e.target.closest('[data-tip]')){ tip.classList.remove('show'); on=false; }
   });
 })();

 // Indicateur « nouvelles parties depuis la dernière MAJ » (Vue d'ensemble) : point rouge
 (function(){
   var rb=document.getElementById('refresh'); if(!rb)return;
   fetch(BASE+'/api/updates?queue='+QUEUE).then(function(r){return r.json()}).then(function(j){
     if(j&&j.new>0){
       rb.classList.add('has-new');
       rb.title=j.new+' nouvelle(s) partie'+(j.new>1?'s':'')+' depuis la dernière mise à jour';
     }
   }).catch(function(){});
 })();

 var btn=document.getElementById('refresh');
 if(btn){var base=btn.textContent;btn.addEventListener('click',function(){
   btn.disabled=true;btn.textContent='⏳ Mise a jour...';
   fetch(BASE+'/api/refresh?queue='+QUEUE,{method:'POST'})
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
       fetch(BASE+'/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({dim:parseInt(dim.value,10)})}).catch(function(){});
     },400);
   })}
   var af=document.getElementById('bg-apply'), fi=document.getElementById('bg-file');
   if(af){af.addEventListener('click',function(){
     if(!fi.files||!fi.files[0]){modal.classList.remove('open');return}
     var fd=new FormData();fd.append('bg',fi.files[0]);
     af.disabled=true;af.textContent='Envoi...';
     fetch(BASE+'/api/background',{method:'POST',body:fd}).then(function(r){return r.json()})
      .then(function(j){if(j.error){af.textContent='⚠ '+j.error;af.disabled=false;}
        else{location.reload()}})
      .catch(function(){af.textContent='⚠ Serveur requis';af.disabled=false});
   })}
   var rb=document.getElementById('bg-reset');
   if(rb){rb.addEventListener('click',function(){
     fetch(BASE+'/api/background/reset',{method:'POST'}).then(function(){location.reload()}).catch(function(){});
   })}
   var ta=document.getElementById('target-apply'), ri=document.getElementById('riot-id'),
       rg=document.getElementById('region');
   if(ta){ta.addEventListener('click',function(){
     var rid=(ri.value||'').trim();
     if(rid.indexOf('#')<1){ta.textContent='⚠ Format Pseudo#TAG';
       setTimeout(function(){ta.textContent='Charger ce compte'},2200);return;}
     ta.disabled=true;ta.textContent='⏳ Chargement du compte...';
     fetch(BASE+'/api/target',{method:'POST',headers:{'Content-Type':'application/json'},
       body:JSON.stringify({riot_id:rid,region:rg.value})})
      .then(function(r){return r.json()})
      .then(function(j){if(j.error){ta.textContent='⚠ '+j.error;ta.disabled=false;return;}
        ta.textContent='⏳ Téléchargement des parties...';
        return fetch(BASE+'/api/refresh?queue='+QUEUE,{method:'POST'})
          .then(function(){location.href=BASE+'/?queue='+QUEUE});})
      .catch(function(){ta.textContent='⚠ Serveur requis';ta.disabled=false});
   })}
 }
})();

/* ============ Carrière — Destin de rêve VALORANT ============ */
(function(){
 var root=document.getElementById('career-root');
 if(!root) return;
 var K='car_save_v1', KP='car_panth_v1';
 var G=null;

 function rnd(a,b){return Math.floor(Math.random()*(b-a+1))+a;}
 function pick(a){return a[Math.floor(Math.random()*a.length)];}
 function clamp(v){return Math.max(0,Math.min(100,Math.round(v)));}
 function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
 function stars(n){var s='';for(var i=0;i<5;i++)s+=i<n?'★':'☆';return s;}

 var COUNTRIES=[['🇫🇷 France','emea'],['🇬🇧 Royaume-Uni','emea'],['🇹🇷 Turquie','emea'],['🇸🇪 Suède','emea'],
   ['🇪🇸 Espagne','emea'],['🇺🇸 USA','americas'],['🇧🇷 Brésil','americas'],['🇨🇦 Canada','americas'],
   ['🇰🇷 Corée','pacific'],['🇯🇵 Japon','pacific'],['🇨🇳 Chine','pacific'],['🇮🇩 Indonésie','pacific']];
 var ROLES={
   duelist:{lbl:'Duelliste',emo:'⚔️',bias:{aim:12,clutch:8,team:-4}},
   controller:{lbl:'Contrôleur',emo:'🌫️',bias:{iq:10,team:8,aim:-3}},
   initiator:{lbl:'Initiateur',emo:'🎯',bias:{iq:8,team:6,clutch:2}},
   sentinel:{lbl:'Sentinelle',emo:'🛡️',bias:{iq:6,mental:8,team:4,aim:-2}}};
 var ORIGINS=[
   {id:'cs',t:'Transfuge de CS:GO',d:'Un aim déjà taillé, mais des habitudes à désapprendre.',fx:{aim:14,mental:6,team:-6}},
   {id:'prodige',t:'Prodige FPS',d:'Des réflexes hors normes repérés très tôt.',fx:{aim:12,clutch:10,mental:-4}},
   {id:'igl',t:'Cerveau tactique',d:'Tu lis le jeu mieux que quiconque ; l’aim suivra.',fx:{iq:16,team:8,aim:-6}},
   {id:'grind',t:'Roi du ranked',d:'Radiant à la sueur, douze heures par jour.',fx:{aim:8,form:10,mental:-6}},
   {id:'academie',t:'Académie structurée',d:'Formé proprement, sans excès ni lacune.',fx:{team:10,iq:8,mental:4}}];
 var LIVES=[
   {id:'fer',t:'Discipline de fer',d:'Sommeil, sport, régularité. L’usure viendra tard.',fx:{mental:12,form:4,fame:-4}},
   {id:'eq',t:'Équilibré',d:'Ni moine ni fêtard.',fx:{mental:4}},
   {id:'nuit',t:'Noctambule grinder',d:'Des sessions de folie… et un corps qui trinque.',fx:{aim:8,form:6,mental:-8}}];
 var ENTOURAGE=[
   {id:'mentor',t:'Un coach mentor',d:'Quelqu’un qui croit en toi et te structure.',fx:{iq:8,mental:8}},
   {id:'famille',t:'Famille sceptique',d:'« Trouve un vrai métier. » Ça forge le caractère.',fx:{mental:12,morale:-10}},
   {id:'reseaux',t:'Star des réseaux',d:'Déjà une commu, déjà une image à tenir.',fx:{fame:20,mental:-6}}];
 var TEAMS={
   emea:{vct:['Fnatic','Team Vitality','Team Heretics','Karmine Corp','Team Liquid','NAVI','FUT','KOI','BBL','GiantX'],
         chg:['Los Ratones','Apeks','Gentle Mates','Case Esports','Zeta Nova','Diamant Épée']},
   americas:{vct:['Sentinels','LOUD','NRG','G2 Esports','Leviatán','MIBR','KRÜ','Cloud9','Evil Geniuses','100 Thieves'],
         chg:['The Guard','Oxygen','M80','Shopify Rebellion','FlyQuest','Moist']},
   pacific:{vct:['Paper Rex','DRX','T1','Gen.G','Team Secret','Rex Regum Qeon','Global Esports','Talon','ZETA','BLEED'],
         chg:['BOOM','NongShim RedForce','Alter Ego','Dewa United','Reject','Nairo']}};
 var REGN={emea:'EMEA',americas:'Americas',pacific:'Pacific'};

 // ---- pool d'événements narratifs ----
 var EVENTS=[
  {tag:'Vestiaire',title:'Le rookie face au vétéran',text:'Un cadre de l’équipe critique ta prise d’espace en review. Devant tout le monde.',
   ch:[{t:'Encaisser et bosser en silence',fx:{mental:6,team:5,morale:-4},out:'Tu ravales, tu notes, tu progresses. Le staff apprécie ton sang-froid.'},
       {t:'Défendre ta lecture, calmement',fx:{team:-3,iq:5,fame:2},out:'Tu tiens ta position, arguments à l’appui. Certains grincent, d’autres respectent.'},
       {t:'Répondre du tac au tac',fx:{team:-8,morale:5,mental:-2},out:'Ambiance électrique. Tu te sens vivant, mais le vestiaire se fissure.',bad:true}]},
  {tag:'Contenu',title:'Stream ou scrims ?',text:'Ta chaîne explose. Un soir de gros scrims tombe pile sur ton créneau le plus rentable.',
   ch:[{t:'Priorité aux scrims',fx:{team:6,iq:4,fame:-5},out:'Le coach te remarque. La commu boude un peu.'},
       {t:'Un stream, vite fait',fx:{fame:8,form:-3},out:'Chiffres records… nuit trop courte.'},
       {t:'Stream ET scrims, nuit blanche',fx:{fame:6,form:-6,mental:-4},out:'Tu fais tout. Ton corps envoie la facture.',bad:true}]},
  {tag:'Méta',title:'Ton agent signature est nerfé',text:'Le patch massacre le perso sur lequel tu as bâti ta réputation.',
   ch:[{t:'Apprendre un nouveau rôle',fx:{iq:8,team:6,form:-4},out:'Semaines difficiles, mais tu élargis ton arsenal.'},
       {t:'Forcer ton perso quand même',fx:{aim:4,team:-5},out:'Par orgueil. Résultats en dents de scie.',bad:true},
       {t:'Suivre la méta à la lettre',fx:{team:4,iq:3},out:'Pragmatique. Efficace, sans éclat.'}]},
  {tag:'Sponsor',title:'Une marque veut ton visage',text:'Un équipementier propose un gros contrat d’image, avec obligations média.',
   ch:[{t:'Signer, l’argent d’abord',fx:{money:40000,fame:12,form:-3},out:'Compte en banque ravi, agenda surchargé.'},
       {t:'Négocier version light',fx:{money:18000,fame:5},out:'Un bon compromis, présenté par ton agent.'},
       {t:'Refuser, focus jeu',fx:{iq:4,team:4,fame:-3},out:'Tes coéquipiers valident ce choix de pro.'}]},
  {tag:'Mental',title:'Le doute après une contre-perf',text:'Un LAN raté. Les réseaux s’acharnent. Tu ne dors plus.',
   ch:[{t:'Voir la psy de l’équipe',fx:{mental:12,morale:8,money:-3000},out:'Parler dénoue tout. Tu reviens plus solide.'},
       {t:'Serrer les dents seul',fx:{mental:-6,form:-4},out:'Tu tiens… en surface.',bad:true},
       {t:'Couper les réseaux 1 mois',fx:{mental:8,fame:-8,morale:5},out:'Silence radio salvateur, hype en pause.'}]},
  {tag:'Leadership',title:'On te propose l’IGL',text:'Le calleur part. Le staff pense à toi pour diriger le jeu.',
   ch:[{t:'Accepter le rôle d’IGL',fx:{iq:12,team:10,aim:-4,mental:-3},out:'Charge mentale énorme, mais tu grandis vite.'},
       {t:'Refuser, rester fragger',fx:{aim:6,clutch:4},out:'Tu restes dans ta zone de confort meurtrière.'}]},
  {tag:'Blessure',title:'Douleur au poignet',text:'Des fourmillements pendant les entraînements. Le médecin est prudent.',
   ch:[{t:'Repos complet 3 semaines',fx:{form:-8,aim:-2,mental:4},out:'Tu manques des matchs, mais tu sauves ta main.'},
       {t:'Infiltration et on continue',fx:{form:6,mental:-6,aim:-4},out:'Tu joues… le poignet s’en souviendra.',bad:true}]},
  {tag:'Transfert',title:'Un rival te tend la main',text:'En coulisses d’un LAN, la star adverse te glisse : « Viens chez nous. »',
   ch:[{t:'Écouter en secret',fx:{fame:4,team:-4},out:'Rumeurs de mercato… l’équipe le sent.'},
       {t:'Rester loyal',fx:{team:8,morale:6},out:'Ta parole vaut de l’or dans le milieu.'}]},
  {tag:'Vie perso',title:'Ta famille s’inquiète',text:'Tes proches trouvent que tu t’isoles dans le gaming house.',
   ch:[{t:'Prendre un vrai week-end off',fx:{morale:10,mental:6,form:-2},out:'Tu reviens rechargé.'},
       {t:'Rester grind',fx:{aim:4,form:3,morale:-6},out:'Le classement grimpe, le moral baisse.',bad:true}]},
  {tag:'Communauté',title:'Un fan en détresse',text:'Un jeune t’écrit que tes matchs l’ont aidé à traverser une année sombre.',
   ch:[{t:'Prendre le temps de répondre',fx:{morale:8,fame:4},out:'Un moment qui te rappelle pourquoi tu joues.'},
       {t:'Un like et on passe',fx:{fame:1},out:'Le flux est incessant, tu fais au mieux.'}]},
  {tag:'Discipline',title:'Clash sur les réseaux',text:'Tu balances un tweet cash sur un adversaire après une défaite.',
   ch:[{t:'Assumer et t’excuser vite',fx:{fame:3,mental:4},out:'Tu désamorces proprement.'},
       {t:'En rajouter une couche',fx:{fame:10,team:-6,morale:4},out:'Buzz énorme, staff furieux.',bad:true},
       {t:'Supprimer, faire profil bas',fx:{fame:-4,mental:2},out:'Trop tard pour les captures, mais l’orage passe.'}]},
  {tag:'Staff',title:'Nouveau coach, nouvelle philosophie',text:'Le coach arrivé veut tout changer dans ton rôle.',
   ch:[{t:'Adhérer à 100%',fx:{iq:8,team:6,form:-3},out:'Transition rude, système plus solide.'},
       {t:'Garder tes automatismes',fx:{aim:4,team:-4},out:'Frictions en review.',bad:true}]}
 ];
 // moments décisifs (skill-check), tirés aux gros stages
 var DECISIVE=[
  {tag:'Moment décisif',title:'Balle de match en finale',text:'12-12, dernier round de la grande finale. Le clutch 1v1 est pour toi.',
   stat:function(p){return p.attrs.clutch*0.6+p.attrs.aim*0.4+p.morale*0.15;},thr:70,
   win:'Tu poses la balle, tu tires, tu gagnes. Le stade explose. LÉGENDE.',
   lose:'La main tremble d’un rien. Si près. La salle retient son souffle, puis soupire.',
   fxWin:{fame:18,clutch:6,mental:6,morale:12},fxLose:{mental:-8,morale:-10,clutch:3}},
  {tag:'Moment décisif',title:'Nerfs d’acier au micro',text:'Timeout, égalité, tout le monde panique. À toi de reprendre le call.',
   stat:function(p){return p.attrs.iq*0.5+p.attrs.mental*0.4+p.attrs.team*0.2;},thr:66,
   win:'Ton call clair remet l’équipe dans le match. Retournement total.',
   lose:'Le message passe mal, le round part en fumée.',
   fxWin:{iq:6,team:8,fame:8,morale:8},fxLose:{team:-4,morale:-8}}
 ];

 function save(){try{localStorage.setItem(K,JSON.stringify(G));}catch(e){}}
 function load(){try{return JSON.parse(localStorage.getItem(K));}catch(e){return null;}}
 function panth(){try{return JSON.parse(localStorage.getItem(KP))||[];}catch(e){return [];}}
 function pushPanth(l){var a=panth();a.unshift(l);try{localStorage.setItem(KP,JSON.stringify(a.slice(0,30)));}catch(e){}}

 function capFor(p,k){ // plafond de talent : le potentiel borne VRAIMENT les skills
   if(k==='aim'||k==='clutch')return p.cap;
   if(k==='iq'||k==='team')return p.cap+6;
   if(k==='mental')return p.cap+18;
   return 100;
 }
 function applyFx(p,fx){for(var k in fx){
   if(k==='money'){p.money+=fx[k];}
   else if(k==='fame'){p.fame=clamp(p.fame+fx[k]);}
   else if(k==='morale'){p.morale=clamp(p.morale+fx[k]);}
   else if(p.attrs[k]!=null){p.attrs[k]=Math.max(0,Math.min(capFor(p,k),Math.round(p.attrs[k]+fx[k])));}
 }}

 // ---------------- écrans ----------------
 function screenHome(){
   var has=load(), p=panth();
   var h='<div class="car-hero"><div class="kick">MODE CARRIÈRE</div>'
     +'<h1>Destin de rêve <span style="color:#FF4655">VALORANT</span></h1>'
     +'<p>Crée un joueur de 16 ans et vis toute sa carrière esport, saison après saison : '
     +'choix décisifs, transferts, gloire et chutes… jusqu’à sa carte de légende.</p></div>'
     +'<div class="car-menu">';
   if(has) h+='<button class="car-btn primary" data-a="resume">▶ Reprendre — '+esc(has.p.name)+' ('+has.p.age+' ans)</button>';
   h+='<button class="car-btn'+(has?'':' primary')+'" data-a="new">＋ Nouvelle carrière</button>';
   h+='<button class="car-btn ghost" data-a="panth">🏛️ Panthéon ('+p.length+')</button>';
   h+='</div>';
   root.innerHTML=h;
 }

 var draft=null;
 function screenCreate(step){
   draft=draft||{name:'',country:null,role:null,origin:null,life:null,ent:null};
   var steps=['name','role','origin','life','ent','confirm'];
   step=step||0; draft._step=step;
   var h='<div class="car-step">Création · étape '+(step+1)+'/6</div>';
   if(step===0){
     h+='<div class="car-q">Ton identité</div>'
       +'<input class="car-input" id="c-name" maxlength="16" placeholder="Pseudo (ex: nAts, Derke…)" value="'+esc(draft.name)+'">'
       +'<div class="car-opts">'+COUNTRIES.map(function(c,i){
         return '<div class="car-opt'+(draft.country===i?' sel':'')+'" data-country="'+i+'"><span class="t">'+c[0]+'</span></div>';
       }).join('')+'</div>';
   } else if(step===1){
     h+='<div class="car-q">Ton rôle sur le serveur</div><div class="car-opts">'
       +Object.keys(ROLES).map(function(k){var r=ROLES[k];
         return '<div class="car-opt'+(draft.role===k?' sel':'')+'" data-role="'+k+'"><div class="t">'+r.emo+' '+r.lbl+'</div></div>';
       }).join('')+'</div>';
   } else if(step===2){ h+=optList('D’où viens-tu ?',ORIGINS,'origin',draft.origin); }
   else if(step===3){ h+=optList('Ton hygiène de vie',LIVES,'life',draft.life); }
   else if(step===4){ h+=optList('Ton entourage',ENTOURAGE,'ent',draft.ent); }
   else { // confirm
     h+='<div class="car-q">Prêt à écrire ta légende ?</div>'
       +'<div class="car-card"><div class="ev-text">'
       +'<b>'+esc(draft.name||'Rookie')+'</b> · '+COUNTRIES[draft.country][0]+'<br>'
       +ROLES[draft.role].emo+' '+ROLES[draft.role].lbl+' · '+ORIGINS.find(o=>o.id===draft.origin).t+'<br>'
       +LIVES.find(o=>o.id===draft.life).t+' · '+ENTOURAGE.find(o=>o.id===draft.ent).t
       +'<br><br>Ton potentiel réel reste caché : seuls les scouts le devineront, au fil des saisons.</div></div>';
   }
   h+='<div class="car-nav"><button class="car-btn ghost" data-nav="back">'+(step===0?'← Menu':'← Retour')+'</button>';
   h+='<button class="car-btn primary" data-nav="next" id="c-next">'+(step===5?'🚀 Lancer la carrière':'Continuer →')+'</button></div>';
   root.innerHTML=h;
 }
 function optList(q,arr,key,cur){
   return '<div class="car-q">'+q+'</div><div class="car-opts">'+arr.map(function(o){
     return '<div class="car-opt'+(cur===o.id?' sel':'')+'" data-opt="'+key+'" data-id="'+o.id+'">'
       +'<div class="t">'+o.t+'</div><div class="d">'+o.d+'</div></div>';}).join('')+'</div>';
 }
 function createValid(){
   var s=draft._step;
   if(s===0)return draft.name.trim().length>0&&draft.country!=null;
   if(s===1)return !!draft.role; if(s===2)return !!draft.origin;
   if(s===3)return !!draft.life; if(s===4)return !!draft.ent; return true;
 }

 function startGame(){
   var base={aim:45,iq:45,mental:45,clutch:45,team:45,form:58};
   applyDelta(base,ROLES[draft.role].bias);
   var pot=weightedPot();
   var p={name:draft.name.trim(),country:COUNTRIES[draft.country][0],region:COUNTRIES[draft.country][1],
     role:draft.role,age:16,attrs:base,fame:20,morale:60,money:0,
     potential:pot,cap:44+pot*7,potShown:false,tier:'chg',team:null,
     palmares:[],history:[],peak:0,retired:false};
   applyFx(p,ORIGINS.find(o=>o.id===draft.origin).fx);
   applyFx(p,LIVES.find(o=>o.id===draft.life).fx);
   applyFx(p,ENTOURAGE.find(o=>o.id===draft.ent).fx);
   p.team=pick(TEAMS[p.region].chg);
   G={p:p,season:1,screen:'season',phase:null,queue:[],cur:null,lastOut:null,result:null,offers:null};
   draft=null; save(); startSeason();
 }
 function applyDelta(a,fx){for(var k in fx)if(a[k]!=null)a[k]=clamp(a[k]+fx[k]);}
 function weightedPot(){var r=Math.random();return r<0.06?5:r<0.22?4:r<0.55?3:r<0.85?2:1;}

 function startSeason(){
   var p=G.p; var n=rnd(2,3), q=[];
   var pool=EVENTS.slice();
   for(var i=0;i<n;i++){var e=pick(pool);pool.splice(pool.indexOf(e),1);q.push({type:'ev',e:e});}
   // moment décisif si bon niveau / gros stage
   if(p.tier==='vct'&&Math.random()<0.5) q.push({type:'dec',e:pick(DECISIVE)});
   G.queue=q; G.phase='events'; G.cur=null; G.lastOut=null; G.screen='season';
   save(); nextStep();
 }
 function nextStep(){
   if(G.queue.length===0){ simulate(); return; }
   G.cur=G.queue.shift(); G.lastOut=null; render();
 }

 function header(){
   var p=G.p;
   var pot=p.potShown?'<span class="car-tag rk" title="Potentiel estimé">'+stars(p.potential)+'</span>':'';
   return '<div class="car-hdr"><div class="car-badge">'+ROLES[p.role].emo+'</div>'
     +'<div class="car-id"><div class="nm">'+esc(p.name)+'</div>'
     +'<div class="sub">'+esc(p.team)+' · '+REGN[p.region]+' · '+(p.tier==='vct'?'VCT':'Challengers')+'</div></div>'
     +'<div class="car-tags"><span class="car-tag">'+p.age+' ans</span>'
     +'<span class="car-tag">Saison '+G.season+'</span>'+pot+'</div></div>';
 }
 function attrsHtml(){
   var p=G.p, A=[['aim','Aim'],['iq','Game Sense'],['clutch','Clutch'],['team','Teamplay'],['mental','Mental'],['form','Forme']];
   return '<div class="car-attrs">'+A.map(function(a){var v=p.attrs[a[0]];
     return '<div class="car-attr"><div class="l">'+a[1]+'</div><div class="v">'+v+'</div>'
       +'<div class="bar"><div style="width:'+v+'%"></div></div></div>';}).join('')+'</div>'
     +'<div class="car-meters"><span>🔥 Notoriété <b>'+p.fame+'</b></span>'
     +'<span>🙂 Moral <b>'+p.morale+'</b></span><span>💰 <b>'+p.money.toLocaleString('fr-FR')+' €</b></span>'
     +'<span>🏆 <b>'+p.palmares.length+'</b> titre(s)</span></div>';
 }

 function render(){
   if(G.screen==='season'){
     var h=header()+attrsHtml();
     var step=G.cur;
     if(!step){ root.innerHTML=h; return; }
     var e=step.e;
     h+='<div class="car-card"><div class="ev-tag">'+e.tag+'</div>'
       +'<div class="ev-title">'+e.title+'</div><div class="ev-text">'+e.text+'</div>';
     if(G.lastOut){
       h+='<div class="car-outcome'+(G.lastOut.bad?' bad':'')+'">'+G.lastOut.txt+'</div>'
         +'<div class="car-nav"><span></span><button class="car-btn primary" data-nav="cont">Continuer →</button></div>';
     } else if(step.type==='dec'){
       h+='<div class="car-choices"><button class="car-btn" data-dec="1">Tenter le moment décisif</button></div>';
     } else {
       h+='<div class="car-choices">'+e.ch.map(function(c,i){
         return '<button class="car-btn" data-ch="'+i+'">'+c.t+'</button>';}).join('')+'</div>';
     }
     h+='</div>';
     root.innerHTML=h;
   } else if(G.screen==='result'){ renderResult(); }
   else if(G.screen==='mercato'){ renderMercato(); }
   else if(G.screen==='legend'){ renderLegend(); }
 }

 function chooseEvent(i){
   var c=G.cur.e.ch[i]; applyFx(G.p,c.fx);
   G.lastOut={txt:c.out,bad:!!c.bad}; save(); render();
 }
 function doDecisive(){
   var d=G.cur.e, p=G.p, sc=d.stat(p)+rnd(-10,10), ok=sc>=d.thr;
   applyFx(p, ok?d.fxWin:d.fxLose);
   if(ok) p._decWin=(p._decWin||0)+1;
   G.lastOut={txt:(ok?d.win:d.lose),bad:!ok}; save(); render();
 }

 function coreRating(p){
   return p.attrs.aim*0.30+p.attrs.clutch*0.18+p.attrs.iq*0.22+p.attrs.team*0.15+p.attrs.form*0.15;
 }
 function simulate(){
   var p=G.p, core=coreRating(p);
   var rating=clamp(core*(0.90+p.morale/700)+rnd(-5,6));
   if(rating>p.peak)p.peak=rating;
   var year=2026+(G.season-1);
   var titles=[], promo=false, releg=false, place;
   if(p.tier==='chg'){
     if(rating>=70&&Math.random()<0.55){titles.push('Champion Challengers '+REGN[p.region]+' '+year);place='🥇 1er';promo=Math.random()<0.6;}
     else if(rating>=58){place='Top 4';promo=rating>=64&&Math.random()<0.4;}
     else if(rating>=46){place='Milieu de tableau';}
     else {place='Bas de tableau';}
   } else {
     if(rating>=86&&Math.random()<0.3){titles.push('🌍 Champion du Monde '+year+' (Champions)');place='🏆 Champion du monde';}
     else if(rating>=80&&Math.random()<0.38){titles.push('Masters '+year);place='Vainqueur Masters';}
     else if(rating>=73&&Math.random()<0.5){titles.push('VCT '+REGN[p.region]+' '+year);place='🥇 Champion régional';}
     else if(rating>=60){place='Playoffs';}
     else if(rating>=48){place='Phase de groupes';}
     else {place='Éliminé tôt';releg=Math.random()<0.45;}
   }
   // récompenses
   var fameGain=Math.round((rating-45)*0.4+(p.tier==='vct'?6:2)+titles.length*10);
   p.fame=clamp(p.fame+fameGain);
   var salary=(p.tier==='vct'?60000:12000)+Math.round(p.fame*400);
   var prize=titles.length*(p.tier==='vct'?50000:8000);
   p.money+=salary+prize;
   p.morale=clamp(p.morale+(titles.length?12:(rating>=56?3:-6)));
   p.palmares=p.palmares.concat(titles);
   // croissance / vieillissement
   grow(p);
   p.history.push({season:G.season,year:year,team:p.team,tier:p.tier,rating:rating,place:place,titles:titles});
   if(!p.potShown&&G.season>=2)p.potShown=true;
   G.result={rating:rating,place:place,titles:titles,fameGain:fameGain,salary:salary,prize:prize,promo:promo,releg:releg};
   G.screen='result'; save(); render();
 }
 function grow(p){
   var cap=p.cap;                         // pot 1→51 … 5→79 : le talent plafonne
   var young=p.age<=23, prime=p.age<=26;
   ['aim','clutch'].forEach(function(k){
     if(young&&p.attrs[k]<cap)p.attrs[k]=clamp(p.attrs[k]+Math.min(cap-p.attrs[k],rnd(1,4)));
     else if(!prime)p.attrs[k]=clamp(p.attrs[k]-rnd(1,4));   // déclin des réflexes
   });
   ['iq','team'].forEach(function(k){ if(p.age<=29&&p.attrs[k]<cap+6)p.attrs[k]=clamp(p.attrs[k]+rnd(1,3)); });
   p.attrs.mental=clamp(p.attrs.mental+(p.morale>60?1:-1));
   p.attrs.form=clamp(58+rnd(-9,9)-(p.age>27?(p.age-27)*4:0));
 }

 function renderResult(){
   var p=G.p, r=G.result;
   var h=header();
   h+='<div class="car-card"><div class="ev-tag">Bilan · Saison '+G.season+'</div>'
     +'<div class="ev-title">Note de saison : '+r.rating+'/100</div>'
     +'<div class="ev-text">Résultat : <b>'+r.place+'</b>'
     +(r.titles.length?'<br>🏆 '+r.titles.map(esc).join('<br>🏆 '):'')
     +'<br><br>Notoriété <span class="car-delta '+(r.fameGain>=0?'up">+':'dn">')+r.fameGain+'</span>'
     +' · Gains <b>'+(r.salary+r.prize).toLocaleString('fr-FR')+' €</b>'
     +(r.promo?'<br><span class="car-delta up">↑ Une équipe VCT s’intéresse à toi !</span>':'')
     +(r.releg?'<br><span class="car-delta dn">↓ Ton équipe vacille…</span>':'')
     +'</div>';
   h+='<div class="car-nav"><span></span><button class="car-btn primary" data-nav="mercato">Mercato →</button></div></div>';
   root.innerHTML=h;
 }

 function buildOffers(){
   var p=G.p, offers=[], r=G.result;
   var vctOK=(p.tier==='vct')||r.promo||p.fame>=60;
   if(vctOK){ var pool=TEAMS[p.region].vct.filter(function(t){return t!==p.team;});
     for(var i=0;i<2;i++){var t=pick(pool);pool.splice(pool.indexOf(t),1);
       offers.push({team:t,tier:'vct',salary:80000+rnd(0,120)*1000,txt:'Projet VCT ambitieux'});}}
   // rester
   if(!r.releg||p.tier==='chg') offers.push({team:p.team,tier:p.tier,salary:(p.tier==='vct'?70000:14000),txt:'Rester, fidèle à ton équipe',stay:true});
   // une option challengers si en difficulté
   if(p.tier==='vct'&&r.releg){var cp=pick(TEAMS[p.region].chg);offers.push({team:cp,tier:'chg',salary:16000,txt:'Rebond en Challengers'});}
   if(p.tier==='chg'){var cp2=TEAMS[p.region].chg.filter(function(t){return t!==p.team;});offers.push({team:pick(cp2),tier:'chg',salary:15000,txt:'Nouveau projet Challengers'});}
   return offers;
 }
 function renderMercato(){
   var p=G.p;
   if(!G.offers)G.offers=buildOffers();
   var h=header()+'<div class="car-q" style="margin-top:4px">Mercato — quelle est la suite ?</div>';
   h+='<div class="car-opts">'+G.offers.map(function(o,i){
     return '<div class="car-opt" data-offer="'+i+'"><div class="t">'+(o.tier==='vct'?'🏆 ':'')+esc(o.team)
       +' <span style="color:var(--muted);font-weight:600">· '+(o.tier==='vct'?'VCT':'Challengers')+'</span></div>'
       +'<div class="d">'+o.txt+' — '+o.salary.toLocaleString('fr-FR')+' €/an</div></div>';}).join('')+'</div>';
   if(p.age>=27) h+='<div class="car-nav"><button class="car-btn ghost" data-retire="1">🎬 Prendre sa retraite</button><span></span></div>';
   root.innerHTML=h;
 }
 function chooseOffer(i){
   var o=G.offers[i], p=G.p;
   p.team=o.team; p.tier=o.tier;
   G.offers=null; G.result=null; G.season++; p.age++;
   if(forcedRetire(p)){ retire('age'); return; }
   startSeason();
 }
 function forcedRetire(p){ return p.age>=30 || (p.age>=27&&p.attrs.form<40) || p.morale<=6; }

 function retire(reason){
   var p=G.p;
   var champ=p.palmares.filter(function(t){return t.indexOf('Champion du Monde')>=0;}).length;
   var masters=p.palmares.filter(function(t){return t.indexOf('Masters')>=0;}).length;
   var reg=p.palmares.filter(function(t){return t.indexOf('VCT ')>=0;}).length;
   var chg=p.palmares.filter(function(t){return t.indexOf('Challengers')>=0;}).length;
   var score=champ*7+masters*4+reg*1.4+chg*0.5+(p._decWin||0)*0.4+Math.max(0,p.peak-55)/12+p.fame/45;
   var verdict,st;
   if(score>=22){verdict='LÉGENDE ÉTERNELLE';st=5;}
   else if(score>=13){verdict='STAR MONDIALE';st=4;}
   else if(score>=7){verdict='JOUEUR SOLIDE';st=3;}
   else if(score>=3){verdict='JOURNEYMAN';st=2;}
   else {verdict='MÉTÉORE';st=1;}
   var legend={name:p.name,country:p.country,role:ROLES[p.role].lbl,years:(2026)+'–'+(2026+G.season-1),
     age:p.age,peak:p.peak,fame:p.fame,titles:p.palmares.slice(),verdict:verdict,stars:st,
     teams:[].concat.apply([],[p.history.map(function(h){return h.team;})]).filter(function(v,i,a){return a.indexOf(v)===i;})};
   G.legendCard=legend; G.screen='legend';
   pushPanth(legend);
   try{localStorage.removeItem(K);}catch(e){}
   render();
 }
 function renderLegend(){
   var l=G.legendCard;
   var h='<div class="car-legend"><div class="verdict">'+l.verdict+'</div>'
     +'<div class="lname">'+esc(l.name)+'</div>'
     +'<div class="car-stars">'+stars(l.stars)+'</div>'
     +'<div class="car-meters" style="justify-content:center;margin-top:10px">'
     +'<span>'+l.country+'</span><span>'+l.role+'</span><span>'+l.years+'</span>'
     +'<span>Pic '+l.peak+'/100</span><span>🔥 '+l.fame+'</span></div>';
   if(l.titles.length){ h+='<div class="car-palmares">'
     +l.titles.map(function(t){return '<div class="tr"><span>🏆 '+esc(t)+'</span></div>';}).join('')
     +'</div>'; } else { h+='<p class="muted mini">Aucun titre majeur — mais chaque carrière raconte une histoire.</p>'; }
   h+='<p class="muted mini" style="margin-top:8px">Équipes : '+l.teams.map(esc).join(' · ')+'</p>';
   h+='<div class="car-menu"><button class="car-btn primary" data-a="new">＋ Nouvelle carrière</button>'
     +'<button class="car-btn ghost" data-a="panth">🏛️ Voir le panthéon</button></div></div>';
   root.innerHTML=h;
 }
 function renderPanth(){
   var a=panth();
   var h='<div class="car-step">Panthéon</div><div class="car-q">Tes légendes</div>';
   if(!a.length){ h+='<p class="muted" style="text-align:center">Aucune carrière terminée pour l’instant.</p>'; }
   else { h+='<div class="car-panth">'+a.map(function(l){
     return '<div class="row"><div><b>'+esc(l.name)+'</b> <span class="car-stars">'+stars(l.stars)+'</span>'
       +'<div class="sub" style="color:var(--muted);font-size:12px">'+l.verdict+' · '+l.country+' · '+l.role+' · '+l.titles.length+' titre(s)</div></div>'
       +'<div style="text-align:right;color:var(--muted);font-size:12px">'+l.years+'</div></div>';}).join('')+'</div>'; }
   h+='<div class="car-nav"><button class="car-btn ghost" data-a="home">← Menu</button><span></span></div>';
   root.innerHTML=h;
 }

 // ---------------- routing / clics ----------------
 root.addEventListener('click',function(ev){
   var t=ev.target.closest('[data-a],[data-nav],[data-ch],[data-dec],[data-offer],[data-retire],[data-country],[data-role],[data-opt]');
   if(!t)return;
   if(t.dataset.a){var a=t.dataset.a;
     if(a==='new'){draft=null;screenCreate(0);}
     else if(a==='resume'){G=load();G.screen=G.screen||'season';routeGame();}
     else if(a==='panth'){renderPanth();}
     else if(a==='home'){screenHome();}
     return;}
   // création
   if(t.dataset.country!=null){draft.country=+t.dataset.country;
     var ni=document.getElementById('c-name');if(ni)draft.name=ni.value;screenCreate(0);return;}
   if(t.dataset.role){draft.role=t.dataset.role;screenCreate(1);return;}
   if(t.dataset.opt){draft[t.dataset.opt]=t.dataset.id;screenCreate(draft._step);return;}
   if(t.dataset.nav){
     var s=draft&&draft._step;
     if(G&&G.screen==='result'&&t.dataset.nav==='mercato'){G.screen='mercato';G.offers=null;render();return;}
     if(G&&G.cur&&t.dataset.nav==='cont'){nextStep();return;}
     if(t.dataset.nav==='back'){ if(draft&&draft._step>0)screenCreate(draft._step-1); else screenHome(); return; }
     if(t.dataset.nav==='next'){
       var ni2=document.getElementById('c-name');if(ni2)draft.name=ni2.value;
       if(!createValid()){var b=document.getElementById('c-next');if(b){b.textContent='Complète ce choix';setTimeout(function(){screenCreate(draft._step);},900);}return;}
       if(draft._step===5)startGame(); else screenCreate(draft._step+1);
     }
     return;}
   if(t.dataset.ch!=null){chooseEvent(+t.dataset.ch);return;}
   if(t.dataset.dec){doDecisive();return;}
   if(t.dataset.offer!=null){chooseOffer(+t.dataset.offer);return;}
   if(t.dataset.retire){retire('choice');return;}
 });
 function routeGame(){ if(G.screen==='mercato'){G.offers=G.offers||null;renderMercato();}
   else if(G.screen==='result'){render();} else { if(!G.cur&&(!G.queue||!G.queue.length)){startSeason();} else render(); } }

 // init quand l'onglet Carrière s'ouvre
 var opened=false;
 document.querySelectorAll('.tab').forEach(function(tb){ if(tb.dataset.tab==='vct'){
   tb.addEventListener('click',function(){ if(!opened){opened=true;screenHome();} });
 }});
})();

/* ============ Suivi de team (5 joueurs) ============ */
(function(){
 var root=document.getElementById('team-root');
 if(!root) return;
 var REGIONS=['eu','na','ap','kr','latam','br'];
 var team=[], sums={}, loading=false, opened=false, teamName='', anaHtml='', analyzing=false;
 var updates={}, updTotal=0, justNew={};

 function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
 function api(u,o){return fetch(BASE+u,o).then(function(r){return r.json();});}

 function boot(){
   api('/api/team').then(function(j){
     team=(j.team||[]).slice(0,6); teamName=j.team_name||'';
     render();
     // auto-charge le cache (rapide) pour les emplacements configurés
     team.forEach(function(p,i){ refreshSlot(i,false); });
     checkUpdates();
   });
 }

 function checkUpdates(){
   if(!team.length) return;
   api('/api/team/updates?queue='+QUEUE).then(function(j){
     updates={}; (j.slots||[]).forEach(function(s){ updates[s.slot]=s.new; });
     updTotal=j.total||0; render();
   }).catch(function(){});
 }

 function refreshSlot(i,fetchNet){
   var p=team[i]; if(!p) return Promise.resolve();
   sums[i]={loading:true}; render();
   return api('/api/team/refresh?slot='+i+'&fetch='+(fetchNet?1:0)+'&queue='+QUEUE,{method:'POST'})
     .then(function(j){ sums[i]=j; render(); })
     .catch(function(){ sums[i]={error:'réseau'}; render(); });
 }

 function updateAll(){
   if(loading) return; loading=true;
   var pending={}; team.forEach(function(p,i){ if(updates[i]>0) pending[i]=updates[i]; });
   render();
   var chain=Promise.resolve();
   team.forEach(function(p,i){ chain=chain.then(function(){ return refreshSlot(i,true); }); });
   chain.then(function(){ loading=false; justNew=pending; updates={}; updTotal=0; render(); checkUpdates(); });
 }

 function saveCfg(){
   var players=[];
   for(var i=0;i<6;i++){
     var rid=(document.getElementById('tm-rid-'+i).value||'').trim();
     var reg=document.getElementById('tm-reg-'+i).value;
     players.push({riot_id:rid,region:reg});
   }
   var nm=document.getElementById('tm-name'); var name=nm?(nm.value||'').trim():teamName;
   var msg=document.getElementById('tm-cfg-msg'); msg.textContent='Enregistrement…';
   api('/api/team/config',{method:'POST',headers:{'Content-Type':'application/json'},
     body:JSON.stringify({players:players,name:name})}).then(function(j){
     if(j.error){msg.textContent='⚠ '+j.error;return;}
     team=j.team||[]; teamName=j.team_name||''; sums={}; justNew={}; msg.textContent='✓ Équipe enregistrée';
     render(); team.forEach(function(p,i){ refreshSlot(i,false); });
   }).catch(function(){msg.textContent='⚠ Serveur requis';});
 }

 function analyzeTeam(){
   if(analyzing||!team.length) return;
   analyzing=true; render();
   api('/api/team/analyze?queue='+QUEUE,{method:'POST'}).then(function(j){
     analyzing=false;
     anaHtml=j.error?('<p class="muted">⚠ '+esc(j.error)+'</p>'):(j.analysis||'<p class="muted">Réponse vide.</p>');
     render();
   }).catch(function(){ analyzing=false; anaHtml='<p class="muted">⚠ Serveur / réseau indisponible.</p>'; render(); });
 }

 // ---- synthèse d'équipe ----
 function synthesis(){
   var loaded=team.map(function(p,i){return sums[i];}).filter(function(s){return s&&s.summary&&s.summary.games;});
   if(!loaded.length) return '';
   var g=0,w=0,acsSum=0,acsN=0,kdN=0,kdSum=0;
   loaded.forEach(function(s){var d=s.summary;
     g+=(d.act_games!=null?d.act_games:d.games);
     w+=(d.act_wins!=null?d.act_wins:(d.wins||0));
     if(d.avg_acs){acsSum+=d.avg_acs;acsN++;} if(d.kd){kdSum+=d.kd;kdN++;}});
   var wr=g?Math.round(w/g*1000)/10:0;
   return '<div class="tm-syn">'
     +cell('Joueurs',loaded.length+'/'+team.length)
     +cell('Parties cumul.',g)
     +cell('WR moyen',wr+'%')
     +cell('ACS moyen',acsN?Math.round(acsSum/acsN):'–')
     +cell('K/D moyen',kdN?(Math.round(kdSum/kdN*100)/100):'–')
     +'</div>';
 }
 function cell(l,v){return '<div class="s"><div class="l">'+l+'</div><div class="v">'+v+'</div></div>';}

 function card(p,s,i){
   var bg=(s&&s.summary&&s.summary.agent_bg)?'<div class="bg" style="background-image:url('+esc(s.summary.agent_bg)+')"></div>':'';
   var nb=(i!=null&&updates[i]>0)?'<span class="tm-dot" title="'+updates[i]+' nouvelle(s) partie(s) depuis la dernière mise à jour"></span>':'';
   var head=nb+'<div class="tm-top">'+bg+'<div><div class="tm-name">'+esc(p.riot_id)+'</div>'
     +'<div class="tm-sub">'+esc(p.region.toUpperCase())+'</div></div>';
   if(s&&s.loading){ return '<div class="tm-card">'+head+'<div class="tm-rank">⏳</div></div>'
     +'<div class="tm-empty">Chargement…</div></div>'; }
   if(s&&s.error){ return '<div class="tm-card">'+head+'</div>'
     +'<div class="tm-empty">⚠ '+esc(s.error)+'</div></div>'; }
   var d=s&&s.summary;
   if(!d||!d.games){ return '<div class="tm-card">'+head+'</div>'
     +'<div class="tm-empty">Aucune donnée en cache — clique « Mettre à jour ».</div></div>'; }
   var rc=d.rank_color||'#ffd479';
   var ric=d.rank_icon?'<img class="tm-rankimg" src="'+esc(d.rank_icon)+'" alt="">':'';
   var rrline;
   if(d.rr!=null){
     var chg=(d.rr_change!=null&&d.rr_change!==0)?' <b style="color:'+(d.rr_change>0?'#37E0A6':'#FF4655')+'">'+(d.rr_change>0?'+':'')+d.rr_change+'</b>':'';
     rrline='<b style="color:var(--ink)">'+esc(d.rr)+' RR</b>'+chg;
   } else { rrline='Niv '+esc(d.level); }
   head+='<div class="tm-rank">'+ric+'<div class="tm-ranktxt"><span style="color:'+rc+'">'+esc(d.rank)
     +'</span><br><span style="color:var(--muted)">'+rrline+'</span></div></div></div>';
   var kpis='<div class="tm-kpis">'
     +kp('WR',(d.win_rate!=null?d.win_rate+'%':'–'))
     +kp('K/D',d.kd!=null?d.kd:'–')
     +kp('ACS',d.avg_acs!=null?d.avg_acs:'–')
     +kp('KAST',d.kast!=null?d.kast+'%':'–')+'</div>';
   var ags=(d.top_agents||[]).map(function(a){
     var ic=a.icon?'<img src="'+esc(a.icon)+'">':'';
     return '<span class="tm-ag">'+ic+esc(a.name)+' <b style="color:var(--muted)">'+a.games+'</b></span>';}).join('');
   var nnew=(i!=null&&justNew[i])?justNew[i]:0;
   var form=(d.recent||[]).map(function(r,idx){
     return '<div class="r '+(r.won?'w':'l')+(idx<nnew?' rnew':'')+'"'
       +(idx<nnew?' title="Nouvelle partie"':'')+'>'+(r.won?'V':'D')+'</div>';}).join('');
   var hasAct=(d.act_games!=null);
   var gGames=hasAct?d.act_games:d.games;
   var gWins=(d.act_wins!=null)?d.act_wins:d.wins;
   var gLoss=(hasAct&&d.act_wins!=null)?(d.act_games-d.act_wins):d.losses;
   return '<div class="tm-card" style="border-top:3px solid '+rc+'">'+head+kpis
     +'<div class="tm-ags">'+(ags||'<span class="tm-sub">—</span>')+'</div>'
     +'<div class="tm-sub" style="margin-bottom:5px">'+gGames+' parties'+(hasAct?' <b style="color:'+rc+'">act</b>':'')+' · '+gWins+'V '+gLoss+'D · HS '
     +(d.avg_hs_pct!=null?d.avg_hs_pct+'%':'n/d')+'</div>'
     +'<div class="tm-form">'+form+'</div></div>';
 }
 function kp(l,v){return '<div class="tm-k"><div class="l">'+l+'</div><div class="v">'+v+'</div></div>';}

 var showCfg=false;
 function render(){
   var h='<div class="tm-head"><div><h2 style="margin:0;display:flex;align-items:center;gap:8px">'
     +'<svg viewBox="0 0 24 24" aria-hidden="true" style="width:19px;height:19px;stroke:var(--red);stroke-width:1.8;fill:none;stroke-linecap:round;stroke-linejoin:round;flex:0 0 auto"><path d="M12 3l7 3v5c0 4.2-3 7.2-7 8.5C8 18.2 5 15.2 5 11V6z"/><circle cx="12" cy="10.5" r="2"/><path d="M8.5 15.5c.7-1.6 2-2.5 3.5-2.5s2.8.9 3.5 2.5"/></svg>'+esc(teamName||'Ma Team')+'</h2>'
     +'<p class="muted mini" style="margin:4px 0 0">Suivi des '+(team.length||'')+' joueurs · '
     +'15 dernières parties '+(QUEUE==='premier'?'Premier':'Ranked')+' · à la demande.</p></div>'
     +'<div class="tm-actions">'
     +'<button class="car-btn ghost" id="tm-toggle" type="button" style="padding:9px 14px">⚙ Configurer</button>'
     +'<button class="car-btn ghost" id="tm-analyze" type="button" style="padding:9px 16px"'+((analyzing||!team.length)?' disabled':'')+'>'
     +(analyzing?'Analyse en cours…':'✦ Analyse IA')+'</button>'
     +'<button class="car-btn primary'+(updTotal>0?' tm-hasnew':'')+'" id="tm-update" type="button" style="padding:9px 16px"'+(loading?' disabled':'')+'>'
     +(loading?'⏳ Mise à jour…':'↻ Mettre à jour')+'</button></div></div>';
   if(showCfg||!team.length){
     h+='<label style="display:block;font-size:11px;text-transform:uppercase;letter-spacing:.14em;color:var(--muted);margin:2px 0 6px;font-weight:800">Nom de l’équipe</label>'
       +'<input id="tm-name" placeholder="Ex. Sentinels" value="'+esc(teamName)+'" autocomplete="off" maxlength="40" style="width:100%;font:inherit;font-size:14px;font-weight:700;padding:9px 12px;border-radius:10px;box-sizing:border-box;background:rgba(255,255,255,.06);border:1px solid var(--brd);color:var(--ink);margin-bottom:12px">';
     h+='<div class="tm-cfg">';
     for(var i=0;i<6;i++){
       var p=team[i]||{riot_id:'',region:'eu'};
       var isCoach=(i===5);
       h+='<div class="tm-row"><span class="idx">'+(isCoach?'C':(i+1))+'</span>'
         +'<input id="tm-rid-'+i+'" placeholder="'+(isCoach?'Pseudo#TAG (coach / remplaçant)':'Pseudo#TAG')+'" value="'+esc(p.riot_id)+'" autocomplete="off">'
         +'<select id="tm-reg-'+i+'">'+REGIONS.map(function(r){
             return '<option value="'+r+'"'+(p.region===r?' selected':'')+'>'+r.toUpperCase()+'</option>';}).join('')
         +'</select></div>';
     }
     h+='</div><div class="tm-actions"><button class="car-btn primary" id="tm-save" type="button" style="padding:9px 16px">💾 Enregistrer l’équipe</button></div>'
       +'<div class="tm-msg" id="tm-cfg-msg"></div>';
   }
   if(team.length){
     h+=synthesis();
     h+='<div class="tm-grid">'+team.map(function(p,i){return card(p,sums[i],i);}).join('')+'</div>';
   }
   if(analyzing||anaHtml){
     h+='<div class="glass card section" style="margin-top:14px"><h2 style="display:flex;align-items:center;gap:8px">'
       +'<svg viewBox="0 0 24 24" aria-hidden="true" style="width:18px;height:18px;stroke:var(--violet);stroke-width:1.7;fill:none;stroke-linecap:round;stroke-linejoin:round;flex:0 0 auto"><path d="M12 3l1.8 4.9L18.7 9l-4.9 1.8L12 15.7 10.2 10.8 5.3 9l4.9-1.1z"/><path d="M18 14l.7 1.9L20.6 17l-1.9.7L18 19.6l-.7-1.9L15.4 17l1.9-.7z"/></svg>'
       +'Analyse d’équipe (IA)</h2>'
       +'<div class="analysis">'+(analyzing?'<p class="muted">Analyse en cours… (DeepSeek)</p>':anaHtml)+'</div></div>';
   }
   root.innerHTML=h;
   var tg=document.getElementById('tm-toggle'); if(tg)tg.onclick=function(){showCfg=!showCfg;render();};
   var up=document.getElementById('tm-update'); if(up)up.onclick=updateAll;
   var an=document.getElementById('tm-analyze'); if(an)an.onclick=analyzeTeam;
   var sv=document.getElementById('tm-save'); if(sv)sv.onclick=saveCfg;
 }

 document.querySelectorAll('.tab').forEach(function(tb){ if(tb.dataset.tab==='team'){
   tb.addEventListener('click',function(){ if(!opened){opened=true;boot();} });
 }});
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
     <div class="pills">{rank_pill}
       <span class="pill">Niveau {level}</span><span class="pill ac">Saison {act}</span></div></div>
   <div class="spacer"></div>
   <div class="controls">{qswitch}
     {map_selector}
     <button id="settings-btn" class="refresh" type="button" title="Personnaliser le fond">⚙</button>
     <button id="refresh" class="refresh" type="button">↻ Mettre à jour</button>
     <div class="gen">Généré le<br>{gen}</div></div>
 </header>

 <nav class="tabs">
   <button class="tab active" data-tab="ov">Vue d'ensemble</button>
   <button class="tab" data-tab="agents">Agents</button>
   <button class="tab" data-tab="weapons">Armes</button>
   <button class="tab" data-tab="fc">First Contact</button>
   <button class="tab" data-tab="maps">Cartes</button>
   <button class="tab" data-tab="splits">Splits</button>
   <button class="tab" data-tab="team"><svg class="tab-ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l7 3v5c0 4.2-3 7.2-7 8.5C8 18.2 5 15.2 5 11V6z"/><circle cx="12" cy="10.5" r="2"/><path d="M8.5 15.5c.7-1.6 2-2.5 3.5-2.5s2.8.9 3.5 2.5"/></svg>Team</button>
   <button class="tab" data-tab="vct"><svg class="tab-ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4h10v3a5 5 0 0 1-10 0z"/><path d="M7 5H4v1a3 3 0 0 0 3 3"/><path d="M17 5h3v1a3 3 0 0 1-3 3"/><path d="M12 12v3"/><path d="M8.5 20h7"/><path d="M10 17h4l.5 3h-5z"/></svg>Carrière</button>
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
     <div class="ov-left">
       <div class="glass card"><h2>Win rate par carte</h2>{map_bars}</div>
       <div class="glass card"><h2>Jours de jeu · saison {act}</h2>{calendar}</div>
     </div>
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
   <div class="cols">
     <div class="glass card"><h2>FCS par agent</h2>{fc_bars}</div>
     <div class="glass card"><h2>First Contact par arme</h2>{fc_weapons}
       <p class="muted mini">Barre : part des duels gagnés (vert) vs perdus (rouge).
         FK = kills d'ouverture avec cette arme · FD = morts d'ouverture face à elle.</p></div>
   </div>
 </section>

 <section id="panel-maps" class="panel">
   <div class="glass card"><h2>Statistiques par carte</h2>
     <p class="muted mini" style="margin:0 0 12px">Clique sur une carte pour filtrer <b>toutes</b> les
       stats de l'app dessus (ou utilise le sélecteur en haut à droite). Win rate coloré selon le seuil 50%.</p>
     {map_table}
   </div>
 </section>

 <section id="panel-splits" class="panel">
   <p class="muted mini" style="margin:0 0 14px">Décomposition round par round. <b>Attaque/Défense</b>
     déduit des plants ; <b>issue</b> selon l'équipe gagnante du round. La valeur la plus favorable
     de chaque ligne est <span style="color:var(--mint);font-weight:800">surlignée</span>.</p>
   {splits}
   <p class="muted mini" style="margin:14px 0 0">HS% par arme et stats d'utilitaires ne sont pas
     fournis par round par l'API HenrikDev — non affichés.</p>
 </section>

 <section id="panel-team" class="panel">
   <div class="glass card section"><div id="team-root"></div></div>
 </section>

 <section id="panel-vct" class="panel">
   <div class="glass card section"><div id="career-root" class="car-wrap"></div></div>
 </section>

 <div class="foot">
   Carrière « Destin de rêve » : jeu narratif, fiction. Inspiré du mode carrière d'Onze de Rêve.<br>
   Noms d'équipes / compétitions cités à titre indicatif — non officiel, non affilié à Riot Games.<br>
   Données perso via l'API tierce non officielle HenrikDev (non affiliée à Riot Games).
 </div>
</div>

<div id="modal" class="modal">
  <div class="modal-card glass">
    <h3>⚙ Paramètres</h3>
    <div class="fgroup">
      <div class="fg-title">🎯 Compte ciblé</div>
      <label class="field">Riot ID (Pseudo#TAG)
        <input id="riot-id" type="text" value="{name}" placeholder="Pseudo#TAG" autocomplete="off"></label>
      <label class="field">Région
        <select id="region">{region_options}</select></label>
      <div class="modal-actions">
        <button id="target-apply" class="btn-primary" type="button">Charger ce compte</button>
      </div>
    </div>
    <div class="fgroup">
      <div class="fg-title">🖼 Fond d'écran</div>
      <label class="field">Image (jpg, png, webp, gif)
        <input id="bg-file" type="file" accept="image/*"></label>
      <label class="field">Assombrissement <span id="dim-val">{dim}%</span>
        <input id="dim" type="range" min="0" max="90" value="{dim}"></label>
      <div class="modal-actions">
        <button id="bg-apply" class="btn-primary" type="button">Appliquer le fond</button>
        <button id="bg-reset" class="btn-ghost" type="button">Réinitialiser</button>
      </div>
    </div>
    <div class="modal-actions"><button id="modal-close" class="btn-ghost" type="button">Fermer</button></div>
    <p class="muted mini">Nécessite le serveur local (python server.py). Changer de compte
      télécharge ses parties (peut prendre 1-2 min la première fois).</p>
  </div>
</div>

<script>var QUEUE={queue!r};var BASE={base!r};{js}</script>
</body></html>
"""
