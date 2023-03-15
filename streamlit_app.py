import pandas as pd
import streamlit as st
import requests

def get_departements():
    url = f"https://geo.api.gouv.fr/departements/"
    response = requests.get(url)
    if response.status_code == 200:
        communes = response.json()
        return communes
    return None

def get_communes(departement):
    url = f"https://geo.api.gouv.fr/departements/{departement}/communes"
    response = requests.get(url)
    if response.status_code == 200:
        communes = response.json()
        return communes
    return None

departements = get_departements()

st.title("Erosion du trait de côte")

departement = st.selectbox("Choix du département", [d["nom"] for d in departements])

communes = get_communes([d["code"] for d in departements if d["nom"] == departement][0])

commune = st.selectbox("Choix de la commune", [c["nom"] for c in communes])

