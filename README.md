# Dashboard de Abonos y Canjes

Dashboard ejecutivo para analizar la utilización de puntos: cuánto se abonó, cuánto se canjeó, qué % se utilizó y en qué comercios y canales se concentra el uso. Usa la colorimetría de Entel.

Incluye dos versiones con los mismos cálculos:

| Versión | Para qué sirve |
|---|---|
| **Streamlit** (`app.py`) | Lee el Excel original y recalcula todo. Para uso interno o para actualizar con datos nuevos. |
| **Web estática** (`docs/index.html`) | Un solo archivo HTML con datos ya agregados. Se abre en cualquier navegador o se publica con GitHub Pages. |

## Privacidad

- El Excel fuente **no se sube al repositorio**: `.gitignore` excluye `data/` y todo `*.xlsx`, porque contiene RUT, nombres y emails.
- Algunas descripciones de abono contienen nombres de personas en lugar de campañas. `data_prep.py` las detecta (cruzándolas con los nombres de beneficiarios) y las reemplaza por "Concepto con dato personal (anonimizado)".
- RUT y usuario se usan solo en memoria para atribuir cada canje al canal del usuario. Nunca aparecen en gráficos, tablas ni filtros.
- `docs/index.html` contiene **solo datos agregados** (por día, canal, comercio y monto), pero son datos comerciales del cliente: **mantén el repositorio privado**.

## Estructura

```
├── app.py                  # Dashboard Streamlit
├── data_prep.py            # Lectura, limpieza y anonimización del Excel
├── build_html.py           # Genera docs/index.html desde el Excel
├── web/template.html       # Plantilla del dashboard web
├── docs/index.html         # Dashboard web generado (GitHub Pages)
├── assets/logo_entel.png
├── .streamlit/config.toml  # Tema con colores Entel
├── data/                   # Aquí va el Excel (ignorado por git)
└── requirements.txt
```

## Uso

```bash
git clone <url-del-repo>
cd dashboard-abonos-canjes
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Copia el Excel en `data/` (por ejemplo `data/ticket_51020.xlsx`).

**Streamlit**

```bash
streamlit run app.py
```

Se abre en http://localhost:8501. Si no hay Excel en `data/`, se puede subir desde la barra lateral.

**Actualizar la versión web**

```bash
python build_html.py data/ticket_51020.xlsx
```

Luego haz commit de `docs/index.html`.

## Publicar

- **GitHub Pages:** Settings → Pages → *Deploy from a branch* → rama `main`, carpeta `/docs`. Ojo: en repos privados requiere un plan de pago, y la página queda pública aunque el repo sea privado (salvo en GitHub Enterprise con Pages privadas).
- **Streamlit Community Cloud:** conecta el repo y elige `app.py`. Como el Excel no está en el repo, se sube desde la barra lateral.

## Datos esperados

Excel con dos pestañas:

- **abonos:** `fecha`, `puntos` (monto), `nombre pdv` (canal), `ultimo_estado`, `descripcion` (concepto), `rut`.
- **canjes:** `fecha`, `monto`, `empresa` (comercio), `giftcard` (red), `usuario`.

El lector soporta el formato *Strict Open XML*, que pandas no abre directamente, convirtiéndolo en memoria.

## Métricas

| Métrica | Fórmula |
|---|---|
| % de canje | Total canjeado ÷ Total abonado × 100 |
| Saldo no canjeado | Total abonado − Total canjeado |
| Ticket promedio | Total canjeado ÷ Nº de canjes |

Se asume 1 punto = $1 (CLP).

## Consideraciones

- **El % de canje puede superar 100%.** En los datos actuales se canjeó más de lo abonado (123,9%), probablemente por saldo anterior al período del archivo. Se muestra como dato, sin interpretarlo.
- **Comercio** solo existe en canjes, así que no hay % de canje por comercio; se muestra la participación en el total canjeado.
- **No hay sucursales de comercio** en el archivo. Se usa el PDV de los abonos como canal, y cada canje se asigna al PDV donde el usuario recibió más puntos.
- **Filtros de un solo lado:** comercio y red afectan solo a canjes; estado solo a abonos.
- Limpieza aplicada: acentos mal codificados corregidos y variantes de comercio unificadas (Super_10, Mayorista_10, Mayorista10).
