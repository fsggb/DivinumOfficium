/* Divinum Officium (FSGGB) : réglages, navigation, parties, recherche, hors connexion.
   Aucun suivi : rien n'est envoyé, tout reste dans ce navigateur. Tout fonctionne sans connexion (la page « ChatGDB » n'est proposée qu'en ligne). */
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); }, $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var racine = document.documentElement, R = racine.getAttribute("data-racine") || ".", page = racine.getAttribute("data-page") || "", jour = racine.getAttribute("data-jour") || "", genre = racine.getAttribute("data-genre") || "";
  var LS = { get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } }, set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) { /* ignoré */ } } };
  var TAILLES = [16, 17, 19, 21, 23, 26, 30], D = null;
  var NOMS = { matutinum: "Matines", laudes: "Laudes", prima: "Prime", tertia: "Tierce", sexta: "Sexte", nona: "None", vesperae: "Vêpres", completorium: "Complies" };
  var ORDRE = ["matutinum", "laudes", "prima", "tertia", "sexta", "nona", "vesperae", "completorium"];
  var JOURS = ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"], MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"];

  // ---------- dates et heure LOCALES de l'appareil (partout dans le monde) ----------
  function iso(d) { return d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2); }
  function aujourdhui() { return iso(new Date()); }
  function dateDe(s) { return new Date(s + "T12:00:00"); }
  function longue(s) { var d = dateDe(s); return JOURS[d.getDay()] + " " + d.getDate() + " " + MOIS[d.getMonth()] + " " + d.getFullYear(); }
  function heureConseillee() { var h = new Date().getHours(); return h < 5 ? "matutinum" : h < 7 ? "laudes" : h < 8 ? "prima" : h < 10 ? "tertia" : h < 13 ? "sexta" : h < 16 ? "nona" : h < 19 ? "vesperae" : "completorium"; }

  // ---------- réglages : taille, thème, langue de la messe, écran allumé ----------
  function taille(i) { i = Math.max(0, Math.min(TAILLES.length - 1, i)); racine.style.setProperty("--fs", TAILLES[i]); LS.set("do.taille", String(i)); var s = $("#t-etat"); if (s) s.textContent = TAILLES[i] + " px"; }
  function theme(t) {
    if (t === "auto") racine.removeAttribute("data-theme"); else racine.setAttribute("data-theme", t);
    LS.set("do.theme", t); $$("[data-theme-btn]").forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.themeBtn === t)); });
    var m = document.querySelector('meta[name="theme-color"]'); if (m) m.content = (t === "dark" || (t === "auto" && window.matchMedia("(prefers-color-scheme:dark)").matches)) ? "#070936" : "#000761";
  }
  var ti = parseInt(LS.get("do.taille") || "2", 10); taille(isNaN(ti) ? 2 : ti); theme(LS.get("do.theme") || "auto");
  $("#t-moins") && $("#t-moins").addEventListener("click", function () { taille(parseInt(LS.get("do.taille") || "2", 10) - 1); });
  $("#t-plus") && $("#t-plus").addEventListener("click", function () { taille(parseInt(LS.get("do.taille") || "2", 10) + 1); });
  $$("[data-theme-btn]").forEach(function (b) { b.addEventListener("click", function () { theme(b.dataset.themeBtn); }); });

  // fenêtres
  function ouvrirDialogue(d) { if (!d) return; if (d.showModal) { if (!d.open) d.showModal(); } else d.setAttribute("open", ""); }
  function fermer(d) { if (d && d.close) d.close(); }
  $$("dialog").forEach(function (d) {
    d.addEventListener("click", function (e) { if (e.target === d) fermer(d); });
    $$("[data-fermer]", d).forEach(function (b) { b.addEventListener("click", function () { fermer(d); }); });
  });
  $$("[data-ouvre]").forEach(function (b) { b.addEventListener("click", function () { var d = document.getElementById(b.dataset.ouvre); if (b.dataset.ouvre === "d-reglages") majHorsLigne(); ouvrirDialogue(d); }); });

  // écran allumé pendant la lecture
  var verrou = null;
  function ecran() { if (genre !== "office" && genre !== "messe") return; if (LS.get("do.ecran") !== "1" || !navigator.wakeLock) return; navigator.wakeLock.request("screen").then(function (w) { verrou = w; }).catch(function () { /* refusé */ }); }
  var se = $("#s-ecran"); if (se) { se.checked = LS.get("do.ecran") === "1"; se.addEventListener("change", function () { LS.set("do.ecran", se.checked ? "1" : "0"); if (se.checked) ecran(); else if (verrou) { try { verrou.release(); } catch (e) { /* ignoré */ } } }); }
  document.addEventListener("visibilitychange", function () { if (document.visibilityState === "visible") ecran(); });
  ecran();

  // ---------- application installable et hors connexion ----------
  var invite = null;
  window.addEventListener("beforeinstallprompt", function (e) { e.preventDefault(); invite = e; majInstall(); });
  window.addEventListener("appinstalled", function () { invite = null; majInstall(); });
  function installee() { return window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true; }
  function majInstall() {
    var ios = /iphone|ipad|ipod/i.test(navigator.userAgent), b = $("#b-installer"), e = $("#inst-etat"), c = $("#c-installer");
    var texte = installee() ? "L’application est installée sur cet appareil." : invite ? "Installez l’application pour la retrouver sur l’écran d’accueil, sans barre de navigateur, et la lire sans connexion." : ios ? "Sur iPhone et iPad : touchez le bouton Partager du navigateur, puis « Sur l’écran d’accueil »." : "Dans le menu du navigateur : « Installer l’application » ou « Ajouter à l’écran d’accueil ».";
    if (e) e.textContent = texte; if (b) b.hidden = !invite;
    if (c) { c.hidden = installee(); var p = $("p", c); if (p) p.textContent = texte; var bi = $("#b-installer-2"); if (bi) bi.hidden = !invite; }
  }
  $$("#b-installer,#b-installer-2").forEach(function (b) { b.addEventListener("click", function () { if (invite) { invite.prompt(); invite.userChoice.then(function () { invite = null; majInstall(); }); } }); });
  majInstall();
  if ("serviceWorker" in navigator && /^https:|^http:\/\/(localhost|127\.)/.test(location.href)) navigator.serviceWorker.register(R + "/sw.js", { scope: R + "/" }).catch(function () { /* hors connexion impossible, le reste fonctionne */ });

  var CACHE = "do-pages-v1";
  function urlsDe(jours) { var u = []; jours.forEach(function (j) { (D.heures[j] || []).forEach(function (s) { if (!/^votive-/.test(s)) u.push(R + "/jours/" + j + "/" + s + ".html"); }); }); return u; }
  function telecharger(jours, onProg) {
    if (!window.caches) return Promise.reject(new Error("non pris en charge"));
    var urls = urlsDe(jours), fait = 0;
    return caches.open(CACHE).then(function (c) {
      var i = 0;
      function lot() { if (i >= urls.length) return Promise.resolve(); var p = urls.slice(i, i + 4); i += 4; return Promise.all(p.map(function (u) { return c.add(u).catch(function () { /* page manquante : ignorée */ }); })).then(function () { fait += p.length; onProg && onProg(Math.min(fait, urls.length), urls.length); return lot(); }); }
      return lot();
    });
  }
  function majHorsLigne() {
    var e = $("#hc-etat"); if (!e) return;
    if (!window.caches) { e.textContent = "Ce navigateur ne permet pas la lecture hors connexion."; return; }
    caches.open(CACHE).then(function (c) { return c.keys(); }).then(function (k) {
      var n = k.filter(function (r) { return /\/jours\//.test(r.url); }).length;
      e.textContent = n ? n + " page(s) disponibles sans connexion (messe et heures). Les pages déjà lues le restent aussi." : "Aucune page enregistrée pour le moment. Les pages que vous lisez sont gardées automatiquement ; vous pouvez aussi télécharger les jours à venir.";
    });
  }
  function boutonTelechargement(id, nbJours) {
    var b = $(id); if (!b) return;
    b.addEventListener("click", function () {
      if (!D) return; var dates = D.dates.filter(function (j) { return j >= aujourdhui(); }); if (nbJours) dates = dates.slice(0, nbJours);
      var barre = $("#hc-barre"), i = barre && $("i", barre), e = $("#hc-etat"); b.disabled = true; if (barre) barre.hidden = false;
      telecharger(dates, function (f, t) { if (i) i.style.width = Math.round(100 * f / t) + "%"; if (e) e.textContent = "Téléchargement : " + f + " / " + t + " pages…"; }).then(function () { if (barre) barre.hidden = true; b.disabled = false; majHorsLigne(); }).catch(function () { b.disabled = false; if (e) e.textContent = "Téléchargement impossible (connexion ?)."; });
    });
  }
  boutonTelechargement("#hc-7", 8); boutonTelechargement("#hc-tout", 0);
  var eff = $("#hc-eff"); if (eff) eff.addEventListener("click", function () { if (window.caches) caches.delete(CACHE).then(majHorsLigne); });

  // ---------- jours disponibles ----------
  fetch(R + "/jours.json").then(function (r) { return r.json(); }).then(function (d) { D = d; demarrer(); }).catch(function () { var m = $("#msg"); if (m) { m.hidden = false; m.textContent = "Les offices ne sont pas disponibles pour le moment."; } });
  function demarrer() {
    var dates = D.dates, i = dates.indexOf(jour), av = $("#j-prec"), ap = $("#j-suiv");
    if (av) { if (i > 0) av.href = R + "/jours/" + dates[i - 1] + "/" + (D.heures[dates[i - 1]].indexOf(page) >= 0 ? page : "messe") + ".html"; else av.setAttribute("aria-disabled", "true"); }
    if (ap) { if (i >= 0 && i < dates.length - 1) ap.href = R + "/jours/" + dates[i + 1] + "/" + (D.heures[dates[i + 1]].indexOf(page) >= 0 ? page : "messe") + ".html"; else ap.setAttribute("aria-disabled", "true"); }
    var inp = $("#j-date"); if (inp) { inp.min = dates[0]; inp.max = dates[dates.length - 1]; inp.addEventListener("change", function () { if (inp.value && D.heures[inp.value]) { var h = D.heures[inp.value]; location.href = R + "/jours/" + inp.value + "/" + (h.indexOf(page) >= 0 ? page : (genre === "messe" ? "messe" : h.indexOf(heureConseillee()) >= 0 ? heureConseillee() : h[0])) + ".html"; } }); }
    var aj = aujourdhui(), lien = $("#j-aujourdhui"); if (lien) { if (jour && jour !== aj && D.heures[aj]) { lien.hidden = false; lien.href = R + "/jours/" + aj + "/" + (D.heures[aj].indexOf(page) >= 0 ? page : "messe") + ".html"; } else lien.hidden = true; }
    document.addEventListener("keydown", function (e) { if (e.target && /input|textarea|select/i.test(e.target.tagName) || e.altKey || e.ctrlKey || e.metaKey) return; if (e.key === "ArrowLeft" && av && av.href) av.click(); if (e.key === "ArrowRight" && ap && ap.href) ap.click(); });
    if (genre === "messe") autresMesses();
    if (page === "accueil") accueil();
    if (page === "calendrier") calendrier();
    majHorsLigne(); elaguer();
    if (navigator.onLine !== false && window.caches && jour === aj) setTimeout(function () { telecharger(dates.filter(function (j) { return j >= aj; }).slice(0, 3)); }, 4000);
  }
  function elaguer() {   // les pages de plus de 2 jours ne servent plus
    if (!window.caches) return; var limite = new Date(); limite.setDate(limite.getDate() - 2); var lim = iso(limite);
    caches.open(CACHE).then(function (c) { c.keys().then(function (ks) { ks.forEach(function (r) { var m = /\/jours\/(\d{4}-\d\d-\d\d)\//.exec(r.url); if (m && m[1] < lim) c.delete(r); }); }); });
  }

  // ---------- parties : sommaire latéral, barre du téléphone, feuille, langue ----------
  var parties = $$("details.partie"), chips = $("#sommaire-liste"), bloque = 0;
  function visibles() { return parties.filter(function (p) { return !p.hidden; }); }
  function ouvrir(p) { if (p && p.tagName === "DETAILS") p.open = true; }
  function aller(id) {
    var p = document.getElementById(id); if (!p) return;
    fermer($("#d-parties")); ouvrir(p); marquer(id);
    // défilement doux pour une courte distance seulement : sur une longue distance, il est instantané (la partie choisie reste bien celle qui est marquée)
    var loin = Math.abs(p.getBoundingClientRect().top) > 1200 || window.matchMedia("(prefers-reduced-motion:reduce)").matches;
    bloque = Date.now() + (loin ? 400 : 1000); setTimeout(espion, loin ? 450 : 1050);
    setTimeout(function () { p.scrollIntoView({ behavior: loin ? "auto" : "smooth", block: "start" }); }, 60);
  }
  var courante = null;
  function marquer(id) {
    courante = id;
    $$("[data-p]").forEach(function (b) { b.classList.toggle("on", b.dataset.p === id); });
    var p = document.getElementById(id), cur = $("#cur"); if (p && cur) { var t = $(".nom", p), fr = $("i", t); cur.innerHTML = ""; var s = document.createElement("span"); s.textContent = fr ? fr.textContent : p.dataset.nom; var sm = document.createElement("small"); sm.textContent = fr ? p.dataset.nom : ""; cur.appendChild(s); if (fr) cur.appendChild(sm); }
    var act = $('.sommaire button.on'); if (act && chips && (act.offsetTop < chips.parentNode.scrollTop || act.offsetTop > chips.parentNode.scrollTop + chips.parentNode.clientHeight - 60)) act.scrollIntoView({ block: "nearest" });
  }
  function espion() {
    if (Date.now() < bloque || !parties.length) return;
    var seuil = window.innerWidth >= 960 ? 120 : 190, c = null; visibles().forEach(function (p) { if (p.getBoundingClientRect().top <= seuil) c = p.id; });
    if (!c) { var v = visibles()[0]; c = v && v.id; } if (c && c !== courante) marquer(c);
  }
  var att = 0; window.addEventListener("scroll", function () { if (!att) att = setTimeout(function () { att = 0; espion(); }, 80); }, { passive: true });
  document.addEventListener("click", function (e) { var b = e.target.closest("[data-p]"); if (b) aller(b.dataset.p); });
  function pas(sens) { var v = visibles(), i = v.map(function (p) { return p.id; }).indexOf(courante); var n = v[Math.max(0, Math.min(v.length - 1, i + sens))]; if (n) aller(n.id); }
  $("#p-prec") && $("#p-prec").addEventListener("click", function () { pas(-1); });
  $("#p-suiv") && $("#p-suiv").addEventListener("click", function () { pas(1); });
  // copie de la liste des parties dans la feuille du téléphone
  var lp = $("#liste-feuille"), side = $("#sommaire-liste"); if (lp && side) lp.innerHTML = side.innerHTML.replace(/<button/g, '<button type="button"');
  if (parties.length) { marquer(parties[0].id); setTimeout(espion, 300); }
  // « Tout replier », psaumes, propre seulement
  $$("[data-tout]").forEach(function (b) { b.addEventListener("click", function () { var ou = parties.some(function (p) { return p.open; }); parties.forEach(function (p) { p.open = !ou; }); $$("[data-tout]").forEach(function (x) { x.textContent = ou ? "Tout déplier" : "Tout replier"; }); }); });
  $$("[data-psaumes]").forEach(function (b) { b.addEventListener("click", function () { var fermer_ = parties.some(function (p) { return /psalm/i.test(p.dataset.nom || "") && p.open; }); parties.forEach(function (p) { if (/psalm/i.test(p.dataset.nom || "")) p.open = !fermer_; }); $$("[data-psaumes]").forEach(function (x) { x.textContent = fermer_ ? "Déplier les psaumes" : "Replier les psaumes"; }); }); });
  function majPropre(on) { $$('details.partie[data-ord="1"]').forEach(function (p) { p.hidden = on; }); $$('[data-p][data-ord="1"]').forEach(function (b) { b.hidden = on; }); $$("[data-propre]").forEach(function (c) { c.checked = on; }); LS.set("do.propre", on ? "1" : "0"); if (!on) return; var v = visibles()[0]; if (v && courante && document.getElementById(courante).hidden) marquer(v.id); }
  $$("[data-propre]").forEach(function (c) { c.addEventListener("change", function () { majPropre(c.checked); }); });
  if ($("[data-propre]")) majPropre(LS.get("do.propre") === "1");
  // langue : latin, français ou les deux, partie par partie (seulement les textes variables d'un jour à l'autre)
  majLangueParties();
  function majLangueParties() { parties.forEach(function (p) { var lg = p.getAttribute("data-lg"); $$(".lang button", p).forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.lg === lg)); }); }); }
  $$(".lang button").forEach(function (b) { b.addEventListener("click", function (e) { e.stopPropagation(); var p = b.closest("details.partie"); p.setAttribute("data-lg", b.dataset.lg); majLangueParties(); }); });
  // hash : ouvrir la partie demandée
  if (location.hash && document.getElementById(location.hash.slice(1))) setTimeout(function () { aller(location.hash.slice(1)); }, 350);

  // ---------- messes de ce jour : autres messes, communs et messes votives ----------
  function autresMesses() {
    var dlg = $("#d-messes"); if (!dlg || !D) return; var c = $(".contenu", dlg), dispo = D.heures[jour] || [];
    var multiples = (D.messes && D.messes[jour]) || [], html = "";
    if (multiples.length > 1) { html += '<div><h3>Messes de ce jour</h3><div class="grp">' + multiples.map(function (m) { return '<a class="btn' + (m.slug === page ? " p" : "") + '" href="' + m.slug + '.html">' + m.label + "</a>"; }).join("") + "</div></div>"; }
    var vot = (D.votives || []).filter(function (v) { return dispo.indexOf(v.slug) >= 0; });
    if (vot.length) {
      var groupes = {}; vot.forEach(function (v) { (groupes[v.groupe] = groupes[v.groupe] || []).push(v); });
      Object.keys(groupes).forEach(function (g) { html += "<div><h3>" + g + '</h3><div class="grp">' + groupes[g].map(function (v) { return '<a class="btn' + (v.slug === page ? " p" : "") + '" href="' + v.slug + '.html">' + v.label + "</a>"; }).join("") + "</div></div>"; });
      html += '<div><a class="btn" href="messe.html">Revenir à la messe du jour</a></div>';
    } else html += '<p class="etat">Les messes votives et les communs sont préparés pour les jours proches (une semaine à partir d’aujourd’hui).</p>';
    c.innerHTML = html;
    if (location.hash === "#autres" && vot.length) ouvrirDialogue(dlg);
  }

  // ---------- accueil : une rubrique Messe, une rubrique Office divin ----------
  function titreDe(j) { return (D.titres && D.titres[j]) || {}; }
  var COUL = { green: "#2e7d32", red: "#c0262d", purple: "#6a3d9a", violet: "#6a3d9a", white: "#cfc7b0", blue: "#1c4fa0", black: "#222222", rose: "#d2698a", pink: "#d2698a", gold: "#c6a24e", grey: "#808080" };
  function accueil() {
    var aj = aujourdhui(), dates = D.dates, p = new URLSearchParams(location.search), demande = p.get("d");
    var j = demande && D.heures[demande] ? demande : (D.heures[aj] ? aj : (aj < dates[0] ? dates[0] : dates[dates.length - 1])), dispo = D.heures[j] || [], t = titreDe(j), reel = j === aj;
    $("#h-date").textContent = (reel ? "Aujourd’hui · " : "") + longue(j); $("#h-titre").textContent = t.t || ""; $("#h-ecr").textContent = t.e || "";
    var ti_ = $(".titre"); if (COUL[t.c]) ti_.style.setProperty("--c", COUL[t.c]);
    var bg = $("#h-badges"); if (bg) { bg.innerHTML = ""; [t.k ? t.k + (t.k === 1 ? "re" : "e") + " classe" : "", t.y === "dim" ? "Dimanche" : t.y === "feria" ? "Férie" : ""].filter(Boolean).forEach(function (x) { var s = document.createElement("span"); s.className = "badge"; s.textContent = x; bg.appendChild(s); }); }
    if (!reel && D.heures[aj]) { var l = $("#h-aujourdhui"); l.hidden = false; l.href = "index.html"; }
    // messe
    var gm = $("#r-messe"), multiples = (D.messes && D.messes[j]) || [{ slug: "messe", label: "Messe du jour" }]; gm.innerHTML = "";
    multiples.forEach(function (m, i) { var a = document.createElement("a"); a.className = "choix p" + (multiples.length === 1 ? " large" : ""); a.href = R + "/jours/" + j + "/" + m.slug + ".html"; a.innerHTML = "<span></span><small></small>"; a.firstChild.textContent = m.label; a.lastChild.textContent = i === 0 && multiples.length === 1 ? "Propre et ordinaire, avec traduction française" : ((D.titres[j] || {}).t || "").slice(0, 60); gm.appendChild(a); });
    var vot = (D.votives || []).filter(function (v) { return dispo.indexOf(v.slug) >= 0; });
    var av = document.createElement("a"); av.className = "choix large"; av.href = R + "/jours/" + j + "/messe.html#autres"; av.innerHTML = "<span>Autres messes</span><small>Communs des saints, défunts, Vierge Marie, messes votives</small>"; if (vot.length) gm.appendChild(av);
    // office : les huit heures, la plus proche de l'heure locale mise en avant
    var go = $("#r-office"); go.innerHTML = ""; var hc = heureConseillee();
    ORDRE.forEach(function (h) { if (dispo.indexOf(h) < 0) return; var a = document.createElement("a"); a.className = "choix" + (reel && h === hc ? " reco" : ""); a.href = R + "/jours/" + j + "/" + h + ".html"; a.innerHTML = "<span></span><small></small>"; a.firstChild.textContent = NOMS[h]; a.lastChild.textContent = { matutinum: "Office de nuit", laudes: "Au lever du jour", prima: "Première heure", tertia: "Troisième heure", sexta: "Sixième heure", nona: "Neuvième heure", vesperae: "Le soir", completorium: "Avant le repos" }[h]; go.appendChild(a); });
    var inp = $("#h-pick"); inp.min = dates[0]; inp.max = dates[dates.length - 1]; inp.value = j; inp.addEventListener("change", function () { if (D.heures[inp.value]) location.href = "index.html?d=" + inp.value; });
    // prochaines grandes fêtes
    var fe = $("#h-fetes"); if (fe) { var l2 = dates.filter(function (x) { return x > j && D.titres[x] && D.titres[x].k && D.titres[x].k <= 2 && D.titres[x].y !== "dim"; }).slice(0, 5); fe.innerHTML = l2.map(function (x) { return '<li><a href="index.html?d=' + x + '"><span class="d">' + dateDe(x).getDate() + " " + MOIS[dateDe(x).getMonth()].slice(0, 4) + '.</span><span class="t">' + D.titres[x].t.replace(/ ~.*$/, "") + "</span></a></li>"; }).join(""); $("#c-fetes").hidden = !l2.length; }
    recherche(j);
    if (location.hash === "#autres" && vot.length) {}
  }

  // ---------- recherche intelligente : tout se passe sur l'appareil, donc aussi sans connexion ----------
  function norm(s) { return String(s || "").toLowerCase().replace(/œ/g, "oe").replace(/æ/g, "ae").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9 ]+/g, " ").replace(/\s+/g, " ").trim(); }
  var SYN = { messe: ["messe", "missa", "eucharistie"], matutinum: ["matines", "matutinum", "office de nuit", "nocturne"], laudes: ["laudes", "office du matin", "matin"], prima: ["prime", "prima"], tertia: ["tierce", "tertia"], sexta: ["sexte", "sexta", "midi"], nona: ["none", "nona", "apres midi"], vesperae: ["vepres", "vesperae", "office du soir", "soir"], completorium: ["complies", "completorium", "coucher", "nuit"] };
  var PARTIES_ = { evangile: ["messe", "evangelium", "Évangile"], epitre: ["messe", "lectio", "Épître"], lecture: ["messe", "lectio", "Épître"], introit: ["messe", "introitus", "Introït"], graduel: ["messe", "graduale", "Graduel"], collecte: ["messe", "oratio", "Collecte"], offertoire: ["messe", "offertorium", "Offertoire"], secrete: ["messe", "secreta", "Secrète"], preface: ["messe", "praefatio", "Préface"], canon: ["messe", "canon", "Canon"], credo: ["messe", "credo", "Credo"], gloria: ["messe", "gloria", "Gloria"], communion: ["messe", "communio", "Communion"], postcommunion: ["messe", "postcommunio", "Postcommunion"], magnificat: ["vesperae", "canticum-magnificat", "Magnificat"], benedictus: ["laudes", "canticum-benedictus", "Benedictus"], "nunc dimittis": ["completorium", "canticum-nunc-dimittis", "Nunc dimittis"], "salve regina": ["completorium", "antiphona-finalis-b-m-v", "Salve Regina"], psaumes: ["laudes", "psalmi", "Psaumes"], hymne: ["laudes", "hymnus", "Hymne"], capitule: ["laudes", "capitulum", "Capitule"] };
  var ALIAS = [["conceptione immaculata", "immaculee conception 8 decembre"], ["nativitate domini", "noel nativite"], ["in nativitate", "noel"], ["epiphani", "epiphanie rois mages"], ["adventus", "avent"], ["quadragesimae", "careme"], ["cinerum", "cendres"], ["palmarum", "rameaux"], ["coena domini", "jeudi saint cene"], ["parasceve", "vendredi saint passion"], ["sabbato sancto", "samedi saint veillee pascale"], ["resurrectione|dominica paschae", "paques resurrection"], ["paschae|post pascha", "temps pascal paques"], ["ascensione", "ascension"], ["pentecoste", "pentecote"], ["trinitate", "trinite"], ["corporis christi", "fete dieu saint sacrement"], ["sacratissimi cordis", "sacre coeur"], ["christi regis", "christ roi"], ["omnium sanctorum", "toussaint"], ["defunctorum", "defunts morts"], ["assumptione", "assomption"], ["purificatione", "chandeleur purification presentation"], ["annuntiatione", "annonciation"], ["circumcisione", "circoncision"], ["transfiguratione", "transfiguration"], ["exaltatione", "croix glorieuse exaltation"], ["rosarii", "rosaire"], ["angelorum custodum", "anges gardiens"], ["michaelis", "saint michel archange"], ["joseph|ioseph", "saint joseph"], ["petri et pauli", "saint pierre paul"], ["baptistae", "saint jean baptiste"], ["^dominica", "dimanche"], ["^feria|feria ", "feria ferie semaine"], ["septuagesimae", "septuagesime"], ["sexagesimae", "sexagesime"], ["quinquagesimae", "quinquagesime"], ["post pentecosten", "apres pentecote"], ["dedicatione", "dedicace"], ["immaculat", "immaculee"], ["marie|mariae|virginis", "vierge marie"]];
  function termes(j) { var t = norm((D.titres[j] || {}).t + " " + (D.titres[j] || {}).e), extra = ""; ALIAS.forEach(function (a) { if (new RegExp(a[0]).test(t)) extra += " " + a[1]; }); return t + extra; }
  function analyserDate(q, base) {
    var t = " " + q + " ", d = null, mots = [];
    var rel = [[" apres demain ", 2], [" demain ", 1], [" hier ", -1], [" aujourd hui ", 0], [" ce jour ", 0], [" ce soir ", 0], [" ce matin ", 0], [" maintenant ", 0]];
    rel.forEach(function (r) { if (d === null && t.indexOf(r[0]) >= 0) { d = new Date(base.getTime() + r[1] * 86400000); mots.push(r[0].trim()); } });
    if (d === null) { var m = /\b(\d{1,2}) (janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre)( (\d{4}))?\b/.exec(q); if (m) { var mi = ["janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet", "aout", "septembre", "octobre", "novembre", "decembre"].indexOf(m[2]); d = new Date(m[4] ? +m[4] : base.getFullYear(), mi, +m[1], 12); if (!m[4] && d < new Date(base.getTime() - 86400000 * 30)) d.setFullYear(d.getFullYear() + 1); mots.push(m[0]); } }
    if (d === null) { var m2 = /\b(\d{1,2}) ?[\/.-] ?(\d{1,2})\b/.exec(q); if (m2) { d = new Date(base.getFullYear(), +m2[2] - 1, +m2[1], 12); mots.push(m2[0]); } }
    if (d === null) { ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"].forEach(function (nom, i) { if (d === null && t.indexOf(" " + nom + " ") >= 0) { var n = new Date(base); n.setHours(12); var k = (i - n.getDay() + 7) % 7; if (k === 0 && /prochain/.test(q)) k = 7; n.setDate(n.getDate() + k); d = n; mots.push(nom); } }); }
    return { date: d && !isNaN(d) ? iso(d) : null, mots: mots };
  }
  function recherche(jHub) {
    var inp = $("#q"), liste = $("#sugg"), defaut = $("#defaut"); if (!inp) return;
    function item(label, sous, url) { return { label: label, sous: sous, url: url }; }
    function calculer(brut) {
      var q = norm(brut), res = []; if (!q) return res;
      var base = dateDe(jHub), ad = analyserDate(q, base), j = ad.date || jHub, reste = q;
      ad.mots.forEach(function (m) { reste = reste.replace(norm(m), " "); }); reste = reste.replace(/\b(le|la|les|de|du|des|d|l|a|au|office|messe du)\b/g, " ").replace(/\s+/g, " ").trim();
      var dispo = D.heures[j];
      // une heure ou la messe, éventuellement pour un jour précis
      var heure = null; Object.keys(SYN).forEach(function (k) { SYN[k].forEach(function (s) { if (!heure && (" " + q + " ").indexOf(" " + s + " ") >= 0) heure = k; }); });
      var pk = null; Object.keys(PARTIES_).forEach(function (k) { if (!pk && (" " + q + " ").indexOf(" " + k + " ") >= 0) pk = k; });
      if (!dispo && (heure || ad.date || pk)) { res.push(item("Jour non préparé : " + longue(j), "Du " + longue(D.dates[0]) + " au " + longue(D.dates[D.dates.length - 1]), "calendrier.html")); }
      else if (dispo) {
        if (pk) { var cible = PARTIES_[pk][0] === "messe" ? "messe" : PARTIES_[pk][0]; if (dispo.indexOf(cible) >= 0) res.push(item(PARTIES_[pk][2], (cible === "messe" ? "Messe" : NOMS[cible]) + " · " + longue(j), R + "/jours/" + j + "/" + cible + ".html#" + PARTIES_[pk][1])); }
        if (heure && dispo.indexOf(heure) >= 0) res.push(item(heure === "messe" ? "Messe" : NOMS[heure], longue(j) + (heure === heureConseillee() && j === aujourdhui() ? " · recommandé maintenant" : ""), R + "/jours/" + j + "/" + heure + ".html"));
        else if (ad.date && !heure) res.push(item("Jour du " + longue(j), (D.titres[j] || {}).t || "", "index.html?d=" + j));
        (D.votives || []).forEach(function (v) { var n = norm(v.label + " " + v.groupe + " " + (v.mots || "")); var tk = reste.split(" ").filter(function (x) { return x.length > 2; }); if (tk.length && tk.every(function (x) { return n.indexOf(x) >= 0; }) && dispo.indexOf(v.slug) >= 0) res.push(item(v.label, "Messe · " + v.groupe + " · " + longue(j), R + "/jours/" + j + "/" + v.slug + ".html")); });
      }
      // titres de jours (fêtes, dimanches, féries), français ou latin
      var tk2 = reste.split(" ").filter(function (x) { return x.length > 2; });
      if (tk2.length && !(heure && !tk2.length)) {
        var trouves = D.dates.filter(function (x) { var T = termes(x); return tk2.every(function (w) { return T.indexOf(w) >= 0; }); }).sort(function (a, b) { return Math.abs(dateDe(a) - base) - Math.abs(dateDe(b) - base); }).slice(0, 4);
        trouves.forEach(function (x) { res.push(item((D.titres[x].t || "").replace(/ ~.*$/, ""), longue(x), "index.html?d=" + x)); });
      }
      // sans rien d'autre : le jour lui-même
      var vus = {}; return res.filter(function (r) { if (vus[r.url]) return false; vus[r.url] = 1; return true; }).slice(0, 6);
    }
    function afficher() {
      var brut = inp.value, r = calculer(brut); liste.innerHTML = ""; liste.hidden = !brut.trim();
      if (defaut) defaut.hidden = !!brut.trim();
      if (!brut.trim()) return;
      r.forEach(function (x) { var li = document.createElement("li"), a = document.createElement("a"); a.href = x.url; var s = document.createElement("span"); s.textContent = x.label; var sm = document.createElement("small"); sm.textContent = x.sous; a.appendChild(s); a.appendChild(sm); li.appendChild(a); liste.appendChild(li); });
      if (!r.length) { var li0 = document.createElement("li"); li0.innerHTML = '<a href="calendrier.html"><span>Aucun résultat</span><small>Essayez « vêpres demain », « évangile », « Immaculée Conception »</small></a>'; liste.appendChild(li0); }
      if (navigator.onLine !== false) { var li1 = document.createElement("li"), a1 = document.createElement("a"); a1.href = "https://fsggb.github.io/ScoutHub/ChatGDB/?q=" + encodeURIComponent("Divinum Officium : " + brut); a1.target = "_blank"; a1.rel = "noopener"; var s1 = document.createElement("span"); s1.textContent = "Poser la question à ChatGDB"; var sm1 = document.createElement("small"); sm1.textContent = "En ligne seulement"; a1.appendChild(s1); a1.appendChild(sm1); li1.appendChild(a1); liste.appendChild(li1); }
    }
    inp.addEventListener("input", afficher);
    inp.addEventListener("keydown", function (e) { if (e.key === "Enter") { var a = $("#sugg a"); if (a) { e.preventDefault(); a.click(); } } });
    $("#q-vider") && $("#q-vider").addEventListener("click", function () { inp.value = ""; afficher(); inp.focus(); });
  }

  // ---------- calendrier : filtres comme dans un missel (temps liturgiques, fêtes, féries) ----------
  function calendrier() {
    var liste = $("#cal-liste"), filtres = $("#filtres"), rech = $("#cal-q"), actif = "tous";
    var F = { tous: function () { return true; }, fetes: function (t) { return t.k && t.k <= 2; }, dim: function (t) { return t.y === "dim"; }, feria: function (t) { return t.y === "feria"; } };
    ["avent", "noel", "epiphanie", "septuagesime", "careme", "pascal", "pentecote"].forEach(function (s) { F[s] = function (t) { return t.s === s; }; });
    function dessiner() {
      var q = norm(rech.value), mois = null, html = "";
      D.dates.forEach(function (j) {
        var t = D.titres[j] || {}; if (!F[actif](t)) return; if (q) { var T = termes(j) + " " + norm(longue(j)); if (!q.split(" ").every(function (w) { return T.indexOf(w) >= 0; })) return; }
        var d = dateDe(j), m = d.getFullYear() + "-" + d.getMonth(); if (m !== mois) { if (mois) html += "</ul></div>"; mois = m; html += '<div class="carte"><h2>' + MOIS[d.getMonth()] + " " + d.getFullYear() + '</h2><ul class="liste">'; }
        html += '<li><a href="index.html?d=' + j + '"><span class="d"><i class="pt" style="--c:' + (COUL[t.c] || "var(--gold)") + '"></i>' + JOURS[d.getDay()].slice(0, 3) + ". " + d.getDate() + '</span><span class="t">' + (t.t || "").replace(/ ~.*$/, "") + (t.k ? '<i class="cl">' + t.k + (t.k === 1 ? "re" : "e") + " cl.</i>" : "") + "</span></a></li>";
      });
      liste.innerHTML = (html ? html + "</ul></div>" : '<p class="vide">Aucun jour ne correspond.</p>');
    }
    $$("button", filtres).forEach(function (b) { b.addEventListener("click", function () { actif = b.dataset.f; $$("button", filtres).forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); }); dessiner(); }); });
    rech.addEventListener("input", dessiner); dessiner();
  }
})();
