"""Carga, limpieza y anonimización de ticket_51020.xlsx (pestañas abonos / canjes).

Ninguna columna identificatoria (rut, nombre, email, usuario, Id) sale de este módulo:
el RUT se usa solo internamente para atribuir cada canje al canal (PDV) del usuario.
"""
import io, re, unicodedata, zipfile
import pandas as pd

STRICT_NS = {
    "http://purl.oclc.org/ooxml/spreadsheetml/main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "http://purl.oclc.org/ooxml/officeDocument/relationships": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "http://purl.oclc.org/ooxml/drawingml/main": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "http://purl.oclc.org/ooxml/officeDocument/extendedProperties": "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties",
    "http://purl.oclc.org/ooxml/officeDocument/docPropsVTypes": "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes",
}


def _strict_to_transitional(raw: bytes) -> bytes:
    """El archivo viene en formato 'Strict Open XML', que openpyxl no reconoce.
    Se reescriben los namespaces al formato estándar (transitional) en memoria."""
    src = zipfile.ZipFile(io.BytesIO(raw))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename.endswith((".xml", ".rels")):
                txt = data.decode("utf-8")
                for k, v in STRICT_NS.items():
                    txt = txt.replace(k, v)
                txt = txt.replace(' conformance="strict"', "")
                data = txt.encode("utf-8")
            dst.writestr(item, data)
    return out.getvalue()


def read_workbook(path_or_bytes):
    raw = path_or_bytes if isinstance(path_or_bytes, bytes) else open(path_or_bytes, "rb").read()
    try:
        sheets = pd.read_excel(io.BytesIO(raw), sheet_name=None)
        if not sheets:
            raise ValueError
    except Exception:
        sheets = pd.read_excel(io.BytesIO(_strict_to_transitional(raw)), sheet_name=None)
    sheets = {k.strip().lower(): v for k, v in sheets.items()}
    return sheets["abonos"], sheets["canjes"]


def fix_text(s):
    """Corrige textos con acentos mal codificados (p. ej. 'Desaf√≠o' -> 'Desafío')."""
    if not isinstance(s, str):
        return s
    try:
        return s.encode("mac_roman").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


# Variantes del mismo comercio que solo difieren en guion bajo / espaciado
COMERCIO_ALIAS = {
    "Super_10": "Super 10",
    "Mayorista_10": "Mayorista 10",
    "Mayorista10": "Mayorista 10",
}


PERSONAL_LABEL = "Concepto con dato personal (anonimizado)"


def _norm(s):
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()


def _tokens(s):
    return set(re.findall(r"[a-z]{3,}", _norm(s)))


def anonymize_concepts(desc: pd.Series, nombres: pd.Series) -> pd.Series:
    """Algunas descripciones de abono contienen el nombre de una persona en lugar
    del nombre de la campaña. Se reemplazan por una etiqueta genérica si:
    - comparten 2+ palabras con el nombre del propio beneficiario de esa fila, o
    - contienen el apellido paterno y el primer nombre de cualquier beneficiario."""
    pairs = set()
    for n in nombres.dropna():
        p = re.findall(r"[a-z]{3,}", _norm(n))
        if len(p) >= 3:
            pairs.add((p[0], p[2]))
        if len(p) >= 2:
            pairs.add((p[0], p[1]))
    personal = {}
    out = desc.copy()
    for i, (d, n) in enumerate(zip(desc, nombres)):
        if d in personal:
            if personal[d]:
                out.iat[i] = PERSONAL_LABEL
            continue
        dt = _tokens(d)
        hit = len(dt & _tokens(n)) >= 2 or any(a in dt and b in dt for a, b in pairs)
        if hit:
            out.iat[i] = PERSONAL_LABEL
            personal[d] = True
    return out


def _norm_rut(x):
    return re.sub(r"[^0-9K]", "", str(x).upper())


def prepare(path_or_bytes):
    """Devuelve (abonos, canjes, calidad) ya anonimizados."""
    a_raw, c_raw = read_workbook(path_or_bytes)
    qa = {
        "abonos_filas": len(a_raw),
        "canjes_filas": len(c_raw),
        "abonos_duplicados_exactos": int(a_raw.drop(columns=["Id"]).duplicated().sum()),
        "canjes_duplicados_exactos": int(c_raw.drop(columns=["id"]).duplicated().sum()),
        "abonos_sin_pdv": int(a_raw["nombre pdv"].isna().sum()),
        "canjes_monto_menor_1000": int((c_raw["monto"] < 1000).sum()),
    }

    a = pd.DataFrame({
        "fecha": pd.to_datetime(a_raw["fecha"]),
        "monto": pd.to_numeric(a_raw["puntos"], errors="coerce").fillna(0),
        "canal": a_raw["nombre pdv"].fillna("Sin PDV asignado").map(fix_text),
        "estado": a_raw["ultimo_estado"].str.strip().str.capitalize(),
        "campana": anonymize_concepts(a_raw["descripcion"].map(fix_text).str.strip(),
                                      a_raw["nombre"].map(fix_text)),
        "_rut": a_raw["rut"].map(_norm_rut),
    })

    qa["conceptos_anonimizados"] = int((a["campana"] == PERSONAL_LABEL).sum())

    # Canal de cada usuario = canal donde recibió más puntos (para atribuir canjes)
    user_canal = (a.groupby(["_rut", "canal"])["monto"].sum().reset_index()
                    .sort_values("monto", ascending=False).drop_duplicates("_rut")
                    .set_index("_rut")["canal"])
    qa["usuarios_multi_canal"] = int((a.groupby("_rut")["canal"].nunique() > 1).sum())

    c = pd.DataFrame({
        "fecha": pd.to_datetime(c_raw["fecha"]),
        "monto": pd.to_numeric(c_raw["monto"], errors="coerce").fillna(0),
        "comercio": c_raw["empresa"].map(fix_text).str.strip().replace(COMERCIO_ALIAS),
        "giftcard": c_raw["giftcard"].str.strip(),
        "_rut": c_raw["usuario"].map(_norm_rut),
    })
    c["canal"] = c["_rut"].map(user_canal).fillna("Sin abonos asociados")
    qa["canjes_sin_usuario_en_abonos"] = int((c["canal"] == "Sin abonos asociados").sum())

    # Se eliminan los identificadores: nada personal sale de aquí
    a = a.drop(columns=["_rut"])
    c = c.drop(columns=["_rut"])
    for df in (a, c):
        df["dia"] = df["fecha"].dt.normalize()
        df["mes"] = df["fecha"].dt.to_period("M").astype(str)
        df["anio"] = df["fecha"].dt.year
    return a, c, qa
