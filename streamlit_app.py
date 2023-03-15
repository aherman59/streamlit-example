import requests
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

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

def style_function(feature):
    return {
        "fillOpacity": 0.9,
        "weight": 1,
        "fillColor": "lightgray",
        "color": "darkgray",
    }


departements = get_departements()

st.title("Erosion du trait de côte")

departement = st.selectbox("Choix du département", [d["nom"] for d in departements])

communes = get_communes([d["code"] for d in departements if d["nom"] == departement][0])

commune = st.selectbox("Choix de la commune", [c["nom"] for c in communes])

m = folium.Map(location=[39.949610, -75.150282], zoom_start=16)

"""
folium.GeoJson(self.geojson, 
                name="prix communal", 
                style_function=style_function, 
                popup=folium.GeoJsonPopup(fields=["nom",] + list(affichage_indics.keys()), 
                aliases=["nom",] + list(affichage_indics.values()))).add_to(m)
"""