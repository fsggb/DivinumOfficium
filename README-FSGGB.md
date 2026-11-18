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

## Génération statique (première version, faite)
`scripts/generer_site.py` lance le moteur d'origine, **sans le modifier**, pour chaque jour (3 jours avant à 60 jours après aujourd'hui) et chaque heure (Matines, Laudes, Prime, Tierce, Sexte, None, Vêpres, Complies), en latin, rubriques de 1960 (« Rubrics 1960 - 1960 », bréviaire de 1962 : version retenue pour la FSSPX, à confirmer). Le HTML du moteur est nettoyé (liste blanche de balises, ni script ni formulaire) et mis en page (téléphone, clair et sombre). Sortie : `index.html`, `jours/AAAA-MM-JJ/<heure>.html`, `jours.json`, `a-propos.html` (environ une minute de calcul).
- Essai local : `python3 scripts/generer_site.py --sortie site --avant 1 --apres 2` (perl et les modules de `cpanfile` installés).
- ScoutHub la lance à chaque déploiement (type `perl` de son `apps.txt`) et la relance chaque jour, puis publie le résultat sous `/DivinumOfficium/`. Le workflow `.github/workflows/site.yml` vérifie que la génération fonctionne (artefact de 3 jours).
- Pas encore fait : la messe, les autres langues, le calendrier complet (ordo), les chants en notation grégorienne, la recherche, la lecture hors ligne.
