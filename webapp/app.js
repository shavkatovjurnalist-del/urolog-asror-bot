/* Dr. Asror To'rayev — Telegram Mini App */
(() => {
  'use strict';

  const tg = window.Telegram?.WebApp;
  const initData = tg?.initData || '';
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => Array.from(document.querySelectorAll(s));

  let DATA = null;
  let currentPage = 'home';
  const history = [];

  // ─────────── Telegram sozlamalari ───────────
  function initTelegram() {
    if (!tg) return;
    tg.ready();
    tg.expand();
    try { tg.disableVerticalSwipes?.(); } catch (_) {}
    try {
      tg.setHeaderColor('#007a70');
      tg.setBackgroundColor(tg.themeParams?.secondary_bg_color || '#f2f5f6');
    } catch (_) {}
    tg.BackButton?.onClick(goBack);
  }

  const haptic = (type = 'light') => {
    try { tg?.HapticFeedback?.impactOccurred(type); } catch (_) {}
  };
  const notify = (type) => {
    try { tg?.HapticFeedback?.notificationOccurred(type); } catch (_) {}
  };

  function toast(text) {
    const el = $('#toast');
    el.textContent = text;
    el.classList.add('show');
    clearTimeout(el._t);
    el._t = setTimeout(() => el.classList.remove('show'), 2600);
  }

  const openLink = (url) => (tg?.openLink ? tg.openLink(url) : window.open(url, '_blank'));
  const openTg = (url) => (tg?.openTelegramLink ? tg.openTelegramLink(url) : window.open(url, '_blank'));

  // ─────────── Navigatsiya ───────────
  function showPage(name, push = true) {
    if (name === currentPage) return;
    if (push && currentPage) history.push(currentPage);

    $$('.page').forEach((p) => (p.hidden = true));
    const page = $(`#page-${name}`);
    if (page) page.hidden = false;
    window.scrollTo({ top: 0, behavior: 'instant' in window ? 'instant' : 'auto' });

    $$('.tab').forEach((t) => t.classList.toggle('active', t.dataset.page === name));
    currentPage = name;

    if (tg?.BackButton) {
      if (name === 'home') tg.BackButton.hide();
      else tg.BackButton.show();
    }
  }

  function goBack() {
    if (!$('#sheet').hidden) { closeSheet(); return; }
    const prev = history.pop() || 'home';
    showPage(prev, false);
  }

  // ─────────── Batafsil oyna ───────────
  function openSheet(html, bookable = true) {
    $('#sheet-body').innerHTML = html;
    $('#sheet-book').hidden = !bookable;
    $('#sheet').hidden = false;
    haptic('light');
    tg?.BackButton?.show();
  }
  function closeSheet() {
    $('#sheet').hidden = true;
    if (currentPage === 'home') tg?.BackButton?.hide();
  }

  const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  // ─────────── Kontentni chizish ───────────
  function render(d) {
    const doc = d.doctor;

    // «Jonli murojaat» AI ulangunga qadar yopiq
    const askOn = d.flags?.ask_enabled;
    $('#ask-soon').hidden = !!askOn;
    $('#chat-intro').hidden = !askOn;
    if (!askOn) {
      $('#ask-sub').textContent = 'AI-konsultant tayyorlanmoqda — tez orada ishga tushadi.';
    }

    // Hero
    $('#doc-photo').src = doc.photo || 'assets/asror.webp';
    $('#doc-name').textContent = doc.short_name;
    $('#doc-role').textContent = doc.specialty;
    $('#doc-cat').textContent = '🏅 ' + doc.category;
    $('#doc-exp').textContent = '🕐 Tajriba ' + doc.experience;
    $('#doc-bio').textContent = doc.bio;
    $('#doc-hours').textContent = '🗓 Qabul kunlari: ' + doc.work_hours;
    // Jadval API'dan olinadi — matn hech qachon eskirmasin
    const slots = d.schedule?.slots || [];
    if (slots.length) {
      const span = `${slots[0]} – ${slots[slots.length - 1]}`;
      $('#book-hours').textContent =
        `Onlayn yozilish: Dushanba–Juma, ${span} · ${d.schedule.lunch} tushlik.`;
      $('#b-slot-hint').textContent =
        `Qabul ${span} · ${d.schedule.lunch} tushlik.`;
    }

    // Aloqa
    $('#doc-phone').textContent = doc.phone;
    $('#link-phone').href = 'tel:' + doc.phone.replace(/\s/g, '');
    $('#link-tg').href = doc.telegram;
    $('#link-ig').href = doc.instagram;
    $('#link-yt').href = doc.youtube;
    $('#link-site').href = doc.website;
    ['#link-tg', '#link-ig', '#link-yt', '#link-site'].forEach((sel) => {
      $(sel).addEventListener('click', (e) => {
        e.preventDefault();
        const url = $(sel).href;
        sel === '#link-tg' ? openTg(url) : openLink(url);
      });
    });

    // Afzalliklar
    $('#advantages').innerHTML = d.advantages
      .map((a) => `<div class="adv"><div class="i">${esc(a.icon)}</div>
        <b>${esc(a.title)}</b><span>${esc(a.description)}</span></div>`)
      .join('');

    // Natijalar
    $('#results').innerHTML = d.results
      .map((r) => `<div class="vid" data-url="${esc(r.url)}">
        <div class="vid-thumb">
          <img src="${esc(r.thumb)}" alt="${esc(r.title)}" loading="lazy"
               onerror="this.style.display='none'" />
          <div class="play">▶︎</div>
        </div>
        <div class="vid-title">${esc(r.title)}</div></div>`)
      .join('');
    $$('.vid').forEach((v) =>
      v.addEventListener('click', () => { haptic(); openLink(v.dataset.url); }));

    // FAQ
    $('#faq').innerHTML = d.faq
      .map((f) => `<details><summary>${esc(f.q)}</summary><p>${esc(f.a)}</p></details>`)
      .join('');

    // Xizmatlar
    $('#services').innerHTML = d.services
      .map((s) => `<button class="item" data-type="service" data-id="${s.id}">
        <div class="item-ico">${esc(s.icon)}</div>
        <div class="item-txt"><b>${esc(s.title)}</b><span>${esc(s.short || '')}</span></div>
        <div class="item-arrow">›</div></button>`)
      .join('');

    // Usullar
    $('#methods').innerHTML = d.methods
      .map((m) => `<button class="item" data-type="method" data-id="${m.id}">
        <div class="item-ico">${esc(m.icon)}</div>
        <div class="item-txt"><b>${esc(m.title)}</b><span>${esc(m.description.slice(0, 78))}…</span></div>
        <div class="item-arrow">›</div></button>`)
      .join('');

    $$('.item').forEach((el) =>
      el.addEventListener('click', () => {
        const id = Number(el.dataset.id);
        if (el.dataset.type === 'service') {
          const s = d.services.find((x) => x.id === id);
          openSheet(`<span class="ico">${esc(s.icon)}</span><h3>${esc(s.title)}</h3>
            <p>${esc(s.description)}</p>
            <p class="note">Aniq tashxis va davolash rejasi ko'rikdan so'ng belgilanadi.</p>`);
          $('#sheet-book').dataset.serviceId = id;
        } else {
          const m = d.methods.find((x) => x.id === id);
          openSheet(`<span class="ico">${esc(m.icon)}</span><h3>${esc(m.title)}</h3>
            <p>${esc(m.description)}</p>`);
          delete $('#sheet-book').dataset.serviceId;
        }
      }));

    // Klinikalar
    $('#clinics').innerHTML = d.clinics
      .map((c) => `<div class="clinic">
        ${c.photo ? `<img src="${esc(c.photo)}" alt="${esc(c.name)}" loading="lazy" />` : ''}
        <div class="clinic-b">
          <b>${esc(c.name)}</b>
          <p>📍 ${esc(c.address)}</p>
          ${c.landmark ? `<p>🧭 ${esc(c.landmark)}</p>` : ''}
          ${c.work_hours ? `<p>🕐 ${esc(c.work_hours)}</p>` : ''}
          <div class="clinic-actions">
            ${c.map_url ? `<a href="${esc(c.map_url)}" data-ext>🗺 Xarita</a>` : ''}
            <button class="fill" data-book-clinic="${c.id}">📅 Yozilish</button>
          </div>
        </div></div>`)
      .join('');
    $$('[data-ext]').forEach((a) =>
      a.addEventListener('click', (e) => { e.preventDefault(); openLink(a.href); }));
    $$('[data-book-clinic]').forEach((b) =>
      b.addEventListener('click', () => {
        $('#b-clinic').value = b.dataset.bookClinic;
        showPage('book');
      }));

    // Forma select'lari
    $('#b-clinic').innerHTML =
      '<option value="">Farqi yo\'q</option>' +
      d.clinics.map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join('');
    // «Konsultatsiya» — ro'yxatning eng tepasida
    $('#b-service').innerHTML =
      '<option value="">💬 Konsultatsiya (umumiy maslahat)</option>' +
      d.services.map((s) => `<option value="${s.id}">${esc(s.title)}</option>`).join('');

    initSchedule();
  }

  // ─────────── Sana va soat (qoidalar serverdan keladi) ───────────
  let SLOTS = ['09:00', '10:00', '11:00', '13:00', '14:00',
               '15:00', '16:00', '17:00', '18:00'];
  let CLOSED_DAYS = [5, 6];   // 5 = shanba, 6 = yakshanba (Mon=0)
  const MONTHS_UZ = ['yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun',
                     'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr'];
  const WEEK_UZ = ['Yakshanba', 'Dushanba', 'Seshanba', 'Chorshanba',
                   'Payshanba', 'Juma', 'Shanba'];
  let pickedSlot = '';

  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  // JS: Yakshanba=0 … Shanba=6.  Server: Dushanba=0 … Yakshanba=6.
  const isClosed = (d) => CLOSED_DAYS.includes((d.getDay() + 6) % 7);

  function nextWorkday(from) {
    const d = new Date(from);
    while (isClosed(d)) d.setDate(d.getDate() + 1);
    return d;
  }

  function initSchedule() {
    const sc = DATA?.schedule;
    if (sc) {
      SLOTS = sc.slots || SLOTS;
      CLOSED_DAYS = sc.closed_weekdays || CLOSED_DAYS;
    }

    const input = $('#b-date');
    const minD = sc?.min_date ? new Date(sc.min_date + 'T00:00:00') : (() => {
      const d = new Date(); d.setDate(d.getDate() + 1); return d;
    })();
    const maxD = sc?.max_date ? new Date(sc.max_date + 'T00:00:00') : (() => {
      const d = new Date(); d.setDate(d.getDate() + 60); return d;
    })();

    input.min = iso(minD);
    input.max = iso(maxD);
    input.value = iso(nextWorkday(minD));
    input.dataset.min = iso(minD);

    $('#b-slots').innerHTML = SLOTS
      .map((s) => `<button type="button" class="slot" data-slot="${s}">${s}</button>`)
      .join('');
    $$('.slot').forEach((b) =>
      b.addEventListener('click', () => {
        haptic();
        pickedSlot = b.dataset.slot;
        $$('.slot').forEach((x) => x.classList.toggle('on', x === b));
        $('#b-slots').classList.remove('err');
      }));

    input.addEventListener('change', checkDate);
    checkDate();
  }

  function checkDate() {
    const input = $('#b-date');
    const hint = $('#b-date-hint');
    if (!input.value) return false;
    const d = new Date(input.value + 'T00:00:00');
    const minD = new Date((input.dataset.min || input.min) + 'T00:00:00');

    if (isClosed(d)) {
      hint.textContent = '⚠️ Shanba va yakshanba qabul yo\'q — ish kunini tanlang.';
      hint.classList.add('warn');
      input.classList.add('err');
      return false;
    }
    if (d < minD) {
      hint.textContent = '⚠️ Faqat ertangi kundan boshlab yozilish mumkin.';
      hint.classList.add('warn');
      input.classList.add('err');
      return false;
    }
    hint.textContent = `${d.getDate()}-${MONTHS_UZ[d.getMonth()]}, ${WEEK_UZ[d.getDay()]}`;
    hint.classList.remove('warn');
    input.classList.remove('err');
    return true;
  }

  function scheduleText() {
    const d = new Date($('#b-date').value + 'T00:00:00');
    return `${d.getDate()}-${MONTHS_UZ[d.getMonth()]}, ${WEEK_UZ[d.getDay()]}, soat ${pickedSlot}`;
  }

  // ─────────── API ───────────
  async function api(path, body) {
    const res = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ initData, ...body }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'Xatolik yuz berdi');
    return data;
  }

  // ─────────── Hodisalar ───────────
  function bindEvents() {
    $$('.tab').forEach((t) =>
      t.addEventListener('click', () => { haptic(); showPage(t.dataset.page); }));

    $$('[data-action]').forEach((b) =>
      b.addEventListener('click', () => {
        haptic();
        const a = b.dataset.action;
        if (a === 'book') showPage('book');
        if (a === 'call') window.location.href = 'tel:' + DATA.doctor.phone.replace(/\s/g, '');
        if (a === 'tg') openTg(DATA.doctor.telegram);
      }));

    $('.sheet-back').addEventListener('click', closeSheet);
    $('#sheet-book').addEventListener('click', () => {
      const sid = $('#sheet-book').dataset.serviceId;
      if (sid) $('#b-service').value = sid;
      closeSheet();
      showPage('book');
    });

    // Qabulga yozilish
    $('#book-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const name = $('#b-name');
      const phone = $('#b-phone');
      name.classList.toggle('err', name.value.trim().length < 3);
      const digits = phone.value.replace(/\D/g, '');
      phone.classList.toggle('err', digits.length < 9);
      if (name.classList.contains('err') || phone.classList.contains('err')) {
        notify('error');
        toast('Ism va telefon raqamini to\'g\'ri kiriting');
        return;
      }
      if (!checkDate()) {
        notify('error');
        toast('Qabul kunini to\'g\'ri tanlang');
        return;
      }
      if (!pickedSlot) {
        $('#b-slots').classList.add('err');
        notify('error');
        toast('Qabul soatini tanlang');
        return;
      }
      const btn = e.target.querySelector('button[type=submit]');
      btn.disabled = true;
      btn.textContent = 'Yuborilmoqda…';
      try {
        const r = await api('/api/appointments', {
          full_name: name.value.trim(),
          phone: phone.value.trim(),
          clinic_id: Number($('#b-clinic').value) || null,
          service_id: Number($('#b-service').value) || null,
          scheduled_at: `${$('#b-date').value}T${pickedSlot}:00`,
          preferred_time: scheduleText(),
          comment: $('#b-comment').value.trim(),
        });
        notify('success');
        $('#book-form').hidden = true;
        $('#book-ok').hidden = false;
        $('#book-ok-num').textContent = `№${r.id}`;
        $('#book-ok-text').textContent =
          `Tanlangan vaqt: ${scheduleText()}. Iltimos, javobni kuting — shifokor ` +
          `arizani ko'rib chiqib tasdiqlaydi, natija botga xabar bo'lib keladi.`;
      } catch (err) {
        notify('error');
        toast(err.message);
      } finally {
        btn.disabled = false;
        btn.textContent = 'Arizani yuborish';
      }
    });

    $('#book-close').addEventListener('click', () => {
      $('#book-form').reset();
      $('#book-form').hidden = false;
      $('#book-ok').hidden = true;
      showPage('home');
    });

    // ─────────── Jonli murojaat (AI suhbati) ───────────
    $('#chat-start').addEventListener('click', startChat);
    $('#chat-end').addEventListener('click', endChat);
    $('#chat-form').addEventListener('submit', sendChat);
  }

  // ─────────── Jonli suhbat ───────────
  function bubble(role, text) {
    const div = document.createElement('div');
    div.className = 'msg ' + (role === 'user' ? 'me' : 'op');
    div.textContent = text;
    $('#chat-log').appendChild(div);
    $('#chat-log').scrollTop = $('#chat-log').scrollHeight;
    return div;
  }

  async function startChat() {
    haptic('light');
    $('#chat-intro').hidden = true;
    $('#chat-box').hidden = false;
    $('#chat-log').innerHTML = '';
    const typing = bubble('op', '…');
    try {
      const r = await api('/api/chat/start', {});
      typing.textContent = r.greeting;
      $('#chat-text').focus();
    } catch (err) {
      typing.remove();
      toast(err.message);
      $('#chat-intro').hidden = false;
      $('#chat-box').hidden = true;
    }
  }

  async function sendChat(e) {
    e.preventDefault();
    const input = $('#chat-text');
    const text = input.value.trim();
    if (!text) return;

    input.value = '';
    bubble('user', text);
    const typing = bubble('op', '…');
    typing.classList.add('typing');
    $('#chat-send').disabled = true;

    try {
      const r = await api('/api/chat', { message: text });
      typing.classList.remove('typing');
      typing.textContent = r.reply;
    } catch (err) {
      typing.classList.remove('typing');
      typing.textContent =
        'Javob kelmadi. Internetni tekshiring yoki +998 90 008 38 78 raqamiga qo\'ng\'iroq qiling.';
      notify('error');
    } finally {
      $('#chat-send').disabled = false;
      input.focus();
      $('#chat-log').scrollTop = $('#chat-log').scrollHeight;
    }
  }

  async function endChat() {
    try { await api('/api/chat/end', {}); } catch (_) {}
    $('#chat-box').hidden = true;
    $('#chat-intro').hidden = false;
    $('#chat-log').innerHTML = '';
    toast('Suhbat yakunlandi');
  }

  // ─────────── Start ───────────
  async function start() {
    initTelegram();
    try {
      const res = await fetch('/api/content');
      DATA = await res.json();
      render(DATA);
      bindEvents();
      $('#app').hidden = false;
      $('#splash').classList.add('hide');
      setTimeout(() => $('#splash').remove(), 450);
    } catch (e) {
      $('#splash').innerHTML =
        '<div class="splash-logo">⚠️</div><div class="splash-text">' +
        'Ma\'lumot yuklanmadi. Internetni tekshirib, qayta oching.</div>';
    }
  }

  start();
})();
