import os
import json
import requests
import streamlit as st

st.set_page_config(page_title="ia-consulting-tce", layout="wide")
st.title("ia-consulting-tce")

# -------------------------
# CONFIG
# -------------------------
GEMINI_KEY = st.secrets.get("GEMINI_API_KEY", None) if hasattr(st, "secrets") else None
GEMINI_MODEL = "gemini-1.5-flash"  # bon / rapide / souvent quota gratuit

SYSTEM_RULES = """
Tu es l’Agent IA officiel de Tom Consulting & Event.

MISSIONS:
- Rédaction premium (posts, scripts, emails, landing pages)
- Support client (réponses, FAQ, objections)
- Marketing (stratégie, plan d’action)
- Création de modules de formation (plan, modules, exercices, quiz)

RÈGLES:
1) Si infos manquantes: pose au maximum 5 questions.
2) Toujours produire:
   - Version SIMPLE
   - Version PREMIUM
   - Checklist d’action
3) Style: clair, structuré, directement utilisable.
4) Ne pas inventer de chiffres. Si un chiffre manque, demander.
"""

def offline_agent(user_text: str) -> str:
    return f"""Mode OFFLINE (pas de clé IA configurée).

### Version SIMPLE
- Objectif: préciser la demande.
- Proposition: donne-moi la cible, le canal et le résultat attendu.

### Version PREMIUM
- Angle: bénéfice principal + preuve + appel à l’action.
- Structure: Hook → Valeur → Preuve → CTA.

### Checklist
- [ ] Cible définie
- [ ] Offre définie
- [ ] Canal (IG/TikTok/Email/etc.)
- [ ] CTA clair
- [ ] Ton (premium / direct / amical)

Demande reçue: {user_text}
"""

def gemini_call(messages):
    if not GEMINI_KEY:
        raise RuntimeError("Missing GEMINI_API_KEY")

    model = gemini_pick_model()
    if not model:
        raise RuntimeError("Aucun modèle Gemini disponible pour cette clé (ListModels vide ou sans generateContent).")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY}"

    contents = []
    for m in messages:
        role = m["role"]
        text = m["content"]
        if role == "assistant":
            contents.append({"role": "model", "parts": [{"text": text}]})
        else:
            contents.append({"role": "user", "parts": [{"text": text}]})

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.6,
            "topP": 0.9,
            "maxOutputTokens": 1200
        }
    }

    r = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]



# -------------------------
# UI
# -------------------------
with st.sidebar:
    st.subheader("Paramètres")
    st.write("IA:", "✅ Gemini connecté" if GEMINI_KEY else "⚠️ Pas de clé Gemini (mode offline)")
    st.caption("Règles: SIMPLE + PREMIUM + checklist. Max 5 questions si manque d’infos.")
    st.divider()
    st.subheader("Templates rapides")
    template = st.selectbox(
        "Choisir un type",
        [
            "Post Instagram",
            "Script TikTok",
            "Email relance",
            "Landing page",
            "Réponse support (client)",
            "Plan de formation"
        ]
    )

def template_prompt(t):
    if t == "Post Instagram":
        return "Crée un post Instagram: hook + valeur + preuve + CTA. Thème: ..."
    if t == "Script TikTok":
        return "Crée un script TikTok 30-45s: hook 2s + 3 points + CTA. Sujet: ..."
    if t == "Email relance":
        return "Rédige un email de relance (objet + corps) court et premium. Contexte: ..."
    if t == "Landing page":
        return "Rédige une landing page: titre, sous-titre, bénéfices, preuves, FAQ, CTA. Offre: ..."
    if t == "Réponse support (client)":
        return "Rédige une réponse support: empathie + solution + étapes + clôture. Problème: ..."
    if t == "Plan de formation":
        return "Crée un plan de formation: objectifs, modules, exercices, quiz, livrables. Thème: ..."
    return "Décris la demande."

colA, colB = st.columns([1, 1])

with colA:
    st.subheader("Demande")
    user_text = st.text_area("Décris ce que tu veux", value=template_prompt(template), height=180)
    context = st.text_input("Contexte (optionnel)", placeholder="Ex: cible, offre, prix, canal, ton…")
    go = st.button("Générer")

with colB:
    st.subheader("Réponse")
    if "history" not in st.session_state:
        st.session_state.history = [{"role": "system", "content": SYSTEM_RULES}]

    if go:
        prompt = user_text.strip()
        if context.strip():
            prompt += f"\n\nContexte:\n{context.strip()}"

        st.session_state.history.append({"role": "user", "content": prompt})

        try:
            if GEMINI_KEY:
                answer = gemini_call(st.session_state.history)
            else:
                answer = offline_agent(prompt)
        except Exception as e:
            answer = offline_agent(prompt) + f"\n\n(Erreur IA: {e})"

        st.session_state.history.append({"role": "assistant", "content": answer})
        st.markdown(answer)
    else:
        st.info("Écris une demande puis clique sur “Générer”.")
