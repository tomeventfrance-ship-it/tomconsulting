import streamlit as st
import pandas as pd

st.set_page_config(page_title="IA consulting-tce", layout="wide")

st.title("IA consulting-tce")

tabs = st.tabs(["Agent IA", "Upload CSV (récompenses)"])

# ------------------- TAB 1 : AGENT IA -------------------
with tabs[0]:
    st.subheader("Agent IA (rédaction / support / marketing / formation)")

    st.write("Décris ce que tu veux et je te réponds avec une version SIMPLE + PREMIUM + checklist.")

    user_request = st.text_area("Ta demande", placeholder="Ex : écris un script TikTok pour vendre une formation...")

    if st.button("Générer"):
        if user_request.strip() == "":
            st.warning("Écris une demande.")
        else:
            st.markdown("### ✅ Version SIMPLE")
            st.write(f"Demande : {user_request}")
            st.write("Réponse simple : (à connecter à une IA ensuite)")

            st.markdown("### ✅ Version PREMIUM")
            st.write("Réponse premium : (à connecter à une IA ensuite)")

            st.markdown("### ✅ Checklist")
            st.write("- Relire\n- Adapter la cible\n- Publier\n- Mesurer les résultats")

# ------------------- TAB 2 : CSV -------------------
with tabs[1]:
    st.subheader("Upload CSV (récompenses)")
    st.write("Upload ton CSV pour afficher un aperçu. Ensuite on ajoutera les calculs.")

    file = st.file_uploader("Importer ton fichier CSV", type=["csv"])

    if file is not None:
        df = pd.read_csv(file)
        st.success("CSV chargé ✅")
        st.dataframe(df.head(30), use_container_width=True)
