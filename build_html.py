"""Genera index.html (dashboard web autocontenido) a partir del Excel.

Uso:  python build_html.py data/ticket_51020.xlsx

Los datos se agregan por día, canal, comercio y monto; no se incluye RUT, nombre,
email, usuario ni Id.
"""
import json
import sys
from pathlib import Path

import pandas as pd

from data_prep import prepare

ROOT = Path(__file__).parent


def build_payload(xlsx):
    a, c, qa = prepare(xlsx)
    dias = sorted(set(a["dia"]).union(c["dia"]))
    di = {d: i for i, d in enumerate(dias)}

    def idx(s):
        u = sorted(s.unique())
        return u, {v: i for i, v in enumerate(u)}

    canales, ci = idx(pd.concat([a.canal, c.canal]))
    estados, ei = idx(a.estado)
    campanas, pi = idx(a.campana)
    comercios, mi = idx(c.comercio)
    giftcards, gi = idx(c.giftcard)

    ga = a.groupby(["dia", "canal", "estado", "campana"]).monto.agg(["sum", "count"]).reset_index()
    gc = c.groupby(["dia", "canal", "comercio", "giftcard", "monto"]).size().reset_index(name="n")
    out = {
        "dias": [d.strftime("%Y-%m-%d") for d in dias],
        "canales": canales, "estados": estados, "campanas": campanas,
        "comercios": comercios, "giftcards": giftcards,
        "A": [[di[r.dia], ci[r.canal], ei[r.estado], pi[r.campana], int(r["sum"]), int(r["count"])] for _, r in ga.iterrows()],
        "C": [[di[r.dia], ci[r.canal], mi[r.comercio], gi[r.giftcard], int(r.monto), int(r.n)] for _, r in gc.iterrows()],
        "qa": qa,
        "corte": {"abonos": [str(a.fecha.min().date()), str(a.fecha.max().date())],
                  "canjes": [str(c.fecha.min().date()), str(c.fecha.max().date())]},
    }
    # Control: los agregados cuadran con el detalle
    assert sum(r[4] for r in out["A"]) == a.monto.sum()
    assert sum(r[4] * r[5] for r in out["C"]) == c.monto.sum()
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Uso: python build_html.py data/ticket_51020.xlsx")
    payload = build_payload(sys.argv[1])
    # Funciona con estructura de carpetas (web/, docs/) o con todo en la raíz
    tpl_path = ROOT / "web" / "template.html"
    if not tpl_path.exists():
        tpl_path = ROOT / "template.html"
    tpl = tpl_path.read_text(encoding="utf-8")
    out = ROOT / "docs" / "index.html" if (ROOT / "docs").is_dir() else ROOT / "index.html"
    out.write_text(tpl.replace("__DATA__", json.dumps(payload, ensure_ascii=False, separators=(",", ":"))), encoding="utf-8")
    print(f"OK: {out}  ({len(payload['A'])} filas de abonos, {len(payload['C'])} de canjes agregadas)")
