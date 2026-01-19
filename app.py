import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# ============================================================
# DATABASE SETUP
# ============================================================

def init_db():
    conn = sqlite3.connect("data.db")
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS uploads (
            upload_id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            timestamp TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS fact_capital (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            centro TEXT,
            concepto TEXT,
            inicial REAL,
            aportacion REAL,
            retiro REAL,
            rendimiento REAL,
            saldo REAL,
            upload_id INTEGER
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ============================================================
# SAVE UPLOADED FILE
# ============================================================

def save_upload(file):
    conn = sqlite3.connect("data.db")
    cur = conn.cursor()

    timestamp = datetime.now().isoformat()
    cur.execute("INSERT INTO uploads (filename, timestamp) VALUES (?, ?)", (file.name, timestamp))
    upload_id = cur.lastrowid

    df = pd.read_excel(file)

    for _, row in df.iterrows():
        cur.execute("""
            INSERT INTO fact_capital 
            (fecha, centro, concepto, inicial, aportacion, retiro, rendimiento, saldo, upload_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(row["Fecha"]),
            row["Centro"],
            row["Concepto"],
            row["Inicial"],
            row["Aportación"],
            row["Retiro"],
            row["Rendimiento"],
            row["Saldo"],
            upload_id
        ))

    conn.commit()
    conn.close()


# ============================================================
# LOAD ALL DATA
# ============================================================

def load_data():
    conn = sqlite3.connect("data.db")
    df = pd.read_sql_query("SELECT * FROM fact_capital", conn)
    conn.close()

    if df.empty:
        return df

    df["fecha"] = pd.to_datetime(df["fecha"])
    return df


# ============================================================
# LIST + DELETE UPLOADED FILES
# ============================================================

def get_uploads():
    conn = sqlite3.connect("data.db")
    df = pd.read_sql_query("SELECT * FROM uploads ORDER BY upload_id DESC", conn)
    conn.close()
    return df

def delete_upload(upload_id):
    conn = sqlite3.connect("data.db")
    cur = conn.cursor()

    cur.execute("DELETE FROM fact_capital WHERE upload_id = ?", (upload_id,))
    cur.execute("DELETE FROM uploads WHERE upload_id = ?", (upload_id,))

    conn.commit()
    conn.close()


# ============================================================
# KPI CALCULATIONS (NEW VERSION)
# ============================================================

def calculate_kpis(df):
    df = df.sort_values("fecha")

    capital_inicial = df["inicial"].iloc[0]
    capital_final = df["saldo"].iloc[-1]

    aportes = df["aportacion"].sum()
    retiros = df["retiro"].sum()
    rendimiento_total = df["rendimiento"].sum()

    rendimiento_pct = rendimiento_total / capital_inicial if capital_inicial > 0 else 0

    return {
        "capital_inicial": capital_inicial,
        "capital_final": capital_final,
        "aportaciones": aportes,
        "retiros": retiros,
        "rendimiento_total": rendimiento_total,
        "rendimiento_pct": rendimiento_pct,
    }


# ============================================================
# UI CONFIGURATION
# ============================================================

st.set_page_config(layout="wide")

# Make full-width dashboard
st.markdown("""
    <style>
        .block-container {
            padding-top: 2rem;
            padding-left: 3rem;
            padding-right: 3rem;
            max-width: 95%;
        }
    </style>
""", unsafe_allow_html=True)

# HEADER
st.markdown("""
    <h1 style='text-align:left; color:#ddd;'> Dashboard Financiero</h1>
    <h4 style='text-align:left; color:gray;'>Análisis por Centro, Concepto y Fecha</h4>
    <br>
""", unsafe_allow_html=True)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header("Filtros")

df = load_data()

if df.empty:
    st.sidebar.warning("No hay datos cargados aún.")
    st.stop()

# --- Centro
centro = st.sidebar.selectbox("Centro", sorted(df["centro"].unique()))
df_filtered = df[df["centro"] == centro]

# --- Concepto
conceptos = sorted(df_filtered["concepto"].unique())
concepto = st.sidebar.selectbox("Concepto", ["Todos"] + conceptos)

if concepto != "Todos":
    df_filtered = df_filtered[df_filtered["concepto"] == concepto]

# --- Rango de fechas
st.sidebar.markdown("### Rango de fechas")
min_date = df_filtered["fecha"].min()
max_date = df_filtered["fecha"].max()

date_range = st.sidebar.date_input("Selecciona rango", [min_date, max_date])

if len(date_range) == 2:
    start_date, end_date = date_range
    df_filtered = df_filtered[(df_filtered["fecha"] >= pd.to_datetime(start_date)) &
                              (df_filtered["fecha"] <= pd.to_datetime(end_date))]


# ============================================================
# GROUPING (ALL CONCEPTS)
# ============================================================

if concepto == "Todos":
    df_grouped = df_filtered.groupby("fecha").agg({
        "inicial": "sum",
        "aportacion": "sum",
        "retiro": "sum",
        "rendimiento": "sum",
        "saldo": "sum"
    }).reset_index()
else:
    df_grouped = df_filtered.copy()


# ============================================================
# SIDEBAR – UPLOAD CONTROL
# ============================================================

st.sidebar.markdown("---")
st.sidebar.header(" Archivos")

uploaded = st.sidebar.file_uploader("Subir archivo Excel", type=["xlsx"])
if uploaded:
    save_upload(uploaded)
    st.sidebar.success("✔ Archivo cargado exitosamente. Recarga para verlo.")

uploads_df = get_uploads()

if len(uploads_df) > 0:
    upload_list = {
        f"{row['filename']} — {row['timestamp']}": row["upload_id"]
        for _, row in uploads_df.iterrows()
    }

    selected_upload = st.sidebar.selectbox("Archivos cargados", list(upload_list.keys()))

    if st.sidebar.button(" Borrar archivo seleccionado"):
        delete_upload(upload_list[selected_upload])
        st.sidebar.success("Archivo borrado. Recarga la página.")

else:
    st.sidebar.write("No hay archivos cargados.")


# ============================================================
# KPIs PANEL
# ============================================================

if df_grouped.empty:
    st.warning("No hay datos para los filtros seleccionados.")
    st.stop()

kpis = calculate_kpis(df_grouped)

title = f" KPIs — Centro: **{centro}**"
if concepto != "Todos":
    title += f", Concepto: **{concepto}**"

st.markdown(f"### {title}", unsafe_allow_html=True)

col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("Capital Inicial", f"${kpis['capital_inicial']:,.2f}")
col2.metric("Capital Final", f"${kpis['capital_final']:,.2f}")
col3.metric("Aportaciones", f"${kpis['aportaciones']:,.2f}")
col4.metric("Retiros", f"${kpis['retiros']:,.2f}")
col5.metric("Rendimiento Total", f"${kpis['rendimiento_total']:,.2f}")

col6 = st.columns(1)[0]
col6.metric("Rendimiento %", f"{kpis['rendimiento_pct']*100:.2f}%")

st.markdown("---")


# ============================================================
# CHART
# ============================================================

st.subheader(" Evolución del Capital (Saldo mensual)")

df_plot = df_grouped.sort_values("fecha")
st.line_chart(df_plot[["fecha", "saldo"]].set_index("fecha"))

st.markdown("---")


# ============================================================
# TABLE
# ============================================================

with st.expander("📄 Ver datos detallados"):
    st.dataframe(df_grouped)
