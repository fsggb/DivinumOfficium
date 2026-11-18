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
3. Refaire l'affichage (lisible sur téléphone, clair et sombre) et l'intégrer à ScoutHub.

Ne rien supprimer ici avant d'avoir cette génération statique : le moteur en Perl est la référence pour comparer les résultats.
