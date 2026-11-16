"""
Data Volley (.dvw / .dvv) Parser for Volleyball League Analytics.
Handles parsing of match metadata, team rosters, and point-by-point scout events.
Includes high-performance caching for rapid batch loading of dozens or hundreds of matches.
"""

import os
import glob
import pickle
import hashlib
import pandas as pd
from datetime import datetime

# Mapping of Data Volley position code to human-readable role
POSITION_MAP = {
    '1': 'Líbero',
    '2': 'Central',
    '3': 'Opuesta',
    '4': 'Punta Receptora',
    '5': 'Armadora',
    'L': 'Líbero'
}

def clean_str(val):
    if not val:
        return ""
    # Remove null bytes or special control characters
    return val.strip().replace('\x00', '')

def parse_dvw_file(filepath):
    """
    Parses a single .dvw or .dvv file.
    Returns:
        dict: {
            'metadata': match_metadata_dict,
            'teams': teams_dict,
            'players': players_df,
            'events': events_df
        }
    """
    try:
        with open(filepath, 'r', encoding='cp1252', errors='replace') as f:
            lines = [l.strip() for l in f.readlines()]
    except Exception as e:
        # Fallback to latin-1
        with open(filepath, 'r', encoding='latin-1', errors='replace') as f:
            lines = [l.strip() for l in f.readlines()]

    sections = {}
    current_sec = None
    for line in lines:
        if line.startswith('[') and line.endswith(']'):
            current_sec = line[1:-1]
            sections[current_sec] = []
        elif current_sec is not None:
            if line:
                sections[current_sec].append(line)

    # 1. Match metadata
    match_sec = sections.get('3MATCH', [])
    date_str = ""
    tournament = ""
    phase = ""
    match_code = os.path.splitext(os.path.basename(filepath))[0]
    
    if len(match_sec) >= 1:
        m_parts = match_sec[0].split(';')
        if len(m_parts) >= 1: date_str = clean_str(m_parts[0])
        if len(m_parts) >= 3: tournament = clean_str(m_parts[2])
        if len(m_parts) >= 4 and clean_str(m_parts[3]): tournament += f" - {clean_str(m_parts[3])}"
        if len(m_parts) >= 5: phase = clean_str(m_parts[4])
        if len(m_parts) >= 8 and clean_str(m_parts[7]): match_code = clean_str(m_parts[7])

    # 2. Teams
    teams_sec = sections.get('3TEAMS', [])
    home_name = "Local"
    away_name = "Visitante"
    home_coach = ""
    away_coach = ""
    home_sets = 0
    away_sets = 0

    if len(teams_sec) >= 1:
        t1 = teams_sec[0].split(';')
        if len(t1) >= 2 and clean_str(t1[1]): home_name = clean_str(t1[1])
        if len(t1) >= 3 and t1[2].isdigit(): home_sets = int(t1[2])
        if len(t1) >= 4: home_coach = clean_str(t1[3])
    if len(teams_sec) >= 2:
        t2 = teams_sec[1].split(';')
        if len(t2) >= 2 and clean_str(t2[1]): away_name = clean_str(t2[1])
        if len(t2) >= 3 and t2[2].isdigit(): away_sets = int(t2[2])
        if len(t2) >= 4: away_coach = clean_str(t2[3])

    # 3. Sets breakdown
    set_sec = sections.get('3SET', [])
    sets_played = 0
    sets_detail = []
    for s_idx, s_line in enumerate(set_sec[:5]):
        s_parts = s_line.split(';')
        if len(s_parts) >= 5 and s_parts[0].lower() == 'true':
            sets_played += 1
            sets_detail.append({
                'set_num': s_idx + 1,
                'partial_1': s_parts[1].strip() if len(s_parts) > 1 else "",
                'partial_2': s_parts[2].strip() if len(s_parts) > 2 else "",
                'partial_3': s_parts[3].strip() if len(s_parts) > 3 else "",
                'final_score': s_parts[4].strip() if len(s_parts) > 4 else ""
            })

    # If sets won wasn't in 3TEAMS, calculate from sets_detail
    if home_sets == 0 and away_sets == 0 and sets_detail:
        for s in sets_detail:
            if '-' in s['final_score']:
                try:
                    p1, p2 = [int(x) for x in s['final_score'].split('-')]
                    if p1 > p2: home_sets += 1
                    elif p2 > p1: away_sets += 1
                except:
                    pass

    # 4. Players
    players = []
    def parse_player_sec(sec_name, team_code, team_name):
        for line in sections.get(sec_name, []):
            parts = line.split(';')
            if len(parts) >= 11:
                jersey = clean_str(parts[1])
                last_name = clean_str(parts[9])
                first_name = clean_str(parts[10])
                full_name = f"{last_name} {first_name}".strip()
                if not full_name:
                    full_name = f"#{jersey} {team_name}"

                # Role code (field 13 is position code in DVW: 1=L, 2=C, 3=O, 4=P, 5=A)
                role_code = ""
                if len(parts) > 13 and clean_str(parts[13]):
                    role_code = clean_str(parts[13])
                # Libero flag in field 12
                if len(parts) > 12 and clean_str(parts[12]).upper() == 'L':
                    role_code = '1'

                role_desc = POSITION_MAP.get(role_code, 'Sin definir')
                
                # Check starter in sets
                starter_sets = 0
                for s_col in (3, 4, 5, 6, 7):
                    if len(parts) > s_col and clean_str(parts[s_col]) not in ('', '0'):
                        starter_sets += 1

                players.append({
                    'match_code': match_code,
                    'team_code': team_code,
                    'team_name': team_name,
                    'jersey': jersey,
                    'last_name': last_name,
                    'first_name': first_name,
                    'player_name': full_name,
                    'role_code': role_code,
                    'position': role_desc,
                    'starter_sets': starter_sets
                })

    parse_player_sec('3PLAYERS-H', '*', home_name)
    parse_player_sec('3PLAYERS-V', 'a', away_name)

    players_lookup = {
        (p['team_code'], p['jersey']): p['player_name']
        for p in players
    }
    players_role_lookup = {
        (p['team_code'], p['jersey']): p['position']
        for p in players
    }

    # 5. Scout events
    scout_sec = sections.get('3SCOUT', [])
    events = []
    valid_skills = set(['S', 'R', 'A', 'B', 'D', 'E', 'F'])
    current_phase = "K1" # Complex 1 (Side-out) or K2 (Transition/Counter-attack)
    current_set = 1
    home_setter_p = None
    away_setter_p = None

    for line in scout_sec:
        parts = line.split(';')
        if not parts:
            continue
        code = parts[0].strip()
        if not code:
            continue

        # Extract set number and setter position from columns if available
        if len(parts) > 8 and parts[8].isdigit():
            current_set = int(parts[8])
        if len(parts) > 9 and parts[9].isdigit():
            home_setter_p = int(parts[9])
        if len(parts) > 10 and parts[10].isdigit():
            away_setter_p = int(parts[10])

        # Track rally phases
        # After serve (S) and reception (R), the first attack is K1.
        # After a dig (D) or freeball (F), the attack is K2 (counter-attack).
        if len(code) >= 4 and code[0] in ('*', 'a'):
            team_c = code[0]
            skill_c = code[3] if len(code) > 3 else ""

            if skill_c == 'S':
                current_phase = "K1"
            elif skill_c in ('D', 'F'):
                current_phase = "K2"

            # Check if this is a standard skill action
            if len(code) >= 6 and skill_c in valid_skills and code[1:3].isdigit():
                jersey_c = str(int(code[1:3])) # normalize "09" -> "9"
                hit_type = code[4]
                evaluation = code[5]
                combo = code[6:8] if len(code) >= 8 else ""
                start_zone = code[8] if len(code) >= 9 else ""
                end_zone = code[9:11] if len(code) >= 11 else ""

                t_name = home_name if team_c == '*' else away_name
                opp_name = away_name if team_c == '*' else home_name
                p_name = players_lookup.get((team_c, jersey_c), f"#{jersey_c} ({t_name})")
                p_pos = players_role_lookup.get((team_c, jersey_c), "Sin definir")

                events.append({
                    'match_code': match_code,
                    'date': date_str,
                    'tournament': tournament,
                    'set_num': current_set,
                    'team_code': team_c,
                    'team_name': t_name,
                    'opponent_name': opp_name,
                    'jersey': jersey_c,
                    'player_name': p_name,
                    'position': p_pos,
                    'skill': skill_c,
                    'hit_type': hit_type,
                    'evaluation': evaluation,
                    'combo': combo,
                    'start_zone': start_zone,
                    'end_zone': end_zone,
                    'phase': current_phase,
                    'home_setter_p': home_setter_p,
                    'away_setter_p': away_setter_p,
                    'file': os.path.basename(filepath)
                })

    metadata = {
        'filepath': filepath,
        'filename': os.path.basename(filepath),
        'match_code': match_code,
        'date': date_str,
        'tournament': tournament,
        'phase': phase,
        'home_team': home_name,
        'away_team': away_name,
        'home_coach': home_coach,
        'away_coach': away_coach,
        'home_sets': home_sets,
        'away_sets': away_sets,
        'sets_played': (home_sets + away_sets) if (home_sets + away_sets) > 0 else max(sets_played, 1),
        'total_actions': len(events)
    }

    return {
        'metadata': metadata,
        'players': players,
        'events': events
    }


def _norm(path):
    return str(path).replace('/', '\\').lower()


def load_all_dvw_matches(folder_path, cache_file=None, progress_callback=None, info=None):
    """
    Lee los .dvw / .dvv de una o varias carpetas (folder_path puede ser texto o lista).
    - Usa caché según fecha de modificación para no releer lo que no cambió.
    - Si una carpeta no está disponible (otra PC, disco desconectado), usa lo que había en caché de esa carpeta.
    - Si el mismo partido aparece dos veces (misma fecha, local y visitante) cuenta una sola vez.
    Si se pasa un dict en `info`, se completa con info['duplicados'] = [archivos omitidos].
    Devuelve: matches_df, players_df, events_df
    """
    if cache_file is None:
        cache_file = os.path.join(os.path.dirname(__file__), "dvw_cache.pkl")
    folders = [folder_path] if isinstance(folder_path, str) else list(folder_path)

    cache = {}
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'rb') as f:
                cache = pickle.load(f)
        except Exception:
            cache = {}

    entries = []          # (ruta, solo_cache)
    seen_paths = set()
    for folder in folders:
        if folder and os.path.isdir(folder):
            for root, _, files in os.walk(folder):
                for f in sorted(files):
                    if f.lower().endswith(('.dvw', '.dvv')):
                        path = os.path.join(root, f)
                        if _norm(path) not in seen_paths:
                            seen_paths.add(_norm(path))
                            entries.append((path, False))
        elif folder:
            prefix = _norm(folder).rstrip('\\') + '\\'
            for path in cache:
                if _norm(path).startswith(prefix) and _norm(path) not in seen_paths:
                    seen_paths.add(_norm(path))
                    entries.append((path, True))

    all_metadata, all_players, all_events = [], [], []
    vistos, duplicados = set(), []
    updated_cache = False

    total_files = len(entries)
    for idx, (path, solo_cache) in enumerate(entries):
        cached_entry = cache.get(path)
        mtime = None if solo_cache else os.path.getmtime(path)

        if cached_entry and (solo_cache or cached_entry.get('mtime') == mtime):
            parsed = cached_entry['data']
        else:
            try:
                parsed = parse_dvw_file(path)
                cache[path] = {'mtime': mtime, 'data': parsed}
                updated_cache = True
            except Exception as e:
                print(f"Error parsing {path}: {e}")
                continue

        md = parsed['metadata']
        clave = (md['date'], md['home_team'], md['away_team'])
        if clave in vistos:
            duplicados.append(md['filename'])
            continue
        vistos.add(clave)

        all_metadata.append(md)
        all_players.extend(parsed['players'])
        all_events.extend(parsed['events'])

        if progress_callback:
            progress_callback(idx + 1, total_files)

    if updated_cache:
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(cache, f)
        except Exception as e:
            print("Failed to save cache:", e)

    if info is not None:
        info['duplicados'] = duplicados

    matches_df = pd.DataFrame(all_metadata) if all_metadata else pd.DataFrame()
    players_df = pd.DataFrame(all_players) if all_players else pd.DataFrame()
    events_df = pd.DataFrame(all_events) if all_events else pd.DataFrame()

    # Deduplicate players across matches
    if not players_df.empty:
        players_df = players_df.drop_duplicates(subset=['team_name', 'player_name', 'jersey'])

    return matches_df, players_df, events_df
