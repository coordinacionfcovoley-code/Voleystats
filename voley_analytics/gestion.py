"""
Gestión de archivos de VoleyStats: agregar partidos, quitar partidos y cargar el Excel de puestos.

Carpeta de trabajo propia de la app (dentro del proyecto):
    datos/partidos/      copias de los .dvw que se suben desde la app
    datos/excluidos.json partidos de tu carpeta original que se ocultan (los archivos NO se borran)
    datos/puestos.xlsx   Excel de puestos vigente
"""

import io
import os
import json
import shutil
import pandas as pd
import streamlit as st

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "datos")
UPLOAD_DIR = os.path.join(DATA_DIR, "partidos")
EXCL_FILE = os.path.join(DATA_DIR, "excluidos.json")
POS_FILE = os.path.join(DATA_DIR, "puestos.xlsx")
OLD_UPLOAD_DIR = os.path.join(BASE, "uploaded_dvw")          # carpeta de la versión anterior
LEGACY_POS = r"c:\ALICIA\VOLEY\FERRO\Base de datos jugadoras - puestos.xlsx"


# ------------------------------------------------------------------ archivos
def ensure_dirs():
    os.makedirs(UPLOAD_DIR, exist_ok=True)


def migrate_old_uploads():
    """Pasa a datos/partidos lo que se había subido con la versión anterior (carpeta uploaded_dvw)."""
    if not os.path.isdir(OLD_UPLOAD_DIR):
        return
    ensure_dirs()
    for f in os.listdir(OLD_UPLOAD_DIR):
        if f.lower().endswith((".dvw", ".dvv")):
            dst = os.path.join(UPLOAD_DIR, f)
            if not os.path.exists(dst):
                shutil.move(os.path.join(OLD_UPLOAD_DIR, f), dst)


def save_uploads(files):
    ensure_dirs()
    names = []
    for uf in files:
        name = os.path.basename(uf.name)
        with open(os.path.join(UPLOAD_DIR, name), "wb") as f:
            f.write(uf.getbuffer())
        names.append(name)
    return names


def load_excluded():
    try:
        with open(EXCL_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()


def _save_excluded(names):
    ensure_dirs()
    with open(EXCL_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(names), f, ensure_ascii=False, indent=1)


def exclude_files(names):
    _save_excluded(load_excluded() | {n.lower() for n in names})


def restore_files(names):
    _save_excluded(load_excluded() - {n.lower() for n in names})


def remove_uploaded(names):
    """Borra de datos/partidos las copias subidas. Devuelve cuántas borró."""
    n = 0
    wanted = {x.lower() for x in names}
    if os.path.isdir(UPLOAD_DIR):
        for f in os.listdir(UPLOAD_DIR):
            if f.lower() in wanted:
                os.remove(os.path.join(UPLOAD_DIR, f))
                n += 1
    return n


def es_subido(path):
    return os.path.abspath(str(path)).lower().startswith(os.path.abspath(UPLOAD_DIR).lower())


# ------------------------------------------------------------------ puestos
def positions_path():
    if os.path.exists(POS_FILE):
        return POS_FILE
    if os.path.exists(LEGACY_POS):
        return LEGACY_POS
    return None


def positions_template(players_df, team):
    """Excel modelo (APELLIDO | NOMBRE | POS) con las jugadoras del equipo, para completar los puestos."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Puestos"
    ws.append(["N°", "APELLIDO", "NOMBRE", "POS"])
    if players_df is not None and not players_df.empty:
        sub = players_df[players_df["team_name"] == team].sort_values(["last_name", "first_name"])
        for _, r in sub.iterrows():
            ws.append([r["jersey"], r["last_name"], r["first_name"], ""])
    for col, w in zip("ABCD", (6, 24, 22, 18)):
        ws.column_dimensions[col].width = w
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ------------------------------------------------------------------ interfaz
def _flash(kind, text):
    st.session_state.setdefault("flash", []).append((kind, text))


def mostrar_flash():
    for kind, text in st.session_state.pop("flash", []):
        getattr(st, kind)(text)


def _resultado(r):
    return f"{int(r['home_sets'])}-{int(r['away_sets'])}"


def render_partidos(raw_matches, recargar):
    """Pestaña de gestión de partidos: agregar, ver y quitar."""
    st.subheader("Partidos de la liga")
    ver = st.session_state.setdefault("gest_ver", 0)

    # ---------- agregar
    st.markdown("##### ➕ Agregar partidos")
    st.caption("Los archivos se **suman** a los que ya están cargados. Si subís un partido que ya estaba, se detecta y no se duplica.")
    files = st.file_uploader("Arrastrá acá los archivos .dvw", type=["dvw", "dvv"],
                             accept_multiple_files=True, key=f"gest_up_{ver}")
    if files and st.button(f"Agregar {len(files)} archivo(s) a la liga", type="primary"):
        antes = set(raw_matches["filename"].str.lower()) if not raw_matches.empty else set()
        torneo_ref = raw_matches["tournament"].mode().iloc[0] if not raw_matches.empty else None
        nombres = save_uploads(files)
        recargar()
        nuevos = st.session_state["matches_df"]
        despues = set(nuevos["filename"].str.lower()) if not nuevos.empty else set()
        agregados = [n for n in nombres if n.lower() in despues and n.lower() not in antes]
        repetidos = [n for n in nombres if n not in agregados]
        if agregados:
            _flash("success", f"Se agregaron {len(agregados)} partido(s) nuevo(s). Ahora hay {len(despues)} en total.")
            if torneo_ref is not None:
                otros = nuevos[nuevos["filename"].str.lower().isin([a.lower() for a in agregados])
                               & (nuevos["tournament"] != torneo_ref)]
                if not otros.empty:
                    _flash("warning", f"{len(otros)} de los archivos agregados son de otro torneo "
                                      f"({', '.join(sorted(set(otros['tournament'])))}). "
                                      "Revisalo en la lista de abajo; podés quitarlos o elegir el torneo en la barra lateral.")
        if repetidos:
            _flash("info", "Ya estaban cargados (mismo partido), se omitieron: " + ", ".join(repetidos))
        st.session_state["gest_ver"] = ver + 1
        st.rerun()

    # ---------- lista y quitar
    st.divider()
    st.markdown("##### 📋 Partidos cargados")
    if raw_matches.empty:
        st.info("Todavía no hay partidos cargados.")
    else:
        torneos = sorted(raw_matches["tournament"].unique())
        marcar = "—"
        if len(torneos) > 1:
            st.warning(f"Hay partidos de {len(torneos)} torneos distintos mezclados. "
                       "Podés marcar de una vez todos los de un torneo para quitarlos.")
            marcar = st.selectbox("Marcar todos los partidos del torneo:", ["—"] + torneos, key=f"gest_marcar_{ver}")

        t = raw_matches.copy()
        t["_f"] = pd.to_datetime(t["date"], dayfirst=True, errors="coerce")
        t = t.sort_values("_f", ascending=False)
        tabla = pd.DataFrame({
            "Quitar": (t["tournament"] == marcar).values if marcar != "—" else False,
            "Fecha": t["date"].values,
            "Local": t["home_team"].values,
            "Visitante": t["away_team"].values,
            "Sets": t.apply(_resultado, axis=1).values,
            "Torneo": t["tournament"].values,
            "Origen": ["Subido" if es_subido(p) else "Carpeta" for p in t["filepath"]],
            "Archivo": t["filename"].values,
        })
        editado = st.data_editor(
            tabla, hide_index=True, use_container_width=True, key=f"gest_ed_{ver}_{marcar}",
            disabled=[c for c in tabla.columns if c != "Quitar"],
            column_config={"Quitar": st.column_config.CheckboxColumn("Quitar", help="Marcá los partidos a quitar")},
        )
        marcados = editado[editado["Quitar"]]
        st.caption(f"{len(raw_matches)} partidos cargados · {len(marcados)} marcado(s) para quitar.  "
                   "**Subido** = archivo subido desde esta pantalla (se borra la copia). "
                   "**Carpeta** = viene de tu carpeta de partidos (solo se oculta, tus archivos originales no se tocan).")
        c1, c2 = st.columns([2, 1])
        with c1:
            ok = st.checkbox("Confirmo que quiero quitar los partidos marcados", key=f"gest_ok_{ver}")
        with c2:
            if st.button("🗑️ Quitar marcados", disabled=marcados.empty or not ok, use_container_width=True):
                subidos = marcados[marcados["Origen"] == "Subido"]["Archivo"].tolist()
                carpeta = marcados[marcados["Origen"] == "Carpeta"]["Archivo"].tolist()
                if subidos:
                    remove_uploaded(subidos)
                if carpeta:
                    exclude_files(carpeta)
                recargar()
                _flash("success", f"Se quitaron {len(marcados)} partido(s).")
                st.session_state["gest_ver"] = ver + 1
                st.rerun()

    excl = sorted(load_excluded())
    if excl:
        with st.expander(f"♻️ Partidos ocultos ({len(excl)}) · restaurar"):
            elegidos = st.multiselect("Elegí los que querés volver a mostrar:", excl, key=f"gest_rest_{ver}")
            if st.button("Restaurar seleccionados", disabled=not elegidos):
                restore_files(elegidos)
                recargar()
                _flash("success", f"Se restauraron {len(elegidos)} partido(s).")
                st.session_state["gest_ver"] = ver + 1
                st.rerun()


def render_puestos(players_df, player_stats):
    """Sección para cargar / cambiar el Excel de puestos."""
    st.divider()
    st.markdown("##### 🧭 Puestos de las jugadoras")
    ruta = positions_path()
    ferro = player_stats[player_stats["Equipo"].str.contains("Ferro", case=False)] if not player_stats.empty else player_stats
    if ruta:
        vinc = int((ferro["Puesto"] != "—").sum()) if not ferro.empty else 0
        origen = "cargado desde la app" if ruta == POS_FILE else f"leído de {ruta}"
        st.success(f"Excel de puestos activo ({origen}). Puestos vinculados en Ferro: {vinc} de {len(ferro)} jugadoras.")
    else:
        st.info("No hay Excel de puestos cargado. La app funciona igual, sin mostrar puestos.")

    st.caption("El Excel necesita las columnas **APELLIDO**, **NOMBRE** y **POS** (en cualquier orden, con esos títulos). "
               "Al cargar uno nuevo reemplaza al anterior: útil al cambiar de torneo.")
    c1, c2 = st.columns([2, 1])
    with c1:
        up = st.file_uploader("Cargar un nuevo Excel de puestos (.xlsx)", type=["xlsx"], key="pos_up")
        if up is not None and st.button("Usar este Excel", type="primary"):
            ensure_dirs()
            with open(POS_FILE, "wb") as f:
                f.write(up.getbuffer())
            _flash("success", "Excel de puestos actualizado.")
            st.rerun()
        if os.path.exists(POS_FILE) and st.button("Quitar el Excel cargado"):
            os.remove(POS_FILE)
            _flash("info", "Excel de puestos quitado.")
            st.rerun()
    with c2:
        st.download_button("⬇️ Plantilla con las jugadoras de Ferro",
                           data=positions_template(players_df, "Ferro"),
                           file_name="puestos_ferro_plantilla.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)
