"""
Pestaña "Ficha de jugadora": pensada para mostrarla a las jugadoras.
Lenguaje simple, foco en lo positivo y dos gráficos:
  1) cómo viene partido a partido
  2) cómo se compara con sus compañeras y con la liga
"""

import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from ferro_theme import VERDE, VERDE_OSCURO, VERDE_MEDIO, GRIS, es_ferro

MIN_INTENTOS = 15  # para promediar equipo / liga y para mostrar una comparación

# (clave, texto simple, columna en player_stats, columna de volumen)
METRICAS = [
    ("atq", "Remates que terminan en punto (%)", "Atq_%Pts", "Atq_Tot"),
    ("rec", "Recepciones buenas (%)", "Rec_%Pos", "Rec_Tot"),
    ("saq", "Saques que complican al rival (%)", "Saq_%Presion", "Saq_Tot"),
]


def _promedio(df, col, vol, excluir=None):
    d = df[df[vol] >= MIN_INTENTOS]
    if excluir is not None:
        d = d[~d.index.isin([excluir])]
    return round(d[col].mean(), 1) if not d.empty else None


def _por_partido(ev, matches_df, equipo):
    filas = []
    for code, g in ev.groupby("match_code"):
        m = matches_df[matches_df["match_code"] == code]
        if m.empty:
            continue
        m = m.iloc[0]
        local = m["home_team"] == equipo
        rival = m["away_team"] if local else m["home_team"]
        a, b = (m["home_sets"], m["away_sets"]) if local else (m["away_sets"], m["home_sets"])
        atq, rec = g[g["skill"] == "A"], g[g["skill"] == "R"]
        puntos = int((atq["evaluation"] == "#").sum() + (g[g["skill"] == "S"]["evaluation"] == "#").sum()
                     + (g[g["skill"] == "B"]["evaluation"] == "#").sum())
        filas.append({
            "fecha": pd.to_datetime(m["date"], dayfirst=True, errors="coerce"),
            "etiqueta": f"{rival}<br>{str(m['date'])[:5]}",
            "resultado": f"{int(a)}-{int(b)}",
            "rival": rival,
            "puntos": puntos,
            "pct_atq": (atq["evaluation"] == "#").mean() * 100 if len(atq) >= 5 else None,
            "pct_rec": rec["evaluation"].isin(["#", "+"]).mean() * 100 if len(rec) >= 5 else None,
            "n_atq": len(atq), "n_rec": len(rec),
        })
    return pd.DataFrame(filas).sort_values("fecha").reset_index(drop=True) if filas else pd.DataFrame()


def _card(valor, titulo):
    return f'<div class="metric-card"><div class="metric-val">{valor}</div><div class="metric-lbl">{titulo}</div></div>'


def render(events_df, matches_df, player_stats):
    st.subheader("Ficha de jugadora")
    st.markdown("Un resumen simple de cómo viene cada jugadora: sus puntos, su evolución y cómo se compara con el equipo y la liga.")

    ps = player_stats.reset_index(drop=True)
    equipos = sorted(ps["Equipo"].unique())
    idx_eq = next((i for i, t in enumerate(equipos) if es_ferro(t)), 0)
    c1, c2 = st.columns([1, 2])
    with c1:
        equipo = st.selectbox("Equipo", equipos, index=idx_eq, key="fj_equipo")
    plantel = ps[ps["Equipo"] == equipo].sort_values("Ptos_Tot", ascending=False)
    opciones = {f"#{r['Numero']} · {r['Jugadora']}": i for i, r in plantel.iterrows()}
    with c2:
        elegida = st.selectbox("Jugadora", list(opciones), key=f"fj_jugadora_{equipo}")
    i = opciones[elegida]
    p = ps.loc[i]

    # ---------- encabezado
    puesto = f" · {p['Puesto']}" if p["Puesto"] != "—" else ""
    st.markdown(f"### {p['Jugadora']}  <span style='color:#5B6B62;font-size:1.1rem'>#{p['Numero']}{puesto} · {equipo}</span>",
                unsafe_allow_html=True)

    # A quien no suma puntos directos (ej. líbero) se le muestra su trabajo en defensa en vez de "0 puntos"
    if p["Ptos_Tot"] == 0 and p["Def_Tot"] > 0:
        principal = (int(p["Def_Tot"]), "Defensas realizadas")
    else:
        principal = (int(p["Ptos_Tot"]), "Puntos conseguidos")
    cards = [principal,
             (int(p["Partidos"]), "Partidos jugados"),
             (int(p["Sets"]), "Sets jugados")]
    if p["Atq_Tot"] >= 10:
        cards.append((f"{p['Atq_%Pts']}%", "Remates que terminan en punto"))
    if p["Rec_Tot"] >= 10:
        cards.append((f"{p['Rec_%Pos']}%", "Recepciones buenas"))
    if p["Saq_Aces"] > 0:
        cards.append((int(p["Saq_Aces"]), "Aces de saque"))
    if p["Bloq_Pts"] > 0:
        cards.append((int(p["Bloq_Pts"]), "Bloqueos que son punto"))
    cols = st.columns(min(len(cards), 6))
    for col, (v, t) in zip(cols, cards[:6]):
        col.markdown(_card(v, t), unsafe_allow_html=True)
    st.write("")

    ev = events_df[(events_df["team_name"] == p["Equipo"]) & (events_df["player_name"] == p["Jugadora"])
                   & (events_df["jersey"] == p["Numero"])]
    pp = _por_partido(ev, matches_df, p["Equipo"])

    # ---------- gráfico 1: partido a partido
    st.markdown("#### Cómo viene partido a partido")
    if pp.empty:
        st.info("Todavía no hay partidos para mostrar.")
    else:
        opciones_graf = ["Puntos por partido"]
        if pp["pct_rec"].notna().sum() >= 2:
            opciones_graf.append("Recepciones buenas (%)")
        if pp["pct_atq"].notna().sum() >= 2:
            opciones_graf.append("Remates que terminan en punto (%)")
        defecto = 0
        if p["Ptos_Tot"] < 10 and "Recepciones buenas (%)" in opciones_graf:
            defecto = opciones_graf.index("Recepciones buenas (%)")
        sel = st.radio("Ver:", opciones_graf, index=defecto, horizontal=True, key=f"fj_graf_{i}")
        col_y = {"Puntos por partido": "puntos", "Recepciones buenas (%)": "pct_rec",
                 "Remates que terminan en punto (%)": "pct_atq"}[sel]
        d = pp.dropna(subset=[col_y])
        prom = d[col_y].mean()
        mejor = d[col_y].idxmax()
        colores = [VERDE_OSCURO if k == mejor else VERDE for k in d.index]
        fmt = (lambda v: f"{v:.0f}") if col_y == "puntos" else (lambda v: f"{v:.0f}%")
        fig = go.Figure(go.Bar(
            x=d["etiqueta"], y=d[col_y], marker_color=colores,
            text=[fmt(v) for v in d[col_y]], textposition="outside",
            customdata=[[r, s] for r, s in zip(d["rival"], d["resultado"])],
            hovertemplate="%{customdata[0]} (sets %{customdata[1]})<br>%{y:.0f}<extra></extra>",
        ))
        fig.add_hline(y=prom, line_dash="dot", line_color=GRIS,
                      annotation_text=f"Tu promedio: {fmt(prom)}", annotation_position="top left")
        fig.update_layout(height=360, margin=dict(t=30, b=10, l=10, r=10), showlegend=False,
                          yaxis=dict(title=sel, rangemode="tozero"), plot_bgcolor="white")
        st.plotly_chart(fig, use_container_width=True)
        if sel != "Puntos por partido":
            st.caption("Se muestran los partidos con al menos 5 acciones de ese tipo.")
        if col_y == "puntos" and d[col_y].max() > 0:
            r = d.loc[mejor]
            st.success(f"🌟 Tu mejor partido: contra {r['rival']}, con {int(r['puntos'])} puntos.")

    # ---------- gráfico 2: comparación
    st.markdown("#### Cómo se compara con sus compañeras y con la liga")
    filas, fuertes = [], []
    for _, texto, col, vol in METRICAS:
        if p[vol] < MIN_INTENTOS:
            continue
        comp = _promedio(ps[ps["Equipo"] == p["Equipo"]], col, vol, excluir=i)
        liga = _promedio(ps, col, vol)
        filas.append((texto, p[col], comp, liga))
        if liga is not None and p[col] > liga:
            fuertes.append(f"**{texto.split(' (')[0]}**: {p[col]}% (promedio de la liga: {liga}%)")
    if not filas:
        st.info("Esta jugadora todavía tiene pocas acciones registradas para compararla (se necesitan al menos "
                f"{MIN_INTENTOS} en algún fundamento).")
    else:
        textos = [f[0] for f in filas][::-1]
        fig2 = go.Figure()
        for nombre, color, k in (("Liga", GRIS, 3), ("Compañeras", VERDE_MEDIO, 2), (p["Jugadora"], VERDE, 1)):
            vals = [f[k] for f in filas][::-1]
            fig2.add_trace(go.Bar(y=textos, x=vals, name=nombre, orientation="h", marker_color=color,
                                  text=[f"{v:.0f}%" if v is not None else "" for v in vals], textposition="outside"))
        fig2.update_layout(barmode="group", height=120 + 110 * len(filas), margin=dict(t=10, b=10, l=10, r=40),
                           xaxis=dict(title="Porcentaje (%)", range=[0, 110]), plot_bgcolor="white",
                           legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                                       traceorder="reversed"))
        st.plotly_chart(fig2, use_container_width=True)
        st.caption(f"Solo se compara en los fundamentos donde tiene al menos {MIN_INTENTOS} acciones. "
                   "\"Compañeras\" y \"Liga\" son promedios de jugadoras con esa cantidad mínima de acciones.")
        if fuertes:
            st.markdown("**Lo que está por encima del promedio de la liga:**")
            for f in fuertes:
                st.markdown(f"- ✅ {f}")

    if p["Sets"] < 6:
        st.caption("ℹ️ Con pocos sets jugados los números son orientativos: pueden moverse mucho de un partido a otro.")
