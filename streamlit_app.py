import sqlite3
import json
import requests
import folium
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium
import locale

#locale.setlocale(locale.LC_ALL, 'fr_FR')

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

conn = sqlite3.connect("indicateurs_tdc.sqlite3")

def format_dep(departement):
    return departement.lstrip("0").zfill(2)

@st.cache_data
def data(perimetre):
    df = pd.read_sql_query(f"SELECT * FROM indicateurs_com_{perimetre}", con=conn, dtype={"idcom": str, 'iddep': str}) 
    df["iddep"] = df['iddep'].apply(format_dep)
    return df

@st.cache_data
def data_dep(perimetre):
    df = pd.read_sql_query(f"SELECT * FROM indicateurs_dpt_{perimetre}", con=conn, dtype={'iddep': str}) 
    df["iddep"] = df['iddep'].apply(format_dep)
    return df

def get_val(value, code, perimetre, id='idcom'):
    df = data(perimetre) if id=='idcom' else data_dep(perimetre)
    valeur = df[df[id] == code][value].values[0]
    return int(valeur) if valeur.is_integer() else valeur

def get(value, code, perimetre, id='idcom'):
    valeur = get_val(value, code, perimetre, id=id)
    return f"{valeur:,}".replace(",", " ")

def get_departements_dispo(perimetre):
    df = data(perimetre) 
    deps = [d for d in list(df["iddep"].unique())]
    return deps

@st.cache_data
def get_departements(perimetre):
    url = f"https://geo.api.gouv.fr/departements/"
    departements = ask(url)
    return [d for d in departements if d["code"] in get_departements_dispo(perimetre)]

def get_communes_dispo(departement, perimetre):
    df = data(perimetre)
    dep = list(df[df["iddep"] == departement]["idcom"].unique())
    return dep

@st.cache_data
def get_communes(departement, perimetre):
    url = f"https://geo.api.gouv.fr/departements/{departement}/communes"
    communes = ask(url)
    return [c for c in communes if c["code"] in get_communes_dispo(departement, perimetre)]

@st.cache_data
def data_aav():
    with open('aav.geojson') as response:
        aav = json.load(response)
    for a in aav["features"]:
        a["id"] = a["properties"]["id"]
    return aav

@st.cache_data
def carto_aav(ratio, perimetre):
    seuil = perimetre[:-1]
    aav = data_aav()
    df = pd.read_sql_query(f"""
                           SELECT aav2020, libaav2020, {ratio} AS ratio 
                           FROM indicateurs_aav 
                           WHERE seuil_frange={seuil}
                           """, 
                           con=conn, 
                           dtype={"aav2020": str})
    df["comparaison_base_100"] = df["ratio"].apply(lambda x: round(x*100, 1) if x <= 1 else round(100/(2 - x), 1))

    fig = px.choropleth_mapbox(df, geojson=aav, locations='aav2020', color="comparaison_base_100",
                            color_continuous_scale="tropic",
                            range_color=(50, 150),
                            mapbox_style="carto-positron",
                            zoom=5, center = {"lat": 50, "lon": 3},
                            opacity=0.7,
                            #mapbox_style="open-street-map",
                            hover_name="libaav2020",
                            labels={"comparaison_base_100":"Pourcentage", "aav2020": "Code AAV"}
                            )
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
    return fig

def taux_rotation(perimetre):
    seuil = perimetre[:-1]
    df = pd.read_sql_query(f"""
                           SELECT libaav2020 AS "Nom AAV", 
                                cast(tx_rotation_impact * 100.0 As text) || ' %' AS "Taux rotation dans la zone", 
                                cast(tx_rotation_non_impact * 100.0 As text) || ' %' AS "Taux rotation hors zone"
                           FROM indicateurs_aav 
                           WHERE seuil_frange={seuil};
                           """, 
                           con=conn,)
    return df

def graphe_occupation_parc(code_insee, perimetre, id="idcom"):
    type_occupation=['Total', 'Occupés par propriétaire', 'Loué', 'Résidences secondaires', 'Vacants', ]
    valeurs = [
        get("nb_logt", code_insee, perimetre, id=id),
        get("nb_logt_po", code_insee, perimetre, id=id),
        get("nb_logt_pb", code_insee, perimetre, id=id),
        get("nb_logt_rs", code_insee, perimetre, id=id),
        get("nb_logt_va", code_insee, perimetre, id=id),
    ]
    fig = go.Figure([go.Bar(x=type_occupation, y=valeurs)])
    fig.update_layout(title_text="Nombre de logements impactés en fonction de leur occupation")
    return fig

def graphe_age_parc(code_insee, perimetre, id='idcom'):
    type_occupation=['Total', 'Avant 1945', '1945-1959', '1960-1974', '1975-1997', '1998-2012', 'Après 2012']
    valeurs_maison = [
        get("nb_maisons", code_insee, perimetre, id=id),
        get("nb_maisons_av45", code_insee, perimetre, id=id),
        get("nb_maisons_45_59", code_insee, perimetre, id=id),
        get("nb_maisons_60_74", code_insee, perimetre, id=id),
        get("nb_maisons_75_97", code_insee, perimetre, id=id),
        get("nb_maisons_98_12", code_insee, perimetre, id=id),
        get("nb_maisons_ap12", code_insee, perimetre, id=id),
    ]
    valeurs_appartement = [
        get("nb_appts", code_insee, perimetre, id=id),
        get("nb_appts_av45", code_insee, perimetre, id=id),
        get("nb_appts_45_59", code_insee, perimetre, id=id),
        get("nb_appts_60_74", code_insee, perimetre, id=id),
        get("nb_appts_75_97", code_insee, perimetre, id=id),
        get("nb_appts_98_12", code_insee, perimetre, id=id),
        get("nb_appts_ap12", code_insee, perimetre, id=id),
    ]
    fig = go.Figure([
            go.Bar(x=type_occupation, y=valeurs_maison, name="Maison"),
            go.Bar(x=type_occupation, y=valeurs_appartement, name="Appartements"),
                     ])
    fig.update_layout(title_text = "Nombre de logements impactés en fonction de leur période de construction")
    return fig

def graphe_foncier(code_insee, perimetre, id="idcom"):
    labels = ['Surfaces NAF', "Surface urbanisées"]
    values = [get_val("surfaces_naf", code_insee, perimetre, id=id), get_val("surfaces_urba", code_insee, perimetre, id=id)]
    fig = go.Figure(data=[go.Pie(labels=labels, values=values)])
    return fig

def graphe_estimation_logement_taille(code_insee, perimetre, id="idcom"):
    data = dict(
        typo=["Maison", "Maison", "Maison", "Appartement", "Appartement", "Appartement"],
        taille=["Petite", "Moyenne", "Grande", "Petit", "Moyen", "Grand",],
        estimation=[
            get_val("estim_maisons_petites", code_insee, perimetre, id=id), 
            get_val("estim_maisons_moyennes", code_insee, perimetre, id=id), 
            get_val("estim_maisons_grandes", code_insee, perimetre, id=id), 
            get_val("estim_appts_petits", code_insee, perimetre, id=id), 
            get_val("estim_appts_moyens", code_insee, perimetre, id=id), 
            get_val("estim_appts_grands", code_insee, perimetre, id=id), 
            ]
        )
    df = pd.DataFrame.from_dict(data)
    fig = px.sunburst(
        df,
        path=["typo", "taille"],
        values="estimation",
        #title="Estimation financière des logements selon leur taille",
    )
    fig.update_traces(textinfo="label+percent entry")
    return fig

def graphe_estimation_logement_age(code_insee, perimetre, id="idcom"):
    data = dict(
        typo=["Maison", "Maison", "Maison","Maison", "Maison", "Maison", "Appartement", "Appartement", "Appartement", "Appartement", "Appartement", "Appartement"],
        taille=['Avant 1945', '1945-1959', '1960-1974', '1975-1997', '1998-2012', 'Après 2012','Avant 1945', '1945-1959', '1960-1974', '1975-1997', '1998-2012', 'Après 2012'],
        estimation=[
            get_val("estim_maisons_av45", code_insee, perimetre, id=id), 
            get_val("estim_maisons_45_59", code_insee, perimetre, id=id), 
            get_val("estim_maisons_60_74", code_insee, perimetre, id=id), 
            get_val("estim_maisons_75_97", code_insee, perimetre, id=id), 
            get_val("estim_maisons_98_12", code_insee, perimetre, id=id), 
            get_val("estim_maisons_ap12", code_insee, perimetre, id=id), 
            get_val("estim_appts_av45", code_insee, perimetre, id=id), 
            get_val("estim_appts_45_59", code_insee, perimetre, id=id), 
            get_val("estim_appts_60_74", code_insee, perimetre, id=id), 
            get_val("estim_appts_75_97", code_insee, perimetre, id=id), 
            get_val("estim_appts_98_12", code_insee, perimetre, id=id), 
            get_val("estim_appts_ap12", code_insee, perimetre, id=id), 
            ]
        )
    df = pd.DataFrame.from_dict(data)
    fig = px.sunburst(
        df,
        path=["typo", "taille"],
        values="estimation",
        #title="Estimation financière des logements selon leur taille",
    )
    fig.update_traces(textinfo="label+percent entry")
    return fig

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

perimetres = ["200m", "1000m", "10000m"]
perimetre = st.selectbox("Choix de la distance au littoral (limite terre-mer)", perimetres)


tab_comm, tab_dep, tab_aav = st.tabs(["Commune", "Département", "AAV"])

with tab_aav:
    st.header(f"Aires d'attraction des villes")

    st.subheader("Comparaison des niveaux de prix")

    st.markdown("""
    Pour les maisons moyennes et les appartements 3/4 pièces,
    une comparaison du prix médian dans la bande littorale par rapport 
    au prix médian dans chaque territoire de référence (Aire d'Attration des Villes)
     est proposée.""")


    with st.spinner("Chargement..."):
        col_carto_aav_mai, col_carto_aav_apt = st.columns(2)
        with col_carto_aav_mai:
            st.subheader("Maisons moyennes (90-130 m2)")
            st.plotly_chart(carto_aav("valeur_ratio_2021_maison", perimetre), use_container_width=True)
        with col_carto_aav_apt:
            st.subheader("Appartements 3/4 pièces")
            st.plotly_chart(carto_aav("valeur_ratio_2021_appt", perimetre), use_container_width=True)
        
    st.markdown("""
    *Interprétation : si le ratio calculé à 200 m vaut 122 % 
    pour les maisons moyennes de l'AAV de Vannes, cela signifie, que les
    biens situés dans la zone littorale des 200 m sur cette AAV sont 1,22 fois 
    plus chers que ceux du même AAV à l'extérieur de cette zone.*
    """)


    st.subheader("Taux de rotation du parc privé")
    st.markdown("""
    Les taux de rotation proposés correspondent au nombre de logements privés ayant muté entre 2019 et 2021 
    divisé par la taille du parc de logements privés en 2019 dans les zone impactées et non impactées.  
     """)

    st.dataframe(taux_rotation(perimetre), use_container_width=True)

with tab_dep:

    departements_dep = get_departements(perimetre)
    departement_dep = st.selectbox("Choix d'un département", [d["nom"] for d in departements_dep])

    code_dep = [d["code"] for d in departements_dep if d["nom"] == departement_dep][0]

    with st.spinner("Chargement..."):
        st.header(f"{departement_dep} - Bande {perimetre}")
        col21, col22 = st.columns(2)
        with col21:
            st.metric("Nombre de logements", get("nb_logt", code_dep, perimetre, "iddep"),)
            st.metric("Estimation des logements",get("estim_logt", code_dep, perimetre, "iddep") + " €")
            st.metric("Surface urbanisée",get("surfaces_urba", code_dep, perimetre, "iddep") + " m2",)
        with col22:
            st.metric("Nombre de locaux d'activité", get("nb_loc_act", code_dep, perimetre, "iddep"),)
            st.metric("Estimation bureaux/commerces",get("estim_bur_com", code_dep, perimetre, "iddep") + " €")
            st.metric("Surface NAF", get("surfaces_naf", code_dep, perimetre, "iddep") + " m2",)

    st.header("Enjeux impactés")

    with st.spinner("Chargement..."):
        st.subheader("Logement")
        col_occ_dep, col_cstr_dep = st.columns(2, gap="large")
        with col_occ_dep:
            st.plotly_chart(graphe_occupation_parc(code_dep, perimetre, "iddep"), use_container_width=True)
        with col_cstr_dep:
            st.plotly_chart(graphe_age_parc(code_dep, perimetre, "iddep"), use_container_width=True)

        col_foncier_dep, col_act_dep = st.columns(2, gap="large")
        with col_foncier_dep: 
            st.subheader("Foncier")
            st.plotly_chart(graphe_foncier(code_dep, perimetre, "iddep"), use_container_width=True)
        with col_act_dep:
            st.subheader("Activité")
            col_hotel_dep, col_camping_dep = st.columns(2)
            with col_hotel_dep:
                st.metric("Hotels", get("nb_hotels", code_dep, perimetre, "iddep"),)
            with col_camping_dep:
                st.metric("Campings", get("nb_campings", code_dep, perimetre, "iddep"),)

            col_commerce_dep, col_bureau_dep = st.columns(2)
            with col_commerce_dep:
                st.metric("Commerces", get("nb_commerces", code_dep, perimetre, 'iddep'),)
            with col_bureau_dep:
                st.metric("Locaux de bureau", get("nb_bureaux", code_dep, perimetre, 'iddep'),)
            
            st.metric("Autres locaux d'activité", get("nb_act_autres", code_dep, perimetre, 'iddep'),)

    st.header("Estimation des biens")

    with st.spinner("Chargement..."):
        st.subheader("Estimation des logements")
        col_estim_dep, col_mai_dep, col_apt_dep = st.columns(3, gap="large")
        with col_estim_dep:
            st.metric("Ensemble des logements",get("estim_logt", code_dep, perimetre, "iddep") + " €")
        with col_mai_dep:
            st.metric("Maisons",get("estim_maisons", code_dep, perimetre, "iddep") + " €",)
        with col_apt_dep:
            st.metric("Appartements",get("estim_appts", code_dep, perimetre, "iddep") + " €",)

        st.plotly_chart(graphe_estimation_logement_taille(code_dep, perimetre, "iddep"), use_container_width=True)

        st.subheader("Estimation des locaux d'activité")
        col_estim_bureau_dep, col_estim_commerce_dep = st.columns(2, gap="large")
        with col_estim_bureau_dep:
            st.metric("Bureaux", get("estimation_bureaux", code_dep, perimetre, "iddep") + " €",)
        with col_estim_commerce_dep:
            st.metric("Commerces", get("estimation_commerces", code_dep, perimetre, "iddep") + " €",)


with tab_comm:

    col_dep, col_com = st.columns(2)
    
    with col_dep:
        departements = get_departements(perimetre)
        departement = st.selectbox("Choix du département", [d["nom"] for d in departements])

    coddep = [d["code"] for d in departements if d["nom"] == departement][0]

    with col_com:
        communes = get_communes(coddep, perimetre)
        commune = st.selectbox("Choix de la commune", [c["nom"] for c in communes])

    code_insee = [c["code"] for c in communes if c["nom"] == commune][0] 

    col1, col2 = st.columns(2, gap="large")

    with col1: 
        st.header(f"Carte de situation - {commune}")
        # Carte
        with st.spinner("Chargement..."):
            x_center, y_center = get_center(code_insee)
            geojson = get_perimetre(code_insee)
            m = folium.Map(location=[y_center, x_center], zoom_start=10)
            folium.GeoJson(geojson, name=commune, style_function=style_perimetre).add_to(m)
            # folium.GeoJson(json.loads(open(f"bande_200_d{code_dep}.geojson").read()), name="frange", style_function=style_recul).add_to(m)
            map = st_folium(m, width=500, height=400)

    with col2:
        st.header(f"Principaux chiffres - Bande {perimetre}")
        col21, col22 = st.columns(2)
        with col21:
            st.metric("Nombre de logements", get("nb_logt", code_insee, perimetre),)
            st.metric("Estimation des logements",get("estim_logt", code_insee, perimetre) + " €")
            st.metric("Surface urbanisée",get("surfaces_urba", code_insee, perimetre) + " m2",)
        with col22:
            st.metric("Nombre de locaux d'activité", get("nb_loc_act", code_insee, perimetre),)
            st.metric("Estimation bureaux/commerces",get("estim_bur_com", code_insee, perimetre) + " €")
            st.metric("Surface NAF", get("surfaces_naf", code_insee, perimetre) + " m2",)

    st.header("Enjeux impactés")

    with st.spinner("Chargement..."):
        st.subheader("Logement")
        col_occ, col_cstr = st.columns(2, gap="large")
        with col_occ:
            st.plotly_chart(graphe_occupation_parc(code_insee, perimetre), use_container_width=True)
        with col_cstr:
            st.plotly_chart(graphe_age_parc(code_insee, perimetre), use_container_width=True)

        col_foncier, col_act = st.columns(2, gap="large")
        with col_foncier: 
            st.subheader("Foncier")
            st.plotly_chart(graphe_foncier(code_insee, perimetre), use_container_width=True)
        with col_act:
            st.subheader("Activité")
            col_hotel, col_camping = st.columns(2)
            with col_hotel:
                st.metric("Hotels", get("nb_hotels", code_insee, perimetre),)
            with col_camping:
                st.metric("Campings", get("nb_campings", code_insee, perimetre),)

            col_commerce, col_bureau = st.columns(2)
            with col_commerce:
                st.metric("Commerces", get("nb_commerces", code_insee, perimetre),)
            with col_bureau:
                st.metric("Locaux de bureau", get("nb_bureaux", code_insee, perimetre),)
            
            st.metric("Autres locaux d'activité", get("nb_act_autres", code_insee, perimetre),)

    st.header("Estimation des biens")

    with st.spinner("Chargement..."):
        st.subheader("Estimation des logements")
        col_estim, col_mai, col_apt = st.columns(3, gap="large")
        with col_estim:
            st.metric("Ensemble des logements",get("estim_logt", code_insee, perimetre) + " €")
        with col_mai:
            st.metric("Maisons",get("estim_maisons", code_insee, perimetre) + " €",)
        with col_apt:
            st.metric("Appartements",get("estim_appts", code_insee, perimetre) + " €",)

        st.plotly_chart(graphe_estimation_logement_taille(code_insee, perimetre), use_container_width=True)

        st.subheader("Estimation des locaux d'activité")
        col_estim_bureau, col_estim_commerce = st.columns(2, gap="large")
        with col_estim_bureau:
            st.metric("Bureaux", get("estimation_bureaux", code_insee, perimetre) + " €",)
        with col_estim_commerce:
            st.metric("Commerces", get("estimation_commerces", code_insee, perimetre) + " €",)