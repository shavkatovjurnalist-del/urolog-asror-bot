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

    // «Murojaat» bo'limi AI ulangunga qadar yopiq
    const askOn = d.flags?.ask_enabled;
    $('#ask-form').hidden = !askOn;
    $('#ask-soon').hidden = !!askOn;
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
    $('#book-hours').textContent = 'Qabul kunlari: ' + doc.work_hours;

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
    $('#b-service').innerHTML =
      '<option value="">Umumiy maslahat</option>' +
      d.services.map((s) => `<option value="${s.id}">${esc(s.title)}</option>`).join('');
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
      const btn = e.target.querySelector('button[type=submit]');
      btn.disabled = true;
      btn.textContent = 'Yuborilmoqda…';
      try {
        const r = await api('/api/appointments', {
          full_name: name.value.trim(),
          phone: phone.value.trim(),
          clinic_id: Number($('#b-clinic').value) || null,
          service_id: Number($('#b-service').value) || null,
          preferred_time: $('#b-time').value.trim(),
          comment: $('#b-comment').value.trim(),
        });
        notify('success');
        $('#book-form').hidden = true;
        $('#book-ok').hidden = false;
        $('#book-ok-text').textContent =
          `Ariza raqami №${r.id}. Shifokor yordamchisi tez orada siz bilan bog'lanadi.`;
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

    // Murojaat (AI joyi)
    $('#ask-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const ta = $('#ask-text');
      if (ta.value.trim().length < 5) {
        ta.classList.add('err');
        notify('error');
        toast('Savolingizni batafsilroq yozing');
        return;
      }
      ta.classList.remove('err');
      const btn = e.target.querySelector('button[type=submit]');
      btn.disabled = true;
      btn.textContent = 'Yuborilmoqda…';
      try {
        const r = await api('/api/consultations', { message: ta.value.trim() });
        notify('success');
        $('#ask-form').hidden = true;
        $('#ask-ok').hidden = false;
        if (r.answer) {
          $('#ask-ok').querySelector('p').textContent = r.answer;
        }
      } catch (err) {
        notify('error');
        toast(err.message);
      } finally {
        btn.disabled = false;
        btn.textContent = 'Yuborish';
      }
    });

    $('#ask-again').addEventListener('click', () => {
      $('#ask-text').value = '';
      $('#ask-form').hidden = false;
      $('#ask-ok').hidden = true;
    });
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
