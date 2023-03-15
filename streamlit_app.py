import requests
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

def ask(url):
    try:
        response = requests.get(url)
        if response.status_code == 200: 
            return response.json()
    except Exception as e:
        return None

def get_departements():
    url = f"https://geo.api.gouv.fr/departements/"
    return ask(url)

def get_communes(departement):
    url = f"https://geo.api.gouv.fr/departements/{departement}/communes"
    return ask(url)

def style_function(feature):
    return {
        "fillOpacity": 0.9,
        "weight": 1,
        "fillColor": "lightgray",
        "color": "darkgray",
    }

def get_center(code_insee):
    url = f"https://geo.api.gouv.fr/communes/{code_insee}/?format=geojson&geometry=bbox"
    geojson = ask(url)
    coordinates = geojson["geometry"]["coordinates"][0]
    xmin = min([x for x, y in coordinates])
    xmax = max([x for x, y in coordinates])
    ymin = min([y for x, y in coordinates])
    ymax = max([y for x, y in coordinates])
    x_center = xmin + (xmax - xmin)/2.0
    y_center = ymin + (ymax - ymin)/2.0
    return x_center, y_center

def get_perimetre(code_insee):
    url = f"https://geo.api.gouv.fr/communes/{code_insee}/?format=geojson&geometry=contour"
    return ask(url)



departements = get_departements()

st.title("Erosion du trait de côte")

departement = st.selectbox("Choix du département", [d["nom"] for d in departements])

communes = get_communes([d["code"] for d in departements if d["nom"] == departement][0])

commune = st.selectbox("Choix de la commune", [c["nom"] for c in communes])

code_insee = [c["code"] for c in communes if c["nom"] == commune][0] 
x_center, y_center = get_center(code_insee)
geojson = get_perimetre(code_insee)

m = folium.Map(location=[y_center, x_center], zoom_start=16)
folium.GeoJson(geojson, name=commune, style_function=style_function).add_to(m)

map = st_folium(m, width=725)