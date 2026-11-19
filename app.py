"""
Volleyball League Analytics Dashboard (Data Volley DVW)
Developed for comprehensive league analysis: team efficiencies, league rankings,
player quadrants vs league averages, and head-to-head comparisons.
"""

import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from dvw_parser import load_all_dvw_matches, parse_dvw_file
from ferro_theme import (
    inject_css, sidebar_brand, render_header, footer, short_team,
    ranking_colors, team_colors, VERDE, VERDE_OSCURO, VERDE_MEDIO, ROJO, NARANJA
)
import gestion
import ficha_jugadora
from analytics import (
    compute_team_rankings,
    compute_player_stats,
    get_league_benchmarks,
    load_official_positions_dict
)

# Page configuration
st.set_page_config(
    page_title="Ferro Vóley · VoleyStats",
    page_icon="🏐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Identidad visual del club (verde y blanco)
inject_css()

# Session state initialization
if 'data_folder' not in st.session_state:
    st.session_state['data_folder'] = r"c:\ALICIA\VOLEY\FERRO\METRO 2026"
if 'matches_df' not in st.session_state:
    st.session_state['matches_df'] = pd.DataFrame()
if 'players_df' not in st.session_state:
    st.session_state['players_df'] = pd.DataFrame()
if 'events_df' not in st.session_state:
    st.session_state['events_df'] = pd.DataFrame()

APP_VERSION = "1.3"
PUBLICO = gestion.modo_publico()   # True = versión para jugadoras (sin carpeta local ni gestión)

# Helper to load data
def _acortar_equipos(matches, players, events):
    """Muestra nombres cortos de club (Ferro, Boca, River...) sin tocar la caché en disco."""
    if not matches.empty:
        matches = matches.assign(home_team=matches['home_team'].map(short_team),
                                 away_team=matches['away_team'].map(short_team))
    if not events.empty:
        events = events.assign(team_name=events['team_name'].map(short_team),
                               opponent_name=events['opponent_name'].map(short_team))
    if not players.empty:
        players = players.assign(team_name=players['team_name'].map(short_team))
    return matches, players, events

def load_data(folder_path):
    """Lee la carpeta de partidos + los subidos desde la app, y aplica los partidos ocultos."""
    gestion.ensure_dirs()
    gestion.migrate_old_uploads()
    gestion.sync_legacy_positions()
    if not os.path.isdir(folder_path) and not PUBLICO:
        st.info("No se encontró la carpeta indicada: se usan los partidos de esa carpeta guardados en la caché, "
                "más los subidos desde la app.")
    cache_path = os.path.join(os.path.dirname(__file__), "dvw_cache.pkl")
    with st.spinner("Leyendo partidos..."):
        matches, players, events = load_all_dvw_matches([folder_path, gestion.UPLOAD_DIR], cache_file=cache_path)
    excl = gestion.load_excluded()
    if excl and not matches.empty:
        matches = matches[~matches['filename'].str.lower().isin(excl)].reset_index(drop=True)
        if not events.empty:
            events = events[~events['file'].str.lower().isin(excl)].reset_index(drop=True)
    return _acortar_equipos(matches, players, events)


def recargar():
    m, p, e = load_data(st.session_state['data_folder'])
    st.session_state['matches_df'] = m
    st.session_state['players_df'] = p
    st.session_state['events_df'] = e


# Sidebar
with st.sidebar:
    sidebar_brand()
    st.caption("Analítica de voleibol desde archivos Data Volley")
    torneo_slot = st.container()
    st.divider()

    if not PUBLICO:
        st.subheader("📂 Carpeta de partidos")
        folder_input = st.text_input("Carpeta con archivos .dvw", value=st.session_state['data_folder'])
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("🔄 Cargar / Actualizar", use_container_width=True):
                st.session_state['data_folder'] = folder_input
                recargar()
                st.success(f"¡{len(st.session_state['matches_df'])} partidos cargados!")
        with col_btn2:
            if st.button("🧹 Limpiar Caché", use_container_width=True,
                         help="Borra la memoria de lectura. Si la carpeta no está disponible en esta PC, esos partidos se pierden."):
                cache_file = os.path.join(os.path.dirname(__file__), "dvw_cache.pkl")
                if os.path.exists(cache_file):
                    os.remove(cache_file)
                st.info("Caché reiniciada.")
        st.caption("Para **sumar o quitar partidos** y cargar el **Excel de puestos**, usá la pestaña 📁 Partidos y Archivos.")


    st.divider()
    pos_file = gestion.positions_path()
    if PUBLICO:
        if pos_file:
            st.success("✅ Puestos de las jugadoras cargados")
    elif pos_file:
        st.success("✅ Puestos vinculados desde Excel")
    else:
        st.caption("ℹ️ Sin Excel de puestos. La app muestra métricas directas sin asumir puestos.")
    st.caption("Desarrollado para cuerpo técnico y análisis estadístico avanzado de Voleibol.")
    st.caption(f"Versión {APP_VERSION}" + (" · publicada" if PUBLICO else " · administración"))

# Auto-load on first run
if st.session_state['matches_df'].empty and not st.session_state.get('auto_cargado'):
    recargar()
    st.session_state['auto_cargado'] = True

raw_matches = st.session_state['matches_df']
raw_events = st.session_state['events_df']
players_df = st.session_state['players_df']

# Si hay partidos de varios torneos, se analiza uno a la vez
matches_df, events_df = raw_matches, raw_events
if not raw_matches.empty:
    cuenta = raw_matches['tournament'].value_counts()
    if len(cuenta) > 1:
        if st.session_state.get('torneo_sel') not in cuenta.index:
            st.session_state.pop('torneo_sel', None)
        with torneo_slot:
            torneo_sel = st.selectbox("🏆 Torneo a analizar", list(cuenta.index), key="torneo_sel",
                                      help="Hay partidos de más de un torneo cargados. Los números se calculan solo con el elegido.")
        matches_df = raw_matches[raw_matches['tournament'] == torneo_sel].reset_index(drop=True)
        events_df = raw_events[raw_events['tournament'] == torneo_sel].reset_index(drop=True)

if PUBLICO and not matches_df.empty:
    with torneo_slot:
        st.caption(f"📊 {len(matches_df)} partidos analizados")

# Top Header
render_header(matches_df)
gestion.mostrar_flash()

if matches_df.empty or events_df.empty:
    if PUBLICO:
        st.warning("⚠️ Todavía no hay partidos para mostrar.")
    else:
        st.warning("⚠️ No hay partidos cargados. Subí archivos .dvw acá abajo o indicá la carpeta en la barra lateral.")
        gestion.render_partidos(raw_matches, recargar)
    st.stop()

# Compute core analytics
pos_path = gestion.positions_path()
positions = load_official_positions_dict(pos_path)


@st.cache_data(show_spinner="Calculando estadísticas...")
def compute_all(_events, _matches, _positions, key):
    # `key` se hashea (los argumentos con _ no): identifica qué partidos y qué Excel se están usando.
    tr = compute_team_rankings(_events, _matches)
    ps = compute_player_stats(_events, _matches, _positions)
    return tr, ps, get_league_benchmarks(ps)


team_rankings, player_stats, league_benchmarks = compute_all(
    events_df, matches_df, positions,
    (tuple(sorted(matches_df['filename'])), pos_path, os.path.getmtime(pos_path) if pos_path else 0)
)

# Top KPI Banner
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.markdown(f'<div class="metric-card"><div class="metric-val">{len(matches_df)}</div><div class="metric-lbl">Partidos Analizados</div></div>', unsafe_allow_html=True)
with col2:
    st.markdown(f'<div class="metric-card"><div class="metric-val">{len(team_rankings)}</div><div class="metric-lbl">Equipos en Liga</div></div>', unsafe_allow_html=True)
with col3:
    st.markdown(f'<div class="metric-card"><div class="metric-val">{len(player_stats)}</div><div class="metric-lbl">Jugadoras Registradas</div></div>', unsafe_allow_html=True)
with col4:
    st.markdown(f'<div class="metric-card"><div class="metric-val">{len(events_df):,}</div><div class="metric-lbl">Acciones Analizadas</div></div>', unsafe_allow_html=True)
with col5:
    st.markdown(f'<div class="metric-card"><div class="metric-val">{league_benchmarks.get("atq_efic_mean", 0)}%</div><div class="metric-lbl">Efic. Ataque Liga</div></div>', unsafe_allow_html=True)

st.write("")

# Explanatory collapse for "Balance de Puntos"
with st.expander("ℹ️ ¿Qué indica el Balance de Puntos? (Haz clic para ver la fórmula y significado)"):
    st.markdown("""
    El **Balance de Puntos** mide el **saldo neto real** que una jugadora o equipo aporta al marcador:
    $$\\text{Balance} = \\text{Puntos Ganados Directos} - \\text{Errores No Forzados Cometidos}$$

    * **Puntos Ganados (+):** Remates punto (Ataque `#`) + Bloqueos directos (Bloqueo `#`) + Saques directos (Aces `#`).
    * **Errores Directos (-):** Errores de ataque (red/fuera: `=`), Ataques bloqueados por el rival (`/`), Errores de saque (`=`), Errores de recepción (ace rival: `=`) e Invasiones de bloqueo (`=`).

    **Interpretación técnica:**
    * Un balance fuertemente positivo (ej. $+30$, $+60$) indica jugadoras desequilibrantes que producen mucho más de lo que conceden en fallos.
    * Un balance cercano a $0$ o negativo indica que los puntos ganados se vieron neutralizados por los errores directos cometidos.
    """)

# Navigation Tabs
nombres_tabs = [
    "🏆 Rankings de Equipos",
    "📊 Eficiencia por Equipo & Plantel",
    "🎯 Mapa de Jugadoras (vs Promedio Liga)",
    "⚔️ Comparativa Cara a Cara",
    "🙋‍♀️ Ficha de Jugadora",
]
if not PUBLICO:
    nombres_tabs.append("📁 Partidos y Archivos")
_tabs = st.tabs(nombres_tabs)
tab1, tab2, tab3, tab4, tab5 = _tabs[:5]
tab6 = _tabs[5] if not PUBLICO else None

# -------------------------------------------------------------
# TAB 1: RANKINGS DE EQUIPOS
# -------------------------------------------------------------
with tab1:
    st.subheader("Clasificación y Rankings de Equipos de la Liga")
    st.markdown("Compara el rendimiento global de los equipos en cada fase del juego. Ordena por cualquier columna haciendo click en su encabezado.")

    fundamento = st.radio(
        "Seleccionar Fundamento para Ranking:",
        ["Ataque (General & Fases)", "Recepción", "Saque", "Bloqueo", "Balance General"],
        horizontal=True
    )

    if fundamento == "Ataque (General & Fases)":
        cols_show = ['Equipo', 'Partidos', 'Sets', 'Atq_Tot', 'Atq_Pts', 'Atq_%Pts', 'Atq_%Err', 'Atq_%Bloq', 'Atq_Efic', 'K1_Efic', 'K2_Efic']
        df_display = team_rankings[cols_show].sort_values(by='Atq_Efic', ascending=False)
        st.dataframe(df_display.style.highlight_max(subset=['Atq_%Pts', 'Atq_Efic', 'K1_Efic', 'K2_Efic'], color='#d1fae5')
                                   .highlight_min(subset=['Atq_%Err', 'Atq_%Bloq'], color='#d1fae5'),
                     use_container_width=True)

        fig = px.bar(
            df_display,
            x='Atq_Efic',
            y='Equipo',
            orientation='h',
            title="Eficiencia Neta de Ataque por Equipo (%)",
            labels={'Atq_Efic': 'Eficiencia (%)', 'Equipo': 'Equipo'},
            color='Equipo',
            color_discrete_map=ranking_colors(df_display['Equipo'])
        )
        fig.update_layout(yaxis={'categoryorder': 'total ascending'}, height=450, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    elif fundamento == "Recepción":
        cols_show = ['Equipo', 'Partidos', 'Sets', 'Rec_Tot', 'Rec_#', 'Rec_%#', 'Rec_%Pos', 'Rec_%Err', 'Rec_Efic']
        df_display = team_rankings[cols_show].sort_values(by='Rec_%Pos', ascending=False)
        st.dataframe(df_display.style.highlight_max(subset=['Rec_%#', 'Rec_%Pos', 'Rec_Efic'], color='#d1fae5')
                                   .highlight_min(subset=['Rec_%Err'], color='#d1fae5'),
                     use_container_width=True)

        fig = px.bar(
            df_display,
            x=['Rec_%#', 'Rec_%Pos'],
            y='Equipo',
            barmode='group',
            orientation='h',
            title="Recepción: % Doble Positiva (#) vs % Positiva Total (+ y #)",
            labels={'value': 'Porcentaje (%)', 'variable': 'Tipo de Recepción'},
            color_discrete_sequence=[VERDE_OSCURO, VERDE_MEDIO]
        )
        fig.update_layout(yaxis={'categoryorder': 'total ascending'}, height=450, legend_title_text='')
        st.plotly_chart(fig, use_container_width=True)

    elif fundamento == "Saque":
        cols_show = ['Equipo', 'Partidos', 'Sets', 'Saq_Tot', 'Saq_Aces', 'Saq_Aces/Set', 'Saq_%Err', 'Saq_%Presion']
        df_display = team_rankings[cols_show].sort_values(by='Saq_Aces/Set', ascending=False)
        st.dataframe(df_display.style.highlight_max(subset=['Saq_Aces', 'Saq_Aces/Set', 'Saq_%Presion'], color='#d1fae5')
                                   .highlight_min(subset=['Saq_%Err'], color='#d1fae5'),
                     use_container_width=True)

        fig = px.bar(
            df_display,
            x='Saq_Aces/Set',
            y='Equipo',
            orientation='h',
            title="Aces de Saque por Set Jugado",
            color='Equipo',
            color_discrete_map=ranking_colors(df_display['Equipo'])
        )
        fig.update_layout(yaxis={'categoryorder': 'total ascending'}, height=450, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    elif fundamento == "Bloqueo":
        cols_show = ['Equipo', 'Partidos', 'Sets', 'Bloq_Pts', 'Bloq_Pts/Set', 'Bloq_Pos']
        df_display = team_rankings[cols_show].sort_values(by='Bloq_Pts/Set', ascending=False)
        st.dataframe(df_display.style.highlight_max(subset=['Bloq_Pts', 'Bloq_Pts/Set'], color='#d1fae5'),
                     use_container_width=True)

        fig = px.bar(
            df_display,
            x='Bloq_Pts/Set',
            y='Equipo',
            orientation='h',
            title="Puntos de Bloqueo por Set Jugado",
            color='Equipo',
            color_discrete_map=ranking_colors(df_display['Equipo'])
        )
        fig.update_layout(yaxis={'categoryorder': 'total ascending'}, height=450, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    elif fundamento == "Balance General":
        cols_show = ['Equipo', 'Partidos', 'Sets', 'Ptos_Tot', 'Ptos/Set', 'Err_Tot', 'Balance']
        df_display = team_rankings[cols_show].sort_values(by='Balance', ascending=False)
        st.dataframe(df_display.style.highlight_max(subset=['Ptos_Tot', 'Ptos/Set', 'Balance'], color='#d1fae5')
                                   .highlight_min(subset=['Err_Tot'], color='#d1fae5'),
                     use_container_width=True)

# -------------------------------------------------------------
# TAB 2: DETALLE Y EFICIENCIA POR EQUIPO
# -------------------------------------------------------------
with tab2:
    st.subheader("Detalle del Equipo y Desglose de Jugadoras")

    team_list = sorted(team_rankings['Equipo'].unique())
    default_idx = 0
    for idx, t in enumerate(team_list):
        if 'ferro' in t.lower():
            default_idx = idx
            break

    selected_team = st.selectbox("Seleccionar Equipo:", team_list, index=default_idx)

    team_row = team_rankings[team_rankings['Equipo'] == selected_team].iloc[0]

    # Display team KPIs vs League Averages
    st.markdown(f"#### Resumen de Rendimiento: **{selected_team}**")
    t_c1, t_c2, t_c3, t_c4, t_c5 = st.columns(5)
    with t_c1:
        st.metric(
            label="Eficiencia de Ataque",
            value=f"{team_row['Atq_Efic']}%",
            delta=f"{round(team_row['Atq_Efic'] - league_benchmarks.get('atq_efic_mean', 0), 1)}% vs Liga"
        )
    with t_c2:
        st.metric(
            label="Recepción Positiva",
            value=f"{team_row['Rec_%Pos']}%",
            delta=f"{round(team_row['Rec_%Pos'] - league_benchmarks.get('rec_pct_pos_mean', 0), 1)}% vs Liga"
        )
    with t_c3:
        st.metric(
            label="Aces por Set",
            value=f"{team_row['Saq_Aces/Set']}",
            delta=f"{round(team_row['Saq_Aces/Set'] - league_benchmarks.get('saq_aces_per_set_mean', 0), 2)} vs Liga"
        )
    with t_c4:
        st.metric(
            label="Bloqueos por Set",
            value=f"{team_row['Bloq_Pts/Set']}",
            delta=f"{round(team_row['Bloq_Pts/Set'] - league_benchmarks.get('bloq_pts_per_set_mean', 0), 2)} vs Liga"
        )
    with t_c5:
        st.metric(
            label="Puntos por Set",
            value=f"{team_row['Ptos/Set']}",
            delta=f"{round(team_row['Ptos/Set'] - league_benchmarks.get('ptos_per_set_mean', 0), 1)} vs Liga"
        )

    st.write("")

    # Complex 1 vs Complex 2 Comparison
    k_col1, k_col2 = st.columns(2)
    with k_col1:
        st.markdown("##### Ataque según Fase de Juego (K1 vs K2)")
        k_df = pd.DataFrame({
            'Fase': ['K1 (Side-out tras recepción)', 'K2 (Contraataque tras defensa)'],
            'Eficiencia (%)': [team_row['K1_Efic'], team_row['K2_Efic']]
        })
        fig_k = px.bar(k_df, x='Fase', y='Eficiencia (%)', color='Fase', text_auto=True, color_discrete_sequence=[VERDE, VERDE_MEDIO])
        fig_k.update_layout(showlegend=False, height=280)
        st.plotly_chart(fig_k, use_container_width=True)

    with k_col2:
        st.markdown("##### Desglose de Ataque (%)")
        atq_breakdown = pd.DataFrame({
            'Resultado': ['Punto (#)', 'Continuidad (-)', 'Error (=)', 'Bloqueado (/)'],
            'Porcentaje': [
                team_row['Atq_%Pts'],
                max(0.0, round(100 - team_row['Atq_%Pts'] - team_row['Atq_%Err'] - team_row['Atq_%Bloq'], 1)),
                team_row['Atq_%Err'],
                team_row['Atq_%Bloq']
            ]
        })
        fig_pie = px.pie(atq_breakdown, values='Porcentaje', names='Resultado', color_discrete_sequence=[VERDE, VERDE_MEDIO, ROJO, NARANJA])
        fig_pie.update_layout(height=280, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig_pie, use_container_width=True)

    # Team roster players table
    st.markdown(f"##### Plantel Completo de {selected_team}")
    team_players = player_stats[player_stats['Equipo'] == selected_team].copy()
    if not team_players.empty:
        # Show verified position only if known, otherwise omitted
        has_verified_pos = (team_players['Puesto'] != '—').any()
        p_cols = ['Numero', 'Jugadora']
        if has_verified_pos:
            p_cols.append('Puesto')
        p_cols += ['Partidos', 'Sets', 'Atq_Tot', 'Atq_Pts', 'Atq_Efic', 'Rec_Tot', 'Rec_%Pos', 'Rec_Efic', 'Saq_Aces', 'Bloq_Pts', 'Ptos_Tot', 'Balance']

        st.dataframe(
            team_players[p_cols].sort_values(by='Ptos_Tot', ascending=False),
            use_container_width=True
        )
    else:
        st.info("No hay jugadoras registradas para este equipo.")

# -------------------------------------------------------------
# TAB 3: MAPA DE JUGADORAS (SCATTER / CUADRANTES VS LIGA)
# -------------------------------------------------------------
with tab3:
    st.subheader("Mapa de Rendimiento de Jugadoras respecto al Promedio General de la Liga")
    st.markdown("Identifica a las jugadoras determinantes mediante gráficos de 4 cuadrantes. Puedes comparar todos los equipos o filtrar únicamente los equipos que te interesan. Las líneas punteadas rojas siempre representan la **media exacta general de la liga**.")

    all_teams_list = sorted(player_stats['Equipo'].unique())

    m_col1, m_col2, m_col3 = st.columns([1.5, 1, 2])
    with m_col1:
        eje_opcion = st.selectbox(
            "Fundamento a analizar:",
            [
                "Ataque: Volumen vs Eficiencia Neta",
                "Ataque: % Puntos (#) vs % Errores (=)",
                "Recepción: Volumen vs % Positiva",
                "Recepción: % Doble Positiva (#) vs % Error (=)",
                "Saque: Volumen vs Aces por Set"
            ]
        )
    with m_col2:
        min_intentos = st.slider("Mínimo de intentos / toques:", min_value=5, max_value=80, value=25)
    with m_col3:
        equipos_filtro = st.multiselect(
            "Filtrar Equipos a comparar:",
            options=all_teams_list,
            default=[],
            placeholder="Todos los equipos de la liga",
            help="Selecciona uno o varios equipos específicos para enfocar la comparación. Si lo dejas vacío, se muestran todas las jugadoras de la liga."
        )

    df_scatter = player_stats.copy()

    # Determine metric columns & labels
    if eje_opcion == "Ataque: Volumen vs Eficiencia Neta":
        df_base = df_scatter[df_scatter['Atq_Tot'] >= min_intentos].copy()
        x_col = 'Atq_Tot'
        y_col = 'Atq_Efic'
        x_title = 'Volumen de Ataque (Total de remates)'
        y_title = 'Eficiencia Neta de Ataque (%)'

    elif eje_opcion == "Ataque: % Puntos (#) vs % Errores (=)":
        df_base = df_scatter[df_scatter['Atq_Tot'] >= min_intentos].copy()
        x_col = 'Atq_%Err'
        y_col = 'Atq_%Pts'
        x_title = '% Errores de Ataque'
        y_title = '% Puntos de Ataque (Efectividad)'

    elif eje_opcion == "Recepción: Volumen vs % Positiva":
        df_base = df_scatter[df_scatter['Rec_Tot'] >= min_intentos].copy()
        x_col = 'Rec_Tot'
        y_col = 'Rec_%Pos'
        x_title = 'Volumen de Recepciones'
        y_title = '% Recepción Positiva Total (# y +)'

    elif eje_opcion == "Recepción: % Doble Positiva (#) vs % Error (=)":
        df_base = df_scatter[df_scatter['Rec_Tot'] >= min_intentos].copy()
        x_col = 'Rec_%Err'
        y_col = 'Rec_%#'
        x_title = '% Error de Recepción (Ace rival)'
        y_title = '% Recepción Doble Positiva / Perfecta (#)'

    elif eje_opcion == "Saque: Volumen vs Aces por Set":
        df_base = df_scatter[df_scatter['Saq_Tot'] >= min_intentos].copy()
        x_col = 'Saq_Tot'
        y_col = 'Saq_Aces/Set'
        x_title = 'Total de Saques Ejecutados'
        y_title = 'Aces Directos por Set'

    # Compute league benchmark averages from df_base (whole league)
    x_mean = df_base[x_col].mean() if not df_base.empty else 0
    y_mean = df_base[y_col].mean() if not df_base.empty else 0

    # Apply team filter if specified
    if equipos_filtro:
        df_plot = df_base[df_base['Equipo'].isin(equipos_filtro)].copy()
        texto_equipos = f"Comparando {len(equipos_filtro)} equipo(s)"
    else:
        df_plot = df_base.copy()
        texto_equipos = "Todos los equipos de la liga"

    if df_plot.empty:
        st.warning("No hay jugadoras que cumplan los filtros seleccionados. Prueba bajar el mínimo de intentos o seleccionar más equipos.")
    else:
        fig_scatter = px.scatter(
            df_plot,
            x=x_col,
            y=y_col,
            color='Equipo',
            color_discrete_map=team_colors(sorted(df_plot['Equipo'].unique())),
            hover_name='Jugadora',
            hover_data=['Equipo', 'Ptos_Tot', 'Sets', 'Balance'],
            title=f"Mapa de Dispersión: {eje_opcion} ({len(df_plot)} jugadoras | {texto_equipos})",
            labels={x_col: x_title, y_col: y_title},
            size='Ptos_Tot',
            size_max=18
        )

        fig_scatter.add_vline(x=x_mean, line_width=1.5, line_dash="dash", line_color="red")
        fig_scatter.add_hline(y=y_mean, line_width=1.5, line_dash="dash", line_color="red")

        fig_scatter.add_annotation(
            x=x_mean, y=df_plot[y_col].max(),
            text=f"Media Liga X: {round(x_mean, 1)}",
            showarrow=False, font=dict(color="red", size=11), yshift=10
        )
        fig_scatter.add_annotation(
            x=df_plot[x_col].max(), y=y_mean,
            text=f"Media Liga Y: {round(y_mean, 1)}",
            showarrow=False, font=dict(color="red", size=11), yshift=10
        )

        fig_scatter.update_layout(height=560)
        st.plotly_chart(fig_scatter, use_container_width=True)

        st.markdown(f"##### 🌟 Líderes en este Fundamento ({texto_equipos}):")
        top_destacadas = df_plot.sort_values(by=y_col, ascending=False).head(10)
        st.dataframe(top_destacadas[['Jugadora', 'Equipo', x_col, y_col, 'Ptos_Tot', 'Balance', 'Sets']], use_container_width=True)

# -------------------------------------------------------------
# TAB 4: COMPARATIVA CARA A CARA (HEAD-TO-HEAD)
# -------------------------------------------------------------
with tab4:
    st.subheader("Comparativa Cara a Cara entre Jugadoras")
    st.markdown("Compara el perfil técnico y los números acumulados de dos jugadoras cualesquiera de la liga en un gráfico de radar y tabla detallada.")

    all_players_list = player_stats.sort_values(by='Jugadora').to_dict('records')
    player_options = [f"{p['Jugadora']} ({p['Equipo']} - #{p['Numero']})" for p in all_players_list]

    p_col1, p_col2 = st.columns(2)
    with p_col1:
        st.markdown("#### 🟢 Jugadora 1")
        idx_1 = 0
        for i, opt in enumerate(player_options):
            if 'aguilar' in opt.lower() or 'ferro' in opt.lower():
                idx_1 = i
                break
        sel_1 = st.selectbox("Seleccionar Jugadora 1:", player_options, index=idx_1, key="sel_p1")
        p1_data = all_players_list[player_options.index(sel_1)]

    with p_col2:
        st.markdown("#### 🟠 Jugadora 2")
        idx_2 = 1 if len(player_options) > 1 else 0
        for i, opt in enumerate(player_options):
            if 'meinardi' in opt.lower():
                idx_2 = i
                break
        sel_2 = st.selectbox("Seleccionar Jugadora 2:", player_options, index=idx_2, key="sel_p2")
        p2_data = all_players_list[player_options.index(sel_2)]

    st.write("")

    # Player profile headers
    h1, h2 = st.columns(2)
    pos_p1_text = f" | *Puesto:* {p1_data['Puesto']}" if p1_data['Puesto'] != '—' else ""
    pos_p2_text = f" | *Puesto:* {p2_data['Puesto']}" if p2_data['Puesto'] != '—' else ""

    with h1:
        st.info(f"**{p1_data['Jugadora']}** (#{p1_data['Numero']})\n\n*Equipo:* {p1_data['Equipo']}{pos_p1_text}\n\n*Partidos:* {p1_data['Partidos']} | *Sets:* {p1_data['Sets']} | *Puntos:* {p1_data['Ptos_Tot']} | *Balance:* {p1_data['Balance']}")
    with h2:
        st.info(f"**{p2_data['Jugadora']}** (#{p2_data['Numero']})\n\n*Equipo:* {p2_data['Equipo']}{pos_p2_text}\n\n*Partidos:* {p2_data['Partidos']} | *Sets:* {p2_data['Sets']} | *Puntos:* {p2_data['Ptos_Tot']} | *Balance:* {p2_data['Balance']}")

    # Radar Chart
    categories = [
        'Efic. Ataque (%)',
        '% Atq Punto',
        '% Rec Positiva',
        'Aces / Set',
        'Bloq / Set',
        'Puntos / Set'
    ]

    def get_radar_val(p):
        return [
            max(0, min(100, p['Atq_Efic'] * 1.5)),
            max(0, min(100, p['Atq_%Pts'] * 1.5)),
            max(0, min(100, p['Rec_%Pos'] * 1.2)),
            max(0, min(100, p['Saq_Aces/Set'] * 100)),
            max(0, min(100, p['Bloq_Pts/Set'] * 100)),
            max(0, min(100, p['Ptos/Set'] * 20))
        ]

    fig_radar = go.Figure()

    fig_radar.add_trace(go.Scatterpolar(
        r=get_radar_val(p1_data),
        theta=categories,
        fill='toself',
        name=p1_data['Jugadora'],
        line_color=VERDE
    ))

    fig_radar.add_trace(go.Scatterpolar(
        r=get_radar_val(p2_data),
        theta=categories,
        fill='toself',
        name=p2_data['Jugadora'],
        line_color='#EA580C'
    ))

    fig_radar.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                showticklabels=False
            )
        ),
        showlegend=True,
        title="Perfil Técnico Comparado (Gráfico de Radar Normalizado)",
        height=450
    )
    st.plotly_chart(fig_radar, use_container_width=True)

    # Side-by-side metric comparison table
    st.markdown("##### 📋 Tabla Comparativa Métrica a Métrica")
    st.caption("Nota: Las métricas de volumen (cantidades absolutas) son contextuales y no otorgan ventaja táctica. La ventaja se calcula estrictamente en métricas de eficiencia, porcentajes y promedios por set.")

    # Format: (Metric Name, v1, v2, metric_type)
    # metric_type: 'volume' (no advantage), 'higher_is_better', 'lower_is_better'
    comp_metrics = [
        # Contexto / Volumen
        ("Partidos Jugados", p1_data['Partidos'], p2_data['Partidos'], 'volume'),
        ("Sets Jugados", p1_data['Sets'], p2_data['Sets'], 'volume'),
        ("Ataques Totales", p1_data['Atq_Tot'], p2_data['Atq_Tot'], 'volume'),
        ("Recepciones Totales", p1_data['Rec_Tot'], p2_data['Rec_Tot'], 'volume'),
        ("Saques Totales", p1_data['Saq_Tot'], p2_data['Saq_Tot'], 'volume'),
        ("Bloqueos Totales (#)", p1_data['Bloq_Pts'], p2_data['Bloq_Pts'], 'volume'),
        ("Puntos Totales Ganados", p1_data['Ptos_Tot'], p2_data['Ptos_Tot'], 'volume'),
        # Rendimiento de Ataque
        ("Eficiencia Neta de Ataque", f"{p1_data['Atq_Efic']}%", f"{p2_data['Atq_Efic']}%", 'higher_is_better'),
        ("% Puntos de Ataque (Efectividad)", f"{p1_data['Atq_%Pts']}%", f"{p2_data['Atq_%Pts']}%", 'higher_is_better'),
        ("% Errores de Ataque", f"{p1_data['Atq_%Err']}%", f"{p2_data['Atq_%Err']}%", 'lower_is_better'),
        ("% Ataques Bloqueados (Punto rival)", f"{p1_data['Atq_%Bloq']}%", f"{p2_data['Atq_%Bloq']}%", 'lower_is_better'),
        # Rendimiento de Recepción
        ("% Recepción Positiva Total (# y +)", f"{p1_data['Rec_%Pos']}%", f"{p2_data['Rec_%Pos']}%", 'higher_is_better'),
        ("% Recepción Doble Positiva (#)", f"{p1_data['Rec_%#']}%", f"{p2_data['Rec_%#']}%", 'higher_is_better'),
        ("% Error de Recepción (Ace recibido)", f"{p1_data['Rec_%Err']}%", f"{p2_data['Rec_%Err']}%", 'lower_is_better'),
        # Rendimiento de Saque
        ("Aces de Saque por Set", p1_data['Saq_Aces/Set'], p2_data['Saq_Aces/Set'], 'higher_is_better'),
        ("% Error de Saque", f"{p1_data['Saq_%Err']}%", f"{p2_data['Saq_%Err']}%", 'lower_is_better'),
        ("% Presión de Saque", f"{p1_data['Saq_%Presion']}%", f"{p2_data['Saq_%Presion']}%", 'higher_is_better'),
        # Rendimiento de Bloqueo
        ("Bloqueos Punto por Set", p1_data['Bloq_Pts/Set'], p2_data['Bloq_Pts/Set'], 'higher_is_better'),
        # Aporte Global y Balance
        ("Puntos Ganados por Set", p1_data['Ptos/Set'], p2_data['Ptos/Set'], 'higher_is_better'),
        ("Balance de Puntos Total", p1_data['Balance'], p2_data['Balance'], 'higher_is_better'),
        ("Balance de Puntos por Set", p1_data['Balance/Set'], p2_data['Balance/Set'], 'higher_is_better'),
    ]

    comp_rows = []
    for m_name, v1, v2, m_type in comp_metrics:
        raw_v1 = float(str(v1).replace('%', ''))
        raw_v2 = float(str(v2).replace('%', ''))

        if m_type == 'volume':
            adv = "—"
        elif m_type == 'higher_is_better':
            if raw_v1 > raw_v2:
                adv = f"🟢 {p1_data['Jugadora']}"
            elif raw_v2 > raw_v1:
                adv = f"🟠 {p2_data['Jugadora']}"
            else:
                adv = "Empate"
        elif m_type == 'lower_is_better':
            if raw_v1 < raw_v2:
                adv = f"🟢 {p1_data['Jugadora']}"
            elif raw_v2 < raw_v1:
                adv = f"🟠 {p2_data['Jugadora']}"
            else:
                adv = "Empate"
        else:
            adv = "—"

        comp_rows.append({
            'Métrica': m_name,
            f"🟢 {p1_data['Jugadora']}": v1,
            f"🟠 {p2_data['Jugadora']}": v2,
            'Ventaja Táctica': adv
        })

    st.dataframe(pd.DataFrame(comp_rows).astype(str), use_container_width=True)

# -------------------------------------------------------------
# TAB 5: FICHA DE JUGADORA
# -------------------------------------------------------------
with tab5:
    ficha_jugadora.render(events_df, matches_df, player_stats)

# -------------------------------------------------------------
# TAB 6: PARTIDOS Y ARCHIVOS (agregar / quitar partidos, Excel de puestos)
# -------------------------------------------------------------
if tab6 is not None:
    with tab6:
        gestion.render_partidos(raw_matches, recargar)
        gestion.render_puestos(players_df, player_stats)

footer()
