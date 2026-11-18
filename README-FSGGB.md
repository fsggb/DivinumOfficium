# DivinumOfficium (FSGGB)

Copie de travail de **Divinum Officium** pour en faire une application de ScoutHub (office divin en latin, version utilisée par la Fraternité Saint-Pie X, rendu simplifié et lisible), servie en statique.

## Origine
- Dépôt d'origine : https://github.com/DivinumOfficium/divinum-officium (licence MIT, voir `LICENSE`).
- Version copiée : commit `e6846e731265e5dd2e030f84d2b8b91b50600546` (18 novembre 2026).
- Copiée telle quelle, **sans aucune modification**, à l'exception du dossier `obsolete/` (anciens scripts de l'amont, sans lien avec le fonctionnement), non repris. Le fichier d'origine `README.md` est conservé.

## Contenu (utile pour la suite)
- `web/cgi-bin/` : le moteur en Perl qui compose les offices (calendrier, rubriques, assemblage des textes).
- `web/www/horas/<langue>/` : les textes du bréviaire (office des heures) par langue ; `Latin` est le texte latin, `Latin-gabc` les chants en notation grégorienne ; `Help` : documentation des rubriques (PDF).
- `web/www/missa/<langue>/` : les textes de la messe.
- `web/www/Tabulae/` : tables du calendrier selon les versions des rubriques.
- `web/www/js`, `web/www/style` : scripts et feuilles de style des pages.
- `app.psgi`, `cpanfile`, `standalone/`, `docker/` : lancement du moteur en local ; `t/`, `regress/` : tests de l'amont.

## Ce qui est prévu (pas encore fait)
1. Ne garder que les offices en latin et la version des rubriques utilisée par la FSSPX.
2. Faire produire les offices à l'avance (génération statique du calendrier, jour par jour) pour un service sans serveur Perl.
3. Affiner l’affichage et l’intégrer à ScoutHub (fait pour une première version : voir ci-dessous).

Ne rien supprimer ici avant d'avoir cette génération statique : le moteur en Perl est la référence pour comparer les résultats.

## Génération statique (faite)
`scripts/generer_site.py` lance les moteurs d'origine, **sans les modifier**, pour chaque jour (3 jours avant à 60 jours après aujourd'hui) : la **messe** (`web/cgi-bin/missa/missa.pl`, missel de 1962) et les **huit heures** du bréviaire (`web/cgi-bin/horas/officium.pl` : Matines, Laudes, Prime, Tierce, Sexte, None, Vêpres, Complies), en latin, rubriques de 1960 (« Rubrics 1960 », bréviaire et missel de 1962 : version retenue pour la FSSPX, à confirmer).

Le HTML du moteur est nettoyé (liste blanche de balises, ni script ni formulaire), regroupé en parties (Introït, Collecte, Évangile… ; Psaumes, Hymne, Capitule…) et mis en page dans la charte de ScoutMap, d'abord pour le téléphone : choix messe ou bréviaire, heures, jour précédent et suivant, date au choix, barre pour aller à une partie, parties repliables, « propre du jour seulement » pour la messe, taille du texte, thème clair, sombre ou automatique, couleur liturgique du jour. Aucun suivi : les réglages restent dans le navigateur.

- Sortie : `index.html`, `calendrier.html`, `a-propos.html`, `jours.json`, `assets/` (CSS, JS, logo), `jours/AAAA-MM-JJ/<messe|matutinum|laudes|…>.html`.
- Essai local : `python3 scripts/generer_site.py --sortie site --avant 1 --apres 2` (perl et les modules de `cpanfile` installés) ; 60 jours se calculent en une demi-minute, une année en moins de trois minutes.
- Vérification du moteur : les 274 tests de l'amont passent (`prove -r -I web/cgi-bin/ t`) ; sur 404 jours, les 9 offices sont produits sans échec ; le texte de nos pages est celui du moteur, mot pour mot.
- ScoutHub la lance à chaque déploiement (type `perl` de son `apps.txt`) et la relance chaque jour, puis publie le résultat sous `/DivinumOfficium/`. Le workflow `.github/workflows/site.yml` vérifie que la génération fonctionne (artefact de 3 jours).
- Pas encore fait : les autres langues, les messes votives et les jours à plusieurs messes, les chants en notation grégorienne, la recherche, la lecture hors ligne.
