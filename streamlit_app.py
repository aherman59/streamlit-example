import pandas as pd
import streamlit as st
import requests

def get_communes(departement):
    url = f"https://geo.api.gouv.fr/departements/{departement}/communes"
    response = requests.get(url)
    if response.status_code == 200:
        communes = response.json()
        return communes
    return None

st.title("Erosion du trait de côte")

departement = st.selectbox("Choix du département", ["06", "59", "33"])

communes = get_communes(departement)

commune = st.selectbox("Choix de la commune", [c["nom"] for c in communes])

