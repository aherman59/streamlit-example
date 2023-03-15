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

st.title("Application test - Commune")

st.subheader("Choix de la commune")

st.text(get_communes("06"))