#!/usr/bin/env python3
"""Pré-calcule la messe et les huit heures du bréviaire (latin, rubriques de 1960 : missel et bréviaire de 1962) jour par jour,
en pages statiques lisibles surtout sur téléphone, dans la charte de ScoutMap (marine et or).

Les moteurs Perl de l'amont (web/cgi-bin/horas/officium.pl et web/cgi-bin/missa/missa.pl) sont lancés tels quels, une fois par
jour et par office ; leur HTML est nettoyé (liste blanche de balises, aucun script, aucun formulaire), regroupé en parties
(Introït, Collecte… ou Psaumes, Hymne…) et rangé dans des cartes repliables. Aucun serveur n'est nécessaire ensuite.

Usage : python3 scripts/generer_site.py --sortie site [--avant 3] [--apres 60] [--debut AAAA-MM-JJ] [--heures laudes,messe]
Prérequis : perl et les modules du fichier cpanfile (CGI, CGI::Session, Algorithm::Diff, Date::Calc, Date::Format, URI, URL::Encode).
Sortie : index.html, calendrier.html, a-propos.html, jours.json, assets/, jours/AAAA-MM-JJ/<office>.html
"""
import argparse
import concurrent.futures
import datetime
import html
import json
import os
import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

RACINE = Path(__file__).resolve().parent.parent
HORAS = RACINE / "web" / "cgi-bin" / "horas"
MISSA = RACINE / "web" / "cgi-bin" / "missa"
ASSETS = Path(__file__).resolve().parent / "assets"
VERSION_BREVIAIRE = "Rubrics 1960 - 1960"      # bréviaire romain de 1962
VERSION_MESSE = "Rubrics 1960"                  # missel romain de 1962
# (commande du moteur, nom latin, nom français, identifiant de page)
HEURES = [
    ("Matutinum", "Matutinum", "Matines", "matutinum"),
    ("Laudes", "Laudes", "Laudes", "laudes"),
    ("Prima", "Prima", "Prime", "prima"),
    ("Tertia", "Tertia", "Tierce", "tertia"),
    ("Sexta", "Sexta", "Sexte", "sexta"),
    ("Nona", "Nona", "None", "nona"),
    ("Vesperae", "Vesperae", "Vêpres", "vesperae"),
    ("Completorium", "Completorium", "Complies", "completorium"),
]
MESSE = ("Missa", "Sancta Missa", "Messe", "messe")
JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS_COURTS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
# Aide en français pour les titres latins des parties
FR = {
    "Incipit": "Ouverture", "Introitus": "Introït", "Kyrie": "Kyrie", "Gloria": "Gloria", "Oratio": "Collecte", "Lectio": "Épître",
    "Graduale": "Graduel", "Tractus": "Trait", "Alleluia": "Alléluia", "Sequentia": "Séquence", "Evangelium": "Évangile", "Credo": "Credo",
    "Offertorium": "Offertoire", "Secreta": "Secrète", "Præfatio": "Préface", "Prefatio": "Préface", "Canon": "Canon",
    "Preparatio Communionis": "Préparation à la communion", "Communio": "Communion", "Postcommunio": "Postcommunion",
    "Conclusio": "Conclusion", "Orationes Leonis XIII": "Prières après la messe", "Psalmi": "Psaumes", "Hymnus": "Hymne",
    "Capitulum": "Capitule", "Lectio brevis": "Lecture brève", "Invitatorium": "Invitatoire", "Responsorium": "Répons",
    "Canticum: Nunc dimittis": "Cantique de Syméon", "Canticum: Benedictus": "Cantique de Zacharie", "Canticum: Magnificat": "Cantique de Marie",
    "Antiphona finalis B.M.V.": "Antienne mariale", "Preces": "Prières", "Commemoratio": "Mémoire", "Martyrologium": "Martyrologe",
    "Capitulum Responsorium Versus": "Capitule, répons, verset", "Oratio Dominica": "Notre Père", "Te Deum": "Te Deum",
}
PROPRE = {"Introitus", "Oratio", "Lectio", "Graduale", "Tractus", "Alleluia", "Sequentia", "Evangelium", "Offertorium", "Secreta",
          "Præfatio", "Prefatio", "Communio", "Postcommunio", "Commemoratio"}


# ---------- moteurs ----------
def lancer(dossier: Path, script: str, requete: str) -> str:
    env = dict(os.environ, REQUEST_METHOD="GET", QUERY_STRING=requete)
    try:
        p = subprocess.run(["perl", script], cwd=dossier, env=env, capture_output=True, timeout=180)
    except (subprocess.TimeoutExpired, OSError):
        return ""
    sortie = p.stdout.decode("utf-8", "replace")
    i = sortie.find("<!DOCTYPE")
    return sortie[i:] if p.returncode == 0 and i >= 0 else ""


def moteur(jour: datetime.date, office) -> str:
    d = "%02d-%02d-%04d" % (jour.month, jour.day, jour.year)
    if office[3] == "messe":
        return lancer(MISSA, "missa.pl", "date=%s&command=pray&version=%s&lang1=Latin&lang2=Latin&votive=&testmode=regular" % (d, VERSION_MESSE.replace(" ", "%20")))
    return lancer(HORAS, "officium.pl", "date=%s&command=pray%s&version=%s&lang1=Latin&lang2=Latin&votive=&testmode=regular" % (d, office[0], VERSION_BREVIAIRE.replace(" ", "%20")))


# ---------- nettoyage du HTML de l'amont ----------
class Nettoyeur(HTMLParser):
    """Ne garde qu'une liste blanche de balises, sans attribut sauf des classes que nous choisissons."""
    SIMPLES = {"b", "i", "em", "strong", "u", "br", "p", "small", "sup", "sub"}
    IGNORES = {"script", "style", "form", "select", "option", "textarea", "button", "head"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sortie, self.pile, self.ignore = [], [], 0

    @staticmethod
    def _attr(attrs, nom):
        for k, v in attrs:
            if k.lower() == nom:
                return (v or "").strip().lower()
        return ""

    def _classe(self, tag, attrs):
        if tag == "font":
            couleur, taille = self._attr(attrs, "color"), self._attr(attrs, "size")
            if couleur == "red" and taille == "+2":
                return "cap"
            if couleur == "red" and taille == "1":
                return "ver"
            if couleur == "red":
                return "r"
            if couleur in ("green", "maroon") or taille == "-1":
                return "g"
            return ""
        if "color:red" in self._attr(attrs, "style").replace(" ", ""):
            return "r"
        return ""

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.IGNORES:
            self.ignore += 1
            return
        if self.ignore:
            return
        if tag in ("font", "span"):
            c = self._classe(tag, attrs)
            self.sortie.append('<span class="%s">' % c if c else "<span>")
            self.pile.append("span")
        elif tag in self.SIMPLES:
            self.sortie.append("<%s>" % tag)
            if tag != "br":
                self.pile.append(tag)
        # tout le reste (a, img, input, table, tr, div…) est supprimé, son texte est gardé

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.IGNORES:
            self.ignore = max(0, self.ignore - 1)
            return
        if self.ignore:
            return
        nom = "span" if tag in ("font", "span") else tag
        if (nom in self.SIMPLES or nom == "span") and nom != "br" and nom in self.pile:
            while self.pile:
                t = self.pile.pop()
                self.sortie.append("</%s>" % t)
                if t == nom:
                    break

    def handle_data(self, data):
        if not self.ignore:
            self.sortie.append(html.escape(data, quote=False))

    def resultat(self):
        while self.pile:
            self.sortie.append("</%s>" % self.pile.pop())
        return "".join(self.sortie)


def nettoyer(fragment: str) -> str:
    n = Nettoyeur()
    n.feed(fragment)
    n.close()
    return n.resultat()


def texte(s: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))).strip()


def analyser(page: str):
    """(parties, titre du jour, seconde ligne, couleur liturgique). Une partie = {titre, html} ; les rangées sans titre rejoignent la partie précédente."""
    corps = page[page.upper().find("<BODY"):]
    # En-tête du moteur : <P ALIGN=CENTER><FONT COLOR="couleur liturgique">Jour</FONT><br/><I>… Étiquette : <FONT>Autre jour</FONT></I></P>
    m0 = re.search(r'<P ALIGN="?CENTER"?>\s*<FONT\s*(?:COLOR="([^"]*)")?\s*>([^<]*)</FONT>(.*?)</P>', corps, re.S | re.I)
    titre, couleur, ecriture = "", "", ""
    if m0:
        couleur, titre = (m0.group(1) or "").strip().lower(), texte(m0.group(2))
        e = re.search(r'<SPAN STYLE="color:maroon;">([^<]*)</SPAN>\s*<FONT[^>]*>([^<]*)</FONT>', m0.group(3), re.S | re.I)
        if e:
            ecriture = "%s %s" % (texte(e.group(1)), texte(e.group(2)))
    i, j = corps.upper().find("<TABLE"), corps.upper().rfind("</TABLE>")
    if i < 0 or j < 0:
        return [], titre, ecriture, couleur
    parties = []
    for rangee in re.split(r"<TR>", corps[i:j], flags=re.I)[1:]:
        cellule = re.search(r"<TD([^>]*)>(.*?)</TD>", rangee, re.S | re.I)
        if not cellule or not re.search(r"ID='[A-Za-z]*\d+'", cellule.group(1), re.I):
            continue                                                     # rangées de regroupement (« Ante Missam »…)
        c = re.sub(r"<DIV ALIGN='right'>.*?</DIV>", "", cellule.group(2), flags=re.S | re.I)      # liens « Top / Next » du moteur
        m = re.match(r"\s*<FONT SIZE='\+1' COLOR=\"red\"><B><I>(.*?)</I></B></FONT>\s*(?:<br/?>)?", c, re.S | re.I)
        tete = texte(m.group(1)) if m else ""
        reste = c[m.end():] if m else c
        propre = nettoyer(reste).strip()
        if not propre and not tete:
            continue
        mots = texte(propre).split()
        if not m and len(mots) <= 2 and parties:                         # simple intitulé (« Communio ») : sous-titre de la partie en cours
            parties[-1]["blocs"].append("<h4>%s</h4>" % html.escape(" ".join(mots)))
            continue
        if tete and len(tete) > 2:
            parties.append({"titre": tete, "blocs": [propre] if propre else []})
        else:
            if tete:                                                      # « N. » (mémento) : sous-titre
                propre = "<h4>%s</h4>%s" % (html.escape(tete), propre)
            if not parties:
                parties.append({"titre": "", "blocs": []})
            parties[-1]["blocs"].append(propre)
    for p in parties:
        p["html"] = "<hr>".join(b for b in p["blocs"] if b)
    return [p for p in parties if p["html"]], titre, ecriture, couleur


# ---------- pages ----------
SVG = {
    "reglages": '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><text x="2" y="18" font-size="16" font-weight="700" fill="currentColor" stroke="none" font-family="Georgia,serif">A</text><text x="13" y="18" font-size="12" font-weight="700" fill="currentColor" stroke="none" font-family="Georgia,serif">a</text></svg>',
    "gauche": '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M15 5l-7 7 7 7"/></svg>',
    "droite": '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 5l7 7-7 7"/></svg>',
    "cal": '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>',
    "messe": '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v7M9 6h6"/><path d="M6 21h12M9 21c0-4 1-6 3-8 2 2 3 4 3 8"/></svg>',
    "livre": '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 6v14M12 6C9 4 6 4 3 5v14c3-1 6-1 9 1M12 6c3-2 6-2 9-1v14c-3-1-6-1-9 1"/></svg>',
    "haut": '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5M6 11l6-6 6 6"/></svg>',
}


def date_longue(j, court=False):
    if court:
        return "%s %d %s %d" % (JOURS_FR[j.weekday()][:3] + ".", j.day, MOIS_COURTS[j.month - 1], j.year)
    return "%s %d %s %d" % (JOURS_FR[j.weekday()], j.day, MOIS_FR[j.month - 1], j.year)


def tete_page(titre, racine, slug, jour="", description="Bréviaire et messe en latin, jour par jour."):
    return ('<!doctype html><html lang="fr" data-racine="%s" data-page="%s" data-jour="%s"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#000761">'
            '<meta name="color-scheme" content="light dark"><meta name="description" content="%s"><title>%s</title>'
            '<link rel="icon" href="%s/assets/fsggb.png"><link rel="apple-touch-icon" href="%s/assets/fsggb.png">'
            '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap">'
            '<link rel="stylesheet" href="%s/assets/app.css"></head><body>' % (racine, slug, jour, html.escape(description), html.escape(titre), racine, racine, racine))


def barre(racine):
    return ('<header class="menubar"><a class="brand" href="%s/index.html" title="Divinum Officium"><img src="%s/assets/fsggb.png" alt="FSGGB" width="32" height="32"><b>Divinum Officium</b></a>'
            '<a class="ibtn" href="%s/calendrier.html" aria-label="Calendrier">%s</a>'
            '<button type="button" class="ibtn" id="b-reglages" aria-label="Taille du texte et thème" aria-expanded="false" aria-controls="pop">%s</button></header>'
            '<div class="pop" id="pop" role="dialog" aria-label="Affichage" hidden>'
            '<div><h2>Taille du texte</h2><div class="seg"><button type="button" id="t-moins" aria-label="Plus petit">A−</button><button type="button" id="t-etat" disabled style="font-weight:500">19 px</button><button type="button" id="t-plus" aria-label="Plus grand">A+</button></div></div>'
            '<div><h2>Thème</h2><div class="seg"><button type="button" data-theme-btn="auto">Auto</button><button type="button" data-theme-btn="light">Clair</button><button type="button" data-theme-btn="dark">Sombre</button></div></div></div>'
            % (racine, racine, racine, SVG["cal"], SVG["reglages"]))


COULEURS = {"green": "#2e7d32", "red": "#c0262d", "purple": "#6a3d9a", "violet": "#6a3d9a", "white": "#cfc7b0", "blue": "#1c4fa0", "black": "#222222", "rose": "#d2698a", "pink": "#d2698a", "gold": "#c6a24e"}


def page_office(j, office, titre_jour, ecriture, parties, dispo, couleur=""):
    cmd, latin, francais, slug = office
    est_messe = slug == "messe"
    racine = "../.."
    h = [tete_page("%s · %s" % (francais, date_longue(j)), racine, slug, j.isoformat()), barre(racine)]
    prec, suiv = j - datetime.timedelta(days=1), j + datetime.timedelta(days=1)
    h.append('<div class="bloc"><div class="jour"><a class="pas" id="j-prec" href="../%s/%s.html" aria-label="Jour précédent">%s</a>'
             '<label class="date">%s<span>%s</span><input type="date" id="j-date" value="%s" aria-label="Choisir un jour"></label>'
             '<a class="pas" id="j-suiv" href="../%s/%s.html" aria-label="Jour suivant">%s</a></div>'
             '<a class="aujourdhui" id="j-aujourdhui" href="#" hidden>Aller à aujourd’hui</a>'
             % (prec.isoformat(), slug, SVG["gauche"], SVG["cal"], html.escape(date_longue(j, True)), j.isoformat(), suiv.isoformat(), slug, SVG["droite"]))
    h.append('<div class="titre"%s><b>%s</b>%s</div>' % (' style="--c:%s"' % COULEURS[couleur] if couleur in COULEURS else "", html.escape(titre_jour or date_longue(j)), "<small>%s</small>" % html.escape(ecriture) if ecriture else ""))
    h.append('<nav class="mode" aria-label="Messe ou bréviaire"><a href="messe.html"%s>%s Messe</a><a id="m-breviaire" href="%s.html"%s>%s Bréviaire</a></nav>'
             % (' aria-current="page"' if est_messe else "", SVG["messe"], "laudes" if est_messe else slug, "" if est_messe else ' aria-current="page"', SVG["livre"]))
    if not est_messe:
        h.append('<nav class="heures" aria-label="Heures du bréviaire">')
        for c, l, f, s in HEURES:
            if s in dispo:
                h.append('<a href="%s.html" data-h="%s"%s>%s</a>' % (s, s, ' aria-current="page"' if s == slug else "", html.escape(f)))
        h.append("</nav>")
    h.append("</div>")
    # barre des parties
    chips, cartes = [], []
    for n, p in enumerate(parties, 1):
        nom = p["titre"] or "Début"
        fr = FR.get(nom, "")
        ord_ = 1 if est_messe and nom not in PROPRE and not nom.startswith("Commemoratio") else 0
        court = fr or nom
        chips.append('<button type="button" data-p="p%d" data-ord="%d">%s</button>' % (n, ord_, html.escape(court)))
        cartes.append('<details class="partie" id="p%d" data-nom="%s" data-ord="%d"%s open><summary><span class="nom">%s%s</span>%s</summary><div class="texte"><p>%s</p></div></details>'
                      % (n, html.escape(nom), ord_, "", html.escape(nom), "<i>%s</i>" % html.escape(fr) if fr and fr != nom else "",
                         '<span class="tag">propre du jour</span>' if est_messe and not ord_ else "", p["html"]))
    h.append('<div class="parties"><div class="in"><nav class="chips" id="chips" aria-label="Aller à une partie">%s</nav><button type="button" class="options" id="b-options" aria-expanded="false" aria-controls="menu-parties">Parties</button></div>'
             '<div class="menu-parties" id="menu-parties" hidden><button type="button" class="sw" id="b-tout" style="justify-content:center">Tout replier</button>%s</div></div>'
             % ("".join(chips),
                '<label class="sw"><input type="checkbox" id="o-propre"><span>Propre du jour seulement<small>Cache l’ordinaire de la messe (prières au bas de l’autel, Credo, Canon…)</small></span></label>' if est_messe
                else '<button type="button" class="sw" id="b-psaumes" style="justify-content:center">Replier les psaumes</button>'))
    h.append("<main>%s</main>" % "".join(cartes))
    h.append('<footer>Latin · rubriques de 1960 · <a href="%s/a-propos.html">À propos</a></footer>' % racine)
    h.append('<div class="bas"><a href="../%s/%s.html" id="b-prec" aria-label="Jour précédent">%s Veille</a><button type="button" id="b-haut" aria-label="Haut de la page">%s</button>'
             '<a href="../%s/%s.html" id="b-suiv" aria-label="Jour suivant">Lendemain %s</a></div>'
             % (prec.isoformat(), slug, SVG["gauche"], SVG["haut"], suiv.isoformat(), slug, SVG["droite"]))
    h.append('<script src="%s/assets/app.js" defer></script></body></html>' % racine)
    return "".join(h)


def page_accueil():
    r = "."
    return (tete_page("Divinum Officium", r, "accueil") + barre(r) +
            '<div class="bloc"><p class="sous" id="h-date" style="margin:0;color:var(--muted);font-weight:600"></p>'
            '<div class="titre"><b id="h-titre">…</b><small id="h-ecr"></small></div>'
            '<div class="grand"><a class="f" id="h-messe" href="#"><b>Messe du jour</b><span>Propre et ordinaire, latin (missel de 1962)</span></a>'
            '<a id="h-breviaire" href="#"><b>Bréviaire</b><span id="h-heure">Les huit heures</span></a></div>'
            '<div class="carte"><h2>Toutes les heures</h2><nav class="heures" id="h-heures" style="padding:6px 10px 12px;flex-wrap:wrap;overflow:visible"></nav></div>'
            '<div class="carte"><h2>Un autre jour</h2><p><label class="date" style="max-width:260px">%s<span>Choisir une date</span><input type="date" id="h-pick" aria-label="Choisir un jour"></label></p></div>'
            '<div class="carte"><h2>Calendrier</h2><p><a href="calendrier.html" style="font-weight:650">Voir les jours préparés, avec la fête du jour</a></p></div>'
            '<p id="msg" class="vide" style="display:none"></p></div>'
            '<footer>Latin · rubriques de 1960 · <a href="a-propos.html">À propos</a></footer>'
            '<script src="assets/app.js" defer></script></body></html>' % SVG["cal"])


def page_calendrier(dates, titres, heures):
    h = [tete_page("Calendrier · Divinum Officium", ".", "calendrier"), barre("."), '<div class="bloc"><div class="titre"><b>Calendrier</b><small>Les jours préparés, avec le jour liturgique</small></div>']
    mois = None
    for d in dates:
        j = datetime.date.fromisoformat(d)
        if (j.year, j.month) != mois:
            if mois:
                h.append("</div>")
            mois = (j.year, j.month)
            h.append('<div class="carte"><h2>%s %d</h2><div class="liste">' % (MOIS_FR[j.month - 1].capitalize(), j.year))
        t = titres.get(d, {}).get("t", "")
        h.append('<a href="jours/%s/%s.html"><span class="d">%s %d</span><span class="t">%s</span></a>' % (d, "messe" if "messe" in heures[d] else heures[d][0], JOURS_FR[j.weekday()][:3] + ".", j.day, html.escape(t)))
    h.append("</div></div></div>")
    h.append('<footer><a href="index.html">Accueil</a> · <a href="a-propos.html">À propos</a></footer><script src="assets/app.js" defer></script></body></html>')
    return "".join(h)


def page_a_propos(version_amont):
    return (tete_page("À propos · Divinum Officium", ".", "apropos") + barre(".") +
            '<div class="bloc"><div class="titre"><b>À propos de cette version</b></div><div class="carte"><p>Les textes et le calcul du calendrier viennent du projet libre <b>Divinum Officium</b> (licence MIT), '
            'dont le moteur d’origine a calculé chaque office à l’avance, jour par jour. La mise en page, l’organisation en parties repliables et la navigation sont celles de la FSGGB.</p>'
            '<p><b>Version :</b> rubriques de 1960 : bréviaire romain et missel romain de 1962, en latin seulement.</p>'
            '<p><b>Source :</b> <a href="https://github.com/DivinumOfficium/divinum-officium">github.com/DivinumOfficium/divinum-officium</a>%s.</p>'
            '<p>Les pages sont régénérées chaque jour : les jours proches (quelques jours avant et deux mois après aujourd’hui) sont disponibles. '
            'Rien n’est envoyé ni suivi : la taille du texte et le thème restent dans votre navigateur.</p></div></div>'
            '<footer><a href="index.html">Accueil</a></footer><script src="assets/app.js" defer></script></body></html>' % (" (commit " + version_amont + ")" if version_amont else ""))


# ---------- programme ----------
def produire(jour, office):
    page = moteur(jour, office)
    if not page:
        return jour, office, None
    parties, titre, ecriture, couleur = analyser(page)
    return (jour, office, (titre, ecriture, parties, couleur)) if parties else (jour, office, None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", required=True)
    ap.add_argument("--avant", type=int, default=3)
    ap.add_argument("--apres", type=int, default=60)
    ap.add_argument("--debut", help="jour central AAAA-MM-JJ (aujourd'hui à Paris par défaut)")
    ap.add_argument("--heures", help="identifiants séparés par des virgules (essais) : messe, laudes…")
    ap.add_argument("--amont", default="", help="commit de l'amont, pour la page « À propos »")
    a = ap.parse_args()
    sortie = Path(a.sortie)
    centre = datetime.date.fromisoformat(a.debut) if a.debut else datetime.datetime.now(ZoneInfo("Europe/Paris")).date()
    jours = [centre + datetime.timedelta(days=d) for d in range(-a.avant, a.apres + 1)]
    offices = [o for o in [MESSE] + HEURES if not a.heures or o[3] in a.heures.split(",")]
    taches = [(j, o) for j in jours for o in offices]
    resultats = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(2, os.cpu_count() or 2)) as ex:
        for j, o, r in ex.map(lambda t: produire(*t), taches):
            resultats[(j, o[3])] = r
    ordre = ["messe"] + [h[3] for h in HEURES]
    dispo = {j: [s for s in ordre if resultats.get((j, s))] for j in jours}
    manquants = [(j.isoformat(), o[3]) for j in jours for o in offices if not resultats.get((j, o[3]))]
    for j in jours:
        for o in offices:
            r = resultats.get((j, o[3]))
            if r:
                d = sortie / "jours" / j.isoformat()
                d.mkdir(parents=True, exist_ok=True)
                (d / (o[3] + ".html")).write_text(page_office(j, o, r[0], r[1], r[2], dispo[j], r[3]), encoding="utf-8")
    dates = [j.isoformat() for j in jours if dispo[j]]
    if not dates:
        print("Aucun office produit : le moteur n'a rien renvoyé.", file=sys.stderr)
        sys.exit(1)
    titres = {}
    for j in jours:
        for s in ordre:
            r = resultats.get((j, s))
            if r:
                titres[j.isoformat()] = {"t": r[0], "e": r[1], "c": r[3]}
                break
    heures = {j: dispo[datetime.date.fromisoformat(j)] for j in dates}
    sortie.mkdir(parents=True, exist_ok=True)
    (sortie / "assets").mkdir(exist_ok=True)
    for f in ASSETS.iterdir():
        shutil.copy(f, sortie / "assets" / f.name)
    (sortie / "jours.json").write_text(json.dumps({"dates": dates, "heures": heures, "titres": titres, "version": "%s / %s" % (VERSION_MESSE, VERSION_BREVIAIRE)}, ensure_ascii=False), encoding="utf-8")
    (sortie / "index.html").write_text(page_accueil(), encoding="utf-8")
    (sortie / "calendrier.html").write_text(page_calendrier(dates, titres, heures), encoding="utf-8")
    (sortie / "a-propos.html").write_text(page_a_propos(a.amont), encoding="utf-8")
    print("%d pages pour %d jours (%s → %s) ; %d offices sans résultat." % (sum(len(v) for v in dispo.values()), len(dates), dates[0], dates[-1], len(manquants)))
    if manquants:
        print("Sans résultat (extrait) :", ", ".join("%s/%s" % m for m in manquants[:12]), file=sys.stderr)


if __name__ == "__main__":
    main()
