import streamlit as st

from app_state import page_setup

page_setup("Guide et méthodes", icon="📘")

t1, t2, t3, t4, t5 = st.tabs(["Prise en main", "Correction des prévisions", "Critères de performance",
                              "Tendances et crues", "Limites et références"])

# ---------------------------------------------------------------------------------------------
with t1:
    st.markdown("""
### À quoi sert cette application

GloFAS, le système mondial de prévision des crues du programme Copernicus, produit chaque jour des prévisions de
débit pour toutes les rivières du monde. Ces prévisions sont précieuses, mais sur nos rivières elles sont souvent
loin des débits mesurés : sur la Rusizi, GloFAS donne en moyenne plus du double du débit observé, et sur la
Kaburantwa à peine la moitié. L'application corrige ces prévisions avec les mesures faites aux stations, évalue ce
que vaut la correction sur l'historique, puis produit chaque jour une prévision corrigée pour les sept jours à venir.

### Pour un premier essai

Sur la page d'accueil, cliquez sur **Essayer avec les données d'exemple**. Les neuf stations du bassin sont alors
chargées avec leurs débits observés de 2008 à 2023 et les prévisions GloFAS correspondantes. Vous pouvez parcourir
toutes les pages sans avoir vos propres données.

### Travailler avec vos propres stations

**1. Stations.** On ajoute les stations une par une. Pour chacune, il faut :

- son nom et le nom de la rivière ;
- les coordonnées de la station (en degrés décimaux, par exemple −3.3250 et 29.2250) ;
- les coordonnées de la maille GloFAS si vous les connaissez (sinon celles de la station sont reprises) ;
- un fichier de débits observés : la date dans la première colonne, le débit en m³/s dans la deuxième ;
- un fichier GloFAS historique : la date, puis les prévisions à 1, 2, … 7 jours (huit colonnes en tout).

Les deux fichiers peuvent être en Excel ou en CSV. Des modèles sont proposés sur la page. Le fichier GloFAS est
facultatif, mais sans lui les analyses de performance ne sont pas possibles pour la station.

**2. Fiche station et carte.** On y trouve les coordonnées de la station, ses chiffres principaux et une carte de la
rivière. Le tracé vient d'OpenStreetMap ; le carré orange est la maille GloFAS utilisée pour la prévision. La carte
se télécharge en HTML (elle s'ouvre dans n'importe quel navigateur, sans logiciel particulier) et en GeoJSON pour
QGIS ou ArcGIS. C'est aussi ici que l'on cherche la bonne maille GloFAS d'une station (voir l'onglet *Limites*).

**3 à 7. Analyses.** La station étudiée se choisit dans la barre de gauche. Chaque page reprend une étape de la
méthode : synthèse du bassin, correction et performance, qualité des prévisions d'événements, hydrogrammes,
tendances et crues de référence. Les graphiques sont interactifs : on zoome à la souris, un clic sur la légende
masque ou affiche une courbe, et l'appareil photo en haut à droite enregistre l'image en haute résolution. Chaque
tableau se télécharge en CSV.

**8. Prévision.** C'est la page de tous les jours. Elle a deux onglets.

*Prévision d'une station* reprend la disposition de l'interface de prévision des inondations : à gauche les
réglages, à droite le graphique et les messages.

- **Télécharger.** Trois façons d'obtenir la prévision GloFAS. *Automatique* : rien à faire, la dernière
  prévision (contrôle et 50 membres) est téléchargée au moment d'exécuter, sans clé. *Copernicus (clé API)* : on
  colle sa clé, on garde ou on change les limites de la zone (le Burundi par défaut), on choisit la date et on
  clique OK ; l'application récupère le fichier NetCDF officiel de GloFAS pour 30 jours. Cela prend d'une à
  quelques minutes, selon la file d'attente de Copernicus. *Fichier NetCDF* : on charge un fichier déjà téléchargé.
- **Prévision.** On choisit la station (ou « nouvelle station », avec son nom et sa rivière), on vérifie sa
  longitude et sa latitude, puis on règle les seuils. Au-dessus du seuil rouge le niveau est rouge, entre l'orange
  et le rouge il est orange, entre le jaune et l'orange il est jaune, et sous le seuil jaune tout est vert. On
  saisit l'observation du jour et le nombre de jours à prévoir, puis on clique EXÉCUTER. Au-delà de 7 jours, la
  prévision corrigée reste calculable mais elle n'a pas été évaluée sur l'historique : à lire avec prudence.
- **Vérifier la position sur le cours d'eau** affiche une carte avec le point et la rivière d'après OpenStreetMap.
  Si le point tombe à côté de la rivière, corrigez les coordonnées avant de lancer la prévision.
- **Le graphique** montre l'observation du jour, la prévision brute, la prévision corrigée et la fourchette des
  51 scénarios, sur fond de couleurs d'alerte. On peut afficher la corrigée, la brute ou les deux, et tout
  télécharger : le graphique (HTML), les données (CSV) et l'archive.
- **Messages** garde la trace de ce qui s'est passé : fichier chargé, maille GloFAS utilisée, correction appliquée,
  et les erreurs en rouge (clé refusée, coordonnées manquantes…).

*Toutes les stations* traite toutes les stations d'un coup. Le tableau *Stations à prévoir* reprend les stations
chargées ; on peut y compléter des coordonnées ou ajouter n'importe quelle autre station du Burundi. On saisit le
débit observé à chaque station et on lance le calcul ; un tableau résume le niveau d'alerte de chacune.

### Obtenir une clé Copernicus

La voie *Automatique* suffit dans la plupart des cas. Pour travailler avec les fichiers officiels :

1. créez un compte gratuit sur https://ewds.climate.copernicus.eu (Early Warning Data Store) ;
2. ouvrez le jeu de données *GloFAS forecasts* (`cems-glofas-forecast`) et acceptez sa licence en bas de la page
   *Download* (une seule fois) ;
3. copiez votre clé personnelle (*API Token*) depuis votre profil et collez-la dans la page Prévision.

La clé n'est ni enregistrée ni affichée ; il faut la recoller à chaque visite.

### L'archive des prévisions

À chaque calcul, la prévision GloFAS brute du jour est mise de côté dans une archive. Cette archive permet, quelques
jours plus tard, d'appliquer exactement la formule de correction de l'article (voir l'onglet suivant). En ligne,
l'application ne garde rien d'une visite à l'autre : pensez à télécharger `forecast_archive.csv` à la fin et à le
recharger la fois suivante. Sur un ordinateur où l'application est installée, l'archive est enregistrée toute seule.

### Les niveaux d'alerte

Par défaut, trois seuils sont calculés à partir des débits observés de la station : le débit dépassé 10 % du temps
(Q90), la crue qui revient en moyenne tous les 2 ans et celle qui revient tous les 5 ans. Ils sont rangés du plus
petit au plus grand et donnent les niveaux **Vigilance**, **Alerte** et **Alerte maximale**. Si la protection civile
ou l'IGEBU disposent de seuils officiels, il vaut mieux les saisir à la place. Dans l'onglet *Prévision d'une
station*, ces trois seuils pré-remplissent les cases jaune, orange et rouge.
""")

# ---------------------------------------------------------------------------------------------
with t2:
    st.markdown("""
### Le principe

L'erreur de GloFAS change lentement d'un jour à l'autre : si GloFAS surestime le débit aujourd'hui, il le
surestimera très probablement demain d'une quantité voisine. La correction consiste donc à mesurer l'erreur sur
le dernier débit observé et à la retrancher des prévisions suivantes. C'est la méthode dite de mise à jour en temps
réel, ou de persistance de l'erreur.

### La formule utilisée dans l'article

Pour l'échéance *L* (1 à 7 jours), on ajoute à la prévision du jour l'erreur commise par la prévision de même
échéance *L* pas de temps plus tôt :
""")
    st.latex(r"Q_{corr,L}(t) = Q_{GloFAS,L}(t) + \left[\,Q_{obs}(t-L) - Q_{GloFAS,L}(t-L)\,\right]")
    st.markdown("""
Dans l'historique, les pas de temps sont les dates des mesures (deux par semaine dans les fichiers IGEBU).

### En opérationnel

Pour la prévision émise aujourd'hui (*t₀*) et valable dans *L* jours :
""")
    st.latex(r"Q_{corr}(t_0+L) = Q_{GloFAS,L}(t_0+L) + \left[\,Q_{obs}(t_0) - Q_{GloFAS,L}(t_0)\,\right]")
    st.markdown("""
Le terme *Q_GloFAS,L(t₀)* est la prévision à *L* jours qui avait été émise il y a *L* jours pour aujourd'hui.
L'application la retrouve dans l'archive. Tant que l'archive ne la contient pas (les premiers jours d'utilisation),
elle prend à sa place la valeur GloFAS du jour. La colonne *Méthode* du tableau de résultats indique laquelle des
deux a servi.

La même correction est appliquée aux statistiques de l'ensemble (minimum, quartiles, médiane, maximum). La bande
bleue du graphique montre donc l'incertitude des prévisions météorologiques, une fois l'erreur de niveau retirée.

### Pourquoi comparer à la persistance

La persistance consiste à prévoir que le débit restera celui de la dernière mesure. Sur une rivière lente et
régulée comme la Rusizi, c'est une prévision difficile à battre à court terme. Une prévision corrigée n'apporte
vraiment quelque chose que si elle fait mieux que la persistance, en particulier pour annoncer une montée ou une
décrue. C'est pour cela que la persistance figure à côté de GloFAS dans les pages d'analyse.
""")

# ---------------------------------------------------------------------------------------------
with t3:
    st.markdown("### Critères continus (pages 3 et 4)")
    st.markdown("**KGE, efficacité de Kling-Gupta** (Gupta et al., 2009)")
    st.latex(r"KGE = 1 - \sqrt{(r-1)^2 + (\alpha-1)^2 + (\beta-1)^2},\quad \alpha=\frac{\sigma_{sim}}{\sigma_{obs}},\ \beta=\frac{\mu_{sim}}{\mu_{obs}}")
    st.markdown("""
Elle combine la corrélation *r*, le rapport des variabilités α et le rapport des moyennes β. La valeur parfaite est 1.
Selon Knoben et al. (2019), une valeur supérieure à −0,41 indique déjà que la simulation fait mieux que la simple
moyenne des observations.
""")
    st.markdown("**NSE, efficacité de Nash-Sutcliffe** (Nash et Sutcliffe, 1970)")
    st.latex(r"NSE = 1 - \frac{\sum (Q_{sim}-Q_{obs})^2}{\sum (Q_{obs}-\overline{Q_{obs}})^2}")
    st.markdown("""
Une valeur de 1 est parfaite ; 0 veut dire que la prévision ne fait pas mieux que la moyenne observée ; une valeur
négative, qu'elle fait moins bien.
""")
    st.markdown("**PBIAS, biais en pourcentage, et RSR**")
    st.latex(r"PBIAS = 100\,\frac{\sum (Q_{sim}-Q_{obs})}{\sum Q_{obs}} \qquad RSR = \frac{RMSE}{\sigma_{obs}}")
    st.markdown("""
Le PBIAS dit si GloFAS surestime (valeur positive) ou sous-estime (valeur négative) le débit en moyenne. Le RSR
rapporte l'erreur quadratique moyenne à la variabilité naturelle de la rivière : plus il est petit, mieux c'est.
Moriasi et al. (2007) jugent une simulation satisfaisante quand le NSE dépasse 0,5, que le RSR reste sous 0,7 et que
le PBIAS reste dans ±25 %.

Dans les cartes de chaleur, le bleu indique une bonne performance et le rouge une mauvaise.

### Prévision d'événements (page 5)

On fixe un seuil de débit et on compte, sur tout l'historique, quatre cas : *a*, la crue a été prévue et observée ;
*b*, elle a été prévue mais ne s'est pas produite (fausse alerte) ; *c*, elle s'est produite sans avoir été prévue
(manquée) ; *d*, rien n'a été prévu et rien ne s'est produit.
""")
    st.latex(r"POD=\frac{a}{a+c} \qquad FAR=\frac{b}{b+d} \qquad LR=\frac{POD}{FAR} \qquad ROC = POD-FAR \qquad CSI=\frac{a}{a+b+c}")
    st.markdown("""
Le POD est la part des crues effectivement annoncées et le FAR le taux de fausses alertes. Ils se lisent toujours
ensemble : une prévision qui annonce une crue tous les jours a un POD de 100 % mais ne sert à rien. Le rapport LR
(appelé RV dans le texte de l'article) mesure combien de fois le taux de bonnes détections dépasse celui des
fausses alertes ; nous avons retenu LR ≥ 6 comme seuil d'acceptabilité. Le CSI résume la qualité en un seul chiffre,
en ignorant les jours calmes.

Dans l'article, le seuil d'événement était le débit moyen observé. La page 5 permet aussi d'utiliser un quantile,
une crue de période de retour donnée ou une valeur fixe.
""")

# ---------------------------------------------------------------------------------------------
with t4:
    st.markdown("""
### Tendances (page 7)

On regarde si les maxima annuels et les débits moyens annuels augmentent ou diminuent au fil des années. Le test de
Mann-Kendall vérifie si la tendance est réelle ou due au hasard. Nous utilisons sa version modifiée par Hamed et Rao
(1998), qui tient compte du fait que les années successives ne sont pas indépendantes. La pente de Sen donne l'ampleur
de la tendance en m³/s par an. Une tendance est retenue quand la valeur *p* est inférieure à 0,05.

### Crues de référence

Pour chaque année, on garde le plus fort débit mesuré (maximum annuel). On ajuste trois lois de probabilité à cette
série : Gumbel, GEV (valeurs extrêmes généralisée) et loi normale, par la méthode du maximum de vraisemblance. Le
critère d'Akaike (AIC) indique celle qui décrit le mieux les données ; plus il est bas, meilleur est l'ajustement.
La loi choisie donne les débits de crue de période de retour 2, 5, 10, 25, 50 et 100 ans. Une crue de 10 ans a une
chance sur dix d'être atteinte ou dépassée chaque année.
""")
    st.latex(r"Q_T^{Gumbel} = \mu - \beta\,\ln\!\left[-\ln\!\left(1-\frac{1}{T}\right)\right]")
    st.markdown("""
Attention : les débits IGEBU sont mesurés deux jours par semaine, si bien que le vrai pic de crue est souvent manqué.
Les débits de crue calculés sont donc plutôt prudents (sous-estimés). L'option *Exclure les années incomplètes*
retire les années trop peu mesurées, qui faussent le maximum.

### Jours critiques

Un jour critique est un jour où le débit observé dépasse le Q90, c'est-à-dire le débit qui n'est dépassé que 10 % du
temps. Le diagramme par mois montre à quelle période de l'année ces jours se concentrent ; c'est la période où la
surveillance doit être renforcée. Le tableau en bas de page indique quelle part de ces jours GloFAS aurait annoncée,
avant et après correction.
""")

# ---------------------------------------------------------------------------------------------
with t5:
    st.markdown("""
### Ce qu'il faut garder en tête

**La maille GloFAS.** GloFAS travaille sur une grille d'environ 5,5 km. Pour une petite rivière, la maille la plus
proche de la station peut appartenir à une autre rivière. Le contrôle qualité de la page 1 le signale quand la
moyenne GloFAS est très différente de la moyenne observée. Dans ce cas, utilisez la recherche de maille de la page 2 :
elle compare les mailles voisines aux débits observés et propose la plus ressemblante. Vérifiez toujours sur la carte
que la maille proposée tombe bien sur la rivière.

**Les petites rivières torrentielles.** Sur la Mpanda ou la Ntahangwa, les crues sont provoquées par des orages de
quelques heures. Ni GloFAS ni la correction ne peuvent les annoncer plusieurs jours à l'avance. Pour ces rivières,
la prévision doit être complétée par les avertissements de pluie.

**La Rusizi à Gatumba.** Le débit de la Rusizi dépend des lâchers des barrages Rusizi I à III à la sortie du lac
Kivu, et le niveau à Gatumba subit le remous du lac Tanganyika quand celui-ci est haut. GloFAS ne représente ni l'un
ni l'autre.

**Les courbes de tarage.** Les débits observés sont calculés à partir des hauteurs d'eau grâce aux courbes de tarage
de l'IGEBU. Si une courbe est ancienne, les débits peuvent être faussés, et l'évaluation de GloFAS avec eux.

**La fiabilité affichée.** La colonne *Fiabilité* de la page 8 reprend le NSE historique de la prévision corrigée
pour chaque échéance : bonne au-dessus de 0,5, moyenne entre 0 et 0,5, faible en dessous de 0. Une prévision jugée
faible doit être lue comme une tendance, pas comme un chiffre.

### Sources des données

- Prévisions GloFAS v4 : Copernicus Emergency Management Service, via l'API Open-Meteo Flood ou le Early Warning
  Data Store (jeu `cems-glofas-forecast`).
- Débits observés : Institut Géographique du Burundi (IGEBU).
- Cours d'eau et fonds de carte : contributeurs OpenStreetMap, OpenTopoMap, Esri.

### Références

- Gupta, H. V., Kling, H., Yilmaz, K. K. et Martinez, G. F. (2009). *Journal of Hydrology*, 377, 80–91.
- Hamed, K. H. et Rao, A. R. (1998). A modified Mann-Kendall trend test for autocorrelated data. *Journal of Hydrology*, 204, 182–196.
- Knoben, W. J. M., Freer, J. E. et Woods, R. A. (2019). *Hydrology and Earth System Sciences*, 23, 4323–4331.
- Moriasi, D. N. et al. (2007). *Transactions of the ASABE*, 50(3), 885–900.
- Nash, J. E. et Sutcliffe, J. V. (1970). *Journal of Hydrology*, 10(3), 282–290.
- Harrigan, S. et al. (2020). GloFAS-ERA5 operational global river discharge reanalysis. *Earth System Science Data*, 12, 2043–2060.

La méthode et les résultats sur la Rusizi, la Kaburantwa et la Mpanda sont présentés en détail dans l'article
*Optimizing GloFAS forecasts for a flood early warning system: the case of Burundi* (Hakizimana et al.).
""")
