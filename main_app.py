import os
import io
import streamlit as st
import pandas as pd
from datetime import date

from rewards_engine import db_connect, compute_creators

def make_unique_columns(df: pd.DataFrame) -> pd.DataFrame:
    counts = {}
    new_cols = []
    for c in df.columns:
        c = str(c)
        if c in counts:
            counts[c] += 1
            new_cols.append(f"{c}__{counts[c]}")
        else:
            counts[c] = 0
            new_cols.append(c)
    df = df.copy()
    df.columns = new_cols
    return df

st.set_page_config(page_title="Agent Calcul Récompenses — TCE", layout="wide")
st.title("Agent Calcul Récompenses — Tom Consulting & Event")

DB_PATH = "data/history.sqlite"
os.makedirs("data", exist_ok=True)
conn = db_connect(DB_PATH)

st.subheader("1) Upload fichier (CSV ou Excel)")
up = st.file_uploader("Importer ton export CSV ou Excel", type=["csv", "xlsx"])

if up is None:
    st.info("Importe un fichier pour commencer.")
    st.stop()

if up.name.lower().endswith(".csv"):
    df = pd.read_csv(up)

else:
    df = pd.read_excel(up)
    df = make_unique_columns(df)

    # Supprime les colonnes dupliquées (même nom)
df = df.loc[:, ~df.columns.duplicated(keep="first")]


# Renommer colonnes déjà calculées en (source) pour comparaison
existing_calc_cols = [
    "Palier",
    "Taux appliqué",
    "Bonus",
    "Récompense (diamants)",
    "Déjà atteint 150k (Oui/Non)",
    "Premier mois 150k",
    "Eligible",
    "Raison inéligibilité",
]
rename_map = {c: f"{c} (source)" for c in existing_calc_cols if c in df.columns}
if rename_map:
    df = df.rename(columns=rename_map)
    st.info("Colonnes déjà calculées détectées → renommées en '(source)' pour comparer avec le recalcul.")

st.success(f"Fichier chargé ({df.shape[0]} lignes, {df.shape[1]} colonnes)")
df = df.loc[:, ~df.columns.duplicated()]
st.dataframe(df.head(25), use_container_width=True)

cols = list(df.columns)

def idx(colname: str, fallback: int = 0) -> int:
    return cols.index(colname) if colname in cols else fallback

st.subheader("2) Mapping des colonnes (pré-rempli)")
c1, c2 = st.columns(2)

with c1:
    creator_id = st.selectbox("ID créateur", cols, index=idx("ID créateur(trice)", 0))
    diamonds_month = st.selectbox("Diamants du mois", cols, index=idx("Diamants", 0))
    live_days_valid = st.selectbox("Jours live validés", cols, index=idx("Jours de passage en LIVE validés", 0))

with c2:
    live_hours_valid = st.selectbox("Heures live validées", cols, index=idx("Heures live validées", 0))
    status_excluding = st.selectbox("Statut excluant", cols, index=idx("Statut excluant", 0))
    as_of = st.date_input("Date de traitement (historique 150k)", value=date.today())

mapping = {
    "creator_id": creator_id,
    "diamonds_month": diamonds_month,
    "live_days_valid": live_days_valid,
    "live_hours_valid": live_hours_valid,
    "status_excluding": status_excluding,
}

st.subheader("3) Calcul + Comparaison + Export")

if st.button("Calculer récompenses (Créateurs)"):
    result = compute_creators(df, mapping, conn, str(as_of))

    if result.warnings:
        st.error(" | ".join(result.warnings))
        st.stop()

    out = result.df
    out = make_unique_columns(out)
    out = out.loc[:, ~out.columns.duplicated(keep="first")]

    total_rewards = int(
        pd.to_numeric(out["Récompense (diamants)"], errors="coerce")
        .fillna(0)
        .sum()
    )
    nb_eligibles = int((out["Eligible"] == "OK").sum())

    st.success("Calcul terminé")
    st.write("Total récompenses (recalculé):", total_rewards)
    st.write("Nb éligibles:", nb_eligibles)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        out.to_excel(writer, index=False, sheet_name="RESULTATS_CREATEURS")

    st.download_button(
        "Télécharger le résultat Excel",
        data=output.getvalue(),
        file_name="resultats_createurs.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


    show_cols = [creator_id, diamonds_month, live_days_valid, live_hours_valid, status_excluding]

    if "Palier (source)" in out.columns:
        show_cols += ["Palier (source)", "Palier"]
    else:
        show_cols += ["Palier"]

    if "Taux appliqué (source)" in out.columns:
        show_cols += ["Taux appliqué (source)", "Taux appliqué"]
    else:
        show_cols += ["Taux appliqué"]

    if "Récompense (diamants) (source)" in out.columns:
        show_cols += ["Récompense (diamants) (source)", "Récompense (diamants)"]
    else:
        show_cols += ["Récompense (diamants)"]

    show_cols += ["Eligible", "Raison inéligibilité", "Déjà atteint 150k (Oui/Non)", "Premier mois 150k"]
    show_cols = [c for c in show_cols if c in out.columns]
# --- SECURITE ANTI-DOUBLONS (OBLIGATOIRE AVANT TOUT AFFICHAGE) ---
def make_unique_columns_inplace(df):
    counts = {}
    new_cols = []
    for c in df.columns:
        c = str(c)
        if c in counts:
            counts[c] += 1
            new_cols.append(f"{c}__{counts[c]}")
        else:
            counts[c] = 0
            new_cols.append(c)
    df.columns = new_cols
    return df

# out existe ici (résultat du calcul)
out = out.copy()
make_unique_columns_inplace(out)

# show_cols peut contenir des doublons aussi -> on le nettoie
seen = set()
clean_show_cols = []
for c in show_cols:
    if c not in seen and c in out.columns:
        clean_show_cols.append(c)
        seen.add(c)

# Affichage sécurisé (plus jamais de crash pyarrow)
st.dataframe(out[clean_show_cols].head(200), use_container_width=True)

st.dataframe(out[show_cols].head(80), use_container_width=True)

output = io.BytesIO()
with 
     pd.ExcelWriter(output, engine="openpyxl") as writer:
     out.to_excel(writer, index=False, sheet_name="RESULTATS_CREATEURS")

    st.download_button(
        "Télécharger le résultat Excel",
        data=output.getvalue(),
        file_name="resultats_createurs.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

st.caption("Règles: min 12 jours + 25h, statut excluant => inéligible, arrondi à 100, suivi 150k par ID.")
