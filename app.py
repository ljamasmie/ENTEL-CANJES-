"""Dashboard de Abonos y Canjes (Streamlit).

Ejecutar:  streamlit run app.py
Lee el primer .xlsx de la carpeta data/ o permite subirlo desde la barra lateral.
No se muestra ningún dato personal: RUT/usuario se usan solo internamente en data_prep.py.
"""
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from data_prep import prepare

AZUL, NARANJO, CELESTE = "#002EFF", "#FF3D00", "#8FA5FF"  # Colorimetría Entel
MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
         "Septiembre", "Octubre", "Noviembre", "Diciembre"]

st.set_page_config(page_title="Dashboard de Abonos y Canjes", layout="wide")
st.markdown(f"""<style>
[data-testid="stMetricValue"]{{font-size:2rem;font-weight:700}}
.rate [data-testid="stMetricValue"]{{color:{AZUL}}}
.block-container{{padding-top:2rem;max-width:1300px}}
</style>""", unsafe_allow_html=True)


def clp(n):
    return "—" if pd.isna(n) else "$" + f"{n:,.0f}".replace(",", ".")


def pct(x):
    return "—" if pd.isna(x) else f"{x*100:,.1f}%".replace(",", "X").replace(".", ",").replace("X", ".")


def short(n):
    a = abs(n); s = "−" if n < 0 else ""
    if a >= 1e6:
        return f"{s}${a/1e6:,.1f} M".replace(",", "X").replace(".", ",").replace("X", ".")
    return s + clp(a)


@st.cache_data(show_spinner="Leyendo y anonimizando el Excel…")
def load(raw: bytes):
    return prepare(raw)


# ---------- Datos ----------
DATA_DIR = Path(__file__).parent / "data"
_xlsx = sorted(DATA_DIR.glob("*.xlsx")) or sorted(Path(__file__).parent.glob("*.xlsx"))
default = _xlsx[0] if _xlsx else DATA_DIR / "ticket_51020.xlsx"
up = st.sidebar.file_uploader("Archivo Excel (abonos / canjes)", type="xlsx")
if up is not None:
    raw = up.getvalue()
elif default.exists():
    raw = default.read_bytes()
else:
    st.info("Sube el archivo Excel con las pestañas abonos y canjes desde la barra lateral, o déjalo en la carpeta data/.")
    st.stop()
A0, C0, QA = load(raw)

# ---------- Filtros ----------
st.sidebar.header("Filtros")
fmin = min(A0.dia.min(), C0.dia.min()).date(); fmax = max(A0.dia.max(), C0.dia.max()).date()
rango = st.sidebar.date_input("Fecha desde / hasta", (fmin, fmax), min_value=fmin, max_value=fmax)
d0, d1 = (rango if isinstance(rango, (list, tuple)) and len(rango) == 2 else (fmin, fmax))
anios = [str(y) for y in sorted(set(A0.anio) | set(C0.anio))]
anio = st.sidebar.selectbox("Año", ["Todos"] + anios)
mes = st.sidebar.selectbox("Mes", ["Todos"] + MESES)
canales = sorted(set(A0.canal) | set(C0.canal))
f_canal = st.sidebar.multiselect("Canal (PDV)", canales, placeholder="Todos")
f_com = st.sidebar.multiselect("Comercio", sorted(C0.comercio.unique()), placeholder="Todos")
f_gift = st.sidebar.multiselect("Red giftcard", sorted(C0.giftcard.unique()), placeholder="Todas")
f_est = st.sidebar.multiselect("Estado del abono", sorted(A0.estado.unique()), placeholder="Todos")


def base_filter(df):
    m = (df.dia.dt.date >= d0) & (df.dia.dt.date <= d1)
    if anio != "Todos": m &= df.anio == int(anio)
    if mes != "Todos": m &= df.fecha.dt.month == MESES.index(mes) + 1
    if f_canal: m &= df.canal.isin(f_canal)
    return df[m]


A = base_filter(A0); C = base_filter(C0)
if f_est: A = A[A.estado.isin(f_est)]
if f_com: C = C[C.comercio.isin(f_com)]
if f_gift: C = C[C.giftcard.isin(f_gift)]

# ---------- Header y KPIs ----------
_here = Path(__file__).parent
logo = next((p for p in [_here / "assets" / "logo_entel.png", _here / "logo_entel.png"] if p.exists()), _here / "logo_entel.png")
if logo.exists():
    lc, tc = st.columns([1, 14], vertical_alignment="center")
    lc.image(str(logo), width=56)
    tc.title("Dashboard de Abonos y Canjes")
else:
    st.title("Dashboard de Abonos y Canjes")
st.caption("Análisis de utilización, comercios y comportamiento de canje · Montos en CLP (1 punto = $1)")
if f_com or f_gift:
    st.info("Filtro de comercio/red activo: los abonos no registran comercio, así que el total abonado no se filtra. "
            "El % de canje muestra lo canjeado en la selección sobre todo lo abonado.")

ab, cj = A.monto.sum(), C.monto.sum(); nab, ncj = len(A), len(C)
rate = cj / ab if ab else float("nan"); saldo = ab - cj
k1, k2, k3 = st.columns(3)
k1.metric("Total abonado", short(ab), clp(ab), delta_color="off")
k2.metric("Total canjeado", short(cj), clp(cj), delta_color="off")
with k3:
    st.markdown('<div class="rate">', unsafe_allow_html=True)
    st.metric("% de canje", pct(rate), "Canjeado ÷ Abonado × 100", delta_color="off")
    st.markdown("</div>", unsafe_allow_html=True)
k4, k5, k6, k7 = st.columns(4)
k4.metric("Saldo no canjeado", short(saldo),
          "Negativo: se canjeó más de lo abonado" if saldo < 0 else "Abonado − Canjeado", delta_color="off")
k5.metric("Nº de abonos", f"{nab:,}".replace(",", "."))
k6.metric("Nº de canjes", f"{ncj:,}".replace(",", "."))
k7.metric("Ticket promedio de canje", clp(cj / ncj) if ncj else "—")

# ---------- Agregados ----------
mA = A.groupby("mes").monto.agg(ab="sum", nab="count"); mC = C.groupby("mes").monto.agg(cj="sum", ncj="count")
mens = mA.join(mC, how="outer").fillna(0).sort_index(); mens["rate"] = mens.cj / mens.ab.replace(0, pd.NA)
com = (C.groupby("comercio").monto.agg(cj="sum", n="count", ticket="mean", minimo="min", maximo="max")
         .sort_values("cj", ascending=False))
com["participacion"] = com.cj / cj if cj else 0; com["acumulado"] = com.participacion.cumsum()
can = (A.groupby("canal").monto.agg(ab="sum", nab="count")
         .join(C.groupby("canal").monto.agg(cj="sum", ncj="count"), how="outer").fillna(0))
can["rate"] = can.cj / can.ab.replace(0, pd.NA); can["ticket"] = can.cj / can.ncj.replace(0, pd.NA)

# ---------- Insights ----------
st.subheader("Insights principales")
ins = []
if ab:
    ins.append(f"La tasa de canje acumulada es de **{pct(rate)}**: se canjearon {clp(cj)} de {clp(ab)} abonados.")
    ins.append(f"El monto no canjeado representa **{pct(saldo/ab)}** del total abonado." if saldo >= 0 else
               f"El monto canjeado supera al abonado en {clp(-saldo)} (**{pct(-saldo/ab)}** del abonado). "
               "El archivo no permite identificar el origen de ese saldo.")
if len(com):
    ins.append(f"{com.index[0]} concentra el **{pct(com.participacion.iloc[0])}** del monto total canjeado.")
if len(com) > 5:
    ins.append(f"Los 5 principales comercios concentran el **{pct(com.acumulado.iloc[4])}** del total canjeado.")
if mens.cj.sum():
    mm = mens.cj.idxmax(); ins.append(f"El mes con mayor volumen de canjes fue **{MESES[int(mm[5:])-1].lower()} de {mm[:4]}** ({clp(mens.cj.max())}).")
if ncj:
    ins.append(f"El ticket promedio de canje es de **{clp(cj/ncj)}**; la mediana es {clp(C.monto.median())}.")
cr = can.dropna(subset=["rate"]).sort_values("rate", ascending=False)
if len(cr) > 1:
    ins.append(f"Por canal, la mayor tasa de canje es **{cr.index[0]}** ({pct(cr.rate.iloc[0])}) y la menor **{cr.index[-1]}** ({pct(cr.rate.iloc[-1])}).")
for i in ins[:8]:
    st.markdown("- " + i)

# ---------- Evolución ----------
st.subheader("Evolución temporal")
gran = st.radio("Granularidad", ["Mes", "Semana", "Día"], horizontal=True, label_visibility="collapsed")
rule = {"Mes": "MS", "Semana": "W-MON", "Día": "D"}[gran]
ts = pd.DataFrame({"Abonado": A.set_index("fecha").monto.resample(rule).sum(),
                   "Canjeado": C.set_index("fecha").monto.resample(rule).sum()}).fillna(0)
fig = go.Figure()
fig.add_scatter(x=ts.index, y=ts.Abonado, name="Abonado", fill="tozeroy", line=dict(color=CELESTE, shape="spline"))
fig.add_scatter(x=ts.index, y=ts.Canjeado, name="Canjeado", line=dict(color=AZUL, shape="spline"))
fig.update_layout(height=380, margin=dict(l=0, r=0, t=10, b=0), hovermode="x unified", legend=dict(orientation="h", y=1.08))
st.plotly_chart(fig, width="stretch")

# ---------- % de canje ----------
st.subheader("% de canje")
st.caption("Canjeado ÷ Abonado en cada corte, mostrado como dato objetivo. Por comercio no se puede calcular: los abonos no tienen comercio.")
c1, c2 = st.columns([1.4, 1])
f1 = go.Figure(go.Bar(x=mens.index, y=mens.rate * 100, marker_color=CELESTE, name="% mensual"))
if ab: f1.add_hline(y=rate * 100, line_dash="dash", line_color=NARANJO, annotation_text="Acumulado")
f1.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), yaxis_ticksuffix="%")
c1.plotly_chart(f1, width="stretch")
f2 = go.Figure(go.Bar(y=cr.index, x=cr.rate * 100, orientation="h", marker_color=CELESTE))
f2.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), xaxis_ticksuffix="%", yaxis_autorange="reversed")
c2.plotly_chart(f2, width="stretch")

# ---------- Comercio ----------
st.subheader("Comportamiento por comercio")
top = com.head(15)
f3 = go.Figure()
f3.add_bar(x=top.index, y=top.cj, name="Monto canjeado", marker_color=AZUL)
f3.add_scatter(x=top.index, y=top.acumulado * 100, name="Participación acumulada", yaxis="y2", line=dict(color=NARANJO))
f3.update_layout(height=400, margin=dict(l=0, r=0, t=10, b=0), yaxis2=dict(overlaying="y", side="right", range=[0, 100], ticksuffix="%"),
                 legend=dict(orientation="h", y=1.08))
st.plotly_chart(f3, width="stretch")
st.dataframe(com.reset_index().rename(columns={"comercio": "Comercio", "cj": "Total canjeado", "participacion": "Participación",
             "acumulado": "Acumulado", "n": "Nº canjes", "ticket": "Ticket promedio", "minimo": "Mínimo", "maximo": "Máximo"}),
             hide_index=True, width="stretch",
             column_config={"Participación": st.column_config.NumberColumn(format="percent"),
                            "Acumulado": st.column_config.NumberColumn(format="percent"),
                            **{k: st.column_config.NumberColumn(format="$%d") for k in ["Total canjeado", "Ticket promedio", "Mínimo", "Máximo"]}})

# ---------- Canal ----------
st.subheader("Comportamiento por canal (PDV)")
st.caption("El archivo no incluye sucursales de comercio; se usa el PDV del abono. Cada canje se atribuye al PDV donde el usuario recibió más puntos.")
orden = st.radio("Ordenar por", ["Mayor monto canjeado", "Mayor % de canje"], horizontal=True)
can_v = can.sort_values("cj" if orden.startswith("Mayor monto") else "rate", ascending=False)
st.dataframe(can_v.reset_index().rename(columns={"canal": "Canal (PDV)", "ab": "Total abonado", "cj": "Total canjeado", "rate": "% de canje",
             "nab": "Nº abonos", "ncj": "Nº canjes", "ticket": "Ticket promedio"}), hide_index=True, width="stretch",
             column_config={"% de canje": st.column_config.NumberColumn(format="percent"),
                            **{k: st.column_config.NumberColumn(format="$%d") for k in ["Total abonado", "Total canjeado", "Ticket promedio"]}})

# ---------- Distribución ----------
st.subheader("Distribución de canjes")
bins = [0, 5000, 10000, 15000, 20000, 30000, 50000, 100000, float("inf")]
labels = ["< $5 mil", "$5–10 mil", "$10–15 mil", "$15–20 mil", "$20–30 mil", "$30–50 mil", "$50–100 mil", "≥ $100 mil"]
h = pd.cut(C.monto, bins, right=False, labels=labels).value_counts().reindex(labels)
d1c, d2c = st.columns([1.4, 1])
d1c.plotly_chart(go.Figure(go.Bar(x=h.index, y=h.values, marker_color=CELESTE)).update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0)),
                 width="stretch")
if ncj:
    s = d2c.columns(2)
    s[0].metric("Promedio", clp(C.monto.mean())); s[1].metric("Mediana", clp(C.monto.median()))
    s[0].metric("Mínimo", clp(C.monto.min())); s[1].metric("Máximo", clp(C.monto.max()))
    s[0].metric("Monto más frecuente", clp(C.monto.mode().iloc[0])); s[1].metric("Comercios con canjes", C.comercio.nunique())

# ---------- Tabla detallada ----------
st.subheader("Tabla detallada")
grp = st.selectbox("Agrupar por", ["Mes y canal", "Mes", "Canal", "Mes y comercio", "Comercio", "Concepto de abono"])
keys = {"Mes y canal": ["mes", "canal"], "Mes": ["mes"], "Canal": ["canal"], "Mes y comercio": ["mes", "comercio"],
        "Comercio": ["comercio"], "Concepto de abono": ["campana"]}[grp]
parts = []
if "comercio" not in keys: parts.append(A.groupby(keys).monto.agg(**{"Total abonado": "sum", "Nº abonos": "count"}))
if "campana" not in keys: parts.append(C.groupby(keys).monto.agg(**{"Total canjeado": "sum", "Nº canjes": "count"}))
det = pd.concat(parts, axis=1)
if {"Total abonado", "Total canjeado"} <= set(det.columns):
    det = det.fillna(0); det["% canje"] = det["Total canjeado"] / det["Total abonado"].replace(0, pd.NA)
st.dataframe(det.reset_index().rename(columns={"mes": "Mes", "canal": "Canal (PDV)", "comercio": "Comercio", "campana": "Concepto de abono"}),
             hide_index=True, width="stretch",
             column_config={"% canje": st.column_config.NumberColumn(format="percent"),
                            **{k: st.column_config.NumberColumn(format="$%d") for k in ["Total abonado", "Total canjeado"]}})

with st.expander("Metodología y calidad de datos"):
    st.markdown(f"""
- **% de canje** = Total canjeado ÷ Total abonado × 100. **Saldo no canjeado** = Abonado − Canjeado. **Ticket promedio** = Canjeado ÷ Nº canjes.
- Monto abonado = columna `puntos` (abonos); monto canjeado = columna `monto` (canjes). Se asume 1 punto = $1.
- Comercio solo existe en canjes (`empresa`); por eso no hay % de canje por comercio. Se unificaron variantes (Super_10, Mayorista_10, Mayorista10).
- El archivo no tiene sucursales de comercio: se usa `nombre pdv` como canal ({QA['abonos_sin_pdv']:,} abonos sin PDV → "Sin PDV asignado").
- {QA['abonos_duplicados_exactos']} abonos idénticos salvo el Id (se mantienen). {QA['canjes_monto_menor_1000']} canjes menores a $1.000.
- RUT, nombre, email, usuario e Id no se muestran en ninguna parte. {QA.get('conceptos_anonimizados', 0)} descripciones de abono con nombres de personas se reemplazaron por una etiqueta genérica.
""")
