"""
Volleyball Analytics Engine:
Calculates team efficiencies, league rankings, player distributions, and head-to-head metrics.
Cleaned of speculative position guessing; focuses on exact volleyball metrics and Data Volley codes.
"""

import os
import pandas as pd
import numpy as np

def load_official_positions_dict(excel_path=None):
    """
    Lee los puestos desde un Excel con columnas APELLIDO, NOMBRE y POS (o PUESTO).
    Las columnas se detectan por el título; si no hay títulos se asumen las columnas B, C y D.
    Si un apellido lo comparten dos jugadoras, solo se vincula por apellido + nombre (nunca se adivina).
    """
    pos_dict = {}
    if not excel_path or not os.path.exists(excel_path):
        return pos_dict
    try:
        import openpyxl
        wb = openpyxl.load_workbook(excel_path, data_only=True)
        sheet = wb.active
        c_last, c_first, c_pos = 1, 2, 3
        titulos_pos = ('pos', 'puesto', 'posicion', 'posición')
        filas = []
        for row in sheet.iter_rows(values_only=True):
            cells = [str(c).strip().lower() if c is not None else "" for c in row]
            if 'apellido' in cells and any(c in titulos_pos for c in cells):
                c_last = cells.index('apellido')
                c_first = cells.index('nombre') if 'nombre' in cells else c_last + 1
                c_pos = next(i for i, c in enumerate(cells) if c in titulos_pos)
                continue
            if len(row) > max(c_last, c_first, c_pos) and row[c_last] and row[c_pos]:
                last = str(row[c_last]).strip().lower()
                first = str(row[c_first]).strip().lower() if row[c_first] else ""
                if last.startswith('en pos colocar'):
                    continue
                filas.append((last, first, str(row[c_pos]).strip()))
        cuenta = {}
        for last, _, _ in filas:
            cuenta[last] = cuenta.get(last, 0) + 1
        for last, first, pos in filas:
            pos_dict[f"{last} {first}".strip()] = pos
            if cuenta[last] == 1:
                pos_dict[last] = pos
    except Exception as e:
        print("Notice: Could not load positions excel:", e)
    return pos_dict


def compute_sets_played(matches_df):
    """
    Computes sets played per team from matches_df.
    Returns dict: {team_name: total_sets_played}
    """
    team_sets = {}
    if matches_df.empty:
        return team_sets

    for _, row in matches_df.iterrows():
        h = row.get('home_team')
        a = row.get('away_team')
        # Sets reales = sets ganados por ambos equipos (sets_played venía fijo en 5 en la caché)
        sets = int(row.get('home_sets', 0) + row.get('away_sets', 0)) or row.get('sets_played', 3)
        if h:
            team_sets[h] = team_sets.get(h, 0) + sets
        if a:
            team_sets[a] = team_sets.get(a, 0) + sets
    return team_sets


def compute_team_rankings(events_df, matches_df):
    """
    Computes comprehensive aggregated stats and rankings for all teams in the league.
    """
    if events_df.empty:
        return pd.DataFrame()

    team_sets = compute_sets_played(matches_df)
    teams = sorted(events_df['team_name'].unique())
    records = []

    for team in teams:
        df_t = events_df[events_df['team_name'] == team]
        sets = team_sets.get(team, max(df_t['set_num'].nunique() if not df_t.empty else 1, 1))
        matches_played = df_t['match_code'].nunique()

        # 1. ATAQUE
        df_atq = df_t[df_t['skill'] == 'A']
        atq_tot = len(df_atq)
        atq_pts = len(df_atq[df_atq['evaluation'] == '#'])
        atq_err = len(df_atq[df_atq['evaluation'] == '='])
        atq_bloq = len(df_atq[df_atq['evaluation'] == '/'])
        atq_pct_pts = (atq_pts / atq_tot * 100) if atq_tot > 0 else 0.0
        atq_pct_err = (atq_err / atq_tot * 100) if atq_tot > 0 else 0.0
        atq_pct_bloq = (atq_bloq / atq_tot * 100) if atq_tot > 0 else 0.0
        atq_efic = ((atq_pts - atq_err - atq_bloq) / atq_tot * 100) if atq_tot > 0 else 0.0

        # K1 vs K2 Attack
        df_atq_k1 = df_atq[df_atq['phase'] == 'K1']
        df_atq_k2 = df_atq[df_atq['phase'] == 'K2']
        k1_tot = len(df_atq_k1)
        k1_pts = len(df_atq_k1[df_atq_k1['evaluation'] == '#'])
        k1_err = len(df_atq_k1[df_atq_k1['evaluation'] == '='])
        k1_bloq = len(df_atq_k1[df_atq_k1['evaluation'] == '/'])
        k1_efic = ((k1_pts - k1_err - k1_bloq) / k1_tot * 100) if k1_tot > 0 else 0.0

        k2_tot = len(df_atq_k2)
        k2_pts = len(df_atq_k2[df_atq_k2['evaluation'] == '#'])
        k2_err = len(df_atq_k2[df_atq_k2['evaluation'] == '='])
        k2_bloq = len(df_atq_k2[df_atq_k2['evaluation'] == '/'])
        k2_efic = ((k2_pts - k2_err - k2_bloq) / k2_tot * 100) if k2_tot > 0 else 0.0

        # 2. RECEPCIÓN
        df_rec = df_t[df_t['skill'] == 'R']
        rec_tot = len(df_rec)
        rec_doble_pos = len(df_rec[df_rec['evaluation'] == '#'])
        rec_pos = len(df_rec[df_rec['evaluation'] == '+'])
        rec_tot_pos = rec_doble_pos + rec_pos
        rec_err = len(df_rec[df_rec['evaluation'] == '='])
        rec_pct_doble_pos = (rec_doble_pos / rec_tot * 100) if rec_tot > 0 else 0.0
        rec_pct_pos = (rec_tot_pos / rec_tot * 100) if rec_tot > 0 else 0.0
        rec_pct_err = (rec_err / rec_tot * 100) if rec_tot > 0 else 0.0
        rec_efic = ((rec_tot_pos - rec_err) / rec_tot * 100) if rec_tot > 0 else 0.0

        # 3. SAQUE
        df_saq = df_t[df_t['skill'] == 'S']
        saq_tot = len(df_saq)
        saq_aces = len(df_saq[df_saq['evaluation'] == '#'])
        saq_err = len(df_saq[df_saq['evaluation'] == '='])
        saq_presion = len(df_saq[df_saq['evaluation'].isin(['+', '!'])])
        saq_pct_ace = (saq_aces / saq_tot * 100) if saq_tot > 0 else 0.0
        saq_pct_err = (saq_err / saq_tot * 100) if saq_tot > 0 else 0.0
        saq_aces_per_set = (saq_aces / sets) if sets > 0 else 0.0
        saq_pct_presion = (saq_presion / saq_tot * 100) if saq_tot > 0 else 0.0

        # 4. BLOQUEO
        df_bloq = df_t[df_t['skill'] == 'B']
        bloq_pts = len(df_bloq[df_bloq['evaluation'] == '#'])
        bloq_pos = len(df_bloq[df_bloq['evaluation'] == '+'])
        bloq_err = len(df_bloq[df_bloq['evaluation'] == '='])
        bloq_pts_per_set = (bloq_pts / sets) if sets > 0 else 0.0

        # 5. TOTALES Y BALANCE
        puntos_tot = atq_pts + bloq_pts + saq_aces
        puntos_per_set = (puntos_tot / sets) if sets > 0 else 0.0
        # Balance = Puntos ganados - Errores cometidos
        errores_no_forzados = atq_err + atq_bloq + saq_err + rec_err + bloq_err
        balance_puntos = puntos_tot - errores_no_forzados

        records.append({
            'Equipo': team,
            'Partidos': matches_played,
            'Sets': sets,
            # Ataque
            'Atq_Tot': atq_tot,
            'Atq_Pts': atq_pts,
            'Atq_%Pts': round(atq_pct_pts, 1),
            'Atq_%Err': round(atq_pct_err, 1),
            'Atq_%Bloq': round(atq_pct_bloq, 1),
            'Atq_Efic': round(atq_efic, 1),
            'K1_Efic': round(k1_efic, 1),
            'K2_Efic': round(k2_efic, 1),
            # Recepción
            'Rec_Tot': rec_tot,
            'Rec_#': rec_doble_pos,
            'Rec_%#': round(rec_pct_doble_pos, 1),
            'Rec_%Pos': round(rec_pct_pos, 1),
            'Rec_%Err': round(rec_pct_err, 1),
            'Rec_Efic': round(rec_efic, 1),
            # Saque
            'Saq_Tot': saq_tot,
            'Saq_Aces': saq_aces,
            'Saq_Aces/Set': round(saq_aces_per_set, 2),
            'Saq_%Err': round(saq_pct_err, 1),
            'Saq_%Presion': round(saq_pct_presion, 1),
            # Bloqueo
            'Bloq_Pts': bloq_pts,
            'Bloq_Pts/Set': round(bloq_pts_per_set, 2),
            'Bloq_Pos': bloq_pos,
            # Balance
            'Ptos_Tot': puntos_tot,
            'Ptos/Set': round(puntos_per_set, 1),
            'Err_Tot': errores_no_forzados,
            'Balance': balance_puntos
        })

    rankings_df = pd.DataFrame(records)
    if not rankings_df.empty:
        rankings_df = rankings_df.sort_values(by='Atq_Efic', ascending=False).reset_index(drop=True)
    return rankings_df


def compute_player_stats(events_df, matches_df, positions_dict=None):
    """
    Computes performance stats for every player in the league.
    Only assigns position if found in positions_dict (from verified master Excel).
    Otherwise position is '—' (no assumptions).
    """
    if events_df.empty:
        return pd.DataFrame()

    if positions_dict is None:
        positions_dict = load_official_positions_dict()

    players_group = events_df.groupby(['team_name', 'player_name', 'jersey'])
    records = []

    for (team, player, jersey), df_p in players_group:
        sets_count = df_p.groupby(['match_code', 'set_num']).ngroups
        if sets_count == 0:
            sets_count = 1
        matches_count = df_p['match_code'].nunique()

        # 1. ATAQUE
        df_atq = df_p[df_p['skill'] == 'A']
        atq_tot = len(df_atq)
        atq_pts = len(df_atq[df_atq['evaluation'] == '#'])
        atq_err = len(df_atq[df_atq['evaluation'] == '='])
        atq_bloq = len(df_atq[df_atq['evaluation'] == '/'])
        atq_pct_pts = (atq_pts / atq_tot * 100) if atq_tot > 0 else 0.0
        atq_pct_err = (atq_err / atq_tot * 100) if atq_tot > 0 else 0.0
        atq_pct_bloq = (atq_bloq / atq_tot * 100) if atq_tot > 0 else 0.0
        atq_efic = ((atq_pts - atq_err - atq_bloq) / atq_tot * 100) if atq_tot > 0 else 0.0

        # K1 vs K2 Attack
        df_atq_k1 = df_atq[df_atq['phase'] == 'K1']
        df_atq_k2 = df_atq[df_atq['phase'] == 'K2']
        k1_tot = len(df_atq_k1)
        k1_pts = len(df_atq_k1[df_atq_k1['evaluation'] == '#'])
        k1_efic = ((k1_pts - len(df_atq_k1[df_atq_k1['evaluation'].isin(['=', '/'])])) / k1_tot * 100) if k1_tot > 0 else 0.0

        k2_tot = len(df_atq_k2)
        k2_pts = len(df_atq_k2[df_atq_k2['evaluation'] == '#'])
        k2_efic = ((k2_pts - len(df_atq_k2[df_atq_k2['evaluation'].isin(['=', '/'])])) / k2_tot * 100) if k2_tot > 0 else 0.0

        # 2. RECEPCIÓN
        df_rec = df_p[df_p['skill'] == 'R']
        rec_tot = len(df_rec)
        rec_doble_pos = len(df_rec[df_rec['evaluation'] == '#'])
        rec_pos = len(df_rec[df_rec['evaluation'] == '+'])
        rec_tot_pos = rec_doble_pos + rec_pos
        rec_err = len(df_rec[df_rec['evaluation'] == '='])
        rec_pct_doble_pos = (rec_doble_pos / rec_tot * 100) if rec_tot > 0 else 0.0
        rec_pct_pos = (rec_tot_pos / rec_tot * 100) if rec_tot > 0 else 0.0
        rec_pct_err = (rec_err / rec_tot * 100) if rec_tot > 0 else 0.0
        rec_efic = ((rec_tot_pos - rec_err) / rec_tot * 100) if rec_tot > 0 else 0.0

        # 3. SAQUE
        df_saq = df_p[df_p['skill'] == 'S']
        saq_tot = len(df_saq)
        saq_aces = len(df_saq[df_saq['evaluation'] == '#'])
        saq_err = len(df_saq[df_saq['evaluation'] == '='])
        saq_presion = len(df_saq[df_saq['evaluation'].isin(['+', '!'])])
        saq_pct_ace = (saq_aces / saq_tot * 100) if saq_tot > 0 else 0.0
        saq_pct_err = (saq_err / saq_tot * 100) if saq_tot > 0 else 0.0
        saq_aces_per_set = (saq_aces / sets_count) if sets_count > 0 else 0.0
        saq_pct_presion = (saq_presion / saq_tot * 100) if saq_tot > 0 else 0.0

        # 4. BLOQUEO
        df_bloq = df_p[df_p['skill'] == 'B']
        bloq_pts = len(df_bloq[df_bloq['evaluation'] == '#'])
        bloq_pos = len(df_bloq[df_bloq['evaluation'] == '+'])
        bloq_err = len(df_bloq[df_bloq['evaluation'] == '='])
        bloq_pts_per_set = (bloq_pts / sets_count) if sets_count > 0 else 0.0

        # 5. DEFENSA
        df_def = df_p[df_p['skill'] == 'D']
        def_tot = len(df_def)
        def_pos = len(df_def[df_def['evaluation'].isin(['#', '+'])])

        # 6. TOTALES & BALANCE DE PUNTOS
        puntos_tot = atq_pts + bloq_pts + saq_aces
        puntos_per_set = (puntos_tot / sets_count) if sets_count > 0 else 0.0
        # Balance = Puntos ganados - Errores cometidos
        errores_no_forzados = atq_err + atq_bloq + saq_err + rec_err + bloq_err
        balance_puntos = puntos_tot - errores_no_forzados
        balance_per_set = (balance_puntos / sets_count) if sets_count > 0 else 0.0

        # Look up position strictly in official positions_dict if known
        p_clean = player.strip().lower()
        official_pos = "—"
        if positions_dict:
            if p_clean in positions_dict:
                official_pos = positions_dict[p_clean]
            else:
                # check by last name only
                parts = p_clean.split()
                if parts and parts[0] in positions_dict:
                    official_pos = positions_dict[parts[0]]

        records.append({
            'Equipo': team,
            'Jugadora': player,
            'Numero': jersey,
            'Puesto': official_pos,
            'Partidos': matches_count,
            'Sets': sets_count,
            # Ataque
            'Atq_Tot': atq_tot,
            'Atq_Pts': atq_pts,
            'Atq_%Pts': round(atq_pct_pts, 1),
            'Atq_%Err': round(atq_pct_err, 1),
            'Atq_%Bloq': round(atq_pct_bloq, 1),
            'Atq_Efic': round(atq_efic, 1),
            'K1_Tot': k1_tot,
            'K1_Efic': round(k1_efic, 1),
            'K2_Tot': k2_tot,
            'K2_Efic': round(k2_efic, 1),
            # Recepción
            'Rec_Tot': rec_tot,
            'Rec_#': rec_doble_pos,
            'Rec_%#': round(rec_pct_doble_pos, 1),
            'Rec_%Pos': round(rec_pct_pos, 1),
            'Rec_%Err': round(rec_pct_err, 1),
            'Rec_Efic': round(rec_efic, 1),
            # Saque
            'Saq_Tot': saq_tot,
            'Saq_Aces': saq_aces,
            'Saq_Aces/Set': round(saq_aces_per_set, 2),
            'Saq_%Err': round(saq_pct_err, 1),
            'Saq_%Presion': round(saq_pct_presion, 1),
            # Bloqueo
            'Bloq_Pts': bloq_pts,
            'Bloq_Pts/Set': round(bloq_pts_per_set, 2),
            'Bloq_Pos': bloq_pos,
            # Defensa
            'Def_Tot': def_tot,
            'Def_Pos': def_pos,
            # Balance
            'Ptos_Tot': puntos_tot,
            'Ptos/Set': round(puntos_per_set, 1),
            'Err_Tot': errores_no_forzados,
            'Balance': balance_puntos,
            'Balance/Set': round(balance_per_set, 1)
        })

    player_stats_df = pd.DataFrame(records)
    return player_stats_df


def get_league_benchmarks(player_stats_df, min_attempts=15):
    """
    Computes league average benchmarks for scatter plot crosshairs and radar baselines.
    """
    df = player_stats_df.copy()
    if df.empty:
        return {}

    df_atq = df[df['Atq_Tot'] >= min_attempts]
    df_rec = df[df['Rec_Tot'] >= min_attempts]
    df_saq = df[df['Saq_Tot'] >= min_attempts]

    benchmarks = {
        'atq_efic_mean': round(df_atq['Atq_Efic'].mean(), 1) if not df_atq.empty else 0.0,
        'atq_pct_pts_mean': round(df_atq['Atq_%Pts'].mean(), 1) if not df_atq.empty else 0.0,
        'atq_tot_mean': round(df_atq['Atq_Tot'].mean(), 1) if not df_atq.empty else 0.0,
        'rec_pct_pos_mean': round(df_rec['Rec_%Pos'].mean(), 1) if not df_rec.empty else 0.0,
        'rec_pct_doble_mean': round(df_rec['Rec_%#'].mean(), 1) if not df_rec.empty else 0.0,
        'rec_efic_mean': round(df_rec['Rec_Efic'].mean(), 1) if not df_rec.empty else 0.0,
        'saq_aces_per_set_mean': round(df_saq['Saq_Aces/Set'].mean(), 2) if not df_saq.empty else 0.0,
        'bloq_pts_per_set_mean': round(df['Bloq_Pts/Set'].mean(), 2) if not df.empty else 0.0,
        'ptos_per_set_mean': round(df['Ptos/Set'].mean(), 1) if not df.empty else 0.0,
    }
    return benchmarks
