import os
import io
import streamlit as st
import pandas as pd
from datetime import date, datetime

from rewards_engine import db_connect, compute_creators

st.set_page_config(page_title="Agent Calcul Récompenses — TCE", layout="wide")
st.title("Agent Calcul Récompenses — Tom Consulting & Event")

# ⚠️ Note Streamlit Cloud: le disque peut être réinitialisé lors des redéploiements.
# Pour un historique 150k permanent, il faudra plus tard une DB externe.
DB_PATH = "data/history.sqlite"
os.makedirs("data", exist_ok=True)
conn = db_connect(DB_PATH)

st.subheader("1) Importer ton export (CSV ou Excel)")
up = st.file_uploader("Importer ton export CSV ou Excel", type=["csv", "xlsx"])

if up is None:
    st.info("Importe un fichier pour commencer.")
    st.stop()

# Lecture fichier
if up.name.lower().endswith(".csv"):
    df = pd.read_csv(up)
else:
    df = pd.read_excel(up)

st.success(f"Fichier chargé ✅ ({df.shape[0]} lignes, {df.shape[1]} colonnes)")
st.dataframe(df.head(25), use_container_width=True)

cols = list(df.columns)

# Mapping auto (adapté à TON export)
def default_index(col_name: str) -> int:
    return cols.index(col_name) if col_name in cols else 0

st.subheader("2) Mapping des colonnes (pré-rempli)")
c1, c2 = st.columns(2)

with c1:
    creator_id = st.selectbox("ID créateur", cols, index=default_index("ID créateur(trice)"))
    diamonds_month = st.selectbox("Diamants du mois", cols, index=default_index("Diamants"))
    live_days_valid = st.selectbox("Jours live validés", cols, index=default_index("Jours live validés"))

with c2:
    live_hours_valid = st.selectbox("Heures live validées", cols, index=default_index("Heures live validées"))
    status_excluding = st.selectbox("Statut excluant", cols, index=default_index("Statut excluant"))
    as_of = st.date_input("Date de traitement (historique 150k)", value=date.today())

mapping = {
    "creator_id": creator_id,
    "diamonds_month": diamonds_month,
    "live_days_valid": live_days_valid,
    "live_hours_valid": live_hours_valid,
    "status_excluding": status_excluding,
}

st.subheader("3) Calcul + Export")
if st.button("Calculer récompenses (Créateurs)"):
    result = compute_creators(df, mapping=mapping, conn=conn, as_of_date=str(as_of))

    if result.warnings:
        st.warning(" | ".join(result.warnings))
        st.stop()

    st.success("Calcul terminé ✅")
    st.dataframe(result.df.head(60), use_container_width=True)

    # Export Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        result.df.to_excel(writer, index=False, sheet_name="RESULTATS_CREATEURS")

    st.download_button(
        "Télécharger le résultat Excel",
        data=output.getvalue(),
        file_name="resultats_createurs.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

st.caption("Règles: min 12 jours + 25h, statut excluant => inéligible, arrondi à 100, suivi 150k par ID.")
