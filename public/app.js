/* AIIS patient platform: client app (vanilla JS, no build step, no dependencies).
   Talks to the API in server.js. Field names from the server are read through
   normalisers (norm, normRequest) so small differences in the real data files
   do not break the screens. */
(() => {
  'use strict';

  /* ---------- Helpers ---------- */
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const ic = (id, cls = '') => `<svg class="i ${cls}" aria-hidden="true"><use href="#i-${id}"/></svg>`;
  const pick = (...v) => v.find((x) => x !== undefined && x !== null && x !== '');
  const num = (v) => (v === undefined || v === null || v === '' || Number.isNaN(Number(v)) ? null : Number(v));
  const tel = (p) => 'tel:' + String(p || '').replace(/[^\d+]/g, '');
  // Directions open the hospital's own Google Maps listing (name + address). A raw lat,lng
  // snaps to the nearest building, which is how "Victoria Hospital" opened a different place.
  const mapsDir = (h) => {
    const raw = h && h.raw;
    if (raw && raw.directionsUrl) return raw.directionsUrl;
    if (h && h.directionsUrl) return h.directionsUrl;
    const q = [h && h.name, h && h.address].filter(Boolean).join(', ');
    if (q) return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(q)}&travelmode=driving`;
    return `https://www.google.com/maps/dir/?api=1&destination=${h.lat},${h.lng}`;
  };
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const store = {
    get(k, d) { try { const v = localStorage.getItem('aiis.' + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
    set(k, v) { try { localStorage.setItem('aiis.' + k, JSON.stringify(v)); } catch { /* storage unavailable */ } },
    del(k) { try { localStorage.removeItem('aiis.' + k); } catch { /* storage unavailable */ } }
  };

  async function api(path, body, extra) {
    const headers = { 'Content-Type': 'application/json', ...(extra || {}) };
    const auth = store.get('auth');
    const isCoord = path.indexOf('/api/coordination/') === 0;
    if (!isCoord && auth && auth.access_token && !headers.Authorization) {
      headers['Authorization'] = 'Bearer ' + auth.access_token;
    }
    const opts = body !== undefined
      ? { method: 'POST', headers, body: JSON.stringify(body) }
      : { method: 'GET', headers };
    let res;
    try { res = await fetch(path, opts); } catch { throw new Error('No connection. Check your internet and try again.'); }
    let data = {};
    try { data = await res.json(); } catch { /* empty body */ }
    if (!res.ok) {
      const errMsg = (data && (data.message || (typeof data.error === 'object' ? data.error.message : data.error)))
        || 'Something went wrong. Please try again.';
      const e = new Error(errMsg);
      e.status = res.status;
      throw e;
    }
    return data;
  }

  function ago(iso) {
    const t = new Date(iso).getTime();
    if (!t) return '';
    const s = Math.max(0, Math.round((Date.now() - t) / 1000));
    if (s < 60) return 'just now';
    const m = Math.round(s / 60);
    if (m < 60) return `${m} min ago`;
    const h = Math.round(m / 60);
    return h < 24 ? `${h} h ago` : new Date(t).toLocaleDateString(LOC(), { day: 'numeric', month: 'short' });
  }
  const LOC = () => (window.AIIS_I18N && window.AIIS_I18N.locale()) || 'en-IN';
  const TT = (tpl, ...a) => (window.AIIS_I18N ? window.AIIS_I18N.t(tpl, ...a) : tpl.replace(/\{(\d)\}/g, (_, i) => (a[i] == null ? '' : String(a[i]))));
  const dayMonth = (iso) => { const d = new Date(String(iso) + (String(iso).length === 10 ? 'T00:00:00' : '')); return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString(LOC(), { day: 'numeric', month: 'short', year: 'numeric' }); };
  const SCOPE_SHORT = { cardiac: 'Heart only', neuro: 'Brain and nerves only', trauma: 'Accidents and injuries', children: 'Children only', maternity: 'Pregnancy and newborns' };
  const mmss = (ms) => { const s = Math.max(0, Math.floor(ms / 1000)); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`; };
  function distKm(a, b, c, d) {
    const R = 6371, r = (x) => x * Math.PI / 180;
    const x = Math.sin(r(c - a) / 2) ** 2 + Math.cos(r(a)) * Math.cos(r(c)) * Math.sin(r(d - b) / 2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(x), Math.sqrt(1 - x));
  }
  const fmtDate = (iso) => { const d = new Date(iso + (String(iso).length === 10 ? 'T00:00:00' : '')); return Number.isNaN(d.getTime()) ? String(iso) : d.toLocaleDateString(LOC(), { weekday: 'short', day: 'numeric', month: 'short' }); };

  /* ---------- Content ---------- */
  const PHONES_CHECKED = '2026-11-14'; // date hospital pins and phone numbers were last checked
  const CATEGORIES = [
    { id: 'general', label: 'Any emergency', icon: 'grid' },
    { id: 'cardiac', label: 'Chest pain or heart', icon: 'heart' },
    { id: 'stroke', label: 'Stroke signs', icon: 'brain' },
    { id: 'trauma', label: 'Accident or injury', icon: 'band' },
    { id: 'breathing', label: 'Breathing trouble', icon: 'wind' },
    { id: 'child', label: 'Child emergency', icon: 'baby' },
    { id: 'burns', label: 'Burns', icon: 'flame' }
  ];

  const NEEDS = [
    { id: 'specialist', title: 'See a specialist doctor', sub: 'Heart, bones, skin, children and more', icon: 'steth', next: 2 },
    { id: 'consult', title: 'General check-up', sub: 'Fever, cough, a routine visit', icon: 'user', specialty: 'general medicine', label: 'General physician', next: 3 },
    { id: 'tests', title: 'Tests and scans', sub: 'Blood tests, X-ray, CT, MRI', icon: 'tube', specialty: 'diagnostics', label: 'Tests and scans', next: 3 },
    { id: 'procedure', title: 'Planned surgery or procedure', sub: 'Choose the type of care next', icon: 'clip', next: 2 },
    { id: 'hospital', title: 'Find a hospital by name', sub: 'Search any hospital near you', icon: 'hosp', next: 3, search: true }
  ];

  const SPECIALTIES = [
    { key: 'cardiology', label: 'Heart', term: 'Cardiology', icon: 'heart' },
    { key: 'oncology', label: 'Cancer care', term: 'Oncology', icon: 'ribbon' },
    { key: 'orthopaedics', label: 'Bones and joints', term: 'Orthopaedics', icon: 'bone' },
    { key: 'neurology', label: 'Brain and nerves', term: 'Neurology', icon: 'brain' },
    { key: 'dermatology', label: 'Skin, hair and nails', term: 'Dermatology', icon: 'face' },
    { key: 'paediatrics', label: 'Children', term: 'Paediatrics', icon: 'baby' },
    { key: 'obstetrics', label: "Women's health and pregnancy", term: 'Obstetrics and Gynaecology', icon: 'venus' },
    { key: 'general medicine', label: 'General physician', term: 'General Medicine', icon: 'steth' }
  ];

  const SLOTS = [
    { id: 'Morning', hint: '9 to 12' },
    { id: 'Afternoon', hint: '12 to 4' },
    { id: 'Evening', hint: '4 to 8' }
  ];

  const STATUS = {
    REQUEST_SUBMITTED: { step: 0, title: 'Request sent', live: 'Request sent' },
    AWAITING_HOSPITAL_RESPONSE: { step: 1, title: 'The hospital is checking', live: 'Hospital is checking' },
    HOSPITAL_ACCEPTED: { step: 2, title: 'The hospital is expecting you', live: 'Bed held for you' },
    ARRIVAL_VERIFICATION_PENDING: { step: 2, title: 'Show your code at the desk', live: 'Bed held for you' },
    PATIENT_ARRIVED: { step: 3, title: 'You have arrived', live: 'Arrived', done: true },
    CANCELLED: { step: -1, title: 'Request cancelled', done: true },
    EXPIRED: { step: -1, title: 'The bed hold has ended', done: true }
  };
  const STEPS = [
    { t: 'Request sent', s: 'Your details reached the casualty desk' },
    { t: 'Hospital is checking', s: 'Staff look at free beds and doctors on duty' },
    { t: 'Bed held for you', s: 'Travel now and show your code at the desk' },
    { t: 'You have arrived', s: 'Desk staff confirm you with the code' }
  ];

  /* ---------- State ---------- */
  const DEFAULT_LOC = { name: 'Bengaluru Central', lat: 12.9716, lng: 77.5946, source: 'default' };
  const S = {
    loc: store.get('loc', null) || DEFAULT_LOC,
    locating: false,
    triedGeo: false,
    locations: [],
    category: 'general',
    em: { status: 'idle', list: [], at: 0, key: '' },
    plan: { step: 1, need: null, specialty: '', label: '', sector: 'any', query: '', search: false, results: [], status: 'idle' },
    profile: store.get('profile', {}),
    auth: store.get('auth', null),
    authMode: 'signin',
    appts: store.get('appts', []),
    coordId: store.get('coord', null),
    coord: null,
    hosp: new Map(),
    staff: { id: store.get('staffHospital', null), list: [], draft: null, status: 'idle' },
    timers: []
  };

  /* ---------- Normalisers ---------- */
  function beds(v) {
    if (v == null) return { a: null, t: null };
    if (typeof v === 'number') return { a: v, t: null };
    return { a: num(pick(v.available, v.free, v.vacant, v.count)), t: num(pick(v.total, v.capacity, v.max)) };
  }
  function norm(raw) {
    const h = raw && raw.hospital ? { ...raw.hospital, ...raw } : (raw || {});
    if (h.directionsUrl === undefined && raw && raw.raw && raw.raw.directionsUrl) h.directionsUrl = raw.raw.directionsUrl;
    const c = h.capacity || h.beds || h.liveCapacity || {};
    const er = beds(pick(c.emergencyBeds, c.emergency, c.er, c.casualty, h.emergencyBeds));
    if (er.a == null) er.a = num(pick(c.emergencyBedsAvailable, h.emergencyBedsAvailable, h.availableEmergencyBeds));
    const icu = beds(pick(c.icuBeds, c.icu, h.icuBeds));
    if (icu.a == null) icu.a = num(pick(c.icuBedsAvailable, h.icuBedsAvailable, h.availableIcuBeds));
    const coords = h.coordinates || h.location || {};
    const listOf = (v) => (Array.isArray(v) ? v : v && typeof v === 'object' ? Object.entries(v).map(([name, status]) => ({ name, status })) : []);
    const fac = listOf(pick(h.emergencyFacilities, h.facilities, h.emergencyServices, h.capabilities))
      .map((x) => (typeof x === 'string' ? x : pick(x.name, x.label)))
      .filter(Boolean);
    let why = pick(h.rationale, h.rankingRationale, h.whyRanked, h.reasons, h.explanation, h.rankReasons);
    if (typeof why === 'string') why = [why];
    const fresh = h.dataFreshness || {};
    return {
      id: h.id == null ? h.id : String(h.id),
      name: pick(h.name, 'Hospital'),
      campus: h.campus,
      type: h.type,
      sector: h.sector,
      zone: h.zone,
      address: h.address,
      lat: num(pick(coords.latitude, coords.lat, h.latitude)),
      lng: num(pick(coords.longitude, coords.lng, coords.lon, h.longitude)),
      phoneEm: pick(h.emergencyPhone, h.casualtyPhone, h.phone, h.receptionPhone),
      phoneRec: pick(h.receptionPhone, h.phone, h.emergencyPhone),
      distanceKm: num(pick(h.distanceKm, h.distance)),
      transitMins: num(pick(h.transitMins, h.transitMinutes, h.etaMinutes, h.travelMinutes)),
      er, icu,
      holds: num(pick(c.provisionalHolds, c.holds, h.provisionalHolds)),
      facilities: fac,
      departments: listOf(pick(h.departments, h.departmentReadiness)).map((d) => (typeof d === 'string' ? { name: d } : d)),
      equipment: listOf(pick(h.equipment, h.equipmentAvailability)).map((d) => (typeof d === 'string' ? { name: d } : d)),
      why: Array.isArray(why) ? why.map((w) => (typeof w === 'string' ? w : pick(w.text, w.reason, w.label))).filter(Boolean) : [],
      services: listOf(pick(h.matchedServices, h.plannedServices, h.allServices)),
      allServices: listOf(pick(h.allServices, h.plannedServices)),
      updated: pick(fresh.lastUpdated, fresh.updatedAt, h.lastUpdated, h.updatedAt),
      demo: Boolean(fresh.isSimulated || /demo|simulat/i.test(String(pick(fresh.source, '')))),
      phoneLabel: pick(h.emergencyPhoneLabel, 'Emergency'),
      recLabel: pick(h.receptionPhoneLabel, 'Hospital'),
      phones: Array.isArray(h.phones) ? h.phones.filter((x) => x && x.number) : [],
      listed: h.phoneStatus === 'listing',
      source: h.source || null,
      website: h.website || null,
      partner: Boolean(h.partner),
      scope: pick(h.emergencyScope, 'general'),
      scopeNote: h.scopeNote || '',
      live: er.a != null || icu.a != null,
      noPhone: h.noPhoneNote || null,
      locVerified: Boolean(h.locationVerified),
      checked: pick(fresh.phonesChecked, null),
      raw: h
    };
  }
  function normLoc(l) {
    const c = l.coordinates || {};
    return { name: pick(l.name, l.label, l.zone, 'Area'), lat: num(pick(l.latitude, l.lat, c.latitude)), lng: num(pick(l.longitude, l.lng, l.lon, c.longitude)) };
  }
  // Tracking token and arrival code for each request, kept only on this phone.
  const passes = () => store.get('passes', {});
  const passOf = (id) => (id && passes()[id]) || {};
  const savePass = (id, p) => { const all = passes(); all[id] = { ...(all[id] || {}), ...p }; store.set('passes', all); };
  const trackHdr = (id) => { const t = passOf(id).token; return t ? { 'X-Tracking-Token': t } : {}; };

  function normRequest(r) {
    if (!r) return null;
    const created = new Date(pick(r.createdAt, r.requestedAt, Date.now())).getTime();
    const travel = num(pick(r.estimatedTravelMinutes, r.travelMinutes)) || 15;
    const hold = pick(r.holdExpiresAt, r.provisionalHold && r.provisionalHold.expiresAt, r.expiresAt);
    const hid = r.hospitalId == null ? null : String(r.hospitalId);
    const known = S.hosp.get(hid) || S.em.list.find((h) => h.id === hid);
    return {
      id: r.id || r.requestId,
      status: pick(r.status, 'REQUEST_SUBMITTED'),
      otp: String(pick(r.otp, r.arrivalOtp, r.arrival_otp, r.verificationCode, r.pass && r.pass.otp, passOf(r.id || r.requestId).otp, '')),
      hospitalId: r.hospitalId,
      hospitalName: pick(r.hospitalName, known && known.name, 'Hospital'),
      address: pick(r.hospitalAddress, known && known.address, ''),
      phone: pick(r.emergencyPhone, r.hospitalPhone, known && known.phoneEm),
      lat: known ? known.lat : null,
      lng: known ? known.lng : null,
      created,
      expires: hold ? new Date(hold).getTime() : created + (travel + 15) * 60000,
      raw: r
    };
  }

  /* ---------- DOM refs ---------- */
  const main = $('#main');
  const sheet = $('#sheet');
  const panel = $('.sheet__panel', sheet);
  const sheetBody = $('#sheet-body');
  const toastEl = $('#toast');

  /* ---------- Toast ---------- */
  let toastT;
  function toast(msg) {
    toastEl.textContent = msg;
    toastEl.classList.add('is-on');
    clearTimeout(toastT);
    toastT = setTimeout(() => toastEl.classList.remove('is-on'), 2800);
  }

  /* ---------- Sheet (bottom sheet on phones, side panel on desktop) ---------- */
  let lastFocus = null;
  function openSheet(html) {
    lastFocus = document.activeElement;
    sheetBody.innerHTML = html;
    sheetBody.scrollTop = 0;
    sheet.setAttribute('aria-hidden', 'false');
    panel.style.transform = '';
    requestAnimationFrame(() => sheet.classList.add('is-open'));
    document.documentElement.style.overflow = 'hidden';
    setTimeout(() => {
      const f = $('[autofocus]', sheetBody) || $('.sheet__close', sheet);
      if (f) f.focus({ preventScroll: true });
    }, 80);
  }
  function closeSheet() {
    if (!sheet.classList.contains('is-open')) return;
    panel.style.transform = '';
    sheet.classList.remove('is-open', 'is-dragging');
    sheet.setAttribute('aria-hidden', 'true');
    document.documentElement.style.overflow = '';
    if (lastFocus && lastFocus.focus && document.contains(lastFocus)) lastFocus.focus({ preventScroll: true });
  }
  (function dragToClose() {
    const grab = $('[data-grab]', sheet);
    let y0 = 0, dy = 0, t0 = 0, dragging = false;
    grab.addEventListener('pointerdown', (e) => { dragging = true; y0 = e.clientY; dy = 0; t0 = performance.now(); grab.setPointerCapture(e.pointerId); sheet.classList.add('is-dragging'); });
    grab.addEventListener('pointermove', (e) => { if (!dragging) return; dy = Math.max(0, e.clientY - y0); panel.style.transform = `translateY(${dy}px)`; });
    const end = () => {
      if (!dragging) return;
      dragging = false;
      sheet.classList.remove('is-dragging');
      const v = dy / Math.max(1, performance.now() - t0);
      if (dy > 110 || v > 0.6) closeSheet(); else panel.style.transform = '';
    };
    grab.addEventListener('pointerup', end);
    grab.addEventListener('pointercancel', end);
  })();
  document.addEventListener('keydown', (e) => {
    if (!sheet.classList.contains('is-open')) return;
    if (e.key === 'Escape') { closeSheet(); return; }
    if (e.key === 'Tab') {
      const f = $$('a[href], button:not([disabled]), input, select, textarea', panel).filter((x) => x.offsetParent !== null);
      if (!f.length) return;
      const first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  });

  /* ---------- Timers ---------- */
  function clearTimers() { S.timers.forEach((t) => { clearTimeout(t); clearInterval(t); }); S.timers = []; }
  setInterval(() => {
    $$('[data-countdown]').forEach((el) => { el.textContent = mmss(Number(el.dataset.countdown) - Date.now()); });
    $$('[data-ring]').forEach((el) => {
      const end = Number(el.dataset.ring), start = Number(el.dataset.start), c = Number(el.dataset.c);
      const f = Math.max(0, Math.min(1, (end - Date.now()) / Math.max(1, end - start)));
      el.style.strokeDashoffset = String(c * (1 - f));
      el.style.stroke = f < 0.2 ? 'var(--em)' : '';
    });
  }, 1000);

  /* ---------- Shared bits ---------- */
  const activeCoord = () => (S.coord && !(STATUS[S.coord.status] || {}).done ? S.coord : null);

  function liveStrip() {
    const c = activeCoord();
    if (!c) return '';
    const st = STATUS[c.status] || STATUS.REQUEST_SUBMITTED;
    return `<a class="live" href="#/request/${esc(c.id)}">
      <span class="live__dot" aria-hidden="true"></span>
      <span class="live__txt"><b>${esc(st.live)}</b><span>${esc(c.hospitalName)}</span></span>
      <span class="live__time" data-countdown="${c.expires}" aria-label="Time left on bed hold">${mmss(c.expires - Date.now())}</span>
      ${ic('right')}
    </a>`;
  }

  function bedMetric(b, label) {
    if (b.a == null) return `<div class="metric"><div class="metric__val">?</div><div class="metric__lab">${label}: not reported</div></div>`;
    const cls = b.a >= 3 ? 'metric--ok' : b.a >= 1 ? 'metric--low' : 'metric--none';
    return `<div class="metric ${cls}"><div class="metric__val">${b.a}${b.t ? `<small>of ${b.t}</small>` : ''}</div><div class="metric__lab">${label}</div></div>`;
  }
  function bedLine(b, kind) {
    if (b.a == null) return `<span>${kind} beds: <b>not reported</b></span>`;
    const cls = b.a >= 3 ? 'ok' : b.a >= 1 ? 'low' : 'none';
    const word = b.a === 0 ? 'No' : String(b.a);
    return `<span><b class="${cls}">${word} free</b> ${kind} ${b.a === 1 ? 'bed' : 'beds'}${b.t ? ` <span class="muted">(of ${b.t})</span>` : ''}</span>`;
  }
  function scopeLine(h) {
    if (h.scope && h.scope !== 'general') return `<li class="facts__warn">${ic('info')}<span><b>${esc(h.scopeNote || SCOPE_SHORT[h.scope] || 'Specialty hospital')}</b></span></li>`;
    return `<li>${ic('check')}<span>${esc(h.scopeNote || '24x7 emergency')}</span></li>`;
  }
  function facts(h) {
    return `<ul class="facts">
      <li>${ic('clock')}<span><b>${h.transitMins != null ? 'About ' + h.transitMins + ' min' : 'Travel time unknown'}</b>${h.distanceKm != null ? ` away, ${h.distanceKm} km` : ''}</span></li>
      ${scopeLine(h)}
      ${h.live
        ? `<li>${ic('bed')}${bedLine(h.er, 'emergency')}</li>${h.icu.a != null ? `<li>${ic('bed')}${bedLine(h.icu, 'ICU')}</li>` : ''}${h.demo ? `<li class="facts__note">${ic('info')}<span>Sample bed numbers. Call the hospital to confirm.</span></li>` : ''}`
        : `<li>${ic('bed')}<span>Free beds: <b>call to check</b></span></li>`}
      ${h.phoneEm ? `<li>${ic('phone')}<span>${esc(h.phoneLabel)}: <a class="linkbtn" href="${tel(h.phoneEm)}"><b>${esc(h.phoneEm)}</b></a></span></li>` : `<li class="facts__warn">${ic('info')}<span>No verified phone number. Call 108 for an ambulance.</span></li>`}
      ${h.listed ? `<li class="facts__note">${ic('info')}<span>Number from a public list. If no one answers, call 108.</span></li>` : ''}
    </ul>`;
  }
  const locText = () => (S.loc.source === 'gps' ? 'Near your location' : 'Near ' + S.loc.name);
  function footer() {
    return `<footer class="foot">
      <p><b>AIIS does not replace emergency services.</b> If a life is at risk, call 108 or 112 first. Hospital locations and phone numbers checked ${esc(dayMonth(PHONES_CHECKED))} against each hospital's website and Google Maps listing. Bed numbers can change fast, so call before you go if you can.</p>
      <p>For hospital staff: <a href="#/hospital">Update beds</a></p>
      ${window.AIISNative ? '<p><button class="link" data-action="shake-settings">Shake for help settings</button></p>' : ''}
    </footer>`;
  }
  const metaLine = (h) => [h.type, h.sector, h.zone || h.campus].filter(Boolean).join(', ');

  function skeleton(n = 3) {
    return Array.from({ length: n }, () => `<div class="skel" aria-hidden="true"><i style="width:62%;height:20px"></i><i style="width:40%"></i><i style="height:64px;border-radius:16px"></i><i style="width:80%"></i></div>`).join('') + '<p class="sr" role="status">Loading hospitals</p>';
  }
  function errorBox(msg, retry) {
    return `<div class="empty" role="alert">
      <h3 class="h3">Could not load hospitals</h3>
      <p class="small">${esc(msg)}</p>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <button class="btn btn--ink btn--sm" data-action="${retry}">Try again</button>
        <a class="btn btn--em btn--sm" href="tel:108">${ic('phone')}Call 108</a>
      </div>
    </div>`;
  }

  /* ---------- Data loading ---------- */
  const emKey = () => `${S.loc.lat},${S.loc.lng}`;
  async function loadEmergency(force) {
    if (!force && S.em.status === 'ok' && S.em.key === emKey() && Date.now() - S.em.at < 60000) { paintEm(); return; }
    S.em.status = 'loading';
    paintEm();
    try {
      const d = await api('/api/emergency/search', { latitude: S.loc.lat, longitude: S.loc.lng, category: 'general', locationName: S.loc.name });
      S.em.list = (d.rankedHospitals || d.results || d.hospitals || []).map(norm);
      S.em.list.forEach((h) => { if (!S.hosp.has(h.id)) S.hosp.set(h.id, h); });
      S.em.status = 'ok'; S.em.at = Date.now(); S.em.key = emKey();
    } catch (e) {
      S.em.status = 'error'; S.em.error = e.message;
    }
    paintEm();
  }

  async function loadLocations() {
    try {
      const d = await api('/api/locations');
      S.locations = (d.locations || []).map(normLoc).filter((l) => l.lat != null);
    } catch { S.locations = []; }
  }

  async function loadCoord() {
    if (!S.coordId) { S.coord = null; return null; }
    try {
      const d = await api('/api/coordination/' + encodeURIComponent(S.coordId), undefined, trackHdr(S.coordId));
      S.coord = normRequest(d.request || d);
    } catch (e) {
      if (e.status === 404) { S.coordId = null; store.del('coord'); S.coord = null; }
    }
    return S.coord;
  }

  function nearestArea(lat, lng) {
    let best = null, bd = Infinity;
    S.locations.forEach((l) => { const d = distKm(lat, lng, l.lat, l.lng); if (d < bd) { bd = d; best = l; } });
    return best && bd < 25 ? String(best.name).replace(/^Bengaluru - /, '').replace(/\s*\(.*\)$/, '') : null;
  }

  /* ---------- Precise live location ----------
     Uses the phone's GPS (enableHighAccuracy, no cached fixes), shows the first fix at once,
     keeps refining while accuracy improves, and keeps following the user while the emergency
     screens are open (re-ranking hospitals after a real move). No IP-based guessing. */
  const GEO = { watch: null, timer: null, best: null, lastSearch: null, startedAt: 0 };
  const fmtAcc = (m) => (m == null ? '' : m < 1000 ? `±${Math.round(m)} m` : `±${(m / 1000).toFixed(1)} km`);
  const metersBetween = (a, b) => distKm(a.lat, a.lng, b.lat, b.lng) * 1000;

  function stopGeo() {
    if (GEO.watch != null && navigator.geolocation) navigator.geolocation.clearWatch(GEO.watch);
    GEO.watch = null; clearTimeout(GEO.timer); GEO.timer = null;
    if (S.locating) { S.locating = false; paintLocBtn(); }
  }

  function applyFix(pos, manual) {
    const { latitude: lat, longitude: lng, accuracy } = pos.coords;
    const area = nearestArea(lat, lng);
    const prev = S.loc && S.loc.source === 'gps' ? S.loc : null;
    S.loc = { name: area ? `Your location, near ${area}` : 'Your current location', lat, lng, source: 'gps', acc: accuracy, at: pos.timestamp || Date.now() };
    store.set('loc', S.loc);
    S.geo = { state: 'ok' };
    if (sheet.classList.contains('is-open') && $('#loc-list', sheetBody)) closeSheet();
    paintLocBtn();
    if (S.plan.step === 3 && route().r === 'planned') render(true);
    // Re-rank only on the first fix or after a real move (> 150 m), not on every tiny GPS jitter.
    if (!GEO.lastSearch || metersBetween(GEO.lastSearch, S.loc) > 150 || !prev) {
      GEO.lastSearch = { lat, lng };
      loadEmergency(true);
      if (manual) toast(`Location found (${fmtAcc(accuracy)})`);
    }
  }

  function locate(manual) {
    if (!('geolocation' in navigator)) {
      S.geo = { state: 'unsupported' }; paintLocBtn();
      if (manual) toast('This browser cannot share your location. Choose your area instead.');
      return;
    }
    if (window.isSecureContext === false) {
      S.geo = { state: 'insecure' }; paintLocBtn();
      return;
    }
    stopGeo();
    GEO.best = null; GEO.startedAt = Date.now(); GEO.lastSearch = null;
    S.locating = true; S.geo = { state: 'locating' }; paintLocBtn();

    GEO.watch = navigator.geolocation.watchPosition((pos) => {
      const better = !GEO.best || pos.coords.accuracy <= GEO.best.coords.accuracy;
      if (better) GEO.best = pos;
      const moved = S.loc && S.loc.source === 'gps' && metersBetween(S.loc, { lat: pos.coords.latitude, lng: pos.coords.longitude }) > 150;
      if (better || moved) applyFix(better ? pos : pos, manual && !S.loc.acc);
      // Stop the "finding" state once accuracy is good (≤ 30 m) or after 15 s; keep following movement.
      if (S.locating && (GEO.best.coords.accuracy <= 30 || Date.now() - GEO.startedAt > 15000)) { S.locating = false; paintLocBtn(); }
    }, (err) => {
      S.locating = false;
      if (err.code === 1) {
        S.geo = { state: 'denied' };
        stopGeo();
        if (manual) toast('Location is blocked. Allow it in your browser settings, or choose your area.');
      } else if (!GEO.best) {
        S.geo = { state: 'error' };
        if (manual) toast('Could not get a GPS fix. Move near a window or outdoors and try again.');
      }
      paintLocBtn();
    }, { enableHighAccuracy: true, maximumAge: 0, timeout: 20000 });

    // Battery guard: stop following after 10 minutes; the user can tap "Update" any time.
    GEO.timer = setTimeout(stopGeo, 10 * 60 * 1000);
  }

  // Start automatically when permission is already granted (no surprise prompts on Home).
  async function autoLocate(promptIfNeeded) {
    if (!('geolocation' in navigator)) return;
    try {
      if (navigator.permissions && navigator.permissions.query) {
        const st = await navigator.permissions.query({ name: 'geolocation' });
        if (st.state === 'granted' || (promptIfNeeded && st.state === 'prompt')) locate(false);
        else if (st.state === 'denied') { S.geo = { state: 'denied' }; paintLocBtn(); }
        return;
      }
    } catch { /* permissions API not available */ }
    if (promptIfNeeded) locate(false);
  }

  /* ---------- Router ---------- */
  const route = () => { const [r, ...rest] = location.hash.replace(/^#\/?/, '').split('/'); return { r: r || '', arg: decodeURIComponent(rest.join('/')) }; };
  const NAV_OF = { '': 'home', emergency: 'emergency', request: 'emergency', planned: 'planned', me: 'me', signin: 'signin', login: 'signin' };
  const VIEWS = { '': viewHome, emergency: viewEmergency, request: viewRequest, planned: viewPlanned, me: viewMe, hospital: viewStaff, sri: viewSri, signin: viewSignIn, login: viewSignIn };
  let lastRoute = null;

  function render(soft) {
    clearTimers();
    const { r, arg } = route();
    const view = VIEWS[r] || viewHome;
    const changed = lastRoute !== r + '/' + arg;
    lastRoute = r + '/' + arg;
    main.innerHTML = view(arg);
    if (!soft || changed) {
      main.classList.remove('enter');
      if (!reduceMotion) { void main.offsetWidth; main.classList.add('enter'); }
      if (changed) window.scrollTo(0, 0);
    }
    const mount = MOUNTS[r];
    if (mount) mount(arg);
    paintNav(NAV_OF[r]);
    observeReveals();
    const titles = { '': 'Find hospital care fast', emergency: 'Emergency care near you', request: 'Your hospital request', planned: 'Book a doctor visit', me: 'My requests', hospital: 'Hospital capacity', sri: 'Strain Risk Index', signin: 'Patient Sign In', login: 'Patient Sign In' };
    document.title = `AIIS: ${titles[r] || titles['']}`;
  }
  window.AIIS_rerender = () => render(true);

  function paintNav(active) {
    $$('[data-nav]').forEach((a) => { if (a.dataset.nav === active) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
    const navBtn = $('#navSignIn');
    if (navBtn) {
      const lab = $('.acct__label', navBtn);
      const u = S.auth && S.auth.user;
      if (lab) lab.textContent = u ? (String(u.full_name || 'Account').split(' ')[0]) : 'Sign in';
      navBtn.classList.toggle('acct--in', Boolean(u));
      navBtn.setAttribute('aria-label', u ? `Signed in as ${u.full_name || u.email || 'patient'}` : 'Patient sign in (optional)');
    }
  }

  let io;
  function observeReveals() {
    const els = $$('.reveal:not(.in)');
    if (reduceMotion || !('IntersectionObserver' in window)) { els.forEach((e) => e.classList.add('in')); return; }
    if (!io) io = new IntersectionObserver((entries) => entries.forEach((en) => { if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); } }), { rootMargin: '0px 0px -8% 0px', threshold: 0.05 });
    els.forEach((e) => io.observe(e));
  }

  /* ================================================================
     HOME
     ================================================================ */
  function viewHome() {
    return `<div class="wrap">
      ${liveStrip()}
      <section class="home-top">
        <h1 class="h1">Need a hospital?</h1>
        <div class="bigchoices">
          <a class="bigchoice bigchoice--em" href="#/emergency">
            <span class="bigchoice__icon">${ic('siren')}</span>
            <b>Emergency</b>
            <span>Find a hospital or call an ambulance now</span>
          </a>
          <a class="bigchoice" href="#/planned">
            <span class="bigchoice__icon">${ic('calendar')}</span>
            <b>Not an emergency</b>
            <span>Book a doctor visit</span>
          </a>
        </div>
      </section>
      ${footer()}
    </div>`;
  }

  function nearestCard(h) {
    return `<div class="card">
      <h3 class="card__title">${esc(h.name)}</h3>
      <p class="small">${esc(metaLine(h))}</p>
      ${facts(h)}
      <div class="actions">
        ${h.phoneEm ? `<a class="btn btn--go" href="${tel(h.phoneEm)}">${ic('phone')}Call hospital</a>` : `<a class="btn btn--em" href="tel:108">${ic('phone')}Call 108</a>`}
        <a class="btn btn--line" href="${mapsDir(h)}" target="_blank" rel="noopener">${ic('nav')}Directions</a>
      </div>
      <a class="link more-link" href="#/emergency">See all nearby hospitals ${ic('right', 'i-sm')}</a>
    </div>`;
  }

  function nearbyRow(h) {
    const er = h.er.a;
    return `<li class="row">
      <button class="row__main" data-action="details" data-id="${esc(h.id)}">
        <div class="row__name">${esc(h.name)}</div>
        <div class="row__meta">
          ${h.transitMins != null ? `<span>${ic('clock')}${h.transitMins} min</span>` : ''}
          ${h.scope !== 'general' ? `<span class="row__tag">${esc(SCOPE_SHORT[h.scope] || 'Specialty')}</span>` : `<span>${ic('check')}24x7 emergency</span>`}
          ${er != null ? `<span>${ic('bed')}${er === 0 ? 'No emergency beds free' : `${er} emergency ${er === 1 ? 'bed' : 'beds'} free`}</span>` : ''}
        </div>
      </button>
      ${h.phoneEm ? `<a class="row__call" href="${tel(h.phoneEm)}" aria-label="Call ${esc(h.name)}">${ic('phone')}</a>` : `<a class="row__call row__call--em" href="tel:108" aria-label="No verified number for ${esc(h.name)}. Call 108">108</a>`}
    </li>`;
  }

  /* ================================================================
     EMERGENCY
     ================================================================ */
  function viewEmergency() {
    return `<div class="wrap">
      ${liveStrip()}
      <h1 class="h1 page-title">Emergency</h1>
      <div id="locbox">${locBox()}</div>
      <div class="ambulance">
        <p>If a life is at risk, call an ambulance first.</p>
        <a class="btn btn--em btn--block btn--big" href="tel:108">${ic('amb')}Call ambulance 108</a>
      </div>
      <div id="em-results" aria-live="polite">${skeleton(3)}</div>
      ${footer()}
    </div>`;
  }

  function locBox() {
    const g = S.geo || {};
    if (S.locating) {
      const acc = S.loc && S.loc.source === 'gps' && S.loc.acc ? ` <span class="muted">(${fmtAcc(S.loc.acc)} so far)</span>` : '';
      return `<div class="locbox"><span class="locbox__txt"><span class="pulse" aria-hidden="true"></span>Finding your exact location${acc}</span></div>`;
    }
    if (S.loc.source === 'gps') {
      const acc = S.loc.acc ? `<small class="locbox__acc">GPS ${fmtAcc(S.loc.acc)}${GEO.watch != null ? ' · live' : ''}</small>` : '';
      return `<div class="locbox">${ic('pin')}<span class="locbox__info"><span>${esc(S.loc.name)}</span>${acc}</span><button class="link" data-action="locate">Update</button><button class="link" data-action="pick-location">Change</button></div>`;
    }
    if (g.state === 'denied') {
      return `<div class="locbox locbox--ask">
        <p>${ic('pin')}<span><b>Location is blocked for this site.</b> To see the hospitals closest to you, allow location: tap the lock or settings icon next to the web address, set Location to <b>Allow</b>, then tap Try again.</span></p>
        <div class="actions"><button class="btn btn--blue" data-action="locate">${ic('locate')}Try again</button><button class="btn btn--line" data-action="pick-location">Choose area</button></div>
      </div>`;
    }
    const why = g.state === 'error' ? 'Could not get a GPS fix. Move near a window or outdoors and try again.'
      : g.state === 'insecure' ? 'Location needs a secure (https) connection.'
      : `Showing hospitals near <b>${esc(S.loc.name)}</b>. Turn on location to see the ones closest to you.`;
    return `<div class="locbox locbox--ask">
      <p>${ic('pin')}<span>${why}</span></p>
      <div class="actions">
        <button class="btn btn--blue" data-action="locate">${ic('locate')}Use my exact location</button>
        <button class="btn btn--line" data-action="pick-location">Choose area</button>
      </div>
    </div>`;
  }
  function locBtn() { return locBox(); }
  function paintLocBtn() { const b = $('#locbox'); if (b) b.innerHTML = locBox(); }

  function paintEm() {
    const box = $('#em-results');
    const near = $('#nearest');
    const st = S.em.status;
    if (near) {
      const best = S.em.list.find((h) => (h.er.a || 0) > 0) || S.em.list[0];
      if (st === 'loading' || st === 'idle') near.innerHTML = skeleton(1);
      else if (st === 'error') near.innerHTML = errorBox(S.em.error, 'retry-em');
      else near.innerHTML = best ? nearestCard(best) : '<div class="empty"><p>No hospitals found nearby. Call 108 for an ambulance.</p></div>';
      const pt = $('#place-text'); if (pt) pt.textContent = locText();
    }
    if (!box) return;
    if (st === 'loading' || st === 'idle') { box.innerHTML = skeleton(3); return; }
    if (st === 'error') { box.innerHTML = errorBox(S.em.error, 'retry-em'); return; }
    if (!S.em.list.length) {
      box.innerHTML = `<div class="empty"><h3 class="h3">No hospitals found near here</h3><p class="small">Try another area, or call 108 for an ambulance.</p><button class="btn btn--ink btn--sm" data-action="pick-location">Change area</button></div>`;
      return;
    }
    const list = S.em.list.slice(0, 10);
    const top = list.slice(0, 3), rest = list.slice(3);
    const newest = list.filter((h) => h.live).map((h) => h.updated).filter(Boolean).sort().pop();
    const demo = list.some((h) => h.demo);
    const checked = PHONES_CHECKED;
    box.innerHTML = `
      <h2 class="h2 list-title">${top.length} nearest emergency ${top.length === 1 ? 'hospital' : 'hospitals'}</h2>
      <ol class="results">${top.map(hcard).join('')}</ol>
      <p class="fresh">${ic('clock', 'i-sm')}Locations and numbers checked ${esc(dayMonth(checked))}.${newest ? ` Beds updated ${ago(newest)}.` : ''}${demo ? ' <span class="demo">Demo data</span>' : ''}</p>
      ${rest.length ? `<section class="others">
        <h2 class="h2">More hospitals nearby</h2>
        <ol class="rows">${rest.map(nearbyRow).join('')}</ol>
      </section>` : ''}`;
  }

  function hcard(h, i) {
    const best = i === 0;
    return `<li class="card hcard ${best ? 'card--best' : ''}">
      ${best ? `<p class="best">${ic('check', 'i-sm')}Nearest to you</p>` : ''}
      <div class="hcard__head">
        <span class="num" aria-hidden="true">${i + 1}</span>
        <div>
          <h3 class="card__title">${esc(h.name)}</h3>
          <p class="small">${esc(metaLine(h))}</p>
        </div>
      </div>
      ${facts(h)}
      <div class="actions">
        ${h.phoneEm ? `<a class="btn btn--go" href="${tel(h.phoneEm)}">${ic('phone')}Call hospital</a>` : `<a class="btn btn--em" href="tel:108">${ic('phone')}Call 108</a>`}
        <a class="btn btn--line" href="${mapsDir(h)}" target="_blank" rel="noopener">${ic('nav')}Directions</a>
      </div>
      ${h.partner ? `<button class="btn btn--line-em btn--block" style="margin-top:8px" data-action="coordinate" data-id="${esc(h.id)}">${ic('send')}Tell them I'm coming</button>` : ''}
      <button class="link more-link" data-action="details" data-id="${esc(h.id)}">Address and all phone numbers ${ic('right', 'i-sm')}</button>
    </li>`;
  }

  /* ---------- Location sheet ---------- */
  function locationSheet() {
    return `<h2 class="h2 sheet-title" id="sheet-title">Where are you?</h2>
      <p class="small" style="margin-top:6px">We sort hospitals by travel time from here.</p>
      <button class="btn btn--ink btn--block" style="margin-top:18px" data-action="locate">${ic('locate')}Use my current location</button>
      <div style="margin-top:22px">
        <label class="label" for="loc-filter">Or choose your area</label>
        <input class="input" id="loc-filter" type="search" placeholder="Type an area name" data-filter="loc" autocomplete="off">
        <div class="options" id="loc-list" style="margin-top:10px">${locOptions('')}</div>
      </div>`;
  }
  function locOptions(q) {
    const list = S.locations.filter((l) => !q || l.name.toLowerCase().includes(q.toLowerCase()));
    if (!list.length) return '<p class="small">No matching area. Try a different spelling.</p>';
    return list.map((l) => `<button class="opt" data-action="set-loc" data-name="${esc(l.name)}">
      <span class="opt__icon">${ic('pin')}</span><span class="opt__txt"><b>${esc(l.name)}</b></span>${S.loc.name === l.name ? ic('check') : ic('right')}
    </button>`).join('');
  }

  /* ---------- Details sheet ---------- */
  async function openDetails(id) {
    const base = S.em.list.find((h) => h.id === id) || S.plan.results.find((h) => h.id === id) || S.hosp.get(id);
    openSheet(base ? detailsHtml(base, true) : `<h2 class="h2 sheet-title" id="sheet-title">Loading</h2>${skeleton(1)}`);
    try {
      const d = await api('/api/hospitals/' + encodeURIComponent(id));
      const full = norm(d.hospital || d.data || d);
      const merged = base ? { ...full, distanceKm: base.distanceKm, transitMins: base.transitMins, why: base.why.length ? base.why : full.why } : full;
      S.hosp.set(id, merged);
      if (sheet.classList.contains('is-open') && sheetBody.dataset.id === id) {
        const top = sheetBody.scrollTop;
        sheetBody.innerHTML = detailsHtml(merged, false);
        sheetBody.scrollTop = top;
      }
    } catch (e) {
      if (!base) sheetBody.innerHTML = errorBox(e.message, 'close-sheet');
    }
  }
  function detailsHtml(h, partial) {
    sheetBody.dataset.id = h.id;
    const st = (s) => { const t = String(s || '').toLowerCase(); return /closed|unavail|not avail|none|out|full/.test(t) ? 'st--no' : /limit|low|on call|busy/.test(t) ? 'st--low' : /ready|avail|stock|free|open|yes/.test(t) ? 'st--ok' : ''; };
    return `<div>
        <h2 class="h2 sheet-title" id="sheet-title">${esc(h.name)}</h2>
        <p class="small" style="margin-top:4px">${esc(metaLine(h))}</p>
        ${h.address ? `<p class="small" style="margin-top:8px;display:flex;gap:6px">${ic('pin', 'i-sm')}<span>${esc(h.address)}</span></p>` : ''}
      </div>
      <div class="actions" style="margin-top:16px">
        ${h.phoneEm ? `<a class="btn btn--go" href="${tel(h.phoneEm)}">${ic('phone')}Call hospital</a>` : `<a class="btn btn--em" href="tel:108">${ic('phone')}Call 108</a>`}
        <a class="btn btn--line" href="${mapsDir(h)}" target="_blank" rel="noopener">${ic('nav')}Directions</a>
      </div>
      ${h.partner ? `<button class="btn btn--em btn--block" style="margin-top:8px" data-action="coordinate" data-id="${esc(h.id)}">${ic('send')}Tell them I'm coming</button>` : ''}
      <ul class="facts" style="margin-top:14px">${scopeLine(h)}</ul>
      <section class="dgroup">
        <h3 class="h3">Beds right now</h3>
        ${h.live ? `<div class="bigbeds">
          ${bedMetric(h.er, 'Emergency')}
          ${bedMetric(h.icu, 'ICU')}
          ${h.holds != null ? `<div class="metric"><div class="metric__val">${h.holds}</div><div class="metric__lab">Held for people on the way</div></div>` : ''}
        </div>
        <p class="fresh">${ic('clock', 'i-sm')}Published by the hospital ${h.updated ? ago(h.updated) : 'recently'}${h.demo ? ' <span class="demo">Demo data</span>' : ''}</p>`
        : `<p class="small">This hospital does not share live bed numbers yet. Call the number below to check before you go.</p>`}
      </section>
      ${h.why.length ? `<section class="dgroup"><h3 class="h3">Why it is listed here</h3><ul class="why">${h.why.map((w) => `<li>${ic('check')}<span>${esc(w)}</span></li>`).join('')}</ul></section>` : ''}
      ${h.departments.length ? `<section class="dgroup"><h3 class="h3">Departments and doctors on duty</h3><div class="kv">${h.departments.map((d) => `<div><span><b style="display:block;text-align:left;color:var(--ink)">${esc(pick(d.name, d.department))}</b>${esc(pick(d.onDuty, d.specialist, d.doctor, ''))}</span><span class="st ${st(d.status)}">${esc(pick(d.status, 'Unknown'))}</span></div>`).join('')}</div></section>` : (partial ? `<section class="dgroup">${skeleton(1)}</section>` : '')}
      ${h.equipment.length ? `<section class="dgroup"><h3 class="h3">Equipment</h3><div class="kv">${h.equipment.map((e) => `<div><span>${esc(pick(e.name, e.item))}</span><span class="st ${st(pick(e.status, e.available))}">${esc(String(pick(e.status, e.available === true ? 'Available' : e.available === false ? 'Not available' : 'Unknown')))}</span></div>`).join('')}</div></section>` : ''}
      <section class="dgroup">
        <h3 class="h3">Phone numbers</h3>
        <div class="kv">
          ${(h.phones.length ? h.phones : [{ label: h.phoneLabel, number: h.phoneEm }, ...(h.phoneRec && h.phoneRec !== h.phoneEm ? [{ label: h.recLabel, number: h.phoneRec }] : [])])
            .filter((x) => x.number)
            .map((x) => `<div><span>${esc(x.label || 'Phone')}</span><a class="linkbtn" href="${tel(x.number)}">${esc(x.number)}</a></div>`).join('')}
        </div>
        ${h.listed ? `<p class="small" style="margin-top:10px">Government hospital. This number is from a public list, not the hospital's own website, and may not be answered. If no one picks up, call 108.</p>` : ''}
        ${h.source ? `<p class="fresh">${ic('info', 'i-sm')}<span>Source: ${h.source.url ? `<a class="srclink" href="${esc(h.source.url)}" target="_blank" rel="noopener">${esc(h.source.label || 'website')}</a>` : esc(h.source.label)}${h.checked ? `, checked ${esc(dayMonth(h.checked))}` : ''}</span></p>` : ''}
      </section>
      ${h.allServices.length ? `<section class="dgroup"><h3 class="h3">Departments</h3><p class="small">${h.allServices.map((x) => esc(pick(x.specialty, x.name))).join(', ')}</p></section>` : ''}`;
  }

  /* ---------- Pre-arrival coordination ---------- */
  function coordinateSheet(id) {
    const h = S.em.list.find((x) => x.id === id) || S.hosp.get(id) || { id, name: 'this hospital' };
    const mins = (h.transitMins || 15) + 15;
    return `<h2 class="h2 sheet-title" id="sheet-title">Tell ${esc(h.name)} you are coming?</h2>
      <p class="lead" style="margin-top:8px">Their emergency desk gets an alert and holds a bed for about ${mins} minutes while you travel.</p>
      <p class="small" style="margin-top:8px">We only send your area and travel time. No name or phone number is needed.</p>
      <div style="display:grid;gap:8px;margin-top:18px">
        <button class="btn btn--em btn--block btn--big" data-action="send-coord" data-id="${esc(id)}" autofocus>${ic('send')}Yes, tell them</button>
        <button class="btn btn--line btn--block" data-action="close-sheet">Cancel</button>
      </div>
      <p class="err" data-err hidden></p>
      <div class="notice" style="margin-top:16px">${ic('info')}<span>This is not a guaranteed bed or admission. If the patient gets worse, call 108.</span></div>`;
  }

  async function sendCoordinate(btn) {
    const id = btn.dataset.id;
    const h = S.em.list.find((x) => x.id === id) || S.hosp.get(id) || {};
    const err = $('[data-err]', sheetBody);
    btn.classList.add('is-loading'); btn.disabled = true; err.hidden = true;
    try {
      const d = await api('/api/coordination/request', {
        hospitalId: id,
        emergencyCategory: 'general',
        estimatedTravelMinutes: h.transitMins || 15,
        userLocationName: S.loc.name
      });
      const rec = d.request || d;
      const rid = rec.id || rec.requestId || d.id;
      savePass(rid, { token: d.tracking_token || rec.tracking_token || d.trackingToken || null, otp: String(pick(d.arrival_otp, d.otp, rec.otp, rec.arrivalOtp, '')) });
      S.coord = normRequest(rec);
      S.coordId = S.coord.id;
      store.set('coord', S.coordId);
      closeSheet();
      location.hash = '#/request/' + encodeURIComponent(S.coordId);
      toast('Sent. The hospital knows you are coming.');
    } catch (e) {
      err.hidden = false; err.textContent = e.message;
      btn.classList.remove('is-loading'); btn.disabled = false;
    }
  }

  /* ================================================================
     REQUEST STATUS
     ================================================================ */
  function viewRequest(id) {
    if (!id && S.coordId) id = S.coordId;
    if (!id) return `<div class="wrap"><div class="empty" style="margin-top:16px"><h1 class="h2">No active request</h1><p class="small">Find a hospital and tap Tell them I'm coming.</p><a class="btn btn--em" href="#/emergency">Find emergency care</a></div></div>`;
    return `<div class="wrap" id="req" data-id="${esc(id)}">${S.coord && S.coord.id === id ? requestHtml(S.coord) : skeleton(2)}</div>`;
  }

  function requestHtml(c) {
    const st = STATUS[c.status] || STATUS.REQUEST_SUBMITTED;
    const ended = st.step < 0;
    const arrived = c.status === 'PATIENT_ARRIVED';
    const R = 26, C = 2 * Math.PI * R;
    const showCode = !ended && !arrived && c.otp;
    const stepState = (i) => (arrived ? 'done' : i < st.step ? 'done' : i === st.step ? 'now' : 'todo');
    return `
      <div class="req-hero">
        <a class="linkbtn" href="#/emergency" style="justify-self:start">${ic('left', 'i-sm')}Hospitals</a>
        <h1 class="h1" aria-live="polite">${esc(st.title)}</h1>
        <p class="lead">${esc(c.hospitalName)}${c.address ? `, ${esc(c.address)}` : ''}</p>
      </div>
      <div class="req-grid">
        <div class="panel">
          ${ended ? `<div class="empty" style="background:transparent;padding:0">
              <p class="small">${c.status === 'CANCELLED' ? 'The held bed went back to the hospital for other patients.' : 'The hold time ran out and the bed was released. You can still go to the hospital or send a new request.'}</p>
              <div style="display:flex;gap:8px;flex-wrap:wrap"><a class="btn btn--em" href="#/emergency">Find a hospital again</a>${c.phone ? `<a class="btn btn--go" href="${tel(c.phone)}">${ic('phone')}Call hospital</a>` : ''}</div>
            </div>`
          : `<ol class="steps">${STEPS.map((s, i) => `<li class="${stepState(i)}"><span class="dot">${stepState(i) === 'done' ? ic('check') : stepState(i) === 'now' ? ic('clock') : ''}</span><div><b>${s.t}</b><span>${s.s}</span></div></li>`).join('')}</ol>`}
          ${!ended && !arrived ? `<div class="timer">
              <svg class="ring" viewBox="0 0 64 64" aria-hidden="true"><circle class="track" cx="32" cy="32" r="${R}"/><circle class="bar" cx="32" cy="32" r="${R}" stroke-dasharray="${C}" stroke-dashoffset="0" data-ring="${c.expires}" data-start="${c.created}" data-c="${C}"/></svg>
              <div><b data-countdown="${c.expires}">${mmss(c.expires - Date.now())}</b><span>Bed hold time left, including 15 minutes extra</span></div>
            </div>` : ''}
        </div>
        <div class="panel">
          ${showCode ? `<div class="passcode">
              <h2 class="h3">Show this at the casualty desk</h2>
              <div class="code" aria-label="Your code ${esc(c.otp.split('').join(' '))}">${c.otp.split('').map((d) => `<span>${esc(d)}</span>`).join('')}</div>
              <div class="qr" id="qr" aria-hidden="true"></div>
              <p class="small">Staff can scan the square or type the code.</p>
            </div>`
          : arrived ? `<div class="passcode"><div class="success-badge">${ic('check', 'check-draw')}</div><h2 class="h3">Checked in at the desk</h2><p class="small">The hospital team will take it from here.</p></div>`
          : `<h2 class="h3">Need help?</h2><p class="small" style="margin-top:6px">Call 108 for an ambulance if the patient's condition is serious.</p>`}
          <div style="display:grid;gap:8px;margin-top:18px">
            ${c.phone ? `<a class="btn btn--go btn--block" href="${tel(c.phone)}">${ic('phone')}Call casualty desk</a>` : ''}
            ${!ended && !arrived ? `<a class="btn btn--line btn--block" href="${mapsDir({ name: c.hospitalName, address: c.address, lat: c.lat, lng: c.lng })}" target="_blank" rel="noopener">${ic('nav')}Directions</a>
            <a class="btn btn--wa btn--block" href="${familyLink(c)}" target="_blank" rel="noopener" data-action="share-family">${ic('send')}Send to family on WhatsApp</a>
            <button class="btn btn--sm btn--plain btn--emtext" data-action="cancel-request">Cancel request</button>
            <button class="btn btn--sm btn--plain" data-action="desk-verify">For desk staff: confirm arrival</button>` : ''}
          </div>
        </div>
      </div>
      <div class="notice" style="margin-top:16px">${ic('info')}<span>A hospital reply is not a guaranteed bed or admission. If the patient gets worse on the way, call 108.</span></div>`;
  }

  function familyMessage(c) {
    const map = mapsDir({ name: c.hospitalName, address: c.address, lat: c.lat, lng: c.lng });
    return [TT('We are going to {0} for an emergency.', c.hospitalName), c.address ? TT('Address: {0}.', c.address) : '', c.phone ? TT('Hospital phone: {0}.', c.phone) : '', TT('Map: {0}', map)].filter(Boolean).join(' ');
  }
  const familyLink = (c) => 'https://wa.me/?text=' + encodeURIComponent(familyMessage(c));

  function drawQr(c) {
    const box = $('#qr');
    if (!box || !c || !c.otp) return;
    const make = () => {
      if (typeof window.qrcode !== 'function') { box.remove(); return; }
      try {
        const q = window.qrcode(0, 'M');
        q.addData(`AIIS|${c.id}|${c.otp}`);
        q.make();
        box.innerHTML = q.createImgTag(5, 0);
        const img = $('img', box); if (img) img.alt = '';
      } catch { box.remove(); }
    };
    if (typeof window.qrcode === 'function') make();
    else { const t = setTimeout(make, 1500); S.timers.push(t); }
  }

  async function pollRequest(id) {
    const box = $('#req');
    if (!box) return;
    try {
      const d = await api('/api/coordination/' + encodeURIComponent(id), undefined, trackHdr(id));
      const next = normRequest(d.request || d);
      const changed = !S.coord || S.coord.id !== next.id || S.coord.status !== next.status;
      S.coord = next;
      if (id !== S.coordId && !(STATUS[next.status] || {}).done) { S.coordId = id; store.set('coord', id); }
      if (changed) { box.innerHTML = requestHtml(next); drawQr(next); if (navigator.vibrate && S.coord.status === 'HOSPITAL_ACCEPTED') navigator.vibrate(120); }
      if ((STATUS[next.status] || {}).done) { if (S.coordId === id) { S.coordId = null; store.del('coord'); } return; }
    } catch (e) {
      if (e.status === 404) {
        box.innerHTML = `<div class="empty" style="margin-top:16px"><h1 class="h2">Request not found</h1><p class="small">It may have ended. You can find a hospital again.</p><a class="btn btn--em" href="#/emergency">Find emergency care</a></div>`;
        if (S.coordId === id) { S.coordId = null; store.del('coord'); S.coord = null; }
        return;
      }
    }
    S.timers.push(setTimeout(() => pollRequest(id), 3000));
  }

  /* ================================================================
     PLANNED CARE
     ================================================================ */
  function viewPlanned() {
    const P = S.plan;
    const top = `<div class="flow-top">
      ${P.step > 1 ? `<button class="iconbtn" data-action="plan-back" aria-label="Back">${ic('left')}</button>` : ''}
      <div class="progress" aria-hidden="true">${[1, 2, 3].map((n) => `<i class="${n <= Math.min(P.step, 3) || P.step === 4 ? 'on' : ''}"></i>`).join('')}</div>
    </div>`;
    let body = '';
    if (P.step === 1) {
      body = `<div class="flow-step">
        <h1 class="h1">What do you need?</h1>
        <p class="lead">Pick one. You can change it later.</p>
        <div class="options stagger">${NEEDS.map((n, i) => `<button class="opt" style="--i:${i}" data-action="plan-need" data-id="${n.id}"><span class="opt__icon">${ic(n.icon)}</span><span class="opt__txt"><b>${n.title}</b><span>${n.sub}</span></span>${ic('right')}</button>`).join('')}</div>
      </div>`;
    } else if (P.step === 2) {
      body = `<div class="flow-step">
        <h1 class="h1">Which kind of doctor?</h1>
        <p class="lead">Plain words first. The medical name is underneath.</p>
        <div class="options options--2 stagger">
          ${SPECIALTIES.map((s, i) => `<button class="opt" style="--i:${i}" data-action="plan-spec" data-key="${esc(s.key)}"><span class="opt__icon">${ic(s.icon)}</span><span class="opt__txt"><b>${s.label}</b><span>${s.term}</span></span>${ic('right')}</button>`).join('')}
          <button class="opt opt--quiet" style="--i:${SPECIALTIES.length}" data-action="plan-spec" data-key=""><span class="opt__icon">${ic('grid')}</span><span class="opt__txt"><b>Not sure</b><span>Show all hospitals</span></span>${ic('right')}</button>
        </div>
      </div>`;
    } else if (P.step === 3) {
      body = `<div class="flow-step">
        <h1 class="h1">Where should we look?</h1>
        <p class="lead">${P.label ? `Looking for ${esc(P.label.toLowerCase())}.` : 'Looking at all hospitals.'} Closest first.</p>
        <div style="margin-top:20px;display:grid;gap:22px">
          <button class="btn btn--block ${S.loc.source === 'gps' ? 'btn--ink' : ''}" data-action="locate">${ic('locate')}${S.locating ? 'Finding your location' : S.loc.source === 'gps' ? 'Using your current location' : 'Use my current location'}</button>
          <div>
            <span class="label">Or choose your area</span>
            <div class="chips chips--wrap">${S.locations.map((l) => `<button class="chip" data-action="plan-loc" data-name="${esc(l.name)}" aria-pressed="${S.loc.source !== 'gps' && S.loc.name === l.name}">${esc(l.name)}</button>`).join('')}</div>
          </div>
          <div>
            <span class="label" id="sector-label">Type of hospital</span>
            <div class="seg" role="group" aria-labelledby="sector-label">
              ${[['any', 'Any'], ['government', 'Government'], ['private', 'Private']].map(([v, t]) => `<button data-action="plan-sector" data-v="${v}" aria-pressed="${P.sector === v}">${t}</button>`).join('')}
            </div>
          </div>
          <div>
            <label class="label" for="plan-q">Hospital name <span class="muted">(optional)</span></label>
            <input class="input" id="plan-q" type="search" placeholder="For example: Manipal" value="${esc(P.query)}" data-filter="plan-q" ${P.search ? 'autofocus' : ''}>
          </div>
          <button class="btn btn--ink btn--block" data-action="plan-search">${ic('search')}Show hospitals</button>
        </div>
      </div>`;
    } else {
      body = `<div class="flow-step">
        <h1 class="h1">${P.label ? `Hospitals for ${esc(P.label.toLowerCase())}` : 'Hospitals near you'}</h1>
        <div class="summary">
          <button class="chip" data-action="plan-goto" data-step="3">${ic('pin')}${esc(S.loc.source === 'gps' ? 'Near you' : S.loc.name)}</button>
          <button class="chip" data-action="plan-goto" data-step="${P.need === 'specialist' || P.need === 'procedure' ? 2 : 1}">${ic('steth')}${esc(P.label || 'All care')}</button>
          ${P.sector !== 'any' ? `<button class="chip" data-action="plan-goto" data-step="3">${P.sector === 'government' ? 'Government' : 'Private'}</button>` : ''}
        </div>
        <div id="plan-results" style="margin-top:18px">${planResultsHtml()}</div>
      </div>`;
    }
    return `<div class="wrap">${top}${body}</div>`;
  }

  function planResultsHtml() {
    const P = S.plan;
    if (P.status === 'loading' || P.status === 'idle') return skeleton(3);
    if (P.status === 'error') return errorBox(P.error, 'plan-search');
    let list = P.results;
    if (P.sector !== 'any') list = list.filter((h) => String(h.sector || '').toLowerCase().includes(P.sector));
    if (!list.length) return `<div class="empty"><h2 class="h3">No hospitals match yet</h2><p class="small">Try a different area, or choose All care.</p><button class="btn btn--ink btn--sm" data-action="plan-goto" data-step="1">Start again</button></div>`;
    return `<ol class="results stagger">${list.map(pcard).join('')}</ol>
      <div class="notice" style="margin-top:16px">${ic('info')}<span>Call the hospital to book a visit. AIIS shows real hospitals and their own phone numbers; it does not invent doctor counts or waiting times.</span></div>`;
  }

  function pcard(h, i) {
    const P = S.plan;
    const svc = (P.specialty ? h.services : []).slice(0, 1)[0];
    const doctors = svc ? num(pick(svc.consultants, svc.consultantCount, svc.doctors && svc.doctors.length, svc.verifiedConsultants)) : null;
    const wait = svc ? num(pick(svc.waitDays, svc.avgWaitDays, svc.outpatientWaitDays, svc.nextAvailableDays)) : null;
    const specs = (h.allServices.length ? h.allServices : h.services).map((s) => pick(s.specialty, s.name)).filter(Boolean);
    return `<li class="pcard" style="--i:${i}">
      <div>
        <div class="pcard__head">
          <div><h3 class="hcard__name">${esc(h.name)}</h3><p class="hcard__type">${esc(metaLine(h))}</p></div>
        </div>
        <div class="pcard__facts">
          ${h.distanceKm != null ? `<span>${ic('pin')}<span><b>${h.distanceKm} km</b>${h.transitMins != null ? `, about ${h.transitMins} min` : ''}</span></span>` : ''}
          ${doctors != null ? `<span>${ic('steth')}<span><b>${doctors}</b> ${doctors === 1 ? 'doctor' : 'doctors'}</span></span>` : ''}
          ${wait != null ? `<span>${ic('calendar')}<span>Next opening in about <b>${wait} ${wait === 1 ? 'day' : 'days'}</b></span></span>` : ''}
          ${!P.specialty && specs.length ? `<span>${ic('check')}${esc(specs.slice(0, 4).join(', '))}</span>` : ''}
        </div>
      </div>
      <div class="pcard__actions">
        ${h.partner ? `<button class="btn btn--ink" data-action="book" data-id="${esc(h.id)}">${ic('calendar')}Request visit</button>` : ''}
        ${h.phoneRec && h.phoneRec !== h.phoneEm
          ? `<a class="btn btn--go" href="${tel(h.phoneRec)}" aria-label="Call ${esc(h.name)} to book">${ic('phone')}<span>Call to book</span></a>`
          : h.website
            ? `<a class="btn btn--blue" href="${esc(h.website)}" target="_blank" rel="noopener">${ic('calendar')}<span>Book on website</span></a>`
            : h.phoneRec ? `<a class="btn btn--go" href="${tel(h.phoneRec)}" aria-label="Call ${esc(h.name)}">${ic('phone')}<span>Call hospital</span></a>` : ''}
        <button class="btn btn--line" data-action="details" data-id="${esc(h.id)}">${ic('info')}<span>Details</span></button>
      </div>
    </li>`;
  }

  async function planSearch() {
    const P = S.plan;
    const q = $('#plan-q');
    if (q) P.query = q.value.trim();
    P.step = 4; P.status = 'loading';
    render(true);
    window.scrollTo(0, 0);
    try {
      const d = await api('/api/planned/search', { latitude: S.loc.lat, longitude: S.loc.lng, specialty: P.specialty, query: P.query });
      P.results = (d.results || []).map(norm);
      P.results.forEach((h) => { if (!S.hosp.has(h.id)) S.hosp.set(h.id, h); });
      P.status = 'ok';
    } catch (e) { P.status = 'error'; P.error = e.message; }
    const box = $('#plan-results');
    if (box) box.innerHTML = planResultsHtml();
  }

  /* ---------- Booking sheet ---------- */
  function bookSheet(id) {
    const h = S.plan.results.find((x) => x.id === id) || S.hosp.get(id) || { id, name: 'Hospital' };
    const p = S.profile;
    const today = new Date();
    const days = Array.from({ length: 10 }, (_, i) => { const d = new Date(today); d.setDate(d.getDate() + i + 1); return d; });
    const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    return `<h2 class="h2 sheet-title" id="sheet-title">Request an appointment</h2>
      <p class="small" style="margin-top:4px">${esc(h.name)}${S.plan.label ? `, ${esc(S.plan.label)}` : ''}</p>
      <form data-form="book" data-id="${esc(id)}" style="margin-top:18px" novalidate>
        <div class="field">
          <span class="label" id="day-label">Which day?</span>
          <div class="dates" role="group" aria-labelledby="day-label">
            ${days.map((d, i) => `<button type="button" class="date" data-action="pick-date" data-v="${iso(d)}" aria-pressed="${i === 0}"><small>${i === 0 ? 'Tmrw' : d.toLocaleDateString(LOC(), { weekday: 'short' })}</small><b>${d.getDate()}</b><small>${d.toLocaleDateString(LOC(), { month: 'short' })}</small></button>`).join('')}
          </div>
          <input type="hidden" name="preferredDate" value="${iso(days[0])}">
        </div>
        <div class="field">
          <span class="label" id="slot-label">What time suits you?</span>
          <div class="seg" role="group" aria-labelledby="slot-label">
            ${SLOTS.map((s, i) => `<button type="button" data-action="pick-slot" data-v="${s.id}" aria-pressed="${i === 0}">${s.id}</button>`).join('')}
          </div>
          <p class="hint">Morning 9 to 12, afternoon 12 to 4, evening 4 to 8.</p>
          <input type="hidden" name="preferredTimeSlot" value="${SLOTS[0].id}">
        </div>
        <div class="field">
          <label class="label" for="b-name">Patient name</label>
          <input class="input" id="b-name" name="patientName" autocomplete="name" value="${esc(p.name || '')}" required>
        </div>
        <div class="field">
          <label class="label" for="b-phone">Phone number</label>
          <input class="input" id="b-phone" name="patientPhone" type="tel" inputmode="tel" autocomplete="tel" value="${esc(p.phone || '')}" placeholder="10 digit mobile number" required>
          <p class="hint">The hospital calls this number to confirm.</p>
        </div>
        <label class="field" style="display:flex;gap:12px;align-items:center;margin-top:16px;cursor:pointer">
          <input type="checkbox" name="remember" checked style="width:22px;height:22px;accent-color:var(--ink-fill)">
          <span class="small" style="color:var(--ink)">Remember my name and number on this phone</span>
        </label>
        <div class="notice" style="margin-top:16px">${ic('info')}<span>This is a request, not a confirmed booking. The hospital will call you to fix the exact time.</span></div>
        <p class="err" data-err hidden></p>
        <div class="sheet-cta"><button class="btn btn--ink btn--block" type="submit">${ic('send')}<span>Send request</span></button></div>
      </form>`;
  }

  async function submitBook(form) {
    const f = new FormData(form);
    const err = $('[data-err]', form);
    const name = String(f.get('patientName') || '').trim();
    const phone = String(f.get('patientPhone') || '').trim();
    const show = (m, el) => { err.hidden = false; err.textContent = m; if (el) el.focus(); };
    if (!name) return show('Please add the patient name.', $('#b-name'));
    if (phone.replace(/\D/g, '').length < 10) return show('Please check the phone number. It needs 10 digits.', $('#b-phone'));
    const h = S.plan.results.find((x) => x.id === form.dataset.id) || S.hosp.get(form.dataset.id) || {};
    const btn = $('button[type=submit]', form);
    btn.classList.add('is-loading'); btn.disabled = true; err.hidden = true;
    try {
      const d = await api('/api/appointments/request', {
        hospitalId: form.dataset.id,
        specialty: S.plan.label || 'General consultation',
        preferredDate: f.get('preferredDate'),
        preferredTimeSlot: f.get('preferredTimeSlot'),
        patientName: name,
        patientPhone: phone,
      });
      const a = d.appointment || d;
      const snap = { id: a.id, hospitalId: form.dataset.id, hospitalName: pick(a.hospitalName, h.name), phone: pick(a.receptionPhone, h.phoneRec), specialty: pick(a.specialty, S.plan.label), date: pick(a.preferredDate, f.get('preferredDate')), slot: pick(a.preferredTimeSlot, f.get('preferredTimeSlot')), status: pick(a.status, 'REQUESTED'), patientPhone: phone };
      S.appts = [snap, ...S.appts.filter((x) => x.id !== snap.id)];
      store.set('appts', S.appts);
      if (f.get('remember')) { S.profile = { ...S.profile, name, phone }; store.set('profile', S.profile); }
      sheetBody.innerHTML = `<div style="display:grid;justify-items:start;gap:14px;padding-top:12px">
        <div class="success-badge">${ic('check', 'check-draw')}</div>
        <h2 class="h2" id="sheet-title">Request sent</h2>
        <p class="lead">${esc(snap.hospitalName)} will call <b>${esc(phone)}</b> to confirm a time on ${esc(fmtDate(snap.date))}, ${esc(String(snap.slot).toLowerCase())}.</p>
        <p class="small">Reference ${esc(snap.id || '')}</p>
        <div class="duo" style="width:100%;margin-top:6px">
          <a class="btn btn--ink" href="#/me" data-action="close-sheet">My visits</a>
          <button class="btn" data-action="close-sheet">Done</button>
        </div>
      </div>`;
    } catch (e) {
      show(e.message);
    } finally {
      btn.classList.remove('is-loading'); btn.disabled = false;
    }
  }

  /* ================================================================
     MY CARE
     ================================================================ */
  function viewMe() {
    const c = activeCoord();
    const hasProfile = Boolean(S.profile.name || S.profile.phone);
    const authUser = S.auth && S.auth.user;
    return `<div class="wrap">
      <h1 class="h1 page-title">My requests</h1>
      ${authUser ? `
        <div class="acctbar">
          <div><span class="small">Signed in</span><b>${esc(authUser.full_name || authUser.email)}</b></div>
          <button class="btn btn--sm btn--line" data-action="patient-signout">Sign out</button>
        </div>
      ` : `
        <div class="acctbar acctbar--out">
          <div><b>Want your requests on every device?</b><span class="small">Optional. Sign in or create an account.</span></div>
          <a class="btn btn--sm btn--line" href="#/signin">Sign in</a>
        </div>
      `}
      <section class="block" aria-labelledby="hold-title">
        <h2 class="h2" id="hold-title">Emergency bed hold</h2>
        ${c ? liveStrip() : `<div class="empty"><p class="small">No active request. In an emergency, tap Emergency on the home screen and call the nearest hospital or 108.</p><a class="btn btn--em" href="#/emergency">${ic('siren')}Find emergency care</a></div>`}
      </section>
      <section class="block" aria-labelledby="visits-title">
        <h2 class="h2" id="visits-title">Doctor visit requests</h2>
        <div id="visits" class="stack" style="--gap:10px">${visitsHtml()}</div>
      </section>
      ${hasProfile ? `<p class="small forget">Your name and phone number are saved on this phone to fill forms faster. <button class="link" data-action="forget-me">Remove them</button></p>` : ''}
      ${footer()}
    </div>`;
  }

  /* ================================================================
     PATIENT SIGN IN & REGISTRATION
     ================================================================ */
  function viewSignIn() {
    const back = S.authReturn || '#/';
    if (S.auth && S.auth.user) {
      const u = S.auth.user;
      const initials = String(u.full_name || u.email || 'P').trim().split(/\s+/).map((w) => w[0]).slice(0, 2).join('').toUpperCase();
      return `<div class="wrap auth">
        <div class="auth__card">
          <div class="auth__avatar" aria-hidden="true">${esc(initials)}</div>
          <h1 class="h2 auth__title">${esc(u.full_name || 'Patient')}</h1>
          <p class="small">${esc(u.email || '')}${u.phone ? ` · ${esc(u.phone)}` : ''}</p>
          <div class="auth__row">
            <a class="btn btn--ink" href="#/me">${ic('clip')}My requests</a>
            <button class="btn btn--line" data-action="patient-signout">Sign out</button>
          </div>
        </div>
        ${footer()}
      </div>`;
    }
    const isReg = S.authMode === 'register';
    return `<div class="wrap auth">
      <div class="auth__head">
        <h1 class="h1">${isReg ? 'Create your account' : 'Sign in'}</h1>
        <p class="lead">Optional. Emergency help, hospital calls and directions never need an account. Signing in keeps your visit requests and details on any device.</p>
      </div>
      <div class="auth__card">
        <div class="seg auth__seg" role="tablist" aria-label="Account">
          <button role="tab" aria-selected="${!isReg}" aria-pressed="${!isReg}" data-action="auth-mode" data-v="signin">Sign in</button>
          <button role="tab" aria-selected="${isReg}" aria-pressed="${isReg}" data-action="auth-mode" data-v="register">Create account</button>
        </div>

        <a class="btn btn--line btn--block auth__google" id="btn-google-login" href="https://romwnlabuhsnxuomhevb.supabase.co/auth/v1/authorize?provider=google&redirect_to=${encodeURIComponent(window.location.origin + '/')}">
          <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/></svg>
          Continue with Google
        </a>
        <div class="auth__or"><span>or with email</span></div>

        <form data-form="patient-auth" novalidate>
          <p id="auth-error" class="err" role="alert" hidden></p>
          ${isReg ? `
          <div class="field">
            <label class="label" for="p-name">Full name</label>
            <input class="input" id="p-name" name="full_name" type="text" autocomplete="name" value="${esc(S.profile.name || '')}" required>
          </div>
          <div class="field">
            <label class="label" for="p-phone">Mobile number <span class="muted">(optional)</span></label>
            <input class="input" id="p-phone" name="phone" type="tel" inputmode="tel" autocomplete="tel" value="${esc(S.profile.phone || '')}" placeholder="98765 43210">
          </div>` : ''}
          <div class="field">
            <label class="label" for="p-email">Email</label>
            <input class="input" id="p-email" name="email" type="email" inputmode="email" autocomplete="email" value="${esc(S.profile.email || '')}" required>
          </div>
          <div class="field">
            <label class="label" for="p-pass">Password</label>
            <div class="pw">
              <input class="input" id="p-pass" name="password" type="password" autocomplete="${isReg ? 'new-password' : 'current-password'}" minlength="${isReg ? 8 : 1}" required>
              <button type="button" class="pw__toggle" data-action="toggle-pw" aria-label="Show password" aria-pressed="false">Show</button>
            </div>
            ${isReg ? '<p class="hint">At least 8 characters.</p>' : ''}
          </div>
          <button type="submit" id="auth-submit-btn" class="btn btn--ink btn--block btn--big">${isReg ? 'Create account' : 'Sign in'}</button>
        </form>
      </div>
      <a class="link auth__skip" href="${esc(back)}">Continue without signing in ${ic('right', 'i-sm')}</a>
      ${footer()}
    </div>`;
  }

  function visitsHtml() {
    if (!S.appts.length) return `<div class="empty"><h3 class="h3">No visits booked yet</h3><p class="small">Requests you send to hospitals show up here.</p><a class="btn btn--blue" href="#/planned">${ic('calendar')}Book a doctor visit</a></div>`;
    const label = { REQUESTED: ['Waiting for hospital call', 'st--low'], CONFIRMED: ['Confirmed', 'st--ok'], CANCELLED: ['Cancelled', 'st--no'] };
    return S.appts.map((a) => {
      const [t, cls] = label[a.status] || [String(a.status || '').toLowerCase().replace(/_/g, ' '), ''];
      return `<article class="visit">
        <div class="visit__top"><div><div class="visit__when">${esc(fmtDate(a.date))}, ${esc(a.slot)}</div><div class="small">${esc(a.hospitalName)}, ${esc(a.specialty || 'Consultation')}</div></div><span class="st ${cls}">${esc(t)}</span></div>
        ${a.status !== 'CANCELLED' ? `<div style="display:flex;gap:8px;flex-wrap:wrap">
          ${a.phone ? `<a class="btn btn--sm btn--go" href="${tel(a.phone)}">${ic('phone')}Call hospital</a>` : ''}
          <button class="btn btn--sm btn--plain btn--emtext" data-action="cancel-appt" data-id="${esc(a.id)}">Cancel</button>
        </div>` : ''}
      </article>`;
    }).join('');
  }

  async function refreshAppts() {
    const phones = [...new Set([S.profile.phone, ...S.appts.map((a) => a.patientPhone)].filter(Boolean))];
    if (!phones.length) return;
    try {
      const lists = await Promise.all(phones.map((ph) => api('/api/appointments?phone=' + encodeURIComponent(String(ph).replace(/\s+/g, ''))).catch(() => ({ appointments: [] }))));
      const server = lists.flatMap((l) => l.appointments || []);
      server.forEach((a) => {
        const i = S.appts.findIndex((x) => x.id === a.id);
        const snap = { id: a.id, hospitalId: a.hospitalId, hospitalName: a.hospitalName, phone: a.receptionPhone, specialty: a.specialty, date: a.preferredDate, slot: a.preferredTimeSlot, status: a.status, patientPhone: a.patientPhone };
        if (i >= 0) S.appts[i] = { ...S.appts[i], ...Object.fromEntries(Object.entries(snap).filter(([, v]) => v != null)) };
        else S.appts.push(snap);
      });
      store.set('appts', S.appts);
      const box = $('#visits');
      if (box) box.innerHTML = visitsHtml();
    } catch { /* keep local copy */ }
  }

  /* ================================================================
     HOSPITAL STAFF: CAPACITY
     ================================================================ */
  function viewStaff() {
    const T = S.staff;
    return `<div class="wrap">
      <div style="padding-top:8px">
        <a class="linkbtn" href="#/">${ic('left', 'i-sm')}Home</a>
        <h1 class="h1" style="margin-top:6px">Update beds and readiness</h1>
        <p class="lead" style="margin-top:8px">For hospital staff. Patients see your changes as soon as you publish.</p>
      </div>
      <div class="field" style="margin-top:22px;max-width:520px">
        <label class="label" for="staff-h">Your hospital</label>
        <select class="input" id="staff-h" data-change="staff-hospital">
          ${T.list.length ? T.list.map((h) => `<option value="${esc(h.id)}" ${h.id === T.id ? 'selected' : ''}>${esc(h.name)}</option>`).join('') : '<option>Loading hospitals</option>'}
        </select>
      </div>
      <div class="field" style="margin-top:14px;max-width:520px">
        <label class="label" for="staff-code">Staff access code</label>
        <input class="input" id="staff-code" type="password" autocomplete="off" inputmode="text" placeholder="Given to your hospital by the AIIS team">
      </div>
      <div id="staff-body" style="margin-top:24px">${staffBody()}</div>
      <div class="notice" style="margin-top:24px">${ic('shield')}<span>Only hospital staff with an access code can publish. Patients then see your bed numbers and when you published them. Without a database, published numbers reset when the server restarts.</span></div>
    </div>`;
  }

  function staffBody() {
    const T = S.staff, h = T.draft;
    if (T.status === 'error') return errorBox(T.error, 'staff-reload');
    if (!h) return skeleton(2);
    const statusOf = (s) => { const t = String(s || '').toLowerCase(); return /closed|unavail|not avail|none|out/.test(t) ? 2 : /limit|low|on call/.test(t) ? 1 : 0; };
    return `<div class="mc-grid" style="margin-top:0">
      <section>
        <h2 class="h2" style="margin-bottom:12px">Beds free right now</h2>
        ${[['er', 'Emergency beds', h.er], ['icu', 'ICU beds', h.icu]].map(([k, t, b]) => `<div class="stepper">
          <div><b>${t}</b><div class="small">${b.t != null ? `Out of ${b.t}` : 'Total not set'}</div></div>
          <div class="stepper__ctl">
            <button data-action="step" data-k="${k}" data-d="-1" aria-label="One less ${t.toLowerCase()}">\u2212</button>
            <output id="out-${k}" aria-live="polite">${b.a ?? '-'}</output>
            <button data-action="step" data-k="${k}" data-d="1" aria-label="One more ${t.toLowerCase()}">+</button>
          </div>
        </div>`).join('')}
        <button class="btn btn--ink btn--block" style="margin-top:16px" data-action="staff-publish">${ic('send')}Publish update</button>
        <p class="fresh">${ic('clock', 'i-sm')}Last published ${h.updated ? ago(h.updated) : 'never'}</p>
      </section>
      <section>
        ${h.departments.length ? `<h2 class="h2" style="margin-bottom:12px">Departments</h2>
        ${h.departments.map((d, i) => `<div class="deprow"><b>${esc(d.name)}</b><div class="seg" role="group" aria-label="${esc(d.name)} status">${['Ready', 'Limited', 'Closed'].map((s, j) => `<button data-action="staff-dep" data-i="${i}" data-v="${s}" aria-pressed="${statusOf(d.status) === j}">${s}</button>`).join('')}</div></div>`).join('')}` : ''}
        ${h.equipment.length ? `<h2 class="h2" style="margin:24px 0 12px">Equipment</h2>
        ${h.equipment.map((e, i) => `<div class="deprow"><b>${esc(e.name)}</b><div class="seg" role="group" aria-label="${esc(e.name)} status">${['Available', 'Limited', 'Not available'].map((s, j) => `<button data-action="staff-eq" data-i="${i}" data-v="${s}" aria-pressed="${statusOf(e.status) === j}">${s === 'Not available' ? 'None' : s}</button>`).join('')}</div></div>`).join('')}` : ''}
      </section>
    </div>`;
  }

  async function loadStaff() {
    const T = S.staff;
    try {
      if (!T.list.length) {
        const d = await api('/api/planned/search', { latitude: S.loc.lat, longitude: S.loc.lng, specialty: '', query: '' });
        T.list = (d.results || []).map(norm).sort((a, b) => a.name.localeCompare(b.name));
        if (!T.id || !T.list.some((h) => h.id === T.id)) T.id = T.list[0] && T.list[0].id;
        const sel = $('#staff-h');
        if (sel) sel.innerHTML = T.list.map((h) => `<option value="${esc(h.id)}" ${h.id === T.id ? 'selected' : ''}>${esc(h.name)}</option>`).join('');
      }
      if (!T.id) return;
      const d = await api('/api/hospitals/' + encodeURIComponent(T.id));
      T.draft = norm(d.hospital || d.data || d);
      T.status = 'ok';
    } catch (e) { T.status = 'error'; T.error = e.message; }
    const b = $('#staff-body');
    if (b) b.innerHTML = staffBody();
  }

  async function staffPublish(btn) {
    const h = S.staff.draft;
    if (!h) return;
    const codeEl = $('#staff-code');
    const code = codeEl ? codeEl.value.trim() : '';
    if (!code) { toast('Enter your staff access code first.'); if (codeEl) codeEl.focus(); return; }
    btn.classList.add('is-loading');
    try {
      const d = await api(`/api/hospitals/${encodeURIComponent(h.id)}/capacity`, {
        ...(h.er.a != null ? { emergencyBeds: { available: h.er.a } } : {}),
        ...(h.icu.a != null ? { icuBeds: { available: h.icu.a } } : {}),
        departments: h.departments.map((x) => ({ name: x.name, status: x.status })),
        equipment: h.equipment.map((x) => ({ name: x.name, status: x.status }))
      }, { 'X-AIIS-Staff-Code': code });
      S.staff.draft = norm(d.hospital || d.data || d);
      S.em.at = 0;
      S.hosp.delete(h.id);
      const b = $('#staff-body'); if (b) b.innerHTML = staffBody();
      toast(`Published. Patients now see ${S.staff.draft.er.a} emergency beds free.`);
    } catch (e) {
      toast(e.message);
    } finally { btn.classList.remove('is-loading'); }
  }

  /* ================================================================
     STRAIN RISK INDEX
     ================================================================ */
  function viewSri() {
    return `<div class="wrap">
      <div style="padding-top:8px">
        <a class="linkbtn" href="#/">${ic('left', 'i-sm')}Home</a>
        <h1 class="h1" style="margin-top:6px">Strain Risk Index</h1>
        <p class="lead" style="margin-top:8px">Expected pressure on hospitals over the coming days, by area. Used for planning only.</p>
      </div>
      <div id="sri" style="margin-top:22px">${skeleton(2)}</div>
      <div class="notice" style="margin-top:20px">${ic('shield')}<span>The index never moves an emergency patient away from a suitable hospital. Emergency ranking uses travel time, beds and facilities only.</span></div>
    </div>`;
  }
  async function loadSri() {
    const box = $('#sri');
    try {
      const d = await api('/api/sri/regional');
      const s = d.sri || d;
      const zones = (Array.isArray(s) ? s : s.zones || s.regions || s.areas || s.districts || []).map((z) => {
        let v = num(pick(z.sri, z.score, z.index, z.value, z.riskScore));
        if (v != null && v > 1) v = v / 100;
        return { name: pick(z.zone, z.name, z.region, z.area, 'Area'), v, level: pick(z.level, z.band, z.risk) };
      }).filter((z) => z.v != null).sort((a, b) => b.v - a.v);
      const lvl = (z) => { const t = String(z.level || '').toLowerCase(); if (/high|severe|critical/.test(t) || z.v >= 0.7) return ['lvl-high', z.level || 'High']; if (/elev/.test(t) || z.v >= 0.6) return ['lvl-ele', z.level || 'Elevated']; if (/mod/.test(t) || z.v >= 0.4) return ['lvl-mod', z.level || 'Moderate']; return ['lvl-low', z.level || 'Low']; };
      if (!zones.length) { box.innerHTML = `<div class="empty"><p class="small">No outlook published yet.</p></div>`; return; }
      box.innerHTML = `<div class="sechead"><h2 class="h2">${esc(pick(s.region, 'All areas'))}${s.horizonDays ? `, next ${esc(s.horizonDays)} days` : ''}</h2></div>
        <ol class="sri stagger">${zones.map((z, i) => { const [c, t] = lvl(z); return `<li style="--i:${i}"><div><b>${esc(z.name)}</b><div class="small">${esc(t)} pressure</div></div><span class="sri__val">${Math.round(z.v * 100)}</span><span class="sri__bar ${c}" style="width:${Math.max(4, Math.round(z.v * 100))}%;animation-delay:${i * 70 + 150}ms"></span></li>`; }).join('')}</ol>
        ${s.generatedAt ? `<p class="fresh">${ic('clock', 'i-sm')}Calculated ${ago(s.generatedAt)}</p>` : ''}`;
    } catch (e) { box.innerHTML = errorBox(e.message, 'sri-reload'); }
  }

  /* ---------- Mount hooks (run after a view renders) ---------- */
  const MOUNTS = {
    '': () => { loadEmergency(false); if (GEO.watch == null && !S.locating) autoLocate(false); },
    emergency: () => {
      loadEmergency(false);
      if (GEO.watch == null && !S.locating) autoLocate(true);
    },
    request: (id) => {
      const rid = id || S.coordId;
      if (!rid) return;
      if (S.coord && S.coord.id === rid) drawQr(S.coord);
      pollRequest(rid);
    },
    planned: () => { if (S.plan.step === 4 && S.plan.status === 'idle') planSearch(); },
    me: () => { refreshAppts(); },
    hospital: () => { loadStaff(); },
    sri: () => { loadSri(); },
    signin: () => {},
    login: () => {}
  };

  /* ---------- Actions ---------- */
  function pressIn(el, groupSel) {
    const g = el.closest(groupSel);
    if (g) $$('[aria-pressed]', g).forEach((b) => b.setAttribute('aria-pressed', String(b === el)));
  }

  const ACTIONS = {
    'auth-mode': (el) => {
      // Keep what was typed when switching between Sign in and Create account.
      const keep = { email: ($('#p-email') || {}).value, name: ($('#p-name') || {}).value, phone: ($('#p-phone') || {}).value };
      S.authMode = el.dataset.v === 'register' ? 'register' : 'signin';
      if (keep.email) S.profile.email = keep.email;
      if (keep.name) S.profile.name = keep.name;
      if (keep.phone) S.profile.phone = keep.phone;
      render(true);
    },
    'toggle-pw': (el) => {
      const inp = $('#p-pass'); if (!inp) return;
      const show = inp.type === 'password'; inp.type = show ? 'text' : 'password';
      el.textContent = show ? 'Hide' : 'Show'; el.setAttribute('aria-pressed', String(show));
    },
    'patient-signout': () => { S.auth = null; store.del('auth'); toast('Signed out.'); paintNav(); window.location.hash = '#/'; },
    'close-sheet': () => closeSheet(),
    'share-family': (el) => {
      const c = S.coord;
      if (c && window.AIISNative && window.AIISNative.share) { window.AIISNative.share(familyMessage(c)); return; }
      if (c && navigator.share) { navigator.share({ title: 'AIIS', text: familyMessage(c) }).catch(() => {}); }
      else window.open(el.href, '_blank', 'noopener');
    },
    'pick-location': () => openSheet(locationSheet()),
    locate: () => locate(true),
    'set-loc': (el) => {
      const l = S.locations.find((x) => x.name === el.dataset.name);
      if (!l) return;
      stopGeo();
      S.loc = { ...l, source: 'manual' }; store.set('loc', S.loc);
      closeSheet(); paintLocBtn(); loadEmergency(true);
    },
    'retry-em': () => loadEmergency(true),
    details: (el) => openDetails(el.dataset.id),
    coordinate: (el) => openSheet(coordinateSheet(el.dataset.id)),
    'send-coord': (el) => sendCoordinate(el),
    'shake-settings': () => { if (window.AIISNative) window.AIISNative.openShakeSettings(); },
    who: (el) => {
      pressIn(el, '.seg');
      const form = el.closest('form');
      form.elements.who.value = el.dataset.v;
      $$('[data-show="other"]', form).forEach((x) => { x.hidden = el.dataset.v !== 'other'; });
    },
    'form-cat': (el) => { pressIn(el, '.chips'); el.closest('form').elements.emergencyCategory.value = el.dataset.id; },
    'cancel-request': () => openSheet(`<h2 class="h2 sheet-title" id="sheet-title">Cancel this request?</h2>
      <p class="lead" style="margin-top:8px">The held bed goes back to the hospital for other patients.</p>
      <div style="display:grid;gap:8px;margin-top:20px">
        <button class="btn btn--em btn--block" data-action="confirm-cancel">Yes, cancel request</button>
        <button class="btn btn--block" data-action="close-sheet" autofocus>Keep my request</button>
      </div>`),
    'confirm-cancel': async (el) => {
      const id = ($('#req') && $('#req').dataset.id) || S.coordId;
      el.classList.add('is-loading');
      try {
        const d = await api(`/api/coordination/${encodeURIComponent(id)}/cancel`, { reason: 'Cancelled by patient' }, trackHdr(id));
        S.coord = normRequest(d.request || d);
        S.coordId = null; store.del('coord');
        closeSheet();
        const box = $('#req'); if (box) box.innerHTML = requestHtml(S.coord);
        toast('Request cancelled. The bed was released.');
      } catch (e) { toast(e.message); el.classList.remove('is-loading'); }
    },
    'desk-verify': () => openSheet(`<h2 class="h2 sheet-title" id="sheet-title">Confirm arrival</h2>
      <p class="small" style="margin-top:6px">For casualty desk staff. Type the 4 digit code the patient shows you.</p>
      <form data-form="verify" style="margin-top:18px" novalidate>
        <label class="label" for="v-otp">Arrival code</label>
        <input class="input" id="v-otp" name="otp" inputmode="numeric" maxlength="6" autocomplete="one-time-code" style="font-size:1.75rem;font-weight:800;letter-spacing:.3em;max-width:220px" autofocus>
        <p class="err" data-err hidden></p>
        <button class="btn btn--ink btn--block" type="submit" style="margin-top:16px">Confirm arrival</button>
      </form>`),
    'plan-need': (el) => {
      const n = NEEDS.find((x) => x.id === el.dataset.id);
      Object.assign(S.plan, { need: n.id, specialty: n.specialty || '', label: n.label || '', search: Boolean(n.search), step: n.next, status: 'idle' });
      render();
    },
    'plan-spec': (el) => {
      const s = SPECIALTIES.find((x) => x.key === el.dataset.key);
      Object.assign(S.plan, { specialty: s ? s.key : '', label: s ? s.label : '', step: 3, status: 'idle' });
      render();
    },
    'plan-back': () => {
      const P = S.plan;
      P.step = P.step === 3 && !(P.need === 'specialist' || P.need === 'procedure') ? 1 : Math.max(1, P.step - 1);
      render();
    },
    'plan-goto': (el) => { S.plan.step = Number(el.dataset.step); render(); },
    'plan-loc': (el) => {
      const l = S.locations.find((x) => x.name === el.dataset.name);
      if (!l) return;
      stopGeo();
      S.loc = { ...l, source: 'manual' }; store.set('loc', S.loc);
      pressIn(el, '.chips');
      const g = $('[data-action="locate"]'); if (g) { g.classList.remove('btn--ink'); g.lastChild.textContent = 'Use my current location'; }
    },
    'plan-sector': (el) => { S.plan.sector = el.dataset.v; pressIn(el, '.seg'); },
    'plan-search': () => planSearch(),
    book: (el) => openSheet(bookSheet(el.dataset.id)),
    'pick-date': (el) => { pressIn(el, '.dates'); el.closest('form').elements.preferredDate.value = el.dataset.v; },
    'pick-slot': (el) => { pressIn(el, '.seg'); el.closest('form').elements.preferredTimeSlot.value = el.dataset.v; },
    'cancel-appt': async (el) => {
      el.classList.add('is-loading');
      try {
        await api(`/api/appointments/${encodeURIComponent(el.dataset.id)}/cancel`, { reason: 'Cancelled by patient' });
        S.appts = S.appts.map((a) => (a.id === el.dataset.id ? { ...a, status: 'CANCELLED' } : a));
        store.set('appts', S.appts);
        const box = $('#visits'); if (box) box.innerHTML = visitsHtml();
        toast('Visit request cancelled');
      } catch (e) { toast(e.message); el.classList.remove('is-loading'); }
    },
    'forget-me': () => {
      S.profile = {};
      store.del('profile');
      render(true);
      toast('Your name and number were removed from this phone');
    },
    step: (el) => {
      const h = S.staff.draft; if (!h) return;
      const b = h[el.dataset.k];
      const max = b.t != null ? b.t : 999;
      b.a = Math.max(0, Math.min(max, (b.a ?? 0) + Number(el.dataset.d)));
      const out = $('#out-' + el.dataset.k);
      out.textContent = b.a;
      out.classList.remove('bump'); void out.offsetWidth; out.classList.add('bump');
    },
    'staff-dep': (el) => { pressIn(el, '.seg'); S.staff.draft.departments[Number(el.dataset.i)].status = el.dataset.v; },
    'staff-eq': (el) => { pressIn(el, '.seg'); S.staff.draft.equipment[Number(el.dataset.i)].status = el.dataset.v; },
    'staff-publish': (el) => staffPublish(el),
    'staff-reload': () => { S.staff.status = 'idle'; loadStaff(); },
    'sri-reload': () => loadSri()
  };

  document.addEventListener('click', (e) => {
    const el = e.target.closest('[data-action]');
    if (!el) return;
    const fn = ACTIONS[el.dataset.action];
    if (!fn) return;
    if (el.tagName !== 'A' || el.dataset.action !== 'close-sheet') e.preventDefault();
    if (el.tagName === 'A' && el.dataset.action === 'close-sheet') { closeSheet(); return; }
    fn(el, e);
  });

  document.addEventListener('input', (e) => {
    const f = e.target.dataset && e.target.dataset.filter;
    if (f === 'loc') { const l = $('#loc-list'); if (l) l.innerHTML = locOptions(e.target.value); }
    if (f === 'plan-q') S.plan.query = e.target.value;
  });

  document.addEventListener('change', (e) => {
    if (e.target.dataset && e.target.dataset.change === 'staff-hospital') {
      S.staff.id = e.target.value; store.set('staffHospital', S.staff.id);
      S.staff.draft = null; S.staff.status = 'idle';
      const b = $('#staff-body'); if (b) b.innerHTML = staffBody();
      loadStaff();
    }
  });

  document.addEventListener('submit', async (e) => {
    const form = e.target.closest('form[data-form]');
    if (!form) return;
    e.preventDefault();
    const kind = form.dataset.form;
    if (kind === 'book') submitBook(form);
    else if (kind === 'patient-auth') {
      const errBox = $('#auth-error', form);
      const btn = $('#auth-submit-btn', form);
      if (errBox) { errBox.hidden = true; errBox.textContent = ''; }
      if (btn) { btn.disabled = true; btn.classList.add('is-loading'); }
      try {
        const fd = new FormData(form);
        const isReg = S.authMode === 'register';
        if (isReg) {
          const full_name = String(fd.get('full_name') || '').trim();
          const email = String(fd.get('email') || '').trim();
          const phone = String(fd.get('phone') || '').trim();
          const password = String(fd.get('password') || '');
          if (!full_name) throw new Error('Please add your name.');
          if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) throw new Error('Please check your email address.');
          if (password.length < 8) throw new Error('Password needs at least 8 characters.');
          await api('/api/auth/register', { full_name, email, phone, password, role: 'patient' });
          const res = await api('/api/auth/login', { email, password });
          const data = res.data || res;
          S.auth = { access_token: data.access_token, user: data.user };
          store.set('auth', S.auth);
          S.profile = { ...S.profile, name: data.user.full_name, email: data.user.email, phone: data.user.phone || phone };
          store.set('profile', S.profile);
          toast('Account created! Welcome, ' + (data.user.full_name || 'Patient') + '.');
        } else {
          const email = String(fd.get('email') || '').trim();
          const password = String(fd.get('password') || '');
          if (!email || !password) throw new Error('Please enter your email and password.');
          const res = await api('/api/auth/login', { email, password });
          const data = res.data || res;
          S.auth = { access_token: data.access_token, user: data.user };
          store.set('auth', S.auth);
          if (data.user && data.user.full_name) {
            S.profile = { ...S.profile, name: data.user.full_name, email: data.user.email, phone: data.user.phone || S.profile.phone || '' };
            store.set('profile', S.profile);
          }
          toast('Welcome back, ' + ((data.user && data.user.full_name) || 'Patient') + '!');
        }
        paintNav();
        window.location.hash = S.authReturn && !/signin|login/.test(S.authReturn) ? S.authReturn : '#/me';
      } catch (ex) {
        let msg = ex.message || 'Sign in failed. Please try again.';
        if (/invalid login|invalid credentials|invalid email or password/i.test(msg)) msg = 'Email or password is incorrect.';
        if (/already registered|already exists/i.test(msg)) msg = 'An account with this email already exists. Sign in instead.';
        if (errBox) {
          errBox.textContent = msg;
          errBox.hidden = false;
        } else {
          toast(ex.message || 'Authentication failed.');
        }
      } finally {
        if (btn) { btn.disabled = false; btn.classList.remove('is-loading'); }
      }
    }
    else if (kind === 'profile') {
      const f = new FormData(form);
      S.profile = Object.fromEntries([...f.entries()].map(([k, v]) => [k, String(v).trim()]).filter(([, v]) => v));
      store.set('profile', S.profile);
      toast('Details saved on this phone');
      render(true);
    } else if (kind === 'verify') {
      const err = $('[data-err]', form);
      const id = ($('#req') && $('#req').dataset.id) || S.coordId;
      try {
        const d = await api(`/api/coordination/${encodeURIComponent(id)}/verify-arrival`, { otp: String(new FormData(form).get('otp') || '').trim() });
        S.coord = normRequest(d.request || d);
        S.coordId = null; store.del('coord');
        closeSheet();
        const box = $('#req'); if (box) box.innerHTML = requestHtml(S.coord);
        toast('Arrival confirmed');
      } catch (ex) { err.hidden = false; err.textContent = ex.message; }
    }
  });

  async function checkOAuthCallback() {
    const raw = (window.location.hash || '').replace(/^#\/?/, '');
    if (raw.includes('error=')) {
      const searchPart = raw.includes('#') ? raw.split('#').pop() : (raw.includes('?') ? raw.split('?')[1] : raw);
      const params = new URLSearchParams(searchPart);
      const errDesc = params.get('error_description') || params.get('error') || 'Google sign-in was cancelled.';
      toast(decodeURIComponent(errDesc.replace(/\+/g, ' ')));
      window.location.hash = '#/signin';
      return;
    }
    if (!raw.includes('access_token=')) return;
    const searchPart = raw.includes('#') ? raw.split('#').pop() : (raw.includes('?') ? raw.split('?')[1] : raw);
    const params = new URLSearchParams(searchPart);
    const accessToken = params.get('access_token');
    if (!accessToken) return;

    try {
      S.auth = { access_token: accessToken, user: null };
      store.set('auth', S.auth);
      const meRes = await api('/api/auth/me');
      const user = (meRes && meRes.data) || meRes;
      S.auth.user = user;
      store.set('auth', S.auth);
      if (user && user.full_name) {
        S.profile = { ...S.profile, name: user.full_name, email: user.email, phone: user.phone || S.profile.phone || '' };
        store.set('profile', S.profile);
      }
      toast('Signed in with Google! Welcome, ' + ((user && user.full_name) || 'Patient') + '.');
    } catch {
      try {
        const payload = JSON.parse(atob(accessToken.split('.')[1]));
        const user = { id: payload.sub, email: payload.email, full_name: (payload.user_metadata && (payload.user_metadata.full_name || payload.user_metadata.name)) || 'Patient', role: 'patient' };
        S.auth = { access_token: accessToken, user };
        store.set('auth', S.auth);
        S.profile = { ...S.profile, name: user.full_name, email: user.email };
        store.set('profile', S.profile);
        toast('Signed in with Google!');
      } catch (e) {
        console.error('Failed to parse OAuth session:', e);
      }
    }
    paintNav();
    window.location.hash = '#/me';
  }

  window.addEventListener('hashchange', (ev) => {
    const prev = (ev && ev.oldURL && ev.oldURL.indexOf('#') >= 0) ? ev.oldURL.slice(ev.oldURL.indexOf('#')) : '#/';
    const r = route().r;
    if ((r === 'signin' || r === 'login') && !/#\/(signin|login)/.test(prev) && prev.indexOf('access_token') < 0) S.authReturn = prev;
    if (!['', 'emergency', 'planned', 'request'].includes(r)) stopGeo();
    closeSheet(); checkOAuthCallback(); render();
  });

  /* ---------- Boot ---------- */
  checkOAuthCallback();
  render();
  Promise.all([loadLocations(), loadCoord()]).then(() => {
    const { r } = route();
    if (r === '' || r === 'emergency' || r === 'me' || (r === 'planned' && S.plan.step === 3)) render(true);
  });
})();
