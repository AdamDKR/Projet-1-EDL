import streamlit as st

from base import ouvrir_base

st.title("Partage de frais")

# Lit les membres et les affiche.
with ouvrir_base() as conn:
    membres = conn.execute("SELECT nom FROM membres").fetchall()

st.header("Membres")
for membre in membres:
    st.write(membre["nom"])

# Exemple : ajoute un membre au groupe 1.
nom = st.text_input("Nom")
if st.button("Ajouter") and nom:
    with ouvrir_base() as conn:
        conn.execute("INSERT INTO membres (groupe_id, nom) VALUES (1, ?)", [nom])
    st.rerun()

# Ajoutez la suite de votre application ici.
