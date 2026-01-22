import os
import streamlit as st
import pandas as pd
from datetime import date

from rewards_engine import db_connect, compute_creators

st.set_page_config(page_title="Agent Calcul Récompenses — TCE", layout="wide")
st.title("Agent Calcul Récompenses — Tom Consulting & Event")

DB_PATH = "data/history.sqlite"
os.makedirs("data", exist_ok=True)

conn = db_connect(DB_PATH)

st.subheader("1) Upload CSV")
up = st.file_uploader("Importer ton export CSV ou Excel", type=["csv", "xlsx"])


if up is None:
    st.info("Importe un CSV pour commencer.")
    st.stop()

if up.name.endswith(".csv"):
    df = pd.read_csv(up)
else:
    df = pd.read_excel(up)

st.success("CSV chargé ✅")
st.dataframe(df.head(20), use_container_width=True)

st.subheader("2) Mapping des colonnes (assistant)")
cols = list(df.columns)

col1, col2 = st.columns(2)
with col1:
    creator_id = st.selectbox("creator_id (ID créateur)", cols)
    diamonds_month = st.selectbox("diamonds_month (Diamants du mois)", cols)
    live_days_valid = st.selectbox("live_days_valid (Jours live validés)", cols)
with col2:
    live_hours_valid = st.selectbox("live_hours_valid (Heures live validées)", cols)
    status = st.selectbox("status (banni/infractions/départ/ok)", cols)
    as_of = st.date_input("Date de traitement (historique 150k)", value=date.today())

mapping = {
    "creator_id": creator_id,
    "diamonds_month": diamonds_month,
    "live_days_valid": live_days_valid,
    "live_hours_valid": live_hours_valid,
    "status": status,
}

st.subheader("3) Calcul")
if st.button("Calculer récompenses (Créateurs)"):
    result = compute_creators(df, mapping=mapping, conn=conn, as_of_date=str(as_of))

    if result.warnings:
        st.warning(" | ".join(result.warnings))

    st.dataframe(result.df.head(50), use_container_width=True)

    # Export Excel
    import io
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        result.df.to_excel(writer, index=False, sheet_name="RESULTATS")
    st.download_button(
        "Télécharger Excel",
        data=output.getvalue(),
        file_name="resultats_createurs.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

st.divider()
st.caption("Règles créateurs appliquées: min 12 jours live + 25h, statut banni/départ inéligible, arrondi centaine inférieure, historique 150k.")
