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
from branca.colormap import linear

# locale.setlocale(locale.LC_ALL, 'fr_FR')

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
    df = pd.read_sql_query(
        f"SELECT * FROM indicateurs_com_{perimetre}",
        con=conn,
        dtype={"idcom": str, "iddep": str},
    )
    df["iddep"] = df["iddep"].apply(format_dep)
    return df


@st.cache_data
def data_dep(perimetre):
    df = pd.read_sql_query(
        f"SELECT * FROM indicateurs_dpt_{perimetre}", con=conn, dtype={"iddep": str}
    )
    df["iddep"] = df["iddep"].apply(format_dep)
    return df


def get_val(value, code, perimetre, id="idcom"):
    df = data(perimetre) if id == "idcom" else data_dep(perimetre)
    valeur = df[df[id] == code][value].values[0]
    if valeur < 11:
        return None
    return int(valeur) if valeur.is_integer() else valeur


def get(value, code, perimetre, id="idcom"):
    valeur = get_val(value, code, perimetre, id=id)
    if valeur is None:
        return "< 11"
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


def get_communes_dispo(departement, perimetre, littoral_only=True):
    df = data(perimetre)
    if littoral_only:
        df = df[df["comm_litt"] == "oui"]
    comm = list(df[df["iddep"] == departement]["idcom"].unique())
    return comm


@st.cache_data
def get_communes(departement, perimetre, littoral_only=True):
    url = f"https://geo.api.gouv.fr/departements/{departement}/communes"
    communes = ask(url)
    return [
        c
        for c in communes
        if c["code"] in get_communes_dispo(departement, perimetre, littoral_only)
    ]


@st.cache_data
def data_aav():
    with open("aav.geojson") as response:
        aav = json.load(response)
    for a in aav["features"]:
        a["id"] = a["properties"]["id"]
    return aav


@st.cache_data
def carto_aav(ratio, perimetre):
    seuil = perimetre[:-1]
    aav = data_aav()
    df = pd.read_sql_query(
        f"""
                           SELECT aav2020, libaav2020, {ratio} AS ratio 
                           FROM indicateurs_aav 
                           WHERE seuil_frange={seuil}
                           """,
        con=conn,
        dtype={"aav2020": str},
    )
    df["comparaison_base_100"] = df["ratio"].apply(
        lambda x: round(x * 100, 1) if x <= 1 else round(100 / (2 - x), 1)
    )

    fig = px.choropleth_mapbox(
        df,
        geojson=aav,
        locations="aav2020",
        color="comparaison_base_100",
        color_continuous_scale="tropic",
        range_color=(50, 150),
        mapbox_style="carto-positron",
        zoom=5,
        center={"lat": 50, "lon": 3},
        opacity=0.7,
        # mapbox_style="open-street-map",
        hover_name="libaav2020",
        labels={"comparaison_base_100": "Pourcentage", "aav2020": "Code AAV"},
    )
    fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})
    return fig


def graphe_aav(type, perimetre):
    seuil = perimetre[:-1]
    df = pd.read_sql_query(
        f"""
                        SELECT aav2020, libaav2020, '2015' AS annee,  
                        valeur_ratio_2015_{type} AS ratio
                        FROM indicateurs_aav 
                        WHERE seuil_frange={seuil}
                        
                        UNION
                        
                        SELECT aav2020, libaav2020, '2018' AS annee,  
                        valeur_ratio_2018_{type} AS ratio
                        FROM indicateurs_aav 
                        WHERE seuil_frange={seuil}

                        UNION
                        
                        SELECT aav2020, libaav2020, '2021' AS annee,  
                        valeur_ratio_2021_{type} AS ratio
                        FROM indicateurs_aav 
                        WHERE seuil_frange={seuil}

                    ORDER BY aav2020 DESC 
                        """,
        con=conn,
        dtype={"aav2020": str},
    )

    df["base_100"] = df["ratio"].apply(
        lambda x: round(x * 100, 1) if x <= 1 else round(100 / (2 - x), 1)
    )
    fig = px.scatter(df, y="libaav2020", x="base_100", color="annee")
    fig.add_vrect(
        x0="100",
        x1="200",
        annotation_text="Valeurs foncières supérieures au sein la bande",
        annotation_position="top left",
        fillcolor="tomato",
        opacity=0.25,
        line_width=0,
    )
    fig.update_layout(height=4000)
    fig.update_layout(
        title_text="Situation des prix des dans la bande par rapport à l'AAV"
    )
    return fig


def taux_rotation(perimetre):
    seuil = perimetre[:-1]
    df = pd.read_sql_query(
        f"""
                           SELECT libaav2020 AS "Nom AAV", 
                                cast(tx_rotation_impact * 100.0 As text) || ' %' AS "Taux rotation dans la zone", 
                                cast(tx_rotation_non_impact * 100.0 As text) || ' %' AS "Taux rotation hors zone"
                           FROM indicateurs_aav 
                           WHERE seuil_frange={seuil};
                           """,
        con=conn,
    )
    return df


def graphe_occupation_parc(code_insee, perimetre, id="idcom"):
    type_occupation = [
        "Total",
        "Occupés par propriétaire",
        "Loué",
        "Résidences secondaires",
        "Vacants",
    ]
    valeurs = [
        get("nb_logt", code_insee, perimetre, id=id),
        get("nb_logt_po", code_insee, perimetre, id=id),
        get("nb_logt_pb", code_insee, perimetre, id=id),
        get("nb_logt_rs", code_insee, perimetre, id=id),
        get("nb_logt_va", code_insee, perimetre, id=id),
    ]
    fig = go.Figure([go.Bar(x=type_occupation, y=valeurs)])
    fig.update_layout(
        title_text="Nombre de logements concernés en fonction de leur occupation"
    )
    return fig


def graphe_age_parc(code_insee, perimetre, id="idcom"):
    type_occupation = [
        "Total",
        "Avant 1945",
        "1945-1959",
        "1960-1974",
        "1975-1997",
        "1998-2012",
        "Après 2012",
    ]
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
    fig = go.Figure(
        [
            go.Bar(x=type_occupation, y=valeurs_maison, name="Maison"),
            go.Bar(x=type_occupation, y=valeurs_appartement, name="Appartements"),
        ]
    )
    fig.update_layout(
        title_text="Nombre de logements concernés en fonction de leur période de construction"
    )
    return fig


def graphe_foncier(code_insee, perimetre, id="idcom"):
    labels = ["Surfaces NAF", "Surface urbanisées"]
    values = [
        get_val("surfaces_naf", code_insee, perimetre, id=id),
        get_val("surfaces_urba", code_insee, perimetre, id=id),
    ]
    fig = go.Figure(data=[go.Pie(labels=labels, values=values)])
    return fig


def graphe_estimation_logement_taille(code_insee, perimetre, id="idcom"):
    data = dict(
        typo=[
            "Maison",
            "Maison",
            "Maison",
            "Appartement",
            "Appartement",
            "Appartement",
        ],
        taille=[
            "Petite",
            "Moyenne",
            "Grande",
            "Petit",
            "Moyen",
            "Grand",
        ],
        estimation=[
            get_val("estim_maisons_petites", code_insee, perimetre, id=id),
            get_val("estim_maisons_moyennes", code_insee, perimetre, id=id),
            get_val("estim_maisons_grandes", code_insee, perimetre, id=id),
            get_val("estim_appts_petits", code_insee, perimetre, id=id),
            get_val("estim_appts_moyens", code_insee, perimetre, id=id),
            get_val("estim_appts_grands", code_insee, perimetre, id=id),
        ],
    )
    df = pd.DataFrame.from_dict(data)
    fig = px.sunburst(
        df,
        path=["typo", "taille"],
        values="estimation",
        # title="Estimation financière des logements selon leur taille",
    )
    fig.update_traces(textinfo="label+percent entry")
    return fig


def graphe_estimation_logement_age(code_insee, perimetre, id="idcom"):
    data = dict(
        typo=[
            "Maison",
            "Maison",
            "Maison",
            "Maison",
            "Maison",
            "Maison",
            "Appartement",
            "Appartement",
            "Appartement",
            "Appartement",
            "Appartement",
            "Appartement",
        ],
        taille=[
            "Avant 1945",
            "1945-1959",
            "1960-1974",
            "1975-1997",
            "1998-2012",
            "Après 2012",
            "Avant 1945",
            "1945-1959",
            "1960-1974",
            "1975-1997",
            "1998-2012",
            "Après 2012",
        ],
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
        ],
    )
    df = pd.DataFrame.from_dict(data)
    fig = px.sunburst(
        df,
        path=["typo", "taille"],
        values="estimation",
        # title="Estimation financière des logements selon leur taille",
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


INDICATEURS_SYNTHESE = {
    "nb_logt": "Nombre de logements:",
    "nb_loc_act": "Nombre de locaux d'activités:",
    "estim_logt": "Estimation logements (€):",
    "estim_bur_com": "Estimation bureaux/commerces (€):",
    "surfaces_urba": "Surfaces urbanisées (m2):",
    "surfaces_naf": "Surfaces NAF (m2):",
}

INDICATEURS_FACTEUR = {
    "nb_logt": (1000, "Nombre de logements (milliers)"),
    "nb_loc_act": (1000, "Nombre de locaux d'activités (milliers)"),
    "estim_logt": (1000000000, "Estimation logements (Mds€)"),
    "estim_bur_com": (1000000000, "Estimation bureaux/commerces (Mds€)"),
    "surfaces_urba": (10000, "Surfaces urbanisées (ha)"),
    "surfaces_naf": (10000, "Surfaces NAF (ha)"),
}


def colorline(indicator, perimetre):
    df = data_dep(perimetre)
    min = df[indicator].min()
    max = df[indicator].max()
    colormap = linear.OrRd_09.scale(min, max)
    return colormap, min, max


def style_by_indicator(indicator, perimetre):
    def style(feature):
        df = data_dep(perimetre)
        colormap, _, _ = colorline(indicator, perimetre)
        val = feature["properties"][indicator]
        return {
            "fillColor": colormap(val) if val > 0 else "lightgray",
            "fillOpacity": 0.9 if val > 0 else 0.4,
            "weight": 1,
            "color": "gray",
        }

    return style


@st.cache_data
def get_center(code_insee):
    url = f"https://geo.api.gouv.fr/communes/{code_insee}/?format=geojson&geometry=bbox"
    geojson = ask(url)
    coordinates = geojson["geometry"]["coordinates"][0]
    xmin = min([x for x, y in coordinates])
    xmax = max([x for x, y in coordinates])
    ymin = min([y for x, y in coordinates])
    ymax = max([y for x, y in coordinates])
    x_center = xmin + (xmax - xmin) / 2.0
    y_center = ymin + (ymax - ymin) / 2.0
    return x_center, y_center


@st.cache_data
def get_perimetre(code_insee):
    url = f"https://geo.api.gouv.fr/communes/{code_insee}/?format=geojson&geometry=contour"
    return ask(url)


@st.cache_data
def get_perimetre_departements(perimetre):
    url = f"https://static.data.gouv.fr/resources/carte-des-departements-2-1/20191202-212236/contour-des-departements.geojson"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()

        df = data_dep(perimetre)
        for feature in data["features"]:
            code_dep = feature["properties"]["code"]
            results = df[df.iddep == code_dep]
            if not results.empty:
                for ind in INDICATEURS_SYNTHESE:
                    feature["properties"][ind] = int(results[ind].values[0])
            else:
                for ind in INDICATEURS_SYNTHESE:
                    feature["properties"][ind] = 0
        return data
    return None


######

## APP

######

st.set_page_config(
    page_title="Enjeux littoraux",
    page_icon=None,
    layout="wide",
)

st.title("Connaissance des marchés sur le littoral")


def password_entered():
    if st.session_state["password"] == st.secrets["password"]:
        st.session_state["password_correct"] = True
        st.session_state["password"] = None  # don't store password
    else:
        st.session_state["password_correct"] = False


def check_password():
    if "password_correct" not in st.session_state:
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        st.error("😕 Password incorrect")
        return False
    else:
        return True


if check_password():
    perimetres = ["200m", "1000m", "10000m"]
    perimetre = st.selectbox(
        "Choix de la distance au littoral (limite terre-mer)", perimetres
    )

    tab_dep, tab_synthese, tab_aav = st.tabs(
        [
            "Indicateurs par département",
            "Synthèse - départements littoraux",
            "Synthèse - AAV littoraux",
        ]
    )

    with tab_aav:
        st.header(f"Aires d'attraction des villes")

        with st.expander("Précisions"):
            st.write(
                """
        Les indicateurs de comparaison de marchés à l'AAV 
        concernent uniquement les bandes des communes 
        en bord de mer au sens de la loi littorale.
                     """
            )

        st.subheader("Comparaison des niveaux de prix en 2021")

        st.markdown(
            """
        Pour les maisons moyennes et les appartements 3/4 pièces,
        une comparaison du prix médian dans la bande littorale par rapport 
        au prix médian dans chaque territoire de référence (Aire d'Attration des Villes)
        est proposée."""
        )

        with st.spinner("Chargement..."):
            col_carto_aav_mai, col_carto_aav_apt = st.columns(2)
            with col_carto_aav_mai:
                st.subheader("Maisons moyennes (90-130 m2)")
                st.plotly_chart(
                    carto_aav("valeur_ratio_2021_maison", perimetre),
                    use_container_width=True,
                )
            with col_carto_aav_apt:
                st.subheader("Appartements 3/4 pièces")
                st.plotly_chart(
                    carto_aav("valeur_ratio_2021_appt", perimetre),
                    use_container_width=True,
                )

        st.markdown(
            """
        *Interprétation : si le ratio calculé à 200 m vaut 122 % 
        pour les maisons moyennes de l'AAV de Vannes, cela signifie, que les
        biens situés dans la zone littorale des 200 m sur cette AAV sont 1,22 fois 
        plus chers que ceux du même AAV à l'extérieur de cette zone.*
        """
        )

        st.subheader("Evolution des niveaux de prix par AAV de 2015 à 2021")

        with st.spinner("Chargement..."):
            col_graphe_aav_mai, col_graphe_aav_apt = st.columns(2)
            with col_graphe_aav_mai:
                st.subheader("Maisons moyennes (90-130 m2)")
                st.plotly_chart(
                    graphe_aav("maison", perimetre), use_container_width=True
                )
            with col_graphe_aav_apt:
                st.subheader("Appartements 3/4 pièces")
                st.plotly_chart(graphe_aav("appt", perimetre), use_container_width=True)

        st.subheader("Taux de rotation du parc privé")
        st.markdown(
            """
        Les taux de rotation proposés correspondent au nombre de logements privés ayant muté entre 2019 et 2021 
        divisé par la taille du parc de logements privés en 2019 dans les zones concernées et non concernées.  
        """
        )

        st.dataframe(taux_rotation(perimetre), use_container_width=True)

    with tab_dep:
        with st.expander("Précisions"):
            st.write(
                """
        Les données proposées à l'échelle départementale concernent 
        uniquement les communes en bord de mer au sens de la loi littorale.
                     """
            )
        departements_dep = get_departements(perimetre)
        departement_dep = st.selectbox(
            "Choix d'un département", [d["nom"] for d in departements_dep]
        )

        code_dep = [d["code"] for d in departements_dep if d["nom"] == departement_dep][
            0
        ]

        with st.spinner("Chargement..."):
            st.header(f"{departement_dep} - Bande {perimetre}")
            col21, col22 = st.columns(2)
            with col21:
                st.metric(
                    "Nombre de logements",
                    get("nb_logt", code_dep, perimetre, "iddep"),
                )
                st.metric(
                    "Estimation des logements",
                    get("estim_logt", code_dep, perimetre, "iddep") + " €",
                )
                st.metric(
                    "Surface urbanisée",
                    get("surfaces_urba", code_dep, perimetre, "iddep") + " m2",
                )
            with col22:
                st.metric(
                    "Nombre de locaux d'activité",
                    get("nb_loc_act", code_dep, perimetre, "iddep"),
                )
                st.metric(
                    "Estimation bureaux/commerces",
                    get("estim_bur_com", code_dep, perimetre, "iddep") + " €",
                )
                st.metric(
                    "Surface NAF",
                    get("surfaces_naf", code_dep, perimetre, "iddep") + " m2",
                )

        st.header("Enjeux concernées")

        with st.spinner("Chargement..."):
            st.subheader("Logement")
            col_occ_dep, col_cstr_dep = st.columns(2, gap="large")
            with col_occ_dep:
                st.plotly_chart(
                    graphe_occupation_parc(code_dep, perimetre, "iddep"),
                    use_container_width=True,
                )
            with col_cstr_dep:
                st.plotly_chart(
                    graphe_age_parc(code_dep, perimetre, "iddep"),
                    use_container_width=True,
                )

            col_foncier_dep, col_act_dep = st.columns(2, gap="large")
            with col_foncier_dep:
                st.subheader("Foncier")
                st.plotly_chart(
                    graphe_foncier(code_dep, perimetre, "iddep"),
                    use_container_width=True,
                )
            with col_act_dep:
                st.subheader("Activité")
                col_hotel_dep, col_camping_dep = st.columns(2)
                with col_hotel_dep:
                    st.metric(
                        "Hotels",
                        get("nb_hotels", code_dep, perimetre, "iddep"),
                    )
                with col_camping_dep:
                    st.metric(
                        "Campings",
                        get("nb_campings", code_dep, perimetre, "iddep"),
                    )

                col_commerce_dep, col_bureau_dep = st.columns(2)
                with col_commerce_dep:
                    st.metric(
                        "Commerces",
                        get("nb_commerces", code_dep, perimetre, "iddep"),
                    )
                with col_bureau_dep:
                    st.metric(
                        "Locaux de bureau",
                        get("nb_bureaux", code_dep, perimetre, "iddep"),
                    )

                st.metric(
                    "Autres locaux d'activité",
                    get("nb_act_autres", code_dep, perimetre, "iddep"),
                )

        st.header("Estimation des biens")

        with st.spinner("Chargement..."):
            st.subheader("Estimation des logements")
            col_estim_dep, col_mai_dep, col_apt_dep, col_loyer_dep = st.columns(
                4, gap="large"
            )
            with col_estim_dep:
                st.metric(
                    "Ensemble des logements",
                    get("estim_logt", code_dep, perimetre, "iddep") + " €",
                )
            with col_mai_dep:
                st.metric(
                    "Maisons",
                    get("estim_maisons", code_dep, perimetre, "iddep") + " €",
                )
            with col_apt_dep:
                st.metric(
                    "Appartements",
                    get("estim_appts", code_dep, perimetre, "iddep") + " €",
                )
            with col_loyer_dep:
                st.metric(
                    "Estimation des loyers percus",
                    get("estim_loyer_loue", code_dep, perimetre, "iddep") + " €/mois",
                )

            st.plotly_chart(
                graphe_estimation_logement_taille(code_dep, perimetre, "iddep"),
                use_container_width=True,
            )

            st.subheader("Estimation des locaux d'activité")
            col_estim_bureau_dep, col_estim_commerce_dep = st.columns(2, gap="large")
            with col_estim_bureau_dep:
                st.metric(
                    "Bureaux",
                    get("estimation_bureaux", code_dep, perimetre, "iddep") + " €",
                )
            with col_estim_commerce_dep:
                st.metric(
                    "Commerces",
                    get("estimation_commerces", code_dep, perimetre, "iddep") + " €",
                )

    with tab_synthese:
        st.header(f"Départements - Bande {perimetre}")

        indicateur_carto = st.selectbox(
            "Thème de la carte",
            INDICATEURS_SYNTHESE.keys(),
            format_func=lambda x: INDICATEURS_SYNTHESE[x][:-1],
        )

        # Carte
        with st.spinner("Chargement..."):
            x_center, y_center = get_center("45234")
            geojson = get_perimetre_departements(perimetre)

            m = folium.Map(location=[47, 3], zoom_start=6)
            folium.GeoJson(
                geojson,
                name="Synthese",
                style_function=style_by_indicator(indicateur_carto, perimetre),
                tooltip=folium.GeoJsonTooltip(
                    fields=[
                        "code",
                        "nom",
                    ]
                    + list(INDICATEURS_SYNTHESE.keys()),
                    aliases=[
                        "Code:",
                        "Nom:",
                    ]
                    + list(INDICATEURS_SYNTHESE.values()),
                    localize=True,
                    sticky=False,
                    labels=True,
                    style="""
                    background-color: #F0EFEF;
                    border: 2px solid black;
                    border-radius: 3px;
                    box-shadow: 3px;
                """,
                    max_width=700,
                ),
            ).add_to(m)

            folium.TileLayer("cartodbpositron").add_to(m)
            cl, min, max = colorline(indicateur_carto, perimetre)
            cl = cl.scale(
                min / INDICATEURS_FACTEUR[indicateur_carto][0],
                max / INDICATEURS_FACTEUR[indicateur_carto][0],
            )
            cl.caption = INDICATEURS_FACTEUR[indicateur_carto][1]
            cl.add_to(m)

            map = st_folium(m, height=700, use_container_width=True)
