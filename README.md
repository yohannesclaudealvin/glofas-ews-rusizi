# 🌊 GloFAS EWS – Bassin de la Rusizi

Cette application Streamlit sert de système d'alerte précoce aux crues pour le bassin de la Rusizi (Burundi). Elle applique la méthodologie de l'article *Performance Assessment and Optimization of GloFAS Forecasts on the Rusizi River Basin for Enhanced Anticipatory Flood Action* (Hakizimana et al.) à **toutes les stations du bassin**. Elle produit chaque jour une **prévision corrigée à 7 jours** à partir du débit observé du jour.

## Ce que fait l'application

| Page | Contenu |
|---|---|
| 1 · Stations | Chargement **station par station** : nom, rivière, coordonnées, fichier de débits observés, fichier GloFAS historique. Contrôle qualité, modification des coordonnées, export `stations.csv` |
| 2 · Fiche station et carte | Coordonnées et statistiques de la station, **carte interactive de la rivière** (tracé OpenStreetMap, maille GloFAS, autres stations, fonds OSM / relief / satellite), **téléchargeable en HTML et GeoJSON**, débits observés, recherche de la bonne maille GloFAS |
| 3 · Synthèse du bassin | Carte des stations colorées selon leur KGE, cartes de chaleur KGE, NSE, PBIAS et RSR (brut, corrigé, persistance), classement |
| 4 · Correction et performance | Correction en temps réel de la station active, scores par échéance, exports CSV |
| 5 · Qualité des prévisions | POD, FAR, LR, ROC, CSI avec un seuil au choix (débit moyen, quantile, période de retour, valeur fixe) |
| 6 · Hydrogrammes | Observé / corrigé (/ brut) pour chaque échéance, zoom et curseur temporel |
| 7 · Tendances et crues | Mann-Kendall modifié et pente de Sen, Gumbel / GEV / Normale (AIC), périodes de retour, jours critiques, détection par GloFAS |
| Guide et méthodes | Mode d'emploi détaillé et explication de toutes les méthodes (correction, critères, tendances, crues, limites) |
| 8 · Prévision | **Une station** : interface de prévision des inondations (téléchargement GloFAS automatique, par clé Copernicus ou fichier NetCDF ; coordonnées ; seuils Rouge/Orange/Jaune/Vert ; observation du jour ; nombre de jours ; graphique et zone de messages). **Toutes les stations** : tableau des stations à prévoir (compléter des coordonnées ou ajouter n'importe quelle station du Burundi), téléchargement de GloFAS (ensemble de 51 membres), saisie du débit observé du jour, prévision corrigée, niveaux d'alerte, exports |

Tous les graphiques sont interactifs : survol, zoom, clic sur la légende pour masquer une série, et l'icône 📷 pour télécharger une image PNG haute résolution.

### Formule de correction (section 2.3.2 de l'article)

Pour l'analyse historique, à l'échéance L :

```
Q_corr,L(t) = Q_GloFAS,L(t) + [ Q_obs(t − L) − Q_GloFAS,L(t − L) ]
```

En opérationnel (prévision émise aujourd'hui t₀, valable à t₀ + L) :

```
Q_corr(t₀ + L) = Q_GloFAS,L(t₀ + L) + [ Q_obs(t₀) − Q_GloFAS,L(t₀) ]
```

Q_GloFAS,L(t₀) est la prévision à L jours émise il y a L jours pour aujourd'hui. L'application la lit dans l'**archive des prévisions** qu'elle constitue jour après jour. Tant que cette archive est vide, elle utilise l'erreur sur la valeur GloFAS du jour.

### Niveaux d'alerte

Par défaut, l'application calcule trois seuils sur les débits observés historiques : Q90, la crue de 2 ans et la crue de 5 ans (loi de Gumbel). Elle les classe par ordre croissant pour former 🟡 Vigilance, 🟠 Alerte et 🔴 Alerte maximale. Ces seuils se modifient dans la page 8 (par exemple pour mettre les seuils officiels).

## Lancer l'application sur votre ordinateur

```bash
git clone https://github.com/<votre-compte>/glofas-ews-rusizi.git
cd glofas-ews-rusizi
python -m venv .venv
# Windows : .venv\Scripts\activate      Linux/Mac : source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

L'application s'ouvre dans le navigateur (http://localhost:8501). En local, l'archive des prévisions est enregistrée automatiquement dans `archive/forecast_archive.csv`.

## Mettre l'application sur GitHub et Streamlit Community Cloud

1. **Créer le dépôt sur GitHub.** Sur github.com : *New repository*, nom `glofas-ews-rusizi`, puis *Create*.
2. **Envoyer le code**, depuis ce dossier :
   ```bash
   git init
   git add .
   git commit -m "GloFAS EWS Rusizi"
   git branch -M main
   git remote add origin https://github.com/<votre-compte>/glofas-ews-rusizi.git
   git push -u origin main
   ```
3. **Déployer.** Allez sur https://share.streamlit.io, connectez-vous avec GitHub, cliquez *Create app*, choisissez le dépôt, la branche `main` et le fichier `app.py`, puis *Deploy*. Vous obtenez une adresse publique du type `https://glofas-ews-rusizi.streamlit.app`.

> **Données d'exemple.** Le dépôt contient les données de 9 stations IGEBU (`data/sample/stations/`) : toute personne qui ouvre l'application peut cliquer sur « Essayer avec les données d'exemple » et évaluer les performances sans avoir ses propres observations.
>
> **Archive en ligne.** Sur Streamlit Cloud, les fichiers écrits par l'application ne sont pas conservés. Téléchargez l'archive (`forecast_archive.csv`) après chaque utilisation, et rechargez-la la fois suivante dans la page 8.

## N'importe quelle station du Burundi

La page 1 accepte toute station : la liste contient déjà les 9 stations du bassin de la Rusizi et les rivières **Mugere, Jiji, Murembwe, Kanyosha, Dama et Nyengwe** (positions approximatives, à 3 km en amont de l'exutoire d'après OpenStreetMap, à remplacer par les coordonnées réelles). Pour une autre rivière, tapez son nom et cliquez sur *Chercher la rivière* : le cours d'eau s'affiche sur la carte, un point est proposé, et un clic sur la carte place la station. Le fichier de débits observés est facultatif : sans lui, la station sert seulement à la prévision (seuils à saisir à la main).

## Carte animée des débits

La page *Carte animée des débits* montre le comportement des cours d'eau dans le temps : la rivière prend la couleur du niveau d'alerte et s'épaissit avec le débit, avec un bouton Lecture, un curseur de dates et l'hydrogramme sous la carte. Données : débits observés, GloFAS brut ou corrigé (1 j), ou la dernière prévision. Export en HTML interactif et en GIF animé.

## Téléchargement automatique de GloFAS

La page 8 récupère la prévision GloFAS de trois façons :

- **Automatique** (par défaut, sans clé) : API Open-Meteo Flood, contrôle et 50 membres, jusqu'à 30 jours ;
- **Copernicus (clé API)** : fichier NetCDF officiel du jeu `cems-glofas-forecast` sur le Early Warning Data Store (https://ewds.climate.copernicus.eu). Il faut un compte gratuit, accepter une fois la licence du jeu de données, puis coller sa clé (*API Token*) dans la page. Zone par défaut : le Burundi (lat. −4,50 à −2,25, long. 28,95 à 30,90) ;
- **Fichier NetCDF** : un fichier GloFAS déjà téléchargé (variable `dis24`, `.nc` ou `.zip`).

La clé Copernicus peut être configurée une fois pour toutes : sur Streamlit Cloud, *Settings → Secrets* avec `CDS_API_KEY = "votre-clé"` ; en local, dans le fichier `~/.cdsapirc` (`url: https://ewds.climate.copernicus.eu/api` et `key: votre-clé`).

La correction utilise la prévision GloFAS téléchargée le jour même (valeur pour aujourd'hui et pour les jours suivants) et le débit observé du jour. Le fichier GloFAS historique ne sert qu'à évaluer la méthode sur le passé.

L'application prend la maille la plus proche des coordonnées saisies et l'écrit dans la zone *Messages*.

## Format des données (une station à la fois)

- **Observations** : Excel ou CSV, 1ʳᵉ colonne = date, 2ᵉ colonne = débit (m³/s). Si le fichier contient plusieurs colonnes, l'application demande laquelle utiliser.
- **GloFAS historique** : Excel ou CSV, avec la date puis 7 colonnes (échéances 1 à 7 jours).
- **Prévision manuelle (sans internet)** : CSV avec les colonnes `date` et `river_discharge`, plus éventuellement `river_discharge_min`, `_p25`, `_median`, `_p75`, `_max`.

Des modèles CSV sont téléchargeables dans la page 1 · Stations.

## Cartes

Le tracé de la rivière vient d'OpenStreetMap (API Overpass) : la rivière est retrouvée par son nom autour de la station, avec ou sans accents, et en tenant compte de variantes comme Rusizi / Ruzizi ou Kagunuzi / Kagunizi. La carte téléchargée (`carte_STATION.html`) s'ouvre dans n'importe quel navigateur. Le fichier GeoJSON (station, maille GloFAS, rivière) s'ouvre dans QGIS ou ArcGIS.

## Stations et mailles GloFAS

`config/stations.csv` contient, pour chaque station, sa rivière, les coordonnées de la station et celles de la maille GloFAS (0,05°) utilisée pour la prévision. Ces valeurs pré-remplissent le formulaire de la page 1. Les mailles de **Rusizi, Kaburantwa et Mpanda** ont été vérifiées dans l'article (validation de mai 2025). Pour les autres stations, le contrôle qualité montre que la moyenne des fichiers GloFAS historiques fournis est très éloignée de celle des débits observés : de 13 à 80 fois plus grande pour Mutimbuzi, Ntahangwa, Muhira, Nyamagana et Kagunuzi, et 8 fois plus petite pour Nyakagunda. Pour plusieurs d'entre elles (Kagunuzi, Muhira, Nyamagana), la série GloFAS correspond très probablement à une maille du cours principal de la Rusizi et non à la rivière de la station. Pour chacune de ces stations :

1. ouvrez la page **2 · Fiche station et carte → Rechercher la bonne maille GloFAS**, avec les débits observés comme référence ;
2. vérifiez sur une carte que la maille proposée est bien sur la rivière ;
3. cliquez « Utiliser cette maille », puis, dans la page 1, téléchargez `stations.csv` et remplacez `config/stations.csv` dans le dépôt.

## Structure du code

```
app.py                 point d'entrée Streamlit (navigation)
app_state.py           état partagé et calculs mis en cache
pages/                 une page par étape (stations, fiche et carte, analyses, prévision)
forecast_batch.py      onglet « Toutes les stations » de la page Prévision
ews/                   la méthodologie, indépendante de l'interface
  data_io.py           lecture des fichiers, contrôle qualité
  correction.py        correction en temps réel, prévision opérationnelle, archive
  metrics.py           KGE, NSE, PBIAS, RSR, tableau de contingence
  statistics.py        Mann-Kendall modifié, Sen, Gumbel/GEV/Normale, jours critiques
  glofas_api.py        API Open-Meteo Flood (GloFAS v4), recherche de maille
  glofas_netcdf.py     téléchargement Copernicus EWDS (cdsapi) et lecture des fichiers NetCDF
  geo.py               carte Folium, tracé et recherche des rivières (OpenStreetMap), export GeoJSON
  animation.py         carte animée des débits (Plotly) et GIF (matplotlib)
  plots.py             graphiques Plotly interactifs
  theme.py             couleurs et style de l'application et des graphiques
config/stations.csv    mailles GloFAS des stations
tests/                 tests de non-régression (résultats de l'article) et test de toutes les pages
```

Les tests (`pytest -q tests/test_core.py`) vérifient que le code retrouve les résultats de l'article : KGE/NSE corrigés, crues de 2 et 10 ans, tendance de Rusizi. GitHub les lance automatiquement à chaque `push` (`.github/workflows/tests.yml`).

## Sources des données

- GloFAS v4 : Copernicus Emergency Management Service (CEMS), via l'API Open-Meteo Flood (https://open-meteo.com/en/docs/flood-api) ou le Copernicus Early Warning Data Store. Données sous licence CC BY 4.0. L'API est gratuite et sans clé pour un usage non commercial ; l'application gère la limite de requêtes par minute.
- Débits observés : Institut Géographique du Burundi (IGEBU).
- Cours d'eau et fonds de carte : © contributeurs OpenStreetMap (ODbL), OpenTopoMap, Esri World Imagery.
