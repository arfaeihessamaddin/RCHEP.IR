// RCHEP Main Interactive Scripts (High-Performance & Instant Navigation)

document.addEventListener('DOMContentLoaded', () => {
  // 1. Theme Toggle
  const themeToggle = document.getElementById('theme-toggle');
  const currentTheme = localStorage.getItem('theme') || 'dark';
  document.documentElement.setAttribute('data-theme', currentTheme);

  if (themeToggle) {
    updateThemeIcon(currentTheme);
    themeToggle.addEventListener('click', () => {
      const activeTheme = document.documentElement.getAttribute('data-theme');
      const newTheme = activeTheme === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', newTheme);
      localStorage.setItem('theme', newTheme);
      updateThemeIcon(newTheme);
    });
  }

  function updateThemeIcon(theme) {
    if (!themeToggle) return;
    themeToggle.innerHTML = theme === 'dark' 
      ? '<svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/></svg>'
      : '<svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/></svg>';
  }

  // 2. Mobile Menu Toggle
  const mobileToggle = document.getElementById('mobile-toggle');
  const navLinks = document.querySelector('.nav-links');
  if (mobileToggle && navLinks) {
    mobileToggle.addEventListener('click', () => {
      navLinks.classList.toggle('active');
    });
  }

  // 3. Tab Filtering & Search (Instant with .is-hidden CSS class)
  const tabButtons = document.querySelectorAll('.tab-btn');
  const pubSearchInput = document.getElementById('pub-search');
  const countElem = document.getElementById('pub-count');

  function filterItems() {
    const activeTab = document.querySelector('.tab-btn.active');
    const filter = activeTab ? activeTab.getAttribute('data-filter') : 'all';
    const query = pubSearchInput ? pubSearchInput.value.trim().toLowerCase() : '';

    const items = document.querySelectorAll('[data-category]');
    let visibleCount = 0;

    items.forEach(item => {
      const cat = item.getAttribute('data-category');
      const text = item.textContent.toLowerCase();
      
      const matchCat = (!filter || filter === 'all' || cat === filter);
      const matchQuery = !query || text.includes(query);

      if (matchCat && matchQuery) {
        item.classList.remove('is-hidden');
        visibleCount++;
      } else {
        item.classList.add('is-hidden');
      }
    });

    if (countElem) {
      countElem.textContent = visibleCount;
    }
  }

  if (tabButtons.length > 0) {
    tabButtons.forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const parent = btn.parentElement;
        if (parent) {
          parent.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        } else {
          tabButtons.forEach(b => b.classList.remove('active'));
        }
        btn.classList.add('active');
        filterItems();
      });
    });
  }

  if (pubSearchInput) {
    pubSearchInput.addEventListener('input', filterItems);
  }

  // Initial filter run
  filterItems();

  // 4. Ultra-Fast Bilingual Engine
  const langToggle = document.getElementById('lang-toggle');
  const savedLang = localStorage.getItem('lang') || 'fa';

  if (savedLang === 'en') {
    applyLanguage('en');
  }

  if (langToggle) {
    langToggle.addEventListener('click', (e) => {
      e.preventDefault();
      const cur = document.body.getAttribute('dir') === 'ltr' ? 'en' : 'fa';
      const target = cur === 'fa' ? 'en' : 'fa';
      applyLanguage(target);
      localStorage.setItem('lang', target);
      filterItems();
    });
  }

  function applyLanguage(lang) {
    const isEn = lang === 'en';
    document.body.setAttribute('dir', isEn ? 'ltr' : 'rtl');
    document.documentElement.setAttribute('lang', isEn ? 'en' : 'fa');

    if (langToggle) {
      langToggle.textContent = isEn ? 'فارسی' : 'English';
    }

    // A. Elements with data-fa and data-en
    document.querySelectorAll('[data-fa]').forEach(el => {
      const enText = el.getAttribute('data-en');
      const faText = el.getAttribute('data-fa');
      if (isEn && enText) {
        el.textContent = enText;
      } else if (!isEn && faText) {
        el.textContent = faText;
      }
    });

    // B. Fast O(1) Dictionary Translation (No heavy nested loops)
    const dict = window.RCHEP_TRANSLATIONS;
    if (dict) {
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
      let node;
      while ((node = walker.nextNode())) {
        if (node.parentElement && (node.parentElement.tagName === 'SCRIPT' || node.parentElement.tagName === 'STYLE' || node.parentElement.hasAttribute('data-fa'))) {
          continue;
        }

        const trimmed = node.nodeValue.trim();
        if (!trimmed) continue;

        if (isEn) {
          if (!node._faOriginal) {
            node._faOriginal = node.nodeValue;
          }
          if (dict[trimmed]) {
            node.nodeValue = node.nodeValue.replace(trimmed, dict[trimmed]);
          }
        } else if (node._faOriginal) {
          node.nodeValue = node._faOriginal;
        }
      }
    }

    // C. Search input placeholder
    if (pubSearchInput) {
      pubSearchInput.placeholder = isEn 
        ? 'Search papers by title, author, or arXiv ID...' 
        : 'جستجو بر اساس عنوان مقاله، نام پژوهشگر یا شناسه arXiv...';
    }
  }
});
