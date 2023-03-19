import requests
import folium
import pandas as pd
import plotly.express as px
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
        "fillOpacity": 0.1,
        "weight": 2,
        "fillColor": "darkred",
        "color": "darkred",
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


departement = st.sidebar.selectbox("Choix du département", [d["nom"] for d in departements])

communes = get_communes([d["code"] for d in departements if d["nom"] == departement][0])

commune = st.sidebar.selectbox("Choix de la commune", [c["nom"] for c in communes])

st.title("Erosion du trait de côte")
st.subheader("Carte de situation")

code_insee = [c["code"] for c in communes if c["nom"] == commune][0] 
x_center, y_center = get_center(code_insee)
geojson = get_perimetre(code_insee)

m = folium.Map(location=[y_center, x_center], zoom_start=12)
folium.GeoJson(geojson, name=commune, style_function=style_function).add_to(m)

map = st_folium(m, width=725)

st.subheader("Nombre de ventes de logements")

url = f"https://apidf-preprod.cerema.fr/indicateurs/dv3f/communes/annuel/{code_insee}"
response  = ask(url)
indicateurs = pd.DataFrame.from_dict(response["results"])
fig = px.bar(indicateurs, 
             x='annee', 
             y=['nbtrans_cod111', 'nbtrans_cod121'], 
             title = f"Evolution annuelle du nombre de ventes de logements individuels à {commune}", 
             labels={"annee" : "Année de mutation", 
                     "value" : "Nombre de ventes",},
             )
noms={"nbtrans_cod111": "Maison individuelle", 
      "nbtrans_cod121": "Appartement individuel"}
fig.update_layout(legend_title_text="Nombre de ventes")
fig.for_each_trace(lambda t: t.update(hovertemplate = t.hovertemplate.replace(t.name, noms[t.name]), name=noms[t.name]))

st.plotly_chart(fig, use_container_width=True)

st.subheader("Indicateurs, la suite...")

import numpy as np
df = pd.DataFrame(
   np.random.randn(10, 5),
   columns=('col %d' % i for i in range(5)))

st.table(df)