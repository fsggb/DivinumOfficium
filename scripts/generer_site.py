#!/usr/bin/env python3
"""Pré-calcule la messe (avec traduction française, autres messes du jour, communs et messes votives) et les huit heures du
bréviaire (latin, rubriques de 1960 : missel et bréviaire de 1962) jour par jour, en pages statiques lisibles surtout sur téléphone,
dans la charte de ScoutMap (marine et or). Le résultat s'installe comme application et se lit sans connexion.

Les moteurs Perl de l'amont (web/cgi-bin/horas/officium.pl et web/cgi-bin/missa/missa.pl) sont lancés tels quels ; leur HTML est
nettoyé (liste blanche de balises, aucun script, aucun formulaire), regroupé en parties (Introït, Collecte… ou Psaumes, Hymne…)
et rangé dans des cartes repliables.

Usage : python3 scripts/generer_site.py --sortie site [--avant 3] [--apres 60] [--votives 7] [--debut AAAA-MM-JJ] [--heures laudes,messe]
        [--version-messe "Rubrics 1960"] [--version-breviaire "Rubrics 1960 - 1960"]
Les autres versions des rubriques (Divino Afflatu, 1955, 1570…) sont gardées dans le dépôt (web/www/Tabulae/data.txt) mais ne sont pas publiées.
Prérequis : perl et les modules du fichier cpanfile (CGI, CGI::Session, Algorithm::Diff, Date::Calc, Date::Format, URI, URL::Encode).
"""
import argparse
import concurrent.futures
import datetime
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

RACINE = Path(__file__).resolve().parent.parent
HORAS = RACINE / "web" / "cgi-bin" / "horas"
MISSA = RACINE / "web" / "cgi-bin" / "missa"
ASSETS = Path(__file__).resolve().parent / "assets"
MODELES = Path(__file__).resolve().parent / "modeles"
DIALOGUE_MESSE = RACINE / "web" / "www" / "missa" / "missa.dialog"
VERSION_BREVIAIRE = "Rubrics 1960 - 1960"      # bréviaire romain de 1962
VERSION_MESSE = "Rubrics 1960"                  # missel romain de 1962
HEURES = [
    ("Matutinum", "Matutinum", "Matines", "matutinum"), ("Laudes", "Laudes", "Laudes", "laudes"), ("Prima", "Prima", "Prime", "prima"),
    ("Tertia", "Tertia", "Tierce", "tertia"), ("Sexta", "Sexta", "Sexte", "sexta"), ("Nona", "Nona", "None", "nona"),
    ("Vesperae", "Vesperae", "Vêpres", "vesperae"), ("Completorium", "Completorium", "Complies", "completorium"),
]
JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
MOIS_COURTS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
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
# Seuls ces textes (variables d'un jour à l'autre) ont une traduction française : ni Kyrie, ni Gloria, ni Credo, ni Préface, ni Canon.
TRADUISIBLES = {"Introitus", "Oratio", "Lectio", "Graduale", "Tractus", "Alleluia", "Sequentia", "Evangelium", "Offertorium", "Secreta",
                "Communio", "Postcommunio", "Commemoratio"}
PROPRE = {"Introitus", "Oratio", "Lectio", "Graduale", "Tractus", "Alleluia", "Sequentia", "Evangelium", "Offertorium", "Secreta",
          "Præfatio", "Prefatio", "Communio", "Postcommunio", "Commemoratio"}
# Libellés français des communs et des messes votives du moteur (code → groupe, libellé, mots pour la recherche)
VOTIVES_FR = {
    "C2": ("Communs des saints", "Un martyr pontife : Statuit", "martyr pape"), "C2-1": ("Communs des saints", "Un martyr pontife : Sacerdotes Dei", "martyr pape"),
    "C2a": ("Communs des saints", "Un martyr : In virtute", "martyr"), "C2a-1": ("Communs des saints", "Un martyr : Lætábitur", "martyr"),
    "C2b": ("Communs des saints", "Un martyr souverain pontife : Si diligis", "martyr pape"), "C2p": ("Communs des saints", "Un martyr, temps pascal : Protexísti", "martyr pascal"),
    "C3": ("Communs des saints", "Plusieurs martyrs pontifes : Intret", "martyrs"), "C3a": ("Communs des saints", "Plusieurs martyrs : Sapiéntiam", "martyrs"),
    "C3a-1": ("Communs des saints", "Plusieurs martyrs : Salus autem", "martyrs"), "C3b": ("Communs des saints", "Plusieurs martyrs souverains pontifes : Si diligis", "martyrs pape"),
    "C3p": ("Communs des saints", "Plusieurs martyrs, temps pascal : Sancti tui", "martyrs pascal"),
    "C4": ("Communs des saints", "Confesseur pontife : Statuit", "confesseur evêque pape"), "C4-1": ("Communs des saints", "Confesseur pontife : Sacerdotes", "confesseur evêque"),
    "C4a": ("Communs des saints", "Docteur pontife : In médio", "docteur eglise"), "C4b": ("Communs des saints", "Confesseur souverain pontife : Si diligis", "confesseur pape"),
    "C5": ("Communs des saints", "Confesseur non pontife : Os iusti", "confesseur"), "C5-1": ("Communs des saints", "Confesseur non pontife : Iustus", "confesseur"),
    "C5a": ("Communs des saints", "Docteur non pontife : In médio", "docteur eglise"), "C5b": ("Communs des saints", "Abbé : Os iusti", "abbe moine"),
    "C6": ("Communs des saints", "Vierge et martyre : Loquébar", "vierge martyre"), "C6-1": ("Communs des saints", "Vierge et martyre : Me exspectavérunt", "vierge martyre"),
    "C6a": ("Communs des saints", "Une vierge : Dilexísti", "vierge"), "C6a-1": ("Communs des saints", "Une vierge : Vultum tuum", "vierge"),
    "C6b": ("Communs des saints", "Plusieurs vierges et martyres", "vierges martyres"), "C7": ("Communs des saints", "Une sainte, martyre non vierge", "sainte martyre"),
    "C7a": ("Communs des saints", "Une sainte, ni vierge ni martyre : Cognóvi", "sainte veuve"), "C7b": ("Communs des saints", "Plusieurs saintes martyres", "saintes martyres"),
    "C8": ("Communs des saints", "Dédicace d’église : Terríbilis", "dedicace eglise"), "C9": ("Défunts", "Messe des défunts (quotidienne) : Requiem", "defunts morts requiem"),
    "C11": ("Sainte Vierge", "Fêtes de la Sainte Vierge : Salve sancta Parens", "marie vierge notre dame"),
    "V4": ("Messes votives", "Saint Joseph, époux de la Vierge Marie (mercredi)", "joseph"), "V6": ("Messes votives", "Passion de Notre-Seigneur (vendredi)", "passion croix"),
    "Coronatio": ("Messes votives", "Élection et couronnement du pape", "pape"), "Propaganda": ("Messes votives", "Propagation de la foi", "missions foi"),
}


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


def q(v):
    return v.replace(" ", "%20")


def moteur(jour, genre, commande="", votive="", numero=1, versions=None):
    d = "%02d-%02d-%04d" % (jour.month, jour.day, jour.year)
    if genre == "messe":
        return lancer(MISSA, "missa.pl", "date=%s&command=pray&version=%s&lang1=Latin&lang2=Francais&votive=%s&missanumber=%d&testmode=regular" % (d, q(versions[0]), votive, numero))
    return lancer(HORAS, "officium.pl", "date=%s&command=pray%s&version=%s&lang1=Latin&lang2=Latin&votive=&testmode=regular" % (d, commande, q(versions[1])))


def liste_votives():
    """[(code, libellé latin)] lue dans la configuration du moteur (rubrique [votives] de missa.dialog), sans « Hodie »."""
    try:
        s = DIALOGUE_MESSE.read_text(encoding="utf8")
        bloc = s[s.index("[votives]") + 9:s.index("[interlinearmodes]")]
    except (OSError, ValueError):
        return []
    sortie = []
    for item in [x.strip() for x in bloc.replace("\n", " ").split(",") if x.strip()]:
        if "/" in item:
            lib, code = item.rsplit("/", 1)
            sortie.append((code.strip(), lib.strip()))
    return sortie


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


def lire_cellule(c: str):
    """(intitulé de la partie ou '', html propre) d'une cellule du moteur."""
    c = re.sub(r"<DIV ALIGN='right'>.*?</DIV>", "", c, flags=re.S | re.I)           # liens « Top / Next » et numéro de rangée
    m = re.match(r"\s*<FONT SIZE='\+1' COLOR=\"red\"><B><I>(.*?)</I></B></FONT>\s*(?:<br/?>)?", c, re.S | re.I)
    return (texte(m.group(1)) if m else ""), nettoyer(c[m.end():] if m else c).strip()


def analyser(page: str, deux_langues=False):
    """(parties, titre du jour, seconde ligne, couleur liturgique, numéros de messe).
    Une partie = {titre, la, fr} ; les rangées sans titre rejoignent la partie précédente."""
    corps = page[page.upper().find("<BODY"):]
    m0 = re.search(r'<P ALIGN="?CENTER"?>\s*<FONT\s*(?:COLOR="([^"]*)")?\s*>([^<]*)</FONT>(.*?)</P>', corps, re.S | re.I)
    titre, couleur, ecriture = "", "", ""
    if m0:
        couleur, titre = (m0.group(1) or "").strip().lower(), texte(m0.group(2))
        e = re.search(r'<SPAN STYLE="color:maroon;">([^<]*)</SPAN>\s*<FONT[^>]*>([^<]*)</FONT>', m0.group(3), re.S | re.I)
        if e:
            ecriture = "%s %s" % (texte(e.group(1)), texte(e.group(2)))
    messes = [(int(n), texte(lib)) for n, lib in re.findall(r"name='missanumber' value='(\d)'>([^<]*)", corps)]
    i, j = corps.upper().find("<TABLE"), corps.upper().rfind("</TABLE>")
    if i < 0 or j < 0:
        return [], titre, ecriture, couleur, messes
    parties = []
    for rangee in re.split(r"<TR>", corps[i:j], flags=re.I)[1:]:
        cells = re.findall(r"<TD([^>]*)>(.*?)</TD>", rangee, re.S | re.I)
        if not cells or not re.search(r"ID='[A-Za-z]*\d+'", cells[0][0], re.I):
            continue                                                     # rangées de regroupement (« Ante Missam »…)
        tete, propre = lire_cellule(cells[0][1])
        fr = lire_cellule(cells[1][1])[1] if deux_langues and len(cells) > 1 else ""
        if not propre and not tete:
            continue
        mots = texte(propre).split()
        if not tete and len(mots) <= 2 and parties:                      # simple intitulé (« Communio ») : sous-titre de la partie en cours
            parties[-1]["la"].append("<h4>%s</h4>" % html.escape(" ".join(mots)))
            parties[-1]["fr"].append("<h4>%s</h4>" % html.escape(texte(fr) or " ".join(mots)) if fr else "")
            continue
        if tete and len(tete) > 2:
            parties.append({"titre": tete, "la": [propre] if propre else [], "fr": [fr]})
        else:
            if tete:                                                      # « N. » (mémento) : sous-titre
                propre = "<h4>%s</h4>%s" % (html.escape(tete), propre)
                fr = ("<h4>%s</h4>%s" % (html.escape(tete), fr)) if fr else ""
            if not parties:
                parties.append({"titre": "", "la": [], "fr": []})
            parties[-1]["la"].append(propre)
            parties[-1]["fr"].append(fr)
    sortie = []
    for p in parties:
        la = "<hr>".join(b for b in p["la"] if b)
        fr = "<hr>".join(b for b in p["fr"] if b)
        if la:
            sortie.append({"titre": p["titre"], "la": la, "fr": fr if texte(fr) else ""})
    return sortie, titre, ecriture, couleur, messes


# ---------- calendrier liturgique : classe, genre du jour, temps ----------
def paques(annee):
    a, b, c = annee % 19, annee // 100, annee % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mois = (h + l - 7 * m + 114) // 31
    return datetime.date(annee, mois, ((h + l - 7 * m + 114) % 31) + 1)


def saison(j: datetime.date) -> str:
    p = paques(j.year)
    j1 = datetime.date(j.year, 12, 25)
    avent = datetime.date(j.year, 11, 27) + datetime.timedelta(days=(6 - datetime.date(j.year, 11, 27).weekday()) % 7)   # dimanche le plus proche du 30 novembre
    if abs((avent - datetime.date(j.year, 11, 30)).days) > 3:
        avent -= datetime.timedelta(days=7) if avent > datetime.date(j.year, 11, 30) else datetime.timedelta(days=-7)
    septuag = p - datetime.timedelta(days=63)
    if j >= avent:
        return "avent" if j < j1 else "noel"
    if j <= datetime.date(j.year, 1, 5):
        return "noel"
    if j < septuag:
        return "epiphanie"
    if j < p - datetime.timedelta(days=46):
        return "septuagesime"
    if j < p:
        return "careme"
    if j < p + datetime.timedelta(days=49):
        return "pascal"
    return "pentecote"


def classe(titre):
    m = re.search(r"~\s*(I|II|III|IV)\.\s*classis", titre)
    return {"I": 1, "II": 2, "III": 3, "IV": 4}.get(m.group(1), 0) if m else 0


def genre_du_jour(titre):
    t = titre.strip().lower()
    return "dim" if t.startswith("dominica") else "feria" if t.startswith("feria") else "fete"


# ---------- pages ----------
def ico(nom):
    return {
        "reglages": '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>',
        "maison": '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 11l9-8 9 8M5 10v10h5v-6h4v6h5V10"/></svg>',
        "gauche": '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M15 5l-7 7 7 7"/></svg>',
        "droite": '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 5l7 7-7 7"/></svg>',
        "cal": '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>',
        "messe": '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v7M9 6h6"/><path d="M6 21h12M9 21c0-4 1-6 3-8 2 2 3 4 3 8"/></svg>',
        "livre": '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 6v14M12 6C9 4 6 4 3 5v14c3-1 6-1 9 1M12 6c3-2 6-2 9-1v14c-3-1-6-1-9 1"/></svg>',
        "loupe": '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg>',
        "liste": '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></svg>',
    }[nom]


def date_longue(j, court=False):
    if court:
        return "%s %d %s %d" % (JOURS_FR[j.weekday()][:3] + ".", j.day, MOIS_COURTS[j.month - 1], j.year)
    return "%s %d %s %d" % (JOURS_FR[j.weekday()], j.day, MOIS_FR[j.month - 1], j.year)


def tete_page(titre, racine, slug, genre, jour="", build=""):
    return ('<!doctype html><html lang="fr" data-racine="%s" data-page="%s" data-genre="%s" data-jour="%s" data-build="%s"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#000761">'
            '<meta name="color-scheme" content="light dark"><meta name="description" content="Messe et bréviaire en latin, jour par jour, avec traduction française de la messe.">'
            '<meta name="mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="Divinum Officium">'
            '<title>%s</title><link rel="manifest" href="%s/manifest.webmanifest"><link rel="icon" href="%s/assets/fsggb.png"><link rel="apple-touch-icon" href="%s/assets/apple-touch-icon.png">'
            '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap">'
            '<link rel="stylesheet" href="%s/assets/app.css?v=%s"></head><body>'
            % (racine, slug, genre, jour, build, html.escape(titre), racine, racine, racine, racine, build))


def barre(racine, accueil=False, titre="", sous=""):
    marque = ('<a class="brand" href="%s/index.html" title="Divinum Officium"><img src="%s/assets/fsggb.png" alt="" width="34" height="34"><b>Divinum Officium</b></a>' % (racine, racine)
              if accueil else
              '<a class="ibtn" href="%s/index.html" aria-label="Accueil" title="Accueil">%s</a><div class="brand"><div><b>%s</b>%s</div></div>'
              % (racine, ico("maison"), html.escape(titre), '<span class="sous">%s</span>' % html.escape(sous) if sous else ""))
    return ('<header class="menubar">%s<a class="ibtn" href="%s/calendrier.html" aria-label="Calendrier" title="Calendrier">%s</a>'
            '<button type="button" class="ibtn" data-ouvre="d-reglages" aria-label="Réglages" title="Réglages">%s</button></header>' % (marque, racine, ico("cal"), ico("reglages")))


def dialogue_reglages(racine):
    return ('<dialog class="feuille" id="d-reglages" aria-labelledby="t-reglages"><div class="tete"><h2 id="t-reglages">Réglages</h2><button type="button" data-fermer aria-label="Fermer">×</button></div><div class="contenu">'
            '<div><h3>Taille du texte</h3><div class="seg"><button type="button" id="t-moins" aria-label="Plus petit">A−</button><button type="button" id="t-etat" disabled>19 px</button><button type="button" id="t-plus" aria-label="Plus grand">A+</button></div></div>'
            '<div><h3>Thème</h3><div class="seg"><button type="button" data-theme-btn="auto">Auto</button><button type="button" data-theme-btn="light">Clair</button><button type="button" data-theme-btn="dark">Sombre</button></div></div>'
            '<label class="sw"><input type="checkbox" id="s-ecran"><span>Garder l’écran allumé pendant la lecture<small>Évite la mise en veille du téléphone</small></span></label>'
            '<div><h3>Hors connexion</h3><p class="etat" id="hc-etat"></p><div class="barre-prog" id="hc-barre" hidden><i></i></div><div class="grp" style="margin-top:8px">'
            '<button type="button" class="btn" id="hc-7">Télécharger aujourd’hui et la semaine</button><button type="button" class="btn" id="hc-tout">Télécharger tous les jours préparés</button><button type="button" class="btn" id="hc-eff">Effacer les pages enregistrées</button></div></div>'
            '<div><h3>Application</h3><p class="etat" id="inst-etat"></p><button type="button" class="btn p" id="b-installer" hidden style="margin-top:8px">Installer l’application</button></div>'
            '<p class="etat"><a href="%s/a-propos.html">À propos de cette version</a></p></div></dialog>' % racine)


def slug_ascii(s):
    s = s.lower().replace("æ", "ae").replace("œ", "oe")
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "partie"


COULEURS = {"green": "#2e7d32", "red": "#c0262d", "purple": "#6a3d9a", "violet": "#6a3d9a", "white": "#cfc7b0", "blue": "#1c4fa0", "black": "#222222",
            "rose": "#d2698a", "pink": "#d2698a", "gold": "#c6a24e", "grey": "#808080"}


def page_lecture(j, off, titre_jour, ecriture, parties, dispo, couleur, build, autres=None):
    """off = {slug, genre, nom, latin}. Page d'une messe ou d'une heure du bréviaire."""
    racine = "../.."
    slug, genre = off["slug"], off["genre"]
    est_messe = genre == "messe"
    for p in parties:                      # la traduction n'est gardée que pour les textes variables
        if p["titre"] not in TRADUISIBLES and not p["titre"].startswith("Commemoratio"):
            p["fr"] = ""
    ids, vus = [], {}
    for p in parties:
        base = slug_ascii(p["titre"] or "debut")
        vus[base] = vus.get(base, 0) + 1
        ids.append(base if vus[base] == 1 else "%s-%d" % (base, vus[base]))
    h = [tete_page("%s · %s" % (off["nom"], date_longue(j, True)), racine, slug, genre, j.isoformat(), build),
         barre(racine, False, off["nom"], date_longue(j, True))]
    prec, suiv = j - datetime.timedelta(days=1), j + datetime.timedelta(days=1)
    cible = slug if True else "messe"
    # ----- en-tête de page : date, jour liturgique, outils de la messe -----
    haut = ['<div class="haut"><div class="bloc"><div class="jour"><a class="pas" id="j-prec" href="../%s/%s.html" aria-label="Jour précédent">%s</a>'
            '<label class="date">%s<span>%s</span><input type="date" id="j-date" value="%s" aria-label="Choisir un jour"></label>'
            '<a class="pas" id="j-suiv" href="../%s/%s.html" aria-label="Jour suivant">%s</a></div>'
            '<a class="aujourdhui" id="j-aujourdhui" href="#" hidden>Aller à aujourd’hui</a>'
            % (prec.isoformat(), cible, ico("gauche"), ico("cal"), html.escape(date_longue(j, True)), j.isoformat(), suiv.isoformat(), cible, ico("droite"))]
    badges = []
    k = classe(titre_jour)
    if k:
        badges.append("%d%s classe" % (k, "re" if k == 1 else "e"))
    g = genre_du_jour(titre_jour)
    badges.append({"dim": "Dimanche", "feria": "Férie", "fete": "Fête"}[g])
    haut.append('<div class="titre"%s><b>%s</b>%s<div class="badges">%s</div></div>'
                % (' style="--c:%s"' % COULEURS[couleur] if couleur in COULEURS else "", html.escape(titre_jour or date_longue(j)),
                   "<small>%s</small>" % html.escape(ecriture) if ecriture else "", "".join('<span class="badge">%s</span>' % html.escape(b) for b in badges)))
    if est_messe:
        outils = ['<div class="outils">']
        autres = autres or []
        if len(autres) > 1:
            outils.append('<div class="seg" role="group" aria-label="Messes de ce jour">%s</div>' % "".join(
                '<a href="%s.html"%s>%s</a>' % (m["slug"], ' aria-current="true"' if m["slug"] == slug else "", html.escape(m["label"])) for m in autres))
        if any(s.startswith("votive-") for s in dispo) or slug.startswith("votive-"):
            outils.append('<button type="button" class="btn" data-ouvre="d-messes">%s Autres messes</button>' % ico("liste"))
        outils.append("</div>")
        haut.append("".join(outils))
    haut.append("</div></div>")
    # ----- sommaire (grand écran), barre et feuille (téléphone) -----
    boutons = "".join('<button type="button" data-p="%s" data-ord="%d">%s%s</button>' % (
        ids[n], 0 if (not est_messe or p["titre"] in PROPRE or p["titre"].startswith("Commemoratio")) else 1,
        html.escape(FR.get(p["titre"], p["titre"] or "Début")), "<small>%s</small>" % html.escape(p["titre"]) if FR.get(p["titre"]) and FR.get(p["titre"]) != p["titre"] else "")
        for n, p in enumerate(parties))
    reglages = ('<label class="sw"><input type="checkbox" data-propre><span>Propre du jour seulement<small>Cache l’ordinaire de la messe</small></span></label>' if est_messe
                else '<button type="button" class="btn sm" data-psaumes>Replier les psaumes</button>')
    reglages += '<button type="button" class="btn sm" data-tout>Tout replier</button>'
    side = ('<aside class="sommaire" aria-label="Parties de l’office"><h2>Parties</h2><nav id="sommaire-liste">%s</nav><div class="reglages">%s</div></aside>' % (boutons, reglages))
    barre_p = ('<div class="barre-parties"><div class="in"><button type="button" class="nav" id="p-prec" aria-label="Partie précédente">%s</button>'
               '<button type="button" class="cur" id="cur" data-ouvre="d-parties" aria-label="Choisir une partie"></button>'
               '<button type="button" class="nav" id="p-suiv" aria-label="Partie suivante">%s</button>%s</div></div>'
               % (ico("gauche"), ico("droite"), ""))
    # ----- parties -----
    cartes = []
    for n, p in enumerate(parties):
        nom = p["titre"] or "Début"
        fr = FR.get(p["titre"], "")
        ord_ = 0 if (not est_messe or p["titre"] in PROPRE or p["titre"].startswith("Commemoratio")) else 1
        corps = '<div class="la">%s</div>' % p["la"] + ('<div class="fr">%s</div>' % p["fr"] if p["fr"] else "")
        langue = ('<div class="lang" role="group" aria-label="Langue de cette partie"><button type="button" data-lg="la">Latin</button><button type="button" data-lg="deux">Les deux</button><button type="button" data-lg="fr">Français</button></div>' if p["fr"] else "")
        cartes.append('<details class="partie" id="%s" data-nom="%s" data-ord="%d" data-lg="la" open><summary><span class="nom">%s%s</span>%s</summary>%s<div class="texte">%s</div></details>'
                      % (ids[n], html.escape(nom), ord_, html.escape(nom), "<i>%s</i>" % html.escape(fr) if fr and fr != nom else "",
                         '<span class="tag">propre du jour</span>' if est_messe and not ord_ else "", langue, corps))
    # ----- suite : heure suivante -----
    suite = ['<nav class="suite" aria-label="Suite">']
    heures_dispo = [s for _, _, _, s in HEURES if s in dispo]
    if not est_messe and slug in heures_dispo and heures_dispo.index(slug) < len(heures_dispo) - 1:
        nx = heures_dispo[heures_dispo.index(slug) + 1]
        nom_nx = [f for _, _, f, s in HEURES if s == nx][0]
        suite.append('<a class="btn p" href="%s.html">Ensuite : %s %s</a>' % (nx, html.escape(nom_nx), ico("droite")))
    suite.append('<a class="btn" href="%s/index.html">%s Accueil</a></nav>' % (racine, ico("maison")))
    h.append('<div class="page"><div class="corps">%s%s<div class="colonne">%s<main>%s</main>%s<footer>Latin · rubriques de 1960 · <a href="%s/a-propos.html">À propos</a></footer></div></div></div>'
             % ("".join(haut), side, barre_p, "".join(cartes), "".join(suite), racine))
    # feuille des parties (téléphone) et des autres messes
    h.append('<dialog class="feuille" id="d-parties" aria-labelledby="t-parties"><div class="tete"><h2 id="t-parties">Parties</h2><button type="button" data-fermer aria-label="Fermer">×</button></div><div class="contenu">'
             '<div class="liste-parties" id="liste-feuille"></div><div class="grp">%s%s</div>%s</div></dialog>'
             % (reglages, "", ""))
    if est_messe:
        h.append('<dialog class="feuille" id="d-messes" aria-labelledby="t-messes"><div class="tete"><h2 id="t-messes">Autres messes</h2><button type="button" data-fermer aria-label="Fermer">×</button></div><div class="contenu"></div></dialog>')
    h.append(dialogue_reglages(racine))
    h.append('<script src="%s/assets/app.js?v=%s" defer></script></body></html>' % (racine, build))
    return "".join(h)


def page_accueil(build):
    r = "."
    return (tete_page("Divinum Officium", r, "accueil", "accueil", build=build) + barre(r, True) + dialogue_reglages(r) +
            '<div class="page"><div class="bloc"><div class="recherche">%s<input id="q" type="search" placeholder="Que cherchez-vous ? Vêpres demain, évangile, Toussaint…" aria-label="Rechercher une heure, une messe, une fête" autocomplete="off" enterkeyhint="search"></div>'
            '<ul class="sugg" id="sugg" hidden></ul>'
            '<div id="defaut"><p id="h-date" style="margin:14px 0 0;color:var(--muted);font-weight:650"></p>'
            '<div class="titre"><b id="h-titre">…</b><small id="h-ecr"></small><div class="badges" id="h-badges"></div></div>'
            '<a class="aujourdhui" id="h-aujourdhui" href="#" hidden>Revenir à aujourd’hui</a>'
            '<section class="rubrique"><h2>%s Messe</h2><div class="grille" id="r-messe"></div></section>'
            '<section class="rubrique"><h2>%s Office divin</h2><p class="sous">Les huit heures du bréviaire. L’heure qui convient à votre heure locale est mise en avant.</p><div class="grille" id="r-office"></div></section>'
            '<div class="carte"><h2>Un autre jour</h2><div class="contenu"><label class="date">%s<span>Choisir une date</span><input type="date" id="h-pick" aria-label="Choisir un jour"></label>'
            '<a class="btn" href="calendrier.html">%s Calendrier : fêtes, dimanches, féries</a></div></div>'
            '<div class="carte" id="c-fetes" hidden><h2>Prochaines grandes fêtes</h2><ul class="liste" id="h-fetes"></ul></div>'
            '<div class="carte" id="c-installer"><h2>Application</h2><p></p><div class="contenu"><button type="button" id="b-installer-2" class="btn p" hidden>Installer l’application</button></div></div>'
            '</div><p id="msg" class="vide" hidden></p></div>'
            '<footer>Latin · rubriques de 1960 · <a href="a-propos.html">À propos</a></footer></div>'
            '<script src="assets/app.js?v=%s" defer></script></body></html>' % (ico("loupe"), ico("messe"), ico("livre"), ico("cal"), ico("liste"), build))


def page_calendrier(build):
    r = "."
    filtres = [("tous", "Tous"), ("fetes", "Grandes fêtes"), ("dim", "Dimanches"), ("feria", "Féries"), ("avent", "Avent"), ("noel", "Temps de Noël"), ("epiphanie", "Après l’Épiphanie"),
               ("septuagesime", "Septuagésime"), ("careme", "Carême"), ("pascal", "Temps pascal"), ("pentecote", "Après la Pentecôte")]
    return (tete_page("Calendrier · Divinum Officium", r, "calendrier", "calendrier", build=build) + barre(r, False, "Calendrier", "Jours préparés") + dialogue_reglages(r) +
            '<div class="page"><div class="bloc"><div class="recherche">%s<input id="cal-q" type="search" placeholder="Chercher une fête, un jour, un mois…" aria-label="Chercher dans le calendrier" autocomplete="off"></div>'
            '<div class="filtres" id="filtres" role="group" aria-label="Filtrer">%s</div><div id="cal-liste"></div><p id="msg" class="vide" hidden></p></div>'
            '<footer><a href="index.html">Accueil</a> · <a href="a-propos.html">À propos</a></footer></div><script src="assets/app.js?v=%s" defer></script></body></html>'
            % (ico("loupe"), "".join('<button type="button" data-f="%s" aria-pressed="%s">%s</button>' % (c, "true" if c == "tous" else "false", l) for c, l in filtres), build))


def page_a_propos(amont, build):
    r = "."
    return (tete_page("À propos · Divinum Officium", r, "apropos", "apropos", build=build) + barre(r, False, "À propos") + dialogue_reglages(r) +
            '<div class="page"><div class="bloc"><div class="titre"><b>À propos de cette version</b></div><div class="carte"><p>Les textes et le calcul du calendrier viennent du projet libre <b>Divinum Officium</b> (licence MIT), '
            'dont le moteur d’origine a calculé chaque office à l’avance, jour par jour. La mise en page, la navigation, la traduction française de la messe et la lecture hors connexion sont celles de la FSGGB.</p>'
            '<p><b>Version :</b> rubriques de 1960 : bréviaire romain et missel romain de 1962, en latin. La traduction française existe pour la messe.</p>'
            '<p><b>Messes :</b> messe du jour, autres messes des jours qui en comptent plusieurs (Noël, Défunts), communs des saints et messes votives (les sept jours à venir).</p>'
            '<p><b>Source :</b> <a href="https://github.com/DivinumOfficium/divinum-officium">github.com/DivinumOfficium/divinum-officium</a>%s.</p>'
            '<p>Les pages sont régénérées chaque jour. Rien n’est envoyé ni suivi : la taille du texte, le thème et la langue restent dans votre navigateur.</p></div></div>'
            '<footer><a href="index.html">Accueil</a></footer></div><script src="assets/app.js?v=%s" defer></script></body></html>' % (" (commit " + amont + ")" if amont else "", build))


def manifeste():
    return json.dumps({
        "name": "Divinum Officium", "short_name": "Divinum", "description": "Messe et bréviaire en latin, jour par jour, avec traduction française de la messe.",
        "lang": "fr", "dir": "ltr", "start_url": "./index.html?source=application", "scope": "./", "id": "./", "display": "standalone",
        "orientation": "any", "background_color": "#000761", "theme_color": "#000761", "categories": ["books", "lifestyle"],
        "icons": [{"src": "assets/icon-192.png", "sizes": "192x192", "type": "image/png"}, {"src": "assets/icon-512.png", "sizes": "512x512", "type": "image/png"},
                  {"src": "assets/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}],
        "shortcuts": [{"name": "Messe du jour", "url": "./index.html?source=raccourci#messe"}, {"name": "Calendrier", "url": "./calendrier.html"}],
    }, ensure_ascii=False, indent=1)


# ---------- programme ----------
def produire(tache, versions):
    jour, genre, commande, votive, numero, slug = tache
    page = moteur(jour, genre, commande, votive, numero, versions)
    if not page:
        return tache, None
    parties, titre, ecriture, couleur, messes = analyser(page, genre == "messe")
    return tache, ((titre, ecriture, parties, couleur, messes) if parties else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", required=True)
    ap.add_argument("--avant", type=int, default=3)
    ap.add_argument("--apres", type=int, default=60)
    ap.add_argument("--votives", type=int, default=7, help="nombre de jours (à partir du jour central) pour les communs et messes votives")
    ap.add_argument("--debut", help="jour central AAAA-MM-JJ (aujourd'hui à Paris par défaut)")
    ap.add_argument("--heures", help="identifiants séparés par des virgules (essais) : messe, laudes, votives…")
    ap.add_argument("--version-messe", default=VERSION_MESSE)
    ap.add_argument("--version-breviaire", default=VERSION_BREVIAIRE)
    ap.add_argument("--amont", default="", help="commit de l'amont, pour la page « À propos »")
    a = ap.parse_args()
    versions = (a.version_messe, a.version_breviaire)
    sortie = Path(a.sortie)
    centre = datetime.date.fromisoformat(a.debut) if a.debut else datetime.datetime.now(ZoneInfo("Europe/Paris")).date()
    jours = [centre + datetime.timedelta(days=d) for d in range(-a.avant, a.apres + 1)]
    filtre = a.heures.split(",") if a.heures else None
    veut = lambda s: not filtre or s in filtre
    votives = [(c, l) for c, l in liste_votives()] if veut("votives") else []
    taches = []
    for j in jours:
        if veut("messe"):
            taches.append((j, "messe", "", "", 1, "messe"))
        for c, _, _, s in HEURES:
            if veut(s):
                taches.append((j, "office", c, "", 1, s))
    for j in jours:
        if centre <= j < centre + datetime.timedelta(days=a.votives):
            for code, _ in votives:
                taches.append((j, "messe", "", code, 1, "votive-" + code.lower()))
    resultats = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(2, os.cpu_count() or 2)) as ex:
        for t, r in ex.map(lambda t: produire(t, versions), taches):
            resultats[(t[0], t[5])] = r
        # jours à plusieurs messes (Noël, Défunts…) : une page par messe
        extras = []
        for j in jours:
            r = resultats.get((j, "messe"))
            if r and len(r[4]) > 1:
                for n, _ in r[4][1:]:
                    extras.append((j, "messe", "", "", n, "messe-%d" % n))
        for t, r in ex.map(lambda t: produire(t, versions), extras):
            resultats[(t[0], t[5])] = r
    build = datetime.datetime.now(ZoneInfo("Europe/Paris")).strftime("%Y%m%d") + "-" + (a.amont or "local")[:7]
    # contenu des pages de lecture et table des jours
    nom_votive = {"votive-" + c.lower(): (c, l) for c, l in votives}
    heures_slugs = [s for _, _, _, s in HEURES]
    dispo, messes_jour, titres = {}, {}, {}
    for j in jours:
        slugs = [s for (jj, s), r in resultats.items() if jj == j and r]
        ordre = ["messe"] + sorted(s for s in slugs if re.fullmatch(r"messe-\d", s)) + [s for s in slugs if s.startswith("votive-")] + [s for s in heures_slugs if s in slugs]
        dispo[j] = [s for s in ordre if s in slugs]
        ms = []
        r0 = resultats.get((j, "messe"))
        if r0 and len(r0[4]) > 1:
            ordinaux = {1: "Première messe", 2: "Deuxième messe", 3: "Troisième messe"}
            for n, lib in r0[4]:
                s = "messe" if n == 1 else "messe-%d" % n
                if (j, s) in resultats and resultats[(j, s)]:
                    t = resultats[(j, s)][0].lower()
                    engine = lib.lower().strip()
                    label = ("Messe de la nuit" if " in nocte" in t else "Messe de l’aurore" if " in aurora" in t else "Messe du jour" if re.search(r"\bin die\b", t) else
                             "Forme longue" if "longior" in engine else "Forme brève" if "brevior" in engine else ordinaux.get(n, "Messe %d" % n))
                    ms.append({"slug": s, "label": label, "t": resultats[(j, s)][0]})
        messes_jour[j] = ms
        for s in ["messe"] + heures_slugs:
            r = resultats.get((j, s))
            if r:
                titres[j] = {"t": r[0], "e": r[1], "c": r[3], "k": classe(r[0]), "y": genre_du_jour(r[0]), "s": saison(j)}
                break
    labels_messe = {}
    for j in jours:
        for m in messes_jour[j]:
            labels_messe.setdefault((j, m["slug"]), m["label"])
    for j in jours:
        for (jj, s), r in list(resultats.items()):
            if jj != j or not r:
                continue
            if s in heures_slugs:
                off = {"slug": s, "genre": "office", "nom": [f for _, _, f, x in HEURES if x == s][0], "latin": s}
                autres = None
            else:
                nom = "Messe"
                if s.startswith("votive-"):
                    nom = nom_votive[s][1] if s in nom_votive else "Messe votive"
                    c = nom_votive.get(s, ("", ""))[0]
                    nom = VOTIVES_FR.get(c, ("", nom))[1]
                elif s != "messe":
                    nom = labels_messe.get((j, s), "Messe")
                off = {"slug": s, "genre": "messe", "nom": nom, "latin": "Sancta Missa"}
                autres = messes_jour[j]
            d = sortie / "jours" / j.isoformat()
            d.mkdir(parents=True, exist_ok=True)
            (d / (s + ".html")).write_text(page_lecture(j, off, r[0], r[1], r[2], dispo[j], r[3], build, autres), encoding="utf-8")
    dates = [j.isoformat() for j in jours if dispo[j]]
    if not dates:
        print("Aucun office produit : le moteur n'a rien renvoyé.", file=sys.stderr)
        sys.exit(1)
    manquants = [(t[0].isoformat(), t[5]) for t in taches + extras if not resultats.get((t[0], t[5]))]
    sortie.mkdir(parents=True, exist_ok=True)
    (sortie / "assets").mkdir(exist_ok=True)
    for f in ASSETS.iterdir():
        shutil.copy(f, sortie / "assets" / f.name)
    (sortie / "sw.js").write_text((MODELES / "sw.js").read_text(encoding="utf8").replace("__BUILD__", build), encoding="utf-8")
    (sortie / "manifest.webmanifest").write_text(manifeste(), encoding="utf-8")
    liste_v = [{"slug": "votive-" + c.lower(), "code": c, "groupe": VOTIVES_FR.get(c, ("Messes votives", l, ""))[0], "label": VOTIVES_FR.get(c, ("", l, ""))[1], "mots": VOTIVES_FR.get(c, ("", "", ""))[2]} for c, l in votives]
    (sortie / "jours.json").write_text(json.dumps({
        "dates": dates, "heures": {j: dispo[datetime.date.fromisoformat(j)] for j in dates}, "titres": {j.isoformat(): titres[j] for j in jours if j in titres},
        "messes": {j.isoformat(): messes_jour[j] for j in jours if len(messes_jour[j]) > 1}, "votives": liste_v, "build": build,
        "version": "%s / %s" % (versions[0], versions[1])}, ensure_ascii=False), encoding="utf-8")
    (sortie / "index.html").write_text(page_accueil(build), encoding="utf-8")
    (sortie / "calendrier.html").write_text(page_calendrier(build), encoding="utf-8")
    (sortie / "a-propos.html").write_text(page_a_propos(a.amont, build), encoding="utf-8")
    total = sum(len(v) for v in dispo.values())
    print("%d pages pour %d jours (%s → %s) ; %d offices sans résultat." % (total, len(dates), dates[0], dates[-1], len(manquants)))
    if manquants:
        print("Sans résultat (extrait) :", ", ".join("%s/%s" % m for m in manquants[:12]), file=sys.stderr)


if __name__ == "__main__":
    main()
