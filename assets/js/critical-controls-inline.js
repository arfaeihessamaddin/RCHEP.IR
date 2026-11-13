/* Critical controls run inline in every HTML page.
 * Keep this small: it must work even when an external JavaScript request stalls. */
(function () {
  'use strict';
  if (window.__rchepCriticalControls) return;
  window.__rchepCriticalControls = true;

  const root = document.documentElement;
  const themeButton = document.getElementById('theme-toggle');
  const languageButton = document.getElementById('lang-toggle');

  function readPreference(key, fallback) {
    try { return localStorage.getItem(key) || fallback; } catch (_) { return fallback; }
  }

  function savePreference(key, value) {
    try { localStorage.setItem(key, value); } catch (_) { /* Current page still works. */ }
  }

  function themeIcon(theme) {
    return theme === 'dark'
      ? '<svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/></svg>'
      : '<svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/></svg>';
  }

  function applyTheme(theme) {
    const safeTheme = theme === 'light' ? 'light' : 'dark';
    root.setAttribute('data-theme', safeTheme);
    if (themeButton) {
      themeButton.innerHTML = themeIcon(safeTheme);
      themeButton.setAttribute('aria-label', safeTheme === 'dark'
        ? 'تغییر نمایش به حالت روز' : 'تغییر نمایش به حالت شب');
    }
    savePreference('theme', safeTheme);
  }

  applyTheme(readPreference('theme', 'dark'));
  if (themeButton) {
    themeButton.addEventListener('click', function () {
      applyTheme(root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
    });
  }

  const titles = {
    'مرکز پژوهشی فیزیک انرژی بالا | دانشگاه صنعتی شریف': 'Research Center for High Energy Physics | Sharif University of Technology',
    'درباره مرکز | مرکز پژوهشی فیزیک انرژی بالا (RCHEP)': 'About | Research Center for High Energy Physics (RCHEP)',
    'محورهای پژوهشی | مرکز پژوهشی فیزیک انرژی بالا (RCHEP)': 'Research Areas | Research Center for High Energy Physics (RCHEP)',
    'اعضای مرکز | مرکز پژوهشی فیزیک انرژی بالا (RCHEP)': 'People | Research Center for High Energy Physics (RCHEP)',
    'رویدادها و سمینارها | مرکز پژوهشی فیزیک انرژی بالا (RCHEP)': 'Events & Seminars | Research Center for High Energy Physics (RCHEP)',
    'فهرست مقالات | مرکز پژوهشی فیزیک انرژی بالا (RCHEP)': 'Publications | Research Center for High Energy Physics (RCHEP)',
    'حامیان مرکز | مرکز پژوهشی فیزیک انرژی بالا (RCHEP)': 'Sponsors | Research Center for High Energy Physics (RCHEP)',
    'اطلاعیه‌ها | مرکز پژوهشی فیزیک انرژی بالا (RCHEP)': 'Notices | Research Center for High Energy Physics (RCHEP)',
    'ارتباط با مرکز | مرکز پژوهشی فیزیک انرژی بالا (RCHEP)': 'Contact | Research Center for High Energy Physics (RCHEP)'
  };
  const originalTitle = document.title;

  function activeLanguage() {
    try {
      const query = new URLSearchParams(location.search).get('lang');
      if (query === 'en' || query === 'fa') return query;
    } catch (_) { /* Fall back to storage. */ }
    const stored = readPreference('rchep_lang', 'fa');
    return stored === 'en' ? 'en' : 'fa';
  }

  function applyLanguage(language) {
    const lang = language === 'en' ? 'en' : 'fa';
    const english = lang === 'en';
    root.lang = lang;
    root.dir = english ? 'ltr' : 'rtl';
    document.body.dir = root.dir;
    document.title = english && titles[originalTitle] ? titles[originalTitle] : originalTitle;

    if (languageButton) {
      languageButton.textContent = english ? 'فارسی' : 'English';
      languageButton.title = english ? 'تغییر زبان به فارسی' : 'Switch to English';
    }

    document.querySelectorAll('[data-fa]').forEach(function (element) {
      const value = element.getAttribute(english ? 'data-en' : 'data-fa');
      if (value !== null) element.textContent = value;
    });

    const search = document.getElementById('pub-search');
    if (search) {
      search.placeholder = english
        ? 'Search papers by title, author, or arXiv ID...'
        : 'جستجو بر اساس عنوان مقاله، نام پژوهشگر یا شناسه arXiv...';
    }

    document.querySelectorAll('a[href]').forEach(function (anchor) {
      const href = anchor.getAttribute('href');
      if (!href || /^(?:https?:|mailto:|#)/.test(href) || !href.includes('.html')) return;
      const pieces = href.split('#');
      const path = pieces[0].split('?')[0];
      anchor.setAttribute('href', path + (english ? '?lang=en' : '') + (pieces[1] ? '#' + pieces[1] : ''));
    });

    savePreference('rchep_lang', lang);
    try {
      const url = new URL(location.href);
      if (english) url.searchParams.set('lang', 'en');
      else url.searchParams.delete('lang');
      history.replaceState({}, '', url);
    } catch (_) { /* Language still changes without History API. */ }
  }

  window.rchepApplyLanguage = applyLanguage;
  applyLanguage(activeLanguage());
  if (languageButton) {
    languageButton.addEventListener('click', function (event) {
      event.preventDefault();
      applyLanguage(root.lang === 'fa' ? 'en' : 'fa');
    });
  }
}());
