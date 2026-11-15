/* AIIS language support
 * ---------------------------------------------------------------
 * English is the source. Each language file (/i18n/<code>.json) maps the
 * English text the app shows to the same text in that language. Keys that
 * contain {0}, {1} are templates for text with numbers or names in it.
 *
 * The translator watches the page and swaps English text for the chosen
 * language as the app draws it, so app.js keeps working in English. Text it
 * has no translation for (hospital names, addresses, area names) stays as is.
 */
(function () {
  'use strict';

  var VERSION = '2026-11-14b';
  var LANGS = [
    { code: 'en', native: 'English', name: 'English', letter: 'A', word: 'Language', pick: 'Choose your language', chosen: 'English selected' },
    { code: 'hi', native: 'हिन्दी', name: 'Hindi', letter: 'अ', word: 'भाषा', pick: 'अपनी भाषा चुनें', chosen: 'हिन्दी चुनी गई' },
    { code: 'kn', native: 'ಕನ್ನಡ', name: 'Kannada', letter: 'ಕ', word: 'ಭಾಷೆ', pick: 'ನಿಮ್ಮ ಭಾಷೆ ಆಯ್ಕೆಮಾಡಿ', chosen: 'ಕನ್ನಡ ಆಯ್ಕೆಯಾಗಿದೆ' },
    { code: 'ta', native: 'தமிழ்', name: 'Tamil', letter: 'த', word: 'மொழி', pick: 'உங்கள் மொழியைத் தேர்ந்தெடுக்கவும்', chosen: 'தமிழ் தேர்ந்தெடுக்கப்பட்டது' },
    { code: 'te', native: 'తెలుగు', name: 'Telugu', letter: 'తె', word: 'భాష', pick: 'మీ భాషను ఎంచుకోండి', chosen: 'తెలుగు ఎంచుకోబడింది' },
    { code: 'ml', native: 'മലയാളം', name: 'Malayalam', letter: 'മ', word: 'ഭാഷ', pick: 'നിങ്ങളുടെ ഭാഷ തിരഞ്ഞെടുക്കുക', chosen: 'മലയാളം തിരഞ്ഞെടുത്തു' },
    { code: 'mr', native: 'मराठी', name: 'Marathi', letter: 'म', word: 'भाषा', pick: 'तुमची भाषा निवडा', chosen: 'मराठी निवडली' },
    { code: 'bn', native: 'বাংলা', name: 'Bengali', letter: 'বা', word: 'ভাষা', pick: 'আপনার ভাষা বেছে নিন', chosen: 'বাংলা বেছে নেওয়া হয়েছে' },
    { code: 'gu', native: 'ગુજરાતી', name: 'Gujarati', letter: 'ગુ', word: 'ભાષા', pick: 'તમારી ભાષા પસંદ કરો', chosen: 'ગુજરાતી પસંદ થઈ' },
    { code: 'or', native: 'ଓଡ଼ିଆ', name: 'Odia', letter: 'ଓ', word: 'ଭାଷା', pick: 'ଆପଣଙ୍କ ଭାଷା ବାଛନ୍ତୁ', chosen: 'ଓଡ଼ିଆ ବଛାଗଲା' },
    { code: 'ur', native: 'اردو', name: 'Urdu', letter: 'ار', word: 'زبان', pick: 'اپنی زبان منتخب کریں', chosen: 'اردو منتخب ہو گئی', rtl: true }
  ];
  var BY = {};
  LANGS.forEach(function (l) { BY[l.code] = l; });

  var KEY = 'aiis.lang';
  var CHOSEN = 'aiis.lang.chosen';
  var ls = {
    get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } }
  };

  /* ---------- Which language to start in ---------- */
  function fromUrl() {
    var m = /[?&]lang=([a-z]{2})\b/.exec(location.search) || /[?&]lang=([a-z]{2})\b/.exec(location.hash);
    return m && BY[m[1]] ? m[1] : null;
  }
  function fromBrowser() {
    var list = (navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language || 'en']);
    for (var i = 0; i < list.length; i++) {
      var c = String(list[i] || '').toLowerCase().split('-')[0];
      if (c === 'en') return null; // English first in the browser: keep English
      if (BY[c]) return c;
    }
    return null;
  }
  var urlLang = fromUrl();
  if (urlLang) { ls.set(KEY, urlLang); ls.set(CHOSEN, '1'); }
  var lang = urlLang || ls.get(KEY) || fromBrowser() || 'en';
  if (!BY[lang]) lang = 'en';

  /* ---------- Dictionaries ---------- */
  var dict = null;          // { english: translated }
  var templates = [];       // [regex, key]
  var cache = {};

  function esc(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }
  function prepare(d) {
    var t = [];
    Object.keys(d).forEach(function (k) {
      if (k.indexOf('{0}') < 0) return;
      var src = '^' + esc(k).replace(/\\\{(\d)\\\}/g, '(.+?)') + '$';
      t.push([new RegExp(src), k, k.replace(/\{\d\}/g, '').length]);
    });
    t.sort(function (a, b) { return b[2] - a[2]; });
    return t;
  }
  function useDict(code, d) {
    cache[code] = d;
    if (code !== lang) return;
    dict = d; templates = prepare(d);
  }
  function cached(code) {
    var raw = ls.get('aiis.i18n.' + code);
    if (!raw) return null;
    try { var o = JSON.parse(raw); return o && o.v === VERSION ? o.d : null; } catch (e) { return null; }
  }
  function load(code) {
    if (code === 'en') return Promise.resolve({});
    if (cache[code]) return Promise.resolve(cache[code]);
    var c = cached(code);
    if (c) { cache[code] = c; return Promise.resolve(c); }
    return fetch('/i18n/' + code + '.json?v=' + VERSION).then(function (r) {
      if (!r.ok) throw new Error('lang ' + r.status);
      return r.json();
    }).then(function (d) {
      ls.set('aiis.i18n.' + code, JSON.stringify({ v: VERSION, d: d }));
      cache[code] = d;
      return d;
    });
  }

  /* ---------- Translate one piece of text ---------- */
  var has = function (o, k) { return Object.prototype.hasOwnProperty.call(o, k); };
  function T(s, depth) {
    depth = depth || 0;
    if (!dict || !s) return null;
    if (has(dict, s)) return dict[s];
    var cap = s.charAt(0).toUpperCase() + s.slice(1);
    if (cap !== s && has(dict, cap)) return dict[cap];
    var colon = /^(.*\S)\s*:$/.exec(s);
    if (colon) { var tc = T(colon[1], depth + 1); if (tc != null) return tc + ':'; }
    if (depth < 3) {
      for (var i = 0; i < templates.length; i++) {
        var m = templates[i][0].exec(s);
        if (!m) continue;
        var fills = [], good = true;
        for (var k = 1; k < m.length; k++) {
          var tg = T(m[k], depth + 1);
          if (tg == null && !nameLike(m[k])) { good = false; break; }
          fills.push(tg != null ? tg : m[k]);
        }
        if (!good) continue;
        return dict[templates[i][1]].replace(/\{(\d)\}/g, function (_, n) { return fills[Number(n)] != null ? fills[Number(n)] : ''; });
      }
    }
    if (depth < 2 && s.indexOf(', ') > 0) {
      var any = false, bad = false;
      var parts = s.split(', ').map(function (p) {
        var tp = T(p, depth + 1);
        if (tp != null) { any = true; return tp; }
        if (!nameLike(p)) bad = true;
        return p;
      });
      if (any && !bad) return parts.join(BY[lang].rtl ? '، ' : ', ');
    }
    return null;
  }

  /* A value we may leave untranslated inside a sentence: a number, a name, a web address. */
  var SMALL = { of: 1, and: 1, the: 1, for: 1, on: 1, at: 1, in: 1, de: 1, da: 1, near: 1 };
  function nameLike(g) {
    g = String(g).trim();
    if (!g) return false;
    if (/\d/.test(g)) return true;
    if (!/[A-Za-z]/.test(g)) return true;            // already in another script
    if (/^\S+\.\S+$/.test(g) || g.indexOf('@') > 0) return true; // domain or email
    return g.split(/\s+/).every(function (w) {
      var c = w.replace(/^[^A-Za-z]+/, '');
      return !c || /^[A-Z]/.test(c) || SMALL[c.toLowerCase()];
    });
  }

  /* Used by app.js for whole sentences it builds itself (e.g. the WhatsApp message). */
  function t(template) {
    var args = Array.prototype.slice.call(arguments, 1);
    var out = (dict && has(dict, template)) ? dict[template] : template;
    return out.replace(/\{(\d)\}/g, function (_, n) { return args[Number(n)] != null ? String(args[Number(n)]) : ''; });
  }

  /* ---------- Walk the page ---------- */
  var SKIP = 'script,style,svg,noscript,textarea,code,[translate="no"],[data-i18n-skip]';
  var ATTRS = ['placeholder', 'aria-label', 'title', 'alt'];
  var TXT = new WeakMap();
  var ATT = new WeakMap();
  var LETTER = /[A-Za-z]/;

  function swap(raw) {
    if (lang === 'en' || !dict) return raw;
    var key = raw.replace(/\s+/g, ' ').trim();
    if (!LETTER.test(key)) return raw;
    var tr = T(key);
    if (tr == null) return raw;
    var lead = /^\s*/.exec(raw)[0], trail = /\s*$/.exec(raw)[0];
    return lead + tr + trail;
  }
  function doText(n) {
    var pe = n.parentElement;
    if (!pe || pe.closest(SKIP)) return;
    var v = n.nodeValue;
    var st = TXT.get(n);
    if (!st || v !== st.out) { st = { src: v, out: v }; TXT.set(n, st); }
    if (!LETTER.test(st.src)) return;
    var out = swap(st.src);
    st.out = out;
    if (out !== v) n.nodeValue = out;
  }
  function doAttr(el, a) {
    var v = el.getAttribute(a);
    if (v == null || el.closest(SKIP)) return;
    var m = ATT.get(el);
    if (!m) { m = {}; ATT.set(el, m); }
    var st = m[a];
    if (!st || v !== st.out) { st = { src: v, out: v }; m[a] = st; }
    var out = swap(st.src);
    st.out = out;
    if (out !== v) el.setAttribute(a, out);
  }
  function doMapLink(el) {
    var h = el.getAttribute('href');
    if (!h || h.indexOf('google.com/maps') < 0) return;
    try {
      var u = new URL(h, location.href);
      if (lang === 'en') u.searchParams.delete('hl'); else u.searchParams.set('hl', lang);
      var nh = u.toString();
      if (nh !== h) el.setAttribute('href', nh);
    } catch (e) { /* leave link as is */ }
  }
  function doEl(el) {
    if (el.closest && el.closest(SKIP)) return;
    for (var i = 0; i < ATTRS.length; i++) if (el.hasAttribute(ATTRS[i])) doAttr(el, ATTRS[i]);
    if (el.tagName === 'A') doMapLink(el);
  }
  function walk(root) {
    if (!root) return;
    if (root.nodeType === 3) { doText(root); return; }
    if (root.nodeType !== 1) return;
    if (root.matches && root.matches(SKIP)) return;
    doEl(root);
    var w = document.createTreeWalker(root, 5 /* elements + text */, {
      acceptNode: function (n) {
        if (n.nodeType === 1) return n.matches(SKIP) ? 2 /* reject subtree */ : 1;
        return 1;
      }
    });
    var n;
    while ((n = w.nextNode())) { if (n.nodeType === 3) doText(n); else doEl(n); }
  }

  var mo = new MutationObserver(function (list) {
    for (var i = 0; i < list.length; i++) {
      var r = list[i];
      if (r.type === 'childList') { for (var j = 0; j < r.addedNodes.length; j++) walk(r.addedNodes[j]); }
      else if (r.type === 'characterData') doText(r.target);
      else if (r.type === 'attributes') { if (r.attributeName === 'href') doMapLink(r.target); else doAttr(r.target, r.attributeName); }
    }
  });

  function applyDocLang() {
    var L = BY[lang];
    document.documentElement.lang = lang;
    document.documentElement.dir = L.rtl ? 'rtl' : 'ltr';
    document.documentElement.classList.toggle('lang-indic', lang !== 'en');
  }

  /* ---------- Speech: say the language name so people who cannot read can check ---------- */
  var voices = [];
  function loadVoices() { try { voices = window.speechSynthesis ? speechSynthesis.getVoices() : []; } catch (e) { voices = []; } }
  function voiceFor(code) {
    for (var i = 0; i < voices.length; i++) if (String(voices[i].lang || '').toLowerCase().split(/[-_]/)[0] === code) return voices[i];
    return null;
  }
  function canSpeak(code) { return !!(window.speechSynthesis && voiceFor(code)); }
  function say(text, code) {
    if (!window.speechSynthesis) return;
    var v = voiceFor(code);
    if (!v) return;
    try {
      speechSynthesis.cancel();
      var u = new SpeechSynthesisUtterance(text);
      u.voice = v; u.lang = v.lang; u.rate = 0.9;
      speechSynthesis.speak(u);
    } catch (e) { /* ignore */ }
  }
  if (window.speechSynthesis) {
    loadVoices();
    try { speechSynthesis.addEventListener('voiceschanged', function () { loadVoices(); paintPicker(); }); } catch (e) { /* old browsers */ }
  }

  /* ---------- Language button, first-visit strip and picker ---------- */
  var ORDER = ['en', 'hi', 'kn', 'ta', 'te', 'ml', 'mr', 'bn', 'gu', 'or', 'ur'];
  function ordered() {
    var first = fromBrowser();
    var o = ORDER.slice();
    if (first && first !== 'en') { o.splice(o.indexOf(first), 1); o.splice(1, 0, first); }
    return o.map(function (c) { return BY[c]; });
  }
  var GLYPH = '<span class="lang-glyph" aria-hidden="true">अ<b>A</b></span>';
  var SPEAK_IC = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M11 5 6 9H2v6h4l5 4V5z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M19 5a10 10 0 0 1 0 14"/></svg>';
  var ALL_WORDS = ['Language', 'भाषा', 'ಭಾಷೆ', 'மொழி', 'భాష', 'ഭാഷ', 'ভাষা', 'ભાષા', 'ଭାଷା', 'زبان'];

  function btnLabel() { return BY[lang].native; }
  function paintButton() {
    var b = document.getElementById('langBtn');
    if (!b) return;
    var lab = b.querySelector('.langbtn__lab');
    if (lab) lab.textContent = btnLabel();
    b.setAttribute('aria-label', 'Change language. ' + BY[lang].pick + '. ' + BY[lang].native);
  }
  function mountButton() {
    if (document.getElementById('langBtn')) return;
    var host = document.querySelector('.topbar__actions');
    if (!host) return;
    var b = document.createElement('button');
    b.type = 'button';
    b.id = 'langBtn';
    b.className = 'langbtn';
    b.setAttribute('translate', 'no');
    b.setAttribute('aria-haspopup', 'dialog');
    b.innerHTML = GLYPH + '<span class="langbtn__lab"></span><svg class="langbtn__caret" viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>';
    b.addEventListener('click', openPicker);
    host.insertBefore(b, host.firstChild);
    paintButton();
  }

  function mountStrip() {
    if (ls.get(CHOSEN) || document.getElementById('langStrip')) return;
    var top = document.querySelector('.topbar');
    if (!top) return;
    var s = document.createElement('div');
    s.id = 'langStrip';
    s.className = 'langstrip';
    s.setAttribute('translate', 'no');
    s.setAttribute('role', 'region');
    s.setAttribute('aria-label', BY[lang].pick);
    s.innerHTML = '<div class="langstrip__in">'
      + '<span class="langstrip__lab">' + GLYPH + '<span>' + ALL_WORDS.slice(0, 4).join(' · ') + '</span></span>'
      + '<div class="langstrip__list">' + ordered().map(function (L) {
        return '<button type="button" class="langchip" data-lang="' + L.code + '" lang="' + L.code + '" aria-pressed="' + (L.code === lang) + '">' + L.native + '</button>';
      }).join('') + '</div>'
      + '<button type="button" class="langstrip__all" data-open aria-label="' + BY[lang].pick + '">' + GLYPH + '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg></button>'
      + '<button type="button" class="langstrip__x" aria-label="' + t('Close') + '" data-close>&times;</button>'
      + '</div>';
    s.addEventListener('click', function (e) {
      var c = e.target.closest('[data-lang]');
      if (c) { choose(c.getAttribute('data-lang'), true); return; }
      if (e.target.closest('[data-open]')) { openPicker(); return; }
      if (e.target.closest('[data-close]')) { ls.set(CHOSEN, '1'); s.remove(); }
    });
    top.parentNode.insertBefore(s, top.nextSibling);
  }
  function paintStrip() {
    var s = document.getElementById('langStrip');
    if (!s) return;
    Array.prototype.forEach.call(s.querySelectorAll('[data-lang]'), function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-lang') === lang)); });
  }

  var dlg = null, lastFocus = null;
  function pickerHtml() {
    var L = BY[lang];
    return '<div class="langdlg__panel" role="dialog" aria-modal="true" aria-labelledby="langdlg-title">'
      + '<div class="langdlg__head">'
      + '<div><h2 id="langdlg-title" class="langdlg__title" lang="' + L.code + '">' + L.pick + '</h2>'
      + (lang !== 'en' ? '<p class="langdlg__sub">Choose your language</p>' : '')
      + '<p class="langdlg__words">' + ALL_WORDS.join(' · ') + '</p></div>'
      + '<button type="button" class="langdlg__x" data-close aria-label="' + t('Close') + '">&times;</button>'
      + '</div>'
      + '<ul class="langgrid">' + ordered().map(function (x) {
        var on = x.code === lang;
        var speak = x.code !== 'en' && canSpeak(x.code)
          ? '<button type="button" class="langtile__say" data-say="' + x.code + '" aria-label="Listen: ' + x.name + '">' + SPEAK_IC + '</button>' : '';
        return '<li class="langtile' + (on ? ' is-on' : '') + '">'
          + '<button type="button" class="langtile__main" data-lang="' + x.code + '" aria-pressed="' + on + '" lang="' + x.code + '"' + (x.rtl ? ' dir="rtl"' : '') + '>'
          + '<span class="langtile__letter" aria-hidden="true">' + x.letter + '</span>'
          + '<span class="langtile__txt"><b>' + x.native + '</b><small lang="en" dir="ltr">' + x.name + '</small></span>'
          + (on ? '<span class="langtile__tick" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M20 6 9 17l-5-5"/></svg></span>' : '')
          + '</button>' + speak + '</li>';
      }).join('') + '</ul>'
      + '<p class="langdlg__note">' + t('Hospital names and addresses stay in English, the way they appear on signboards and Google Maps.') + '</p>'
      + '</div>';
  }
  function paintPicker() {
    if (!dlg || !dlg.classList.contains('is-open')) return;
    dlg.innerHTML = '<div class="langdlg__backdrop" data-close></div>' + pickerHtml();
  }
  function openPicker() {
    if (!dlg) {
      dlg = document.createElement('div');
      dlg.className = 'langdlg';
      dlg.setAttribute('translate', 'no');
      dlg.addEventListener('click', function (e) {
        var say1 = e.target.closest('[data-say]');
        if (say1) { var L = BY[say1.getAttribute('data-say')]; say(L.native, L.code); return; }
        var c = e.target.closest('[data-lang]');
        if (c) { choose(c.getAttribute('data-lang'), true); closePicker(); return; }
        if (e.target.closest('[data-close]')) closePicker();
      });
      dlg.addEventListener('keydown', function (e) { if (e.key === 'Escape') closePicker(); });
      document.body.appendChild(dlg);
    }
    lastFocus = document.activeElement;
    dlg.classList.add('is-open');
    document.documentElement.classList.add('langdlg-open');
    paintPicker();
    var on = dlg.querySelector('.langtile.is-on .langtile__main') || dlg.querySelector('.langtile__main');
    if (on) setTimeout(function () { on.focus(); }, 30);
  }
  function closePicker() {
    if (!dlg) return;
    dlg.classList.remove('is-open');
    document.documentElement.classList.remove('langdlg-open');
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  /* ---------- Switch language ---------- */
  function choose(code, byUser) {
    if (!BY[code]) return;
    if (byUser) {
      ls.set(CHOSEN, '1');
      var s = document.getElementById('langStrip');
      if (s) s.remove();
      if (code !== 'en') say(BY[code].chosen, code);
    }
    ls.set(KEY, code);
    var prev = lang;
    lang = code;
    applyDocLang();
    paintButton(); paintStrip();
    return load(code).then(function (d) {
      if (lang !== code) return;
      if (code === 'en') { dict = null; templates = []; } else useDict(code, d);
      walk(document.documentElement);
      if (prev !== code && typeof window.AIIS_rerender === 'function') window.AIIS_rerender();
    }).catch(function () {
      lang = prev; ls.set(KEY, prev); applyDocLang(); paintButton(); paintStrip();
    });
  }

  /* ---------- Start ---------- */
  applyDocLang();
  var pre = lang === 'en' ? null : cached(lang);
  if (pre) useDict(lang, pre);
  mo.observe(document.documentElement, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS.concat(['href']) });
  function ready() {
    mountButton();
    mountStrip();
    walk(document.documentElement);
    if (lang !== 'en' && !pre) choose(lang, false);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ready); else ready();

  window.AIIS_I18N = {
    get lang() { return lang; },
    langs: LANGS,
    locale: function () { return (lang === 'en' ? 'en-IN' : lang + '-IN') + '-u-nu-latn'; },
    t: t,
    set: function (code) { return choose(code, true); },
    open: openPicker
  };
})();
