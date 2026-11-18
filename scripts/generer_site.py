#!/usr/bin/env python3
"""Pré-calcule les offices de Divinum Officium (latin, rubriques de 1960 = bréviaire de 1962) jour par jour, en pages statiques.

Le moteur Perl de l'amont (web/cgi-bin/horas/officium.pl) est lancé tel quel, une fois par jour et par heure ; son HTML est nettoyé
(liste blanche de balises, aucun script, aucun formulaire) puis rangé dans une page lisible. Aucun serveur n'est nécessaire ensuite.

Usage : python3 scripts/generer_site.py --sortie site [--avant 3] [--apres 60] [--debut AAAA-MM-JJ] [--heures laudes,vesperae]
Prérequis : perl et les modules du fichier cpanfile (CGI, CGI::Session, Algorithm::Diff, Date::Calc, Date::Format, URI, URL::Encode).
Sortie : index.html, a-propos.html, jours.json, jours/AAAA-MM-JJ/<heure>.html
"""
import argparse
import concurrent.futures
import datetime
import html
import json
import os
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

RACINE = Path(__file__).resolve().parent.parent
MOTEUR = RACINE / "web" / "cgi-bin" / "horas"
VERSION = "Rubrics 1960 - 1960"          # bréviaire romain de 1962
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
JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


# ---------- moteur ----------
def lancer_moteur(jour: datetime.date, commande: str) -> str:
    """Sortie HTML du moteur pour un jour et une heure ; chaîne vide en cas d'échec."""
    env = dict(os.environ, REQUEST_METHOD="GET", QUERY_STRING=(
        "date=%02d-%02d-%04d&command=pray%s&version=%s&lang1=Latin&lang2=Latin&votive=&testmode=regular"
        % (jour.month, jour.day, jour.year, commande, VERSION.replace(" ", "%20"))))
    try:
        p = subprocess.run(["perl", "officium.pl"], cwd=MOTEUR, env=env, capture_output=True, timeout=180)
    except (subprocess.TimeoutExpired, OSError):
        return ""
    sortie = p.stdout.decode("utf-8", "replace")
    i = sortie.find("<!DOCTYPE")
    return sortie[i:] if p.returncode == 0 and i >= 0 else ""


# ---------- nettoyage du HTML de l'amont ----------
class Nettoyeur(HTMLParser):
    """Ne garde qu'une liste blanche de balises, sans aucun attribut sauf des classes que nous choisissons."""
    SIMPLES = {"b", "i", "em", "strong", "u", "br", "p", "small", "sup", "sub"}
    IGNORES = {"script", "style", "form", "select", "option", "textarea", "button", "head"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sortie = []
        self.pile = []          # balises ouvertes que nous émettons
        self.ignore = 0

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
        style = self._attr(attrs, "style")
        if "color:red" in style.replace(" ", ""):
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
        elif tag == "div" or tag == "td":
            pass
        elif tag == "hr":
            self.sortie.append("<hr>")
        # tout le reste (a, img, input, table, tr…) est supprimé, son texte est gardé

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
        if nom in self.SIMPLES or nom == "span":
            if nom == "br":
                return
            if nom in self.pile:
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


def sections(page: str):
    """Liste de (titre, html propre) pour chaque partie de l'office, et (titre du jour, mention de l'Écriture)."""
    corps = page[page.upper().find("<BODY"):]
    titre = re.search(r"<FONT\s*>(.*?)</FONT>\s*<br/?>", corps, re.S | re.I)
    ecriture = re.search(r"Scriptura:</SPAN>\s*<FONT COLOR=\"green\">(.*?)</FONT>", corps, re.S | re.I)
    texte = lambda s: html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s))).strip()
    t = texte(titre.group(1)) if titre else ""
    e = texte(ecriture.group(1)) if ecriture else ""
    i = corps.upper().find("<TABLE")
    j = corps.upper().rfind("</TABLE>")
    if i < 0 or j < 0:
        return [], t, e
    sorties = []
    for cellule in re.findall(r"<TD[^>]*ID='[A-Za-z]+\d+'[^>]*>(.*?)</TD>", corps[i:j], re.S | re.I):
        cellule = re.sub(r"<DIV ALIGN='right'>.*?</DIV>", "", cellule, flags=re.S | re.I)          # liens « Top / Next » du moteur
        m = re.match(r"\s*<FONT SIZE='\+1' COLOR=\"red\"><B><I>(.*?)</I></B></FONT>\s*(?:<br/?>)?", cellule, re.S | re.I)
        titre_partie = texte(m.group(1)) if m else ""
        reste = cellule[m.end():] if m else cellule
        propre = nettoyer(reste).strip()
        if propre:
            sorties.append((titre_partie, propre))
    return sorties, t, e


# ---------- pages ----------
CSS = """
:root{--bg:#faf8f3;--fg:#241f1a;--mu:#6c6358;--rub:#a3262b;--line:#ddd5c6;--card:#fffdf8;--accent:#6b1d1d;--soft:#f0eadc}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#17130f;--fg:#ebe4d6;--mu:#a69c8c;--rub:#ff8c8c;--line:#3a322a;--card:#1f1a15;--accent:#e8b4b4;--soft:#2a231c;color-scheme:dark}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:18px/1.65 "Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
  padding:0 max(16px,env(safe-area-inset-right,0px)) 64px max(16px,env(safe-area-inset-left,0px))}
main,header,footer{max-width:44rem;margin:0 auto}
header{padding-top:max(16px,env(safe-area-inset-top,0px))}
h1{font-size:1.5rem;line-height:1.25;margin:.2em 0 0;color:var(--accent)}
.sous{color:var(--mu);font-size:.95rem;margin:.1em 0 0}
nav.heures,nav.jours{display:flex;flex-wrap:wrap;gap:6px;margin:14px 0}
nav a,nav button,.btn{font:600 .85rem system-ui,sans-serif;text-decoration:none;color:var(--fg);background:var(--soft);border:1px solid var(--line);border-radius:999px;padding:6px 12px;cursor:pointer}
nav a[aria-current=page]{background:var(--accent);color:var(--bg);border-color:var(--accent)}
nav a:hover,.btn:hover{border-color:var(--accent)}
nav.jours{align-items:center}nav.jours input{font:inherit;font-size:.85rem;border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:8px;padding:5px 8px}
section.partie{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:6px 16px 10px;margin:12px 0}
section.partie h3{margin:.7em 0 .2em;font-size:.95rem;letter-spacing:.06em;text-transform:uppercase;color:var(--rub);font-family:system-ui,sans-serif}
.r{color:var(--rub)}.g{color:var(--mu);font-size:.85em}
.cap{color:var(--rub);font-weight:700;font-style:normal}
.ver{color:var(--mu);font-family:system-ui,sans-serif;font-size:.62em;vertical-align:super;margin-right:.15em}
sup{font-size:.7em}
footer{color:var(--mu);font:.85rem/1.5 system-ui,sans-serif;margin-top:28px}
footer a{color:inherit}
.carte{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:14px 0}
.carte h2{margin:0 0 6px;font-size:1.05rem}
"""


def entete(titre: str, sous: str = "") -> str:
    return ('<!doctype html><html lang="la"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            '<meta name="color-scheme" content="light dark"><title>%s</title><style>%s</style></head><body>' % (html.escape(titre), CSS))


def date_longue(j: datetime.date) -> str:
    return "%s %d %s %d" % (JOURS_FR[j.weekday()], j.day, MOIS_FR[j.month - 1], j.year)


def page_heure(j, heure, titre_jour, ecriture, parties, dispo, racine):
    """racine : chemin relatif vers la racine du site (../..)."""
    cmd, latin, francais, slug = heure
    h = [entete("%s — %s" % (francais, date_longue(j)))]
    h.append('<header><p class="sous"><a href="%s/index.html" style="color:inherit">Divinum Officium</a> · latin · rubriques de 1960</p>' % racine)
    h.append("<h1>%s%s</h1>" % (html.escape(latin), "" if latin == francais else " <span style=\"font-weight:400\">· %s</span>" % html.escape(francais)))
    h.append('<p class="sous">%s' % html.escape(date_longue(j)))
    if titre_jour:
        h.append(" — %s" % html.escape(titre_jour))
    if ecriture:
        h.append("<br><i>%s</i>" % html.escape(ecriture))
    h.append("</p>")
    h.append('<nav class="heures" aria-label="Heures">')
    for c, l, f, s in HEURES:
        if s in dispo:
            cur = ' aria-current="page"' if s == slug else ""
            h.append('<a href="%s.html"%s>%s</a>' % (s, cur, html.escape(f)))
    h.append("</nav>")
    prec, suiv = j - datetime.timedelta(days=1), j + datetime.timedelta(days=1)
    h.append('<nav class="jours" aria-label="Jours"><a href="../%s/%s.html" data-jour="%s">← %s</a><a href="../%s/%s.html" data-jour="%s">%s →</a>'
             '<label>Aller au <input type="date" id="aller" value="%s"></label></nav></header><main>'
             % (prec.isoformat(), slug, prec.isoformat(), "veille", suiv.isoformat(), slug, suiv.isoformat(), "lendemain", j.isoformat()))
    for titre, contenu in parties:
        h.append('<section class="partie">%s<p>%s</p></section>' % ("<h3>%s</h3>" % html.escape(titre) if titre else "", contenu))
    h.append('</main><footer><a href="%s/index.html">Accueil</a> · <a href="%s/a-propos.html">À propos</a></footer>' % (racine, racine))
    h.append("<script>(function(){var a=document.getElementById('aller');if(!a)return;a.addEventListener('change',function(){if(a.value)location.href='../'+a.value+'/%s.html';});"
             "fetch('../../jours.json').then(function(r){return r.json()}).then(function(d){document.querySelectorAll('nav.jours a[data-jour]').forEach(function(l){"
             "if(d.dates.indexOf(l.dataset.jour)<0)l.style.display='none'});a.min=d.dates[0];a.max=d.dates[d.dates.length-1]}).catch(function(){})})();</script>" % slug)
    h.append("</body></html>")
    return "".join(h)


def page_accueil(dates):
    h = [entete("Divinum Officium")]
    h.append('<header><p class="sous">Fraternité · bréviaire romain en latin · rubriques de 1960 (bréviaire de 1962)</p><h1>Divinum Officium</h1><p class="sous" id="jour"></p></header><main>')
    h.append('<div class="carte"><h2>Les heures d’aujourd’hui</h2><nav class="heures" id="heures" aria-label="Heures"></nav></div>')
    h.append('<div class="carte"><h2>Un autre jour</h2><nav class="jours"><label>Date <input type="date" id="date"></label><span id="msg" class="sous"></span></nav></div></main>')
    h.append('<footer><a href="a-propos.html">À propos de cette version</a></footer>')
    h.append("<script>var HEURES=%s;" % json.dumps([[s, f] for _, _, f, s in HEURES], ensure_ascii=False))
    h.append("""
fetch('jours.json').then(function(r){return r.json()}).then(function(d){
  var ds=d.dates,aj=new Date(),iso=aj.getFullYear()+'-'+('0'+(aj.getMonth()+1)).slice(-2)+'-'+('0'+aj.getDate()).slice(-2);
  var j=ds.indexOf(iso)>=0?iso:(iso<ds[0]?ds[0]:ds[ds.length-1]),dispo=d.heures[j]||[];
  document.getElementById('jour').textContent=(j===iso?'':'(dernier jour disponible) ')+new Date(j+'T12:00:00').toLocaleDateString('fr-FR',{weekday:'long',day:'numeric',month:'long',year:'numeric'});
  var nav=document.getElementById('heures');
  HEURES.forEach(function(h){if(dispo.indexOf(h[0])<0)return;var a=document.createElement('a');a.href='jours/'+j+'/'+h[0]+'.html';a.textContent=h[1];nav.appendChild(a)});
  var inp=document.getElementById('date');inp.min=ds[0];inp.max=ds[ds.length-1];inp.value=j;
  inp.addEventListener('change',function(){if(ds.indexOf(inp.value)<0){document.getElementById('msg').textContent='Jour non préparé (du '+ds[0]+' au '+ds[ds.length-1]+').';return}
    location.href='jours/'+inp.value+'/'+((d.heures[inp.value]||['laudes'])[0]==='matutinum'&&d.heures[inp.value].indexOf('laudes')>=0?'laudes':d.heures[inp.value][0])+'.html'});
}).catch(function(){document.getElementById('jour').textContent='Les offices ne sont pas disponibles pour le moment.'});
</script></body></html>""")
    return "".join(h)


def page_a_propos(version_amont):
    return (entete("À propos — Divinum Officium") +
            '<header><p class="sous"><a href="index.html" style="color:inherit">Divinum Officium</a></p><h1>À propos de cette version</h1></header><main>'
            '<div class="carte"><p>Les offices sont ceux du projet libre <b>Divinum Officium</b> (licence MIT), calculés à l’avance, jour par jour, par son moteur d’origine, '
            'puis mis en page pour la lecture sur téléphone.</p>'
            '<p><b>Version :</b> bréviaire romain en latin, rubriques de 1960 (« Rubrics 1960 », bréviaire de 1962). Seules les heures en latin sont proposées.</p>'
            '<p><b>Source :</b> <a href="https://github.com/DivinumOfficium/divinum-officium">github.com/DivinumOfficium/divinum-officium</a>%s.</p>'
            '<p>Les pages sont régénérées chaque jour ; les jours proches (quelques jours avant et plusieurs semaines après aujourd’hui) sont disponibles.</p></div>'
            '</main><footer><a href="index.html">Accueil</a></footer></body></html>' % (" (commit " + version_amont + ")" if version_amont else ""))


# ---------- programme ----------
def produire(jour, heure, sortie: Path):
    page = lancer_moteur(jour, heure[0])
    if not page:
        return jour, heure, None
    parties, titre, ecriture = sections(page)
    if not parties:
        return jour, heure, None
    return jour, heure, (titre, ecriture, parties)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", required=True)
    ap.add_argument("--avant", type=int, default=3)
    ap.add_argument("--apres", type=int, default=60)
    ap.add_argument("--debut", help="jour central AAAA-MM-JJ (aujourd'hui à Paris par défaut)")
    ap.add_argument("--heures", help="liste d'identifiants séparés par des virgules (essais)")
    ap.add_argument("--amont", default="", help="identifiant du commit de l'amont, pour la page « À propos »")
    a = ap.parse_args()
    sortie = Path(a.sortie)
    centre = datetime.date.fromisoformat(a.debut) if a.debut else datetime.datetime.now(ZoneInfo("Europe/Paris")).date()
    jours = [centre + datetime.timedelta(days=d) for d in range(-a.avant, a.apres + 1)]
    heures = [h for h in HEURES if not a.heures or h[3] in a.heures.split(",")]
    taches = [(j, h) for j in jours for h in heures]
    resultats = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(2, (os.cpu_count() or 2))) as ex:
        for j, h, r in ex.map(lambda t: produire(t[0], t[1], sortie), taches):
            resultats[(j, h[3])] = r
    dispo = {j: [h[3] for h in heures if resultats.get((j, h[3]))] for j in jours}
    manquants = [(j.isoformat(), h[3]) for j in jours for h in heures if not resultats.get((j, h[3]))]
    for j in jours:
        for h in heures:
            r = resultats.get((j, h[3]))
            if not r:
                continue
            dossier = sortie / "jours" / j.isoformat()
            dossier.mkdir(parents=True, exist_ok=True)
            (dossier / (h[3] + ".html")).write_text(page_heure(j, h, r[0], r[1], r[2], dispo[j], "../.."), encoding="utf-8")
    dates = [j.isoformat() for j in jours if dispo[j]]
    if not dates:
        print("Aucun office produit : le moteur n'a rien renvoyé.", file=sys.stderr)
        sys.exit(1)
    sortie.mkdir(parents=True, exist_ok=True)
    (sortie / "jours.json").write_text(json.dumps({"dates": dates, "heures": {j: dispo[datetime.date.fromisoformat(j)] for j in dates}, "version": VERSION}, ensure_ascii=False), encoding="utf-8")
    (sortie / "index.html").write_text(page_accueil(dates), encoding="utf-8")
    (sortie / "a-propos.html").write_text(page_a_propos(a.amont), encoding="utf-8")
    print("%d pages pour %d jours (%s → %s) ; %d heures sans résultat." % (sum(len(v) for v in dispo.values()), len(dates), dates[0], dates[-1], len(manquants)))
    if manquants:
        print("Sans résultat (extrait) :", ", ".join("%s/%s" % m for m in manquants[:12]), file=sys.stderr)


if __name__ == "__main__":
    main()
