/* Divinum Officium (FSGGB) : réglages, navigation et parties repliables. Aucun suivi, rien n'est envoyé : tout reste dans ce navigateur. */
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); }, $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var racine = document.documentElement, R = racine.getAttribute("data-racine") || ".", page = racine.getAttribute("data-page") || "", jour = racine.getAttribute("data-jour") || "";
  var LS = { get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } }, set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) { /* ignoré */ } } };
  var TAILLES = [16, 17, 19, 21, 23, 26, 30];

  // ---------- réglages : taille du texte, thème ----------
  function taille(i) { i = Math.max(0, Math.min(TAILLES.length - 1, i)); racine.style.setProperty("--fs", TAILLES[i]); LS.set("do.taille", String(i)); majTaille(i); }
  function majTaille(i) { var s = $("#t-etat"); if (s) s.textContent = TAILLES[i] + " px"; }
  function theme(t) { if (t === "auto") { racine.removeAttribute("data-theme"); LS.set("do.theme", "auto"); } else { racine.setAttribute("data-theme", t); LS.set("do.theme", t); } $$("[data-theme-btn]").forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.themeBtn === (LS.get("do.theme") || "auto"))); }); }
  var ti = parseInt(LS.get("do.taille") || "2", 10); if (isNaN(ti)) ti = 2; taille(ti);
  theme(LS.get("do.theme") || "auto");
  var pop = $("#pop"), bpop = $("#b-reglages");
  if (bpop && pop) {
    bpop.addEventListener("click", function (e) { e.stopPropagation(); var o = pop.hidden; pop.hidden = !o; bpop.setAttribute("aria-expanded", String(o)); });
    document.addEventListener("click", function (e) { if (!pop.hidden && !pop.contains(e.target)) { pop.hidden = true; bpop.setAttribute("aria-expanded", "false"); } });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !pop.hidden) { pop.hidden = true; bpop.setAttribute("aria-expanded", "false"); bpop.focus(); } });
    $("#t-moins").addEventListener("click", function () { taille(parseInt(LS.get("do.taille") || "2", 10) - 1); });
    $("#t-plus").addEventListener("click", function () { taille(parseInt(LS.get("do.taille") || "2", 10) + 1); });
    $$("[data-theme-btn]").forEach(function (b) { b.addEventListener("click", function () { theme(b.dataset.themeBtn); }); });
  }

  // ---------- jours disponibles ----------
  var D = null, voisins = function () { return null; };
  function aujourdhui() { var d = new Date(); return d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2); }
  function versJour(j, p) {
    if (!D) return;
    var dispo = D.heures[j]; if (!dispo) return;
    var cible = dispo.indexOf(p) >= 0 ? p : (p === "messe" ? "messe" : (dispo.indexOf(heureConseillee()) >= 0 ? heureConseillee() : dispo[0]));
    location.href = R + "/jours/" + j + "/" + cible + ".html";
  }
  function heureConseillee() { var h = new Date().getHours(); return h < 5 ? "matutinum" : h < 7 ? "laudes" : h < 8 ? "prima" : h < 10 ? "tertia" : h < 13 ? "sexta" : h < 16 ? "nona" : h < 19 ? "vesperae" : "completorium"; }
  // dernière heure du bréviaire lue : le bouton « Bréviaire » de la messe y retourne ; sinon, l'heure qui convient à l'heure qu'il est
  if (page && page !== "messe" && /^(matutinum|laudes|prima|tertia|sexta|nona|vesperae|completorium)$/.test(page)) LS.set("do.heure", page);
  var bb = $("#m-breviaire"); if (bb && page === "messe") { var h0 = jour === aujourdhui() ? heureConseillee() : (LS.get("do.heure") || "laudes"); bb.href = h0 + ".html"; }
  fetch(R + "/jours.json").then(function (r) { return r.json(); }).then(function (d) {
    D = d;
    var dates = d.dates, i = dates.indexOf(jour);
    var av = $("#j-prec"), ap = $("#j-suiv");
    if (av && i > 0) av.href = R + "/jours/" + dates[i - 1] + "/" + page + ".html"; else if (av) av.setAttribute("aria-disabled", "true");
    if (ap && i >= 0 && i < dates.length - 1) ap.href = R + "/jours/" + dates[i + 1] + "/" + page + ".html"; else if (ap) ap.setAttribute("aria-disabled", "true");
    var inp = $("#j-date"); if (inp) { inp.min = dates[0]; inp.max = dates[dates.length - 1]; inp.addEventListener("change", function () { if (inp.value) versJour(inp.value, page); }); }
    var aj = aujourdhui(), lien = $("#j-aujourdhui"); if (lien) { if (jour && jour !== aj && dates.indexOf(aj) >= 0) { lien.hidden = false; lien.href = R + "/jours/" + aj + "/" + page + ".html"; } else lien.hidden = true; }
    document.addEventListener("keydown", function (e) { if (e.target && /input|textarea/i.test(e.target.tagName)) return; if (e.key === "ArrowLeft" && av && av.href) av.click(); if (e.key === "ArrowRight" && ap && ap.href) ap.click(); });
    if (page === "accueil") accueil(d);
  }).catch(function () { var m = $("#msg"); if (m) m.textContent = "Les offices ne sont pas disponibles pour le moment."; });

  // heure conseillée (le jour même)
  if (jour && jour === aujourdhui()) { var hc = $('.heures a[data-h="' + heureConseillee() + '"]'); if (hc) hc.classList.add("maintenant"); }

  // ---------- parties ----------
  var parties = $$("details.partie"), chips = $("#chips");
  function ouvrir(p) { if (p && p.tagName === "DETAILS") p.open = true; }
  if (chips) chips.addEventListener("click", function (e) {
    var b = e.target.closest("button[data-p]"); if (!b) return; var p = document.getElementById(b.dataset.p); if (!p) return;
    ouvrir(p); p.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion:reduce)").matches ? "auto" : "smooth", block: "start" });
  });
  if (parties.length && "IntersectionObserver" in window && chips) {
    var vus = {}, io = new IntersectionObserver(function (es) {
      es.forEach(function (e) { vus[e.target.id] = e.isIntersecting ? e.boundingClientRect.top : null; });
      var meilleur = null, top = 1e9; Object.keys(vus).forEach(function (k) { if (vus[k] !== null && Math.abs(vus[k] - 130) < top) { top = Math.abs(vus[k] - 130); meilleur = k; } });
      if (meilleur) $$("button[data-p]", chips).forEach(function (b) { var on = b.dataset.p === meilleur; b.classList.toggle("on", on); if (on && b.scrollIntoView) { var c = chips, bl = b.offsetLeft, w = b.offsetWidth; if (bl < c.scrollLeft || bl + w > c.scrollLeft + c.clientWidth) c.scrollLeft = bl - 16; } });
    }, { rootMargin: "-110px 0px -55% 0px", threshold: [0, 1] });
    parties.forEach(function (p) { io.observe(p); });
  }
  var bo = $("#b-options"), mo = $("#menu-parties");
  if (bo && mo) bo.addEventListener("click", function () { var o = mo.hidden; mo.hidden = !o; bo.setAttribute("aria-expanded", String(o)); });
  var tout = $("#b-tout");
  if (tout) tout.addEventListener("click", function () { var ouvertes = parties.some(function (p) { return p.open; }); parties.forEach(function (p) { p.open = !ouvertes; }); tout.textContent = ouvertes ? "Tout déplier" : "Tout replier"; });
  var psaumes = $("#b-psaumes");
  if (psaumes) psaumes.addEventListener("click", function () { var fermer = parties.some(function (p) { return /psalm/i.test(p.dataset.nom || "") && p.open; }); parties.forEach(function (p) { if (/psalm/i.test(p.dataset.nom || "")) p.open = !fermer; }); psaumes.textContent = fermer ? "Déplier les psaumes" : "Replier les psaumes"; });
  var propre = $("#o-propre");
  function majPropre() { var on = propre && propre.checked; $$('details.partie[data-ord="1"]').forEach(function (p) { p.hidden = on; }); $$('#chips button[data-ord="1"]').forEach(function (b) { b.hidden = on; }); if (propre) LS.set("do.propre", on ? "1" : "0"); }
  if (propre) { propre.checked = LS.get("do.propre") === "1"; propre.addEventListener("change", majPropre); majPropre(); }
  var haut = $("#b-haut"); if (haut) haut.addEventListener("click", function () { window.scrollTo({ top: 0, behavior: "smooth" }); });

  // ---------- accueil ----------
  function accueil(d) {
    var aj = aujourdhui(), dates = d.dates, j = dates.indexOf(aj) >= 0 ? aj : (aj < dates[0] ? dates[0] : dates[dates.length - 1]), dispo = d.heures[j] || [];
    var H = ["matutinum", "laudes", "prima", "tertia", "sexta", "nona", "vesperae", "completorium"], hc2 = heureConseillee();
    var lib = d.titres && d.titres[j] || {};
    var f = function (x) { return new Date(x + "T12:00:00").toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long", year: "numeric" }); };
    $("#h-date").textContent = (j === aj ? "Aujourd’hui · " : "Dernier jour disponible · ") + f(j);
    $("#h-titre").textContent = lib.t || ""; $("#h-ecr").textContent = lib.e || ""; var cc = { green: "#2e7d32", red: "#c0262d", purple: "#6a3d9a", violet: "#6a3d9a", white: "#cfc7b0", blue: "#1c4fa0", black: "#222222", rose: "#d2698a", pink: "#d2698a", gold: "#c6a24e" }[lib.c || ""]; if (cc) $(".titre").style.setProperty("--c", cc);
    var m = $("#h-messe"); if (m) { m.href = R + "/jours/" + j + "/messe.html"; m.hidden = dispo.indexOf("messe") < 0; }
    var b = $("#h-breviaire"), cible = dispo.indexOf(hc2) >= 0 ? hc2 : (dispo.filter(function (x) { return x !== "messe"; })[0] || "laudes");
    if (b) { b.href = R + "/jours/" + j + "/" + cible + ".html"; var nom = { matutinum: "Matines", laudes: "Laudes", prima: "Prime", tertia: "Tierce", sexta: "Sexte", nona: "None", vesperae: "Vêpres", completorium: "Complies" }[cible]; $("#h-heure").textContent = "À cette heure : " + nom; }
    var hz = $("#h-heures"); if (hz) H.forEach(function (h) { var a = document.createElement("a"); if (dispo.indexOf(h) < 0) return; a.href = R + "/jours/" + j + "/" + h + ".html"; a.dataset.h = h; a.textContent = { matutinum: "Matines", laudes: "Laudes", prima: "Prime", tertia: "Tierce", sexta: "Sexte", nona: "None", vesperae: "Vêpres", completorium: "Complies" }[h]; if (h === hc2 && j === aj) a.className = "maintenant"; hz.appendChild(a); });
    var inp = $("#h-pick"); if (inp) { inp.min = dates[0]; inp.max = dates[dates.length - 1]; inp.value = j; inp.addEventListener("change", function () { if (dates.indexOf(inp.value) >= 0) location.href = R + "/jours/" + inp.value + "/" + ((d.heures[inp.value] || []).indexOf("messe") >= 0 ? "messe" : "laudes") + ".html"; }); }
  }
})();
