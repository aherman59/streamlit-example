import sqlite3
import json
import requests
import folium
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium
import locale

locale.setlocale(locale.LC_ALL, 'fr_FR')

####

# UTILS

####

def ask(url):
    try:
        response = requests.get(url)
        if response.status_code == 200: 
            return response.json()
    except Exception as e:
        return None


def query(sql):
    conn = sqlite3.connect("data.sqlite3")
    with conn:
        df = pd.read_sql_query(sql, con=conn)
        return df 
    return None

@st.cache_data
def data():
    return pd.read_csv("lacanau_agrege.csv", dtype={"idcom": str, "iddep": str}) 

def get(value, comm):
    df = data()
    valeur = df[df["idcom"] == comm][value].values[0]
    return "{:,d}".format(valeur).replace(",", " ")

def get_val(value, comm):
    df = data()
    valeur = df[df["idcom"] == comm][value].values[0]
    return valeur

def get_departements_dispo():
    #departements_dispo = query("""SELECT DISTINCT code_dep FROM comparaison_200_1000;""")["code_dep"].to_list()
    df = data() 
    deps =  list(df["iddep"].unique())
    return deps

def graphe_occupation_parc(code_insee):
    type_occupation=['Total', 'Occupés par propriétaire', 'Loué', 'Résidences secondaires', 'Vacants', ]
    valeurs = [
        get("nb_logt", code_insee),
        get("nb_logt_po", code_insee),
        get("nb_logt_pb", code_insee),
        get("nb_logt_rs", code_insee),
        get("nb_logt_va", code_insee),
    ]
    fig = go.Figure([go.Bar(x=type_occupation, y=valeurs)])
    fig.update_layout(title_text="Détail des logements impactés en fonction de leur occupation")
    return fig

def graphe_age_parc(code_insee):
    type_occupation=['Total', 'Avant 1945', '1945-1959', '1960-1974', '1975-1997', '1998-2012', 'Après 2012']
    valeurs_maison = [
        get("nb_maisons", code_insee),
        get("nb_maisons_av45", code_insee),
        get("nb_maisons_45_59", code_insee),
        get("nb_maisons_60_74", code_insee),
        get("nb_maisons_75_97", code_insee),
        get("nb_maisons_98_12", code_insee),
        get("nb_maisons_ap2012", code_insee),
    ]
    valeurs_appartement = [
        get("nb_appts", code_insee),
        get("nb_appts_av45", code_insee),
        get("nb_appts_45_59", code_insee),
        get("nb_appts_60_74", code_insee),
        get("nb_appts_75_97", code_insee),
        get("nb_appts_98_12", code_insee),
        get("nb_appts_ap2012", code_insee),
    ]
    fig = go.Figure([
            go.Bar(x=type_occupation, y=valeurs_maison, name="Maison"),
            go.Bar(x=type_occupation, y=valeurs_appartement, name="Appartements"),
                     ])
    fig.update_layout(title_text = "Détail des logements impactés en fonction de leur période de construction")
    return fig

def graphe_foncier(code_insee):
    labels = ['Surfaces NAF', "Surface urbanisées"]
    values = [get_val("surfaces_naf", code_insee), get_val("surfaces_urba", code_insee)]
    fig = go.Figure(data=[go.Pie(labels=labels, values=values)])
    return fig

@st.cache_data
def get_departements():
    url = f"https://geo.api.gouv.fr/departements/"
    departements = ask(url)
    return [d for d in departements if d["code"] in get_departements_dispo()]

def get_communes_dispo(departement):
    df = pd.read_csv("lacanau_agrege.csv", dtype={"idcom": str, "iddep": str})
    return list(df[df["iddep"] == departement]["idcom"].unique())

@st.cache_data
def get_communes(departement):
    url = f"https://geo.api.gouv.fr/departements/{departement}/communes"
    communes = ask(url)
    return [c for c in communes if c["code"] in get_communes_dispo(departement)]

def style_perimetre(feature):
    return {
        "fillOpacity": 0.1,
        "weight": 2,
        "fillColor": "darkred",
        "color": "darkred",
    }

def style_recul(feature):
    return {
        "fillOpacity": 0.1,
        "weight": 2,
        "fillColor": "darkblue",
        "color": "darkblue",
    }

@st.cache_data
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

@st.cache_data
def get_perimetre(code_insee):
    url = f"https://geo.api.gouv.fr/communes/{code_insee}/?format=geojson&geometry=contour"
    return ask(url)


######

## APP

######

st.set_page_config(page_title="Erosion", page_icon=None, layout="wide",)

st.title("Erosion du trait de côte")

col_dep, col_com, col_peri = st.columns(3)

with col_dep:
    departements = get_departements()
    departement = st.selectbox("Choix du département", [d["nom"] for d in departements])

code_dep = [d["code"] for d in departements if d["nom"] == departement][0]

with col_com:
    communes = get_communes(code_dep)
    commune = st.selectbox("Choix de la commune", [c["nom"] for c in communes])

code_insee = [c["code"] for c in communes if c["nom"] == commune][0] 

with col_peri:
    perimetres = ["200m", "1000m", "10000m"]
    perimetre = st.selectbox("Choix du perimètre", perimetres)

tab_dep, tab_comm = st.tabs(["Département", "Commune"])

with tab_dep:
    st.header(f"Département {departement}")

    with st.spinner("Chargement..."):
        st.text("Encore un peu de patience...")

with tab_comm:

    col1, col2 = st.columns(2, gap="large")

    with col1: 
        st.header(f"Carte de situation - {commune}")
        # Carte
        with st.spinner("Chargement..."):
            x_center, y_center = get_center(code_insee)
            geojson = get_perimetre(code_insee)
            m = folium.Map(location=[y_center, x_center], zoom_start=10)
            folium.GeoJson(geojson, name=commune, style_function=style_perimetre).add_to(m)
            folium.GeoJson(json.loads(open(f"bande_200_d{code_dep}.geojson").read()), name="frange", style_function=style_recul).add_to(m)
            map = st_folium(m, width=500, height=400)

    with col2:
        st.header(f"Principaux chiffres - Bande {perimetre}")
        col21, col22 = st.columns(2)
        with col21:
            st.metric("Nombre de logements", get("nb_logt", code_insee),)
            st.metric("Estimation des logements",get("estim_logt", code_insee) + " €",)
            st.metric("Surface urbanisée",get("surfaces_urba", code_insee) + " m2",)
        with col22:
            st.metric("Nombre de locaux d'activité", get("nb_loc_act", code_insee),)
            st.metric("Estimation des locaux d'activité", "-- €",)
            st.metric("Surface NAF", get("surfaces_naf", code_insee) + " m2",)

    st.header("Enjeux impactés")

    with st.spinner("Chargement..."):
        st.subheader("Logement")
        col_occ, col_cstr = st.columns(2, gap="large")
        with col_occ:
            st.plotly_chart(graphe_occupation_parc(code_insee), use_container_width=True)
        with col_cstr:
            st.plotly_chart(graphe_age_parc(code_insee), use_container_width=True)

        col_foncier, col_act = st.columns(2, gap="large")
        with col_foncier: 
            st.subheader("Foncier")
            st.plotly_chart(graphe_foncier(code_insee), use_container_width=True)
        with col_act:
            st.subheader("Activité")
            col_hotel, col_camping = st.columns(2)
            with col_hotel:
                st.metric("Hotels", get("nb_hotels", code_insee),)
            with col_camping:
                st.metric("Campings", get("nb_campings", code_insee),)

            col_commerce, col_bureau = st.columns(2)
            with col_commerce:
                st.metric("Commerces", get("nb_commerces", code_insee),)
            with col_bureau:
                st.metric("Locaux de bureau", get("nb_bureaux", code_insee),)
            
            st.metric("Autres locaux d'activité", get("nb_act_autres", code_insee),)

    st.header("Marché immobilier")