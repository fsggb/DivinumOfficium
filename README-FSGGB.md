# DivinumOfficium (FSGGB)

Copie de travail de **Divinum Officium** pour en faire une application de ScoutHub : la messe et les huit heures du bréviaire en latin (version utilisée par la Fraternité Saint-Pie X : rubriques de 1960, missel et bréviaire de 1962), avec traduction française de la messe, lisibles surtout sur téléphone, installables et utilisables sans connexion.

## Origine
- Dépôt d'origine : https://github.com/DivinumOfficium/divinum-officium (licence MIT, voir `LICENSE`).
- Version copiée : commit `e6846e731265e5dd2e030f84d2b8b91b50600546` (18 novembre 2026), **sans aucune modification**, à l'exception du dossier `obsolete/` (anciens scripts de l'amont), non repris. Le fichier d'origine `README.md` est conservé.
- **Les autres versions des rubriques restent dans le dépôt** (Tridentine 1570/1888/1906, Divino Afflatu 1939/1954, Reduced 1955, monastiques, dominicains… : voir `web/www/Tabulae/data.txt`) mais **ne sont pas publiées**. Pour en essayer une : `python3 scripts/generer_site.py --sortie site --version-breviaire "Divino Afflatu - 1954" --version-messe "Divino Afflatu"`.

## Contenu du dépôt (utile pour la suite)
- `web/cgi-bin/horas/` : moteur Perl de l'office ; `web/cgi-bin/missa/` : moteur Perl de la messe.
- `web/www/horas/<langue>/`, `web/www/missa/<langue>/` : textes ; `web/www/Tabulae/` : tables du calendrier selon les versions.
- `scripts/` : **notre génération statique** (voir ci-dessous) ; `app.psgi`, `cpanfile`, `standalone/`, `docker/` : lancement du moteur en local ; `t/`, `regress/` : tests de l'amont.

## L'application (`scripts/generer_site.py`)
Le script lance les moteurs d'origine, sans les modifier, pour chaque jour (3 jours avant à 60 jours après aujourd'hui) :
- la **messe** avec sa **traduction française** (`lang2=Francais`, une seule passe), les **autres messes** des jours qui en comptent plusieurs (Noël : nuit, aurore, jour ; Défunts ; Quatre-Temps : forme longue ou brève) ;
- les **communs des saints, la messe des défunts, les fêtes de la Sainte Vierge et les messes votives** (liste lue dans `web/www/missa/missa.dialog`, rubrique `[votives]`), pour les 7 jours à partir d'aujourd'hui (`--votives`) ;
- les **huit heures** du bréviaire (Matines, Laudes, Prime, Tierce, Sexte, None, Vêpres, Complies).

Le HTML du moteur est nettoyé (liste blanche de balises, ni script ni formulaire), regroupé en parties (Introït, Collecte, Évangile… ; Psaumes, Hymne, Capitule…) et mis en page dans la charte de ScoutMap.

### Ce que fait l'interface
- **Accueil** : recherche en français courant (« vêpres demain », « évangile », « Toussaint », « 8 décembre »), faite sur l'appareil donc aussi hors connexion ; rubrique *Messe* et rubrique *Office divin* ; l'heure la plus proche de l'**heure locale de l'appareil** est mise en avant (« Recommandé maintenant ») ; calendrier ; prochaines grandes fêtes ; installation.
- **Pages de lecture** : pas de rangée d'onglets (le bouton *Accueil* est toujours là), date précédente/suivante en haut, parties repliables. **Ordinateur** : sommaire latéral (onglets verticaux). **Téléphone** : barre collante (partie en cours, flèches, liste complète dans une feuille). Messe : *propre du jour seulement*, langue *Latin / Les deux / Français* par partie ou globale, *Autres messes*.
- **Calendrier** : filtres comme dans un missel (grandes fêtes, dimanches, féries, temps liturgiques) et recherche.
- **Réglages** (partout) : taille du texte, thème (clair, sombre, automatique), langue de la messe, écran allumé, hors connexion, installation.
- **Application installable** (`manifest.webmanifest`, icônes) et **lecture hors connexion** (`sw.js` : le noyau de l'application est gardé à chaque version ; les pages lues ou téléchargées sont gardées d'une version à l'autre ; réseau d'abord, cache en secours).
- **Couleurs** : chaque paire texte/fond est définie par des variables vérifiées dans les deux thèmes (contraste d'au moins 4,5 : 1) ; aucune donnée n'est envoyée.

### Vérifications faites
- Les 274 tests de l'amont passent (`prove -r -I web/cgi-bin/ t`) ; 404 jours × 9 offices produits sans échec ; le texte de nos pages est celui du moteur, mot pour mot.
- Contraste de toutes les pages et états (téléphone et ordinateur, clair et sombre) par un audit automatique ; lecture hors connexion testée navigateur coupé.

## Utilisation
- Essai local : `python3 scripts/generer_site.py --sortie site --avant 1 --apres 2` (perl et les modules de `cpanfile` installés). 60 jours et les messes votives se calculent en une demi-minute (environ 40 Mo).
- ScoutHub la lance à chaque déploiement (type `perl` de son `apps.txt`) et la relance chaque jour, puis publie le résultat sous `/DivinumOfficium/`. Le workflow `.github/workflows/site.yml` vérifie que la génération fonctionne (artefact de 3 jours).
- Pas encore fait : autres langues (hors traduction française de la messe), traduction du bréviaire, chants grégoriens notés, messes votives au-delà de 7 jours.
