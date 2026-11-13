// RCHEP Main Interactive Scripts (High-Performance & Instant Navigation)

document.addEventListener('DOMContentLoaded', () => {
  // 1. Theme Toggle
  const themeToggle = document.getElementById('theme-toggle');
  let currentTheme = 'dark';
  try {
    currentTheme = localStorage.getItem('theme') || 'dark';
  } catch (error) {
    // Keep the interface functional when browser storage is unavailable.
  }
  document.documentElement.setAttribute('data-theme', currentTheme);

  if (themeToggle) {
    updateThemeIcon(currentTheme);
    themeToggle.addEventListener('click', () => {
      const activeTheme = document.documentElement.getAttribute('data-theme');
      const newTheme = activeTheme === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', newTheme);
      try {
        localStorage.setItem('theme', newTheme);
      } catch (error) {
        // Theme still changes for the current page when storage is unavailable.
      }
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
    const activeTopicBtn = document.querySelector('#topic-filters .tab-btn.active') || document.querySelector('.filter-tabs:not(#year-filters) .tab-btn.active');
    const activeYearBtn = document.querySelector('#year-filters .tab-btn.active');
    
    const topicFilter = activeTopicBtn ? (activeTopicBtn.getAttribute('data-filter') || 'all') : 'all';
    const yearFilter = activeYearBtn ? (activeYearBtn.getAttribute('data-year') || 'all') : 'all';
    const query = pubSearchInput ? pubSearchInput.value.trim().toLowerCase() : '';

    const items = document.querySelectorAll('[data-category]');
    let visibleCount = 0;

    items.forEach(item => {
      const cat = item.getAttribute('data-category');
      const itemYear = item.getAttribute('data-year');
      const text = item.textContent.toLowerCase();
      
      const matchTopic = (!topicFilter || topicFilter === 'all' || cat === topicFilter);
      const matchYear = (!yearFilter || yearFilter === 'all' || itemYear === yearFilter);
      const matchQuery = !query || text.includes(query);

      if (matchTopic && matchYear && matchQuery) {
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
        const parent = btn.closest('.filter-tabs');
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

  // 4. Bulletproof Bilingual Engine (Pure Attribute-Based, Instant & Reliable)
  const langToggle = document.getElementById('lang-toggle');

  const pageTitleMap = {
    'مرکز پژوهشی فیزیک انرژی بالا | دانشگاه صنعتی شریف': 'Research Center for High Energy Physics | Sharif University of Technology',
    'درباره مرکز | مرکز پژوهشی فیزیک انرژی بالا (RCHEP)': 'About | Research Center for High Energy Physics (RCHEP)',
    'محورهای پژوهشی | مرکز پژوهشی فیزیک انرژی بالا (RCHEP)': 'Research Areas | Research Center for High Energy Physics (RCHEP)',
    'اعضای مرکز | مرکز پژوهشی فیزیک انرژی بالا (RCHEP)': 'People | Research Center for High Energy Physics (RCHEP)',
    'رویدادها و سمینارها | مرکز پژوهشی فیزیک انرژی بالا (RCHEP)': 'Events & Seminars | Research Center for High Energy Physics (RCHEP)',
    'فهرست مقالات | مرکز پژوهشی فیزیک انرژی بالا (RCHEP)': 'Publications | Research Center for High Energy Physics (RCHEP)',
    'حامیان مرکز | مرکز پژوهشی فیزیک انرژی بالا (RCHEP)': 'Sponsors | Research Center for High Energy Physics (RCHEP)',
    'اطلاعیه‌ها | مرکز پژوهشی فیزیک انرژی بالا (RCHEP)': 'Notices | Research Center for High Energy Physics (RCHEP)',
    'ارتباط با مرکز | مرکز پژوهشی فیزیک انرژی بالا (RCHEP)': 'Contact | Research Center for High Energy Physics (RCHEP)',
  };

  function getActiveLang() {
    try {
      const urlParam = new URLSearchParams(window.location.search).get('lang');
      if (urlParam === 'en' || urlParam === 'fa') return urlParam;
    } catch(e) {}
    try {
      const stored = localStorage.getItem('rchep_lang');
      if (stored === 'en' || stored === 'fa') return stored;
    } catch(e) {}
    return 'fa';
  }

  function applyLanguage(lang) {
    const isEn = (lang === 'en');

    // Document-level direction and language
    document.documentElement.setAttribute('lang', isEn ? 'en' : 'fa');
    document.documentElement.setAttribute('dir', isEn ? 'ltr' : 'rtl');
    document.body.setAttribute('dir', isEn ? 'ltr' : 'rtl');

    // Title translation
    if (!document._origTitle) document._origTitle = document.title;
    if (isEn && pageTitleMap[document._origTitle]) {
      document.title = pageTitleMap[document._origTitle];
    } else if (!isEn && document._origTitle) {
      document.title = document._origTitle;
    }

    // Toggle button label
    if (langToggle) {
      langToggle.textContent = isEn ? 'فارسی' : 'English';
      langToggle.setAttribute('title', isEn ? 'تغییر زبان به فارسی' : 'Switch to English');
    }

    // Translate all elements with data-fa and data-en
    document.querySelectorAll('[data-fa]').forEach(el => {
      const targetVal = isEn ? el.getAttribute('data-en') : el.getAttribute('data-fa');
      if (targetVal !== null && targetVal !== undefined) {
        el.textContent = targetVal;
      }
    });

    // متن تازه‌نوشته‌شده ممکن است نشانه‌گذاری ریاضی داشته باشد؛ دوباره آرایه‌بندی شود.
    try { renderMathTypography(); } catch(e) {}

    // Search input placeholder
    if (pubSearchInput) {
      pubSearchInput.placeholder = isEn 
        ? 'Search papers by title, author, or arXiv ID...' 
        : 'جستجو بر اساس عنوان مقاله، نام پژوهشگر یا شناسه arXiv...';
    }

    // Sync all internal links so clicking navigates in the chosen language!
    document.querySelectorAll('a[href]').forEach(a => {
      const href = a.getAttribute('href');
      if (!href || href.startsWith('http') || href.startsWith('mailto:') || href.startsWith('#') || !href.includes('.html')) {
        return;
      }
      const [path, hash] = href.split('#');
      const base = path.split('?')[0];
      const hStr = hash ? '#' + hash : '';
      if (isEn) {
        a.setAttribute('href', base + '?lang=en' + hStr);
      } else {
        a.setAttribute('href', base + hStr);
      }
    });

    // Render Lucide icons
    if (window.lucide) {
      try {
        window.lucide.createIcons();
      } catch(e) {}
    }

    // Save preference safely
    try {
      localStorage.setItem('rchep_lang', isEn ? 'en' : 'fa');
    } catch(e) {}

    // Update browser URL query
    try {
      const url = new URL(window.location);
      if (isEn) {
        url.searchParams.set('lang', 'en');
      } else {
        url.searchParams.delete('lang');
      }
      window.history.replaceState({}, '', url.toString());
    } catch(e) {}
  }

  // Initial load
  const initialLang = getActiveLang();
  if (initialLang === 'en') {
    applyLanguage('en');
  }

  // Toggle button click listener
  if (langToggle) {
    langToggle.addEventListener('click', (e) => {
      e.preventDefault();
      const current = document.documentElement.getAttribute('lang') || 'fa';
      const target = current === 'fa' ? 'en' : 'fa';
      applyLanguage(target);
      filterItems();
    });
  }

  // 5. Floating Back-to-Top Button
  const bttBtn = document.createElement('button');
  bttBtn.className = 'back-to-top';
  bttBtn.setAttribute('aria-label', 'Back to top');
  bttBtn.innerHTML = '<svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 15l7-7 7 7"/></svg>';
  document.body.appendChild(bttBtn);

  window.addEventListener('scroll', () => {
    if (window.scrollY > 300) {
      bttBtn.classList.add('visible');
    } else {
      bttBtn.classList.remove('visible');
    }
  }, { passive: true });

  bttBtn.addEventListener('click', () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  // 6. Fast Mathematical Typography Formatter (LaTeX in titles & papers)
  function renderMathTypography() {
    const mathReplacements = [
      // NOTE: patterns must match the real page text: $T\bar{T}$ (single backslash before bar).
      [/\$T\\bar\{T\}\$/g, '<span class="math-tex"><span class="math-var">T</span><span class="math-bar">T̄</span></span>'],
      [/\$\\bar\{T\}T\$/g, '<span class="math-tex"><span class="math-bar">T̄</span><span class="math-var">T</span></span>'],
      [/T̄T̄/g, '<span class="math-tex"><span class="math-var">T</span><span class="math-bar">T̄</span></span>'],
      [/\$\\text\{AdS\}_3\/\\text\{CFT\}_2\$/g, '<span class="math-tex">AdS<sub>3</sub>/CFT<sub>2</sub></span>'],
      [/\$\\text\{AdS\}_3\$/g, '<span class="math-tex">AdS<sub>3</sub></span>'],
      [/\$\\text\{CFT\}_2\$/g, '<span class="math-tex">CFT<sub>2</sub></span>'],
      [/\$\\sqrt\{s\}\s*=\s*13\.6\s*\\text\{\s*TeV\}\$/g, '<span class="math-tex">&radic;s = 13.6 TeV</span>'],
      [/\$\\sqrt\{s\}\s*=\s*13\s*\\text\{\s*TeV\}\$/g, '<span class="math-tex">&radic;s = 13 TeV</span>'],
      [/\$\\sqrt\{s\}\s*=\s*13\s*TeV\$/g, '<span class="math-tex">&radic;s = 13 TeV</span>']
    ];

    document.querySelectorAll('.pub-title, .event-info h4, .event-info h5, .card-title, .card-body li').forEach(el => {
      let html = el.innerHTML;
      let changed = false;
      for (const [re, rep] of mathReplacements) {
        if (re.test(html)) {
          html = html.replace(re, rep);
          changed = true;
        }
      }
      if (changed) {
        el.innerHTML = html;
      }
    });
  }

  renderMathTypography();
  initPosterInteractions();
  if (window.lucide) {
    try {
      window.lucide.createIcons();
    } catch(e) {}
  }
});

// 7. Interactive Poster Hover Preview & Lightbox Modal (خرامش و زنش پوستر)
function initPosterInteractions() {
  const previewEl = document.createElement('div');
  previewEl.className = 'poster-floating-preview';
  previewEl.innerHTML = `
    <img src="" alt="پیش‌نمایش پوستر">
    <div class="preview-hint" data-fa="برای بزرگ‌نمایی کلیک کنید" data-en="Click to enlarge">برای بزرگ‌نمایی کلیک کنید</div>
  `;
  document.body.appendChild(previewEl);
  const previewImg = previewEl.querySelector('img');

  const modalEl = document.createElement('div');
  modalEl.className = 'poster-modal';
  modalEl.innerHTML = `
    <div class="poster-modal-content">
      <div class="poster-modal-header">
        <span class="poster-modal-title" data-fa="پوستر رسمی سمینار" data-en="Official Seminar Poster">پوستر رسمی سمینار</span>
        <div class="poster-modal-actions">
          <a href="#" download class="poster-modal-btn download-link" data-fa="دریافت فایل پوستر ⬇" data-en="Download Poster ⬇">دریافت فایل پوستر ⬇</a>
          <button class="poster-modal-close" aria-label="بستن">✕</button>
        </div>
      </div>
      <div class="poster-modal-img-container">
        <img src="" alt="پوستر کامل سمینار">
      </div>
    </div>
  `;
  document.body.appendChild(modalEl);
  const modalImg = modalEl.querySelector('img');
  const modalTitle = modalEl.querySelector('.poster-modal-title');
  const modalDownload = modalEl.querySelector('.download-link');
  const modalClose = modalEl.querySelector('.poster-modal-close');

  function closeModal() {
    modalEl.classList.remove('active');
    document.body.style.overflow = '';
  }

  modalClose.addEventListener('click', closeModal);
  modalEl.addEventListener('click', (e) => {
    if (e.target === modalEl) closeModal();
  });
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modalEl.classList.contains('active')) {
      closeModal();
    }
  });

  // Cache so a hover never waits on the network twice
  const posterPreloaded = [];
  const preloadPoster = (src) => {
    if (!src || posterPreloaded.includes(src)) return;
    posterPreloaded.push(src);
    const im = new Image();
    im.decoding = 'async';
    im.src = src;
  };

  // Preview files are lighter twins of the posters (see scripts/make_poster_previews.py)
  const previewPath = (src) => /\.(jpe?g|png)$/i.test(src)
    ? src.replace(/\.[a-z]+$/i, '-preview.jpg')
    : src;

  document.querySelectorAll('[data-poster]').forEach(btn => {
    const posterSrc = btn.getAttribute('data-poster');
    const previewSrc = previewPath(btn.getAttribute('data-preview') || posterSrc);
    const title = btn.getAttribute('data-title') || 'پوستر سمینار';

    const isRtl = document.documentElement.getAttribute('dir') !== 'ltr';
    const GAP = 20;
    let lastX = 0, lastY = 0;

    // Place the floating poster beside the pointer, always fully on screen
    const placePreview = (cx, cy) => {
      const w = previewEl.offsetWidth || 440;
      const h = previewEl.offsetHeight || 560;
      let left = isRtl ? cx - w - GAP : cx + GAP;
      if (left < 16 || left + w > window.innerWidth - 16) {
        left = isRtl ? cx + GAP : cx - w - GAP;
      }
      left = Math.max(16, Math.min(window.innerWidth - w - 16, left));
      let top = cy - h / 2;
      top = Math.max(16, Math.min(window.innerHeight - h - 16, top));
      previewEl.style.left = `${left}px`;
      previewEl.style.top = `${top}px`;
    };

    const showPreview = (cx, cy) => {
      lastX = cx; lastY = cy;
      preloadPoster(previewSrc);
      // If the light preview is missing, fall back to the full poster file
      previewImg.onerror = () => {
        if (previewImg.getAttribute('src') !== posterSrc) previewImg.src = posterSrc;
      };
      if (previewImg.getAttribute('src') !== previewSrc) previewImg.src = previewSrc;
      previewEl.classList.add('visible');
      placePreview(cx, cy);
      // Re-place with the real size: on load, or right away when it is cached
      previewImg.onload = () => placePreview(lastX, lastY);
      if (previewImg.complete) requestAnimationFrame(() => placePreview(lastX, lastY));
    };

    // Hover (خرامش)
    btn.addEventListener('mouseenter', (e) => showPreview(e.clientX, e.clientY));
    btn.addEventListener('mousemove', (e) => {
      lastX = e.clientX; lastY = e.clientY;
      if (previewEl.classList.contains('visible')) placePreview(e.clientX, e.clientY);
    });
    btn.addEventListener('mouseleave', () => previewEl.classList.remove('visible'));
    // Keyboard (دسترس‌پذیری)
    btn.addEventListener('focus', () => {
      const r = btn.getBoundingClientRect();
      showPreview(r.left + r.width / 2, r.top + r.height / 2);
    });
    btn.addEventListener('blur', () => previewEl.classList.remove('visible'));

    // Click (زنش)
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      previewEl.classList.remove('visible');
      modalImg.src = previewSrc;
      modalTitle.textContent = title;
      modalDownload.setAttribute('href', posterSrc);
      modalEl.classList.add('active');
      document.body.style.overflow = 'hidden';
    });
  });

  // Warm the preview files while the page sits idle, so hover is instant
  const warmPosters = () => document.querySelectorAll('[data-poster]')
    .forEach(b => preloadPoster(b.getAttribute('data-preview') || b.getAttribute('data-poster')));
  if ('requestIdleCallback' in window) {
    requestIdleCallback(warmPosters, { timeout: 3000 });
  } else {
    setTimeout(warmPosters, 1200);
  }

  // 8. Program Navigation Tabs & Smooth Scroll Highlighting
  document.querySelectorAll('.tab-link').forEach(link => {
    link.addEventListener('click', (e) => {
      const targetId = link.getAttribute('href');
      if (targetId && targetId.startsWith('#')) {
        const targetEl = document.querySelector(targetId);
        if (targetEl) {
          e.preventDefault();
          targetEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
          history.pushState(null, '', targetId);
          
          const parentGroup = link.closest('.nav-program-tabs');
          if (parentGroup) {
            parentGroup.querySelectorAll('.tab-link').forEach(t => t.classList.remove('active-tab'));
            link.classList.add('active-tab');
          }

          targetEl.style.transition = 'box-shadow 0.4s ease, border-color 0.4s ease';
          targetEl.style.boxShadow = '0 0 25px rgba(56, 189, 248, 0.45)';
          targetEl.style.borderColor = 'var(--accent)';
          setTimeout(() => {
            targetEl.style.boxShadow = '';
            targetEl.style.borderColor = '';
          }, 2000);
        }
      }
    });
  });
}

// 9. Newsletter Subscription Handler
window.handleSubscribe = function(event, formPrefix = '') {
  if (event) event.preventDefault();
  const nameInput = document.getElementById(formPrefix ? `${formPrefix}-sub-name` : 'sub-name');
  const emailInput = document.getElementById(formPrefix ? `${formPrefix}-sub-email` : 'sub-email');
  const msgEl = document.getElementById(formPrefix ? `${formPrefix}-sub-msg` : 'sub-msg');
  const lang = localStorage.getItem('rchep_lang') || 'fa';

  const name = nameInput ? nameInput.value.trim() : '';
  const email = emailInput ? emailInput.value.trim() : '';

  if (!email) return;

  const mailtoSubject = encodeURIComponent('درخواست عضویت در سمینارهای RCHEP [subscribe]');
  const mailtoBody = encodeURIComponent(`درود،\nلطفاً این نشانی را در فهرست سمینارهای مرکز فیزیک انرژی بالا ثبت فرمایید.\nنام: ${name}\nرایانامه: ${email}`);
  const mailtoLink = `mailto:rchep@physics.sharif.ir?subject=${mailtoSubject}&body=${mailtoBody}`;

  if (msgEl) {
    msgEl.style.display = 'block';
    msgEl.style.background = 'rgba(2, 132, 199, 0.15)';
    msgEl.style.border = '1px solid rgba(2, 132, 199, 0.4)';
    msgEl.style.color = 'var(--text-color)';

    const textFa = `
      درخواست شما آماده گردید. لطفاً جهت تکمیل، دکمه زیر را بزنید تا برنامه ایمیل باز شود، سپس فقط دکمه <b>ارسال (Send)</b> را بزنید:
      <div style="margin-top: 10px;">
        <a href="${mailtoLink}" class="btn btn-primary" style="display: inline-block; padding: 8px 18px; font-size: 0.9rem;">
          ارسال ایمیل درخواست با یک زنش ✉️
        </a>
      </div>
      <div style="margin-top: 10px; font-size: 0.82rem; color: var(--text-muted); line-height: 1.5;">
        💡 پس از ارسال، رایانامه‌ای برای شما می‌آید که حاوی پیوند پاسخ است؛ با یک زنش روی آن و زدن دکمه <b>Send</b>، دریافت پیام و صحت نشانی شما قطعی می‌شود.
      </div>
    `;

    const textEn = `
      Your request is prepared. Click below to open your email client and send the verification request:
      <div style="margin-top: 10px;">
        <a href="${mailtoLink}" class="btn btn-primary" style="display: inline-block; padding: 8px 18px; font-size: 0.9rem;">
          Send Verification Request ✉️
        </a>
      </div>
      <div style="margin-top: 8px; font-size: 0.8rem; color: var(--text-muted);">
        Once you receive the confirmation email from RCHEP, simply reply to activate.
      </div>
    `;

    msgEl.innerHTML = lang === 'en' ? textEn : textFa;
  }
};

window.handleUnsubscribe = function(event, formPrefix = '') {
  if (event) event.preventDefault();
  const emailInput = document.getElementById(formPrefix ? `${formPrefix}-sub-email` : 'sub-email');
  const msgEl = document.getElementById(formPrefix ? `${formPrefix}-sub-msg` : 'sub-msg');
  const lang = localStorage.getItem('rchep_lang') || 'fa';

  const email = emailInput ? emailInput.value.trim() : '';
  const mailtoSubject = encodeURIComponent('درخواست لغو عضویت در سمینارهای RCHEP [unsubscribe]');
  const mailtoBody = encodeURIComponent(`درود،\nلطفاً نشانی زیر را از فهرست سمینارهای مرکز فیزیک انرژی بالا حذف فرمایید:\n${email}`);
  const mailtoLink = `mailto:rchep@physics.sharif.ir?subject=${mailtoSubject}&body=${mailtoBody}`;

  if (msgEl) {
    msgEl.style.display = 'block';
    msgEl.style.background = 'rgba(239, 68, 68, 0.1)';
    msgEl.style.border = '1px solid rgba(239, 68, 68, 0.3)';
    msgEl.style.color = 'var(--text-color)';

    const textFa = `
      درخواست لغو عضویت آماده گردید. لطفاً روی دکمه زیر بزنید تا برنامه ایمیل باز شود و دکمه <b>ارسال (Send)</b> را بزنید:
      <div style="margin-top: 10px;">
        <a href="${mailtoLink}" class="btn" style="display: inline-block; padding: 8px 18px; font-size: 0.9rem; background-color: #ef4444; color: white;">
          ارسال ایمیل لغو عضویت ✉️
        </a>
      </div>
      <div style="margin-top: 10px; font-size: 0.82rem; color: var(--text-muted); line-height: 1.5;">
        💡 پس از دریافت ایمیل شما در سامانه شریف، لغو عضویت بی‌درنگ ثبت شده و تأییدیه آن به رایانامه شما فرستاده خواهد شد.
      </div>
    `;

    const textEn = `
      Unsubscribe request prepared. Click below to open your email client and send the cancellation email:
      <div style="margin-top: 10px;">
        <a href="${mailtoLink}" class="btn" style="display: inline-block; padding: 8px 18px; font-size: 0.9rem; background-color: #ef4444; color: white;">
          Send Unsubscribe Request ✉️
        </a>
      </div>
      <div style="margin-top: 8px; font-size: 0.8rem; color: var(--text-muted);">
        Once processed by the Sharif system, you will receive confirmation and no further emails will be sent.
      </div>
    `;

    msgEl.innerHTML = lang === 'en' ? textEn : textFa;
  }
};
