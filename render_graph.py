"""
Génère le graphe 'fiche de vie & permutations' d'un tiroir à partir de CSV.
AUCUNE donnée en dur : tout vient de positions.csv, cartes.csv, transferts.csv.

FORMAT
------
positions.csv  (N1 : séjours sur rame -> zone HAUTE)
  drawer, position, train, date_pose, date_depose(vide=en place),
  ot(motif \\w+_OT_\\d+), code, description, commentaire

cartes.csv     (N3 : réparations cartes -> zone BASSE)
  drawer, carte, date_depose, date_repose(=fin du trou), ot, code,
  description, commentaire

transferts.csv (mouvements inter-atelier / mise en stock -> flèches au milieu)
  drawer, datetime(YYYY-MM-DD [HH:MM]), sens(retour=vert montant / defaut=rouge
  descendant), label(nom du stock / mouvement)
  -> PAS d'OT : les flèches affichent le label au survol, sans modale.
  Fichier optionnel : à défaut, les transferts sont dérivés des poses/déposes.

SORTIE : un HTML par tiroir présent dans les données.
"""
import re, html as _h, os
from datetime import datetime
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go

# Chemins portables : par défaut, CSV lus à côté du script et HTML écrit dans ./docs
# (servi tel quel par GitHub Pages). Surchargeables par variables d'environnement.
BASE_DIR       = Path(__file__).resolve().parent
DATA_DIR       = Path(os.environ.get("DATA_DIR", BASE_DIR))
OUT_DIR        = os.environ.get("OUT_DIR", str(BASE_DIR / "docs"))
POSITIONS_CSV  = str(DATA_DIR / "positions.csv")
CARTES_CSV     = str(DATA_DIR / "cartes.csv")
CARTES_REF_CSV = str(DATA_DIR / "cartes_ref.csv")            # config complète des cartes (optionnel)
TRANSFERTS_CSV = str(DATA_DIR / "transferts.csv")            # optionnel
TESTS_CSV      = str(DATA_DIR / "tests.csv")                 # optionnel
GREEN, RED     = "#2ca02c", "#d62728"

D    = lambda s: datetime.strptime(s, "%Y-%m-%d")
Dany = lambda s: datetime.strptime(s[:16], "%Y-%m-%d %H:%M") if len(s) > 10 else D(s)

def build(drawer, pos, crt, trf, tst, cref):
    dates = [D(x) for x in pos.date_pose if x] + [D(x) for x in pos.date_depose if x] \
          + [D(x) for x in crt.date_depose if x] + [D(x) for x in crt.date_repose if x]
    if trf is not None:
        dates += [Dany(x) for x in trf["datetime"] if x]
    if tst is not None:
        dates += [Dany(x) for x in tst["datetime"] if x]
    life_start, life_end = min(dates), max(dates)
    ls, le = life_start.strftime("%Y-%m-%d"), life_end.strftime("%Y-%m-%d")

    positions = list(dict.fromkeys(pos.position))
    # toutes les cartes du tiroir (config), pas seulement celles réparées
    if cref is not None and len(cref):
        cards = list(cref.sort_values("ordre", key=lambda s: s.astype(int)).carte)
    else:
        cards = []
    for c in dict.fromkeys(crt.carte):            # ajoute d'éventuelles cartes absentes du ref
        if c not in cards:
            cards.append(c)
    pos_y  = {p: 2 + i for i, p in enumerate(positions)}
    card_y = {c: -2 - i for i, c in enumerate(cards)}

    fig = go.Figure()
    ot_details = {}
    def reg_ot(ot, equip, code, desc, deposes, comment):
        if ot and ot not in ot_details:
            ot_details[ot] = dict(equip=equip, mtype=code, desc=desc,
                                  deposes=deposes, comment=comment)

    # cartes (bas) : ligne continue + TROU pendant réparation
    for c in cards:
        cy = card_y[c]
        ev = crt[crt.carte == c].copy()
        ev["r"] = ev.date_depose.map(D); ev["t"] = ev.date_repose.map(D)
        ev = ev.sort_values("r")
        wins = []
        for _, e in ev.iterrows():
            if wins and e.r <= wins[-1][1]:
                wins[-1][1] = max(wins[-1][1], e.t); wins[-1][2].append(e)
            else:
                wins.append([e.r, e.t, [e]])
        xs, ys, txt = [ls], [cy], [f"{c} (origine)"]
        for r, t, es in wins:
            lbl = f"#{es[0].ot}, {es[0].code}"
            xs += [r.strftime('%Y-%m-%d'), r.strftime('%Y-%m-%d'), t.strftime('%Y-%m-%d')]
            ys += [cy, None, cy]; txt += [lbl, "", lbl]
            for e in es:
                reg_ot(e.ot, drawer, e.code, e.description,
                       [f"{c} : dépose {e.date_depose} → repose {e.date_repose}"], e.commentaire)
        xs.append(le); ys.append(cy); txt.append("RAS")
        fig.add_trace(go.Scatter(x=xs, y=ys, text=txt, name=c, mode="lines+markers",
            line=dict(shape="hv", width=5),
            marker=dict(symbol="line-ns-open", size=26, line=dict(width=3)),
            hovertemplate="%{text}<extra>"+c+"</extra>"))

    # séjours sur rame (haut)
    seen = set()
    for _, s in pos.iterrows():
        y = pos_y[s.position]; end = s.date_depose or le; open_ = not s.date_depose
        fig.add_trace(go.Scatter(
            x=[s.date_pose, end], y=[y, y],
            text=[f"#{s.ot}, {s.code}", "RAS" if open_ else f"#{s.ot}, {s.code}"],
            name=s.train, legendgroup=s.train, showlegend=s.train not in seen,
            mode="lines+markers", line=dict(shape="hv", width=3),
            marker=dict(symbol="circle-open", size=9, line=dict(width=2)),
            hovertemplate="%{text}<br>"+s.train+" / "+s.position+"<extra></extra>"))
        seen.add(s.train)
        dep = [f"{drawer} posé sur {s.position} / {s.train} le {s.date_pose}"]
        if s.date_depose: dep.append(f"{drawer} déposé de {s.position} / {s.train} le {s.date_depose}")
        reg_ot(s.ot, s.train, s.code, s.description, dep, s.commentaire)

    # transferts (flèches) : depuis transferts.csv (nom du stock, SANS modale)
    if trf is not None and len(trf):
        rows = [(r["datetime"], r["sens"].strip().lower(), r["label"]) for _, r in trf.iterrows()]
    else:                                   # repli : dérivés des poses/déposes (sans OT -> sans modale)
        rows = []
        for _, s in pos.iterrows():
            rows.append((s.date_pose, "retour", f"STOCK → {s.train}"))
            if s.date_depose:
                rows.append((s.date_depose, "defaut", f"{s.train} → Atelier (défaut)"))
    ann, tx, ty, tt, tc = [], [], [], [], []
    for when, sens, label in rows:
        up = sens in ("retour", "vert", "montee", "montée", "n2->n1", "stock")
        # flèche CENTRÉE sur la ligne N1/N2 : queue et tête symétriques autour de y=0
        ann.append(dict(x=when, y=1 if up else -1, ax=when, ay=-1 if up else 1,
                        xref="x", yref="y", axref="x", ayref="y",
                        showarrow=True, arrowhead=2, arrowwidth=2.5,
                        arrowcolor=GREEN if up else RED))
        tx.append(when); ty.append(0)                  # survol seul : le visuel du transfert = la flèche
        tc.append(GREEN if up else RED); tt.append(label)
    fig.add_trace(go.Scatter(x=tx, y=ty, text=tt, mode="markers", name="TRANSFERT",
        showlegend=False, marker=dict(size=16, color=tc, opacity=0),
        hovertemplate="%{text}<extra>transfert</extra>"))

    # tests du tiroir en atelier (N3) : cercle vert = RAS, croix rouge = KO (sous la ligne)
    if tst is not None and len(tst):
        for res, sym, col in [("RAS", "circle-open", GREEN), ("KO", "x-thin-open", RED)]:
            sub = tst[tst.resultat.str.upper() == res]
            if len(sub):
                fig.add_trace(go.Scatter(
                    x=list(sub["datetime"]), y=[-1.1] * len(sub),
                    text=[f"Test {res} — {cm}" for cm in sub["commentaire"]],
                    mode="markers", name=f"Test {res}", showlegend=False,
                    marker=dict(size=12, symbol=sym, color=col, line=dict(width=2.5, color=col)),
                    hovertemplate="%{text}<extra></extra>"))

    tickvals = [card_y[c] for c in cards][::-1] + [-1, 0, 1] + [pos_y[p] for p in positions]
    ticktext = [c for c in cards][::-1] + [" ", "TRANSFERT N1/N2", " "] + positions
    fig.add_hline(y=0, line=dict(color="#888", width=1, dash="dot"))
    fig.update_layout(height=620, hovermode="closest", template="plotly_white",
        title=f"{drawer} — historique de vie & permutations",
        font=dict(family="Arial", size=12),
        legend=dict(orientation="v", x=1.01, y=1, font=dict(size=10), title="Rames"),
        annotations=ann, xaxis=dict(showgrid=True, gridcolor="#eee", type="date"),
        yaxis=dict(showgrid=False, zeroline=False, showline=True, automargin=True,
                   tickvals=tickvals, ticktext=ticktext,
                   range=[min(tickvals)-0.8, max(tickvals)+0.8]))

    plot = fig.to_html(include_plotlyjs="cdn", full_html=False, div_id="graph")
    def modal(ot, d):
        dep = "".join(f"<tr><td><b>{_h.escape(x)}</b></td></tr>" for x in d["deposes"])
        return f"""<div class="modal fade" id="{ot}" tabindex="-1" role="dialog" aria-hidden="true">
 <div class="modal-dialog modal-lg"><div class="modal-content">
  <div class="modal-header"><h5 class="modal-title">Détail de l'OT — {ot}</h5>
   <button type="button" class="close" data-dismiss="modal">&times;</button></div>
  <div class="modal-body"><table class="table table-sm">
     <tr><td><b>Statut</b></td><td>CLOS</td><td><b>Type maint.</b></td><td>{_h.escape(d['mtype'])}</td></tr>
     <tr><td><b>Équipement</b></td><td colspan="3">{_h.escape(d['equip'])}</td></tr>
     <tr><td><b>Description</b></td><td colspan="3">{_h.escape(d['desc'])}</td></tr></table>
   <p><b>Déposes / Poses :</b></p><table class="table table-sm table-bordered">{dep}</table>
   <p><b>Commentaire :</b><br>{_h.escape(d['comment'])}</p>
  </div></div></div></div>"""
    modals = "\n".join(modal(o, d) for o, d in ot_details.items())
    click = """<script>(function(){var g=document.getElementById('graph');
g.on('plotly_click',function(data){var t=data.points[0].text||'',m=t.match(/(#\\w+_OT_\\d+)/);
if(m){var id=m[1].substring(1);if(window.jQuery&&jQuery('#'+id).length){jQuery('#'+id).modal('show');}}});})();</script>"""
    page = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>{_h.escape(drawer)}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/4.0.0/css/bootstrap.min.css">
<style>body{{font-family:Arial,sans-serif;margin:14px}}.legend-note{{font-size:12px;color:#555;margin:6px 0 14px}}
.dot{{display:inline-block;width:11px;height:11px;border-radius:50%;vertical-align:middle;margin:0 4px 0 12px}}
.modal-body td{{font-size:13px}}</style></head><body>
<h4>{_h.escape(drawer)} — fiche de vie</h4>
<div class="legend-note">Cliquez sur un point (séjour ou carte) pour le détail de l'OT.
 Les flèches de transfert affichent le mouvement / stock au survol (pas de modale).
 <span class="dot" style="background:#2ca02c"></span>retour / mise en stock
 <span class="dot" style="background:#d62728"></span>dépose pour défaut
 &nbsp;|&nbsp; sous la ligne : ○ vert = test RAS · ✕ rouge = test KO
 &nbsp;|&nbsp; haut = positions sur rames · bas = cartes (atelier N3)</div>
{plot}
{modals}
<script src="https://code.jquery.com/jquery-3.5.1.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/popper.js/1.16.1/umd/popper.min.js"></script>
<script src="https://maxcdn.bootstrapcdn.com/bootstrap/4.0.0/js/bootstrap.min.js"></script>
{click}</body></html>"""
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", drawer)
    out = f"{OUT_DIR}/fiche_{safe}.html"
    open(out, "w", encoding="utf-8").write(page)
    return out, len(ot_details), len(tx)

def write_index(out_dir, fiches):
    """Page d'accueil GitHub Pages : liste cliquable des fiches générées."""
    items = "\n".join(
        f'    <li><a href="{_h.escape(os.path.basename(f))}">{_h.escape(d)}</a></li>'
        for d, f in fiches)
    page = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<title>Fiches de vie — tiroirs maintenance</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{{font-family:Arial,sans-serif;max-width:760px;margin:40px auto;padding:0 16px;color:#222}}
h1{{font-size:22px}}.lead{{color:#555;font-size:14px;line-height:1.5}}
ul{{list-style:none;padding:0}}li{{margin:10px 0}}
a{{display:inline-block;padding:10px 16px;background:#f4f6f8;border:1px solid #dde2e8;
border-radius:8px;text-decoration:none;color:#1a4d8f;font-weight:600}}
a:hover{{background:#e9eef4}}footer{{margin-top:32px;font-size:12px;color:#888}}</style></head><body>
<h1>Fiches de vie &amp; permutations — tiroirs de maintenance</h1>
<p class="lead">Graphes interactifs retraçant le cycle de vie d'un tiroir : séjours sur rames
(haut), réparations de cartes en atelier N3 (bas), transferts inter-atelier (flèches) et
tests au banc. Données pilotées par CSV, rendu Plotly. Cliquez sur un point pour le détail de l'OT.</p>
<ul>
{items}
</ul>
<footer>Généré par <code>render_graph.py</code> — démonstration avec données anonymisées.</footer>
</body></html>"""
    idx = os.path.join(out_dir, "index.html")
    open(idx, "w", encoding="utf-8").write(page)
    return idx

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    pos = pd.read_csv(POSITIONS_CSV, dtype=str).fillna("")
    crt = pd.read_csv(CARTES_CSV, dtype=str).fillna("")
    cref = pd.read_csv(CARTES_REF_CSV, dtype=str).fillna("") if os.path.exists(CARTES_REF_CSV) else None
    trf = pd.read_csv(TRANSFERTS_CSV, dtype=str).fillna("") if os.path.exists(TRANSFERTS_CSV) else None
    tst = pd.read_csv(TESTS_CSV, dtype=str).fillna("") if os.path.exists(TESTS_CSV) else None
    drawers = list(dict.fromkeys(list(pos.drawer) + list(crt.drawer)))
    fiches = []
    for d in drawers:
        t  = trf[trf.drawer == d].reset_index(drop=True) if trf is not None else None
        ts = tst[tst.drawer == d].reset_index(drop=True) if tst is not None else None
        cr = cref[cref.drawer == d].reset_index(drop=True) if cref is not None else None
        out, n, nt = build(d, pos[pos.drawer == d].reset_index(drop=True),
                              crt[crt.drawer == d].reset_index(drop=True), t, ts, cr)
        fiches.append((d, out))
        print(f"{d}: {out}  ({n} OT cliquables, {nt} flèches)")
    idx = write_index(OUT_DIR, fiches)
    print(f"index: {idx}  ({len(fiches)} fiche(s))")

if __name__ == "__main__":
    main()
