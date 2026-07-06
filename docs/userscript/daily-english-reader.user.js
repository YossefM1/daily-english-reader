// ==UserScript==
// @name         Daily English Reader
// @namespace    https://github.com/YossefM1/daily-english-reader
// @version      1.2.0
// @description  Highlights vocabulary and shows a Hebrew sidebar with Words + Quiz tabs on today's selected BBC article (A/B/C levels)
// @author       YossefM1
// @match        https://bbc.com/news
// @match        https://www.bbc.com/news
// @match        https://bbc.co.uk/news
// @match        https://www.bbc.co.uk/news
// @match        https://www.bbc.co.uk/news/*
// @match        https://bbc.co.uk/news/*
// @match        https://www.bbc.com/news/*
// @match        https://bbc.com/news/*
// @grant        GM_xmlhttpRequest
// @grant        GM_registerMenuCommand
// @connect      yossefm1.github.io
// @connect      raw.githubusercontent.com
// @run-at       document-start
// ==/UserScript==

(function () {
  'use strict';

  // ── Absolute boot diagnostics (must run before anything else) ────────────────
  console.log('[Daily English Reader] BOOT');
  createStatusPill('Daily Reader: BOOT');

  // Tampermonkey menu command for manually forcing a visible pill.
  try {
    if (typeof GM_registerMenuCommand !== 'undefined') {
      GM_registerMenuCommand('Daily Reader test pill', () =>
        createStatusPill('Daily Reader: manual test')
      );
    }
  } catch (e) {
    console.error('[Daily English Reader] menu command registration failed:', e);
  }

  const LOG_PREFIX = '[Daily English Reader]';

  // Data sources. Each base exposes today.json (the 3-article index) and
  // latest.json (backward-compat single article). articleBase is used to
  // resolve each article's relative data_url ("data/articles/YYYY-MM-DD-A.json").
  const SITE_BASES = [
    {
      today: 'https://YossefM1.github.io/daily-english-reader/data/today.json',
      latest: 'https://YossefM1.github.io/daily-english-reader/data/latest.json',
      articleBase: 'https://YossefM1.github.io/daily-english-reader/',
    },
    {
      today: 'https://raw.githubusercontent.com/YossefM1/daily-english-reader/main/docs/data/today.json',
      latest: 'https://raw.githubusercontent.com/YossefM1/daily-english-reader/main/docs/data/latest.json',
      articleBase: 'https://raw.githubusercontent.com/YossefM1/daily-english-reader/main/docs/',
    },
  ];

  // localStorage key prefix for saved quiz results (keyed by article date + id).
  const QUIZ_STORE_PREFIX = 'dailyEnglishReader.quiz.';

  // Tags whose text we must never touch, plus media/embeds.
  const SKIP_TAGS = new Set([
    'script', 'style', 'textarea', 'input', 'button',
    'nav', 'footer', 'noscript', 'svg', 'select', 'option',
    'img', 'video', 'picture', 'audio', 'canvas', 'iframe', 'object', 'embed',
  ]);

  // Ids of elements we inject and must never re-process.
  const INJECTED_IDS = new Set([
    'der-sidebar', 'der-toggle-btn', 'der-status-pill',
  ]);

  function log(...args) {
    console.log(LOG_PREFIX, ...args);
  }

  // ── Status pill ───────────────────────────────────────────────────────────────
  // Hoisted function declaration so it can run at the very top of the IIFE.
  // Works even before <body> exists: falls back to <html> and is relocated to
  // <body> after DOMContentLoaded.

  function createStatusPill(text) {
    let pill = document.getElementById('der-status-pill');
    if (!pill) {
      pill = document.createElement('div');
      pill.id = 'der-status-pill';
      pill.setAttribute('data-der', 'true');
      pill.style.cssText = [
        'position:fixed',
        'bottom:24px',
        'right:24px',
        'z-index:2147483647',
        'background:#1a5276',
        'color:#fff',
        'border-radius:16px',
        'padding:8px 14px',
        'font-size:13px',
        'font-family:Arial, sans-serif',
        'box-shadow:0 2px 8px rgba(0,0,0,0.35)',
        'max-width:80vw',
        'pointer-events:none',
        'direction:ltr',
      ].join(';');
      (document.body || document.documentElement).appendChild(pill);

      // If we had to attach to <html>, move it into <body> once that exists.
      if (!document.body) {
        document.addEventListener('DOMContentLoaded', () => {
          const p = document.getElementById('der-status-pill');
          if (p && document.body && p.parentElement !== document.body) {
            document.body.appendChild(p);
          }
        }, { once: true });
      }
    }
    if (typeof text === 'string') pill.textContent = text;
    return pill;
  }

  // Convenience wrapper that adds the standard "Daily Reader: " prefix.
  function setPill(shortText) {
    return createStatusPill('Daily Reader: ' + shortText);
  }

  // Run a callback once the DOM (body) is available.
  function whenDomReady(cb) {
    if (document.body) { cb(); return; }
    document.addEventListener('DOMContentLoaded', cb, { once: true });
  }

  // ── CSS ─────────────────────────────────────────────────────────────────────
  // Typography tuned for readability: slightly larger English + Hebrew text,
  // clearly legible niqqud in the pronunciation line, comfortable line-height,
  // and only medium weight (never heavy bold) on translation/explanation.

  function injectCSS() {
    if (document.getElementById('der-style')) return;
    const style = document.createElement('style');
    style.id = 'der-style';
    style.setAttribute('data-der', 'true');
    style.textContent = `
      .der-highlight {
        background: #d0d0d0;
        border-radius: 2px;
        cursor: pointer;
        padding: 0 1px;
      }
      .der-highlight:hover {
        background: #b0b8c8;
      }
      #der-toggle-btn {
        position: fixed;
        bottom: 68px;
        right: 24px;
        z-index: 2147483646;
        background: #1a5276;
        color: #fff;
        border: none;
        border-radius: 8px;
        padding: 10px 16px;
        font-size: 15px;
        cursor: pointer;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        font-family: Arial, sans-serif;
      }
      #der-toggle-btn:hover { background: #154360; }
      #der-sidebar {
        position: fixed;
        top: 0;
        right: 0;
        width: 360px;
        max-width: 92vw;
        height: 100vh;
        overflow-y: auto;
        background: #fafafa;
        border-left: 2px solid #1a5276;
        z-index: 2147483645;
        padding: 16px 14px 80px 14px;
        font-family: Arial, sans-serif;
        font-size: 15px;
        line-height: 1.55;
        box-shadow: -4px 0 16px rgba(0,0,0,0.15);
        display: none;
        box-sizing: border-box;
      }
      #der-sidebar.der-open { display: block; }
      #der-sidebar h2 {
        font-size: 17px;
        color: #1a5276;
        margin: 0 0 4px 0;
        font-family: Arial, sans-serif;
      }
      #der-sidebar .der-level-label {
        direction: ltr;
        font-size: 13px;
        font-weight: 600;
        color: #1a5276;
        background: #e8f4fd;
        border-radius: 6px;
        padding: 3px 9px;
        display: inline-block;
        margin-bottom: 8px;
      }
      #der-sidebar .der-meta {
        font-size: 12.5px;
        color: #666;
        margin-bottom: 14px;
        direction: ltr;
      }
      #der-sidebar a.der-article-link {
        display: inline-block;
        background: #1a5276;
        color: #fff;
        text-decoration: none;
        padding: 6px 12px;
        border-radius: 6px;
        font-size: 13px;
        margin-bottom: 16px;
      }
      #der-sidebar .der-empty {
        direction: rtl;
        text-align: right;
        color: #777;
        font-size: 14px;
        margin: 8px 0;
      }
      /* Tabs */
      .der-tabs {
        display: flex;
        gap: 6px;
        margin-bottom: 14px;
      }
      .der-tab {
        flex: 1;
        background: #e8eef4;
        color: #1a5276;
        border: 1px solid #cdd8e3;
        border-radius: 6px;
        padding: 8px 6px;
        font-size: 14px;
        font-family: Arial, sans-serif;
        cursor: pointer;
        text-align: center;
      }
      .der-tab.der-tab-active {
        background: #1a5276;
        color: #fff;
        border-color: #1a5276;
        font-weight: 600;
      }
      .der-panel { display: none; }
      .der-panel.der-panel-active { display: block; }
      .der-card {
        background: #fff;
        border: 1px solid #ddd;
        border-radius: 6px;
        margin-bottom: 10px;
        padding: 11px 13px;
      }
      .der-card .der-word {
        font-weight: 600;
        font-size: 17px;
        color: #1a5276;
        direction: ltr;
        display: inline-block;
        letter-spacing: 0.2px;
      }
      .der-card .der-level {
        display: inline-block;
        background: #e8f4fd;
        color: #1a5276;
        border-radius: 4px;
        font-size: 11px;
        padding: 1px 6px;
        margin-left: 6px;
        vertical-align: middle;
      }
      .der-card .der-hebrew {
        font-size: 16px;
        font-weight: 500;
        direction: rtl;
        text-align: right;
        line-height: 1.5;
        margin: 6px 0 3px 0;
        color: #222;
      }
      .der-card .der-pronun {
        direction: rtl;
        text-align: right;
        color: #4a4a4a;
        font-size: 16px;
        font-weight: 400;
        line-height: 1.6;
        margin-bottom: 3px;
      }
      .der-card .der-explain {
        direction: rtl;
        text-align: right;
        color: #444;
        font-size: 15px;
        font-weight: 400;
        line-height: 1.5;
        margin-bottom: 6px;
      }
      .der-card .der-example {
        direction: ltr;
        text-align: left;
        color: #555;
        font-size: 13px;
        line-height: 1.5;
        font-style: italic;
        border-top: 1px solid #eee;
        padding-top: 5px;
        margin-top: 5px;
      }
      /* Quiz */
      .der-quiz-progress {
        direction: rtl;
        text-align: right;
        color: #666;
        font-size: 13px;
        margin-bottom: 8px;
      }
      .der-quiz-question {
        direction: ltr;
        text-align: left;
        font-size: 16px;
        font-weight: 600;
        line-height: 1.5;
        color: #222;
        margin-bottom: 12px;
      }
      .der-quiz-options {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .der-quiz-option {
        background: #fff;
        border: 1px solid #cdd8e3;
        border-radius: 6px;
        padding: 10px 12px;
        font-size: 16px;
        font-weight: 400;
        line-height: 1.5;
        font-family: Arial, sans-serif;
        cursor: pointer;
        text-align: right;
        direction: rtl;
      }
      .der-quiz-option:hover:not(:disabled) { background: #eef4fa; }
      .der-quiz-option:disabled { cursor: default; }
      .der-quiz-option.der-correct {
        background: #e3f6e6;
        border-color: #3aa657;
        color: #1e6b34;
        font-weight: 600;
      }
      .der-quiz-option.der-wrong {
        background: #fbe6e6;
        border-color: #d05757;
        color: #a12626;
        font-weight: 600;
      }
      .der-quiz-feedback {
        margin-top: 12px;
        direction: rtl;
        text-align: right;
        font-size: 14px;
        line-height: 1.5;
        color: #444;
      }
      .der-quiz-feedback .der-feedback-mark { font-weight: 600; }
      .der-quiz-feedback .der-feedback-mark.der-ok { color: #1e6b34; }
      .der-quiz-feedback .der-feedback-mark.der-no { color: #a12626; }
      .der-quiz-next, .der-quiz-restart {
        margin-top: 14px;
        background: #1a5276;
        color: #fff;
        border: none;
        border-radius: 6px;
        padding: 10px 16px;
        font-size: 15px;
        font-family: Arial, sans-serif;
        cursor: pointer;
        width: 100%;
      }
      .der-quiz-next:hover, .der-quiz-restart:hover { background: #154360; }
      .der-quiz-score {
        direction: rtl;
        text-align: right;
      }
      .der-quiz-score .der-score-big {
        font-size: 22px;
        font-weight: 600;
        color: #1a5276;
        margin-bottom: 8px;
      }
      .der-quiz-score .der-wrong-list {
        margin: 8px 0;
        padding: 0;
        list-style: none;
      }
      .der-quiz-score .der-wrong-list li {
        direction: ltr;
        text-align: left;
        background: #fff;
        border: 1px solid #eed;
        border-radius: 5px;
        padding: 6px 10px;
        margin-bottom: 6px;
        font-size: 14px;
      }
      #der-close-btn {
        float: right;
        background: none;
        border: none;
        font-size: 20px;
        cursor: pointer;
        color: #555;
        line-height: 1;
        padding: 0;
        margin-top: -2px;
      }
    `;
    (document.head || document.documentElement).appendChild(style);
  }

  // ── URL matching ─────────────────────────────────────────────────────────────
  // Compare only host + pathname. Ignore query strings, hashes, trailing slash.
  // Treat www and non-www as equivalent, and (BBC test mode) treat bbc.com and
  // bbc.co.uk as the same site since BBC serves identical article paths on both.

  function normalizeUrl(u) {
    try {
      const url = new URL(u);
      let host = url.hostname.replace(/^www\./i, '');
      // BBC test mode: unify bbc.com and bbc.co.uk to one canonical host.
      if (host === 'bbc.com' || host === 'bbc.co.uk') host = 'bbc.co.uk';
      let path = url.pathname.replace(/\/+$/, '');
      if (path === '') path = '/';
      return url.protocol + '//' + host + path;
    } catch {
      return String(u || '');
    }
  }

  // ── Text highlighting ────────────────────────────────────────────────────────

  function escapeRegex(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  function buildHighlightRegex(words) {
    const sorted = [...words].sort((a, b) => b.length - a.length);
    const pattern = sorted.map(w => `\\b${escapeRegex(w)}\\b`).join('|');
    return new RegExp(pattern, 'gi');
  }

  // True if the node sits inside anything we injected or already highlighted.
  function isInsideInjected(node) {
    let el = node.parentElement;
    while (el) {
      if (el.id && INJECTED_IDS.has(el.id)) return true;
      if (el.dataset && el.dataset.der === 'true') return true;
      if (el.classList && el.classList.contains('der-highlight')) return true;
      el = el.parentElement;
    }
    return false;
  }

  function highlightTextNode(node, regex, wordMap) {
    const text = node.nodeValue;
    const parent = node.parentNode;
    if (!text || !parent) return 0;
    if (SKIP_TAGS.has(parent.tagName?.toLowerCase())) return 0;
    if (isInsideInjected(node)) return 0;

    regex.lastIndex = 0;
    if (!regex.test(text)) return 0;

    regex.lastIndex = 0;
    const frag = document.createDocumentFragment();
    let last = 0;
    let m;
    let count = 0;

    while ((m = regex.exec(text)) !== null) {
      if (m.index > last) {
        frag.appendChild(document.createTextNode(text.slice(last, m.index)));
      }
      const span = document.createElement('span');
      span.className = 'der-highlight';
      span.setAttribute('data-der', 'true');
      span.textContent = m[0];
      const entry = wordMap.get(m[0].toLowerCase());
      if (entry) {
        span.dataset.word = entry.word;
        span.addEventListener('click', () => scrollToCard(entry.word));
      }
      frag.appendChild(span);
      last = m.index + m[0].length;
      count += 1;
    }

    if (last < text.length) {
      frag.appendChild(document.createTextNode(text.slice(last)));
    }

    parent.replaceChild(frag, node);
    return count;
  }

  function walkAndHighlight(root, regex, wordMap) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    let node;
    while ((node = walker.nextNode())) {
      const tag = node.parentElement?.tagName?.toLowerCase();
      if (SKIP_TAGS.has(tag)) continue;
      if (isInsideInjected(node)) continue;
      nodes.push(node);
    }
    let count = 0;
    for (const n of nodes) count += highlightTextNode(n, regex, wordMap);
    return count;
  }

  // ── Small DOM helper ───────────────────────────────────────────────────────────

  function el(tag, opts = {}) {
    const node = document.createElement(tag);
    node.setAttribute('data-der', 'true');
    if (opts.className) node.className = opts.className;
    if (opts.id) node.id = opts.id;
    if (typeof opts.text === 'string') node.textContent = opts.text;
    return node;
  }

  // ── Words tab ──────────────────────────────────────────────────────────────────

  function buildCard(entry) {
    const card = document.createElement('div');
    card.className = 'der-card';
    card.setAttribute('data-der', 'true');
    card.id = `der-card-${entry.word.replace(/\s+/g, '-')}`;
    card.innerHTML = `
      <div>
        <span class="der-word">${entry.word}</span>
        <span class="der-level">${entry.level || ''}</span>
      </div>
      <div class="der-hebrew">${entry.hebrew || ''}</div>
      <div class="der-pronun">${entry.pronunciation_hebrew || ''}</div>
      <div class="der-explain">${entry.explanation_hebrew || ''}</div>
      <div class="der-example">"${entry.example || ''}"</div>
    `;
    return card;
  }

  function scrollToCard(word) {
    const sidebar = document.getElementById('der-sidebar');
    if (sidebar && !sidebar.classList.contains('der-open')) {
      sidebar.classList.add('der-open');
    }
    // A clicked highlight always refers to a vocabulary word → switch to Words.
    activateTab('words');
    const id = `der-card-${word.replace(/\s+/g, '-')}`;
    const card = document.getElementById(id);
    if (!card) return;
    card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    card.style.outline = '2px solid #1a5276';
    setTimeout(() => { card.style.outline = ''; }, 1500);
  }

  function buildWordsPanel(words) {
    const panel = el('div', { className: 'der-panel der-panel-active', id: 'der-panel-words' });
    if (words.length === 0) {
      panel.appendChild(el('div', { className: 'der-empty', text: 'אין מילים זמינות למאמר זה.' }));
      return panel;
    }
    for (const entry of words) panel.appendChild(buildCard(entry));
    return panel;
  }

  // ── Quiz tab ───────────────────────────────────────────────────────────────────

  // Simple one-question-at-a-time quiz with local score persistence.
  function buildQuizPanel(data) {
    const panel = el('div', { className: 'der-panel', id: 'der-panel-quiz' });
    const quiz = Array.isArray(data.quiz) ? data.quiz : [];

    if (quiz.length === 0) {
      panel.appendChild(el('div', { className: 'der-empty', text: 'אין חידון זמין למאמר זה.' }));
      return panel;
    }

    const total = quiz.length;
    let current = 0;
    let score = 0;
    const wrongWords = [];

    function storageKey() {
      const idPart = data.id ? '.' + data.id : '';
      return QUIZ_STORE_PREFIX + (data.date || normalizeUrl(data.url)) + idPart;
    }

    function saveResult() {
      try {
        const record = {
          date: data.date || '',
          id: data.id || '',
          level: data.level || '',
          url: data.url || '',
          score,
          total,
          wrong_words: wrongWords.slice(),
        };
        localStorage.setItem(storageKey(), JSON.stringify(record));
        log('quiz result saved', record);
      } catch (e) {
        log('quiz result save failed:', e.message);
      }
    }

    function clear() { panel.textContent = ''; }

    function renderQuestion() {
      clear();
      const q = quiz[current];

      panel.appendChild(el('div', {
        className: 'der-quiz-progress',
        text: `שאלה ${current + 1} מתוך ${total}`,
      }));
      panel.appendChild(el('div', { className: 'der-quiz-question', text: q.question || '' }));

      const optionsWrap = el('div', { className: 'der-quiz-options' });
      const buttons = [];
      for (const opt of (q.options || [])) {
        const btn = el('button', { className: 'der-quiz-option', text: opt });
        btn.type = 'button';
        btn.addEventListener('click', () => onAnswer(opt, q, buttons));
        optionsWrap.appendChild(btn);
        buttons.push(btn);
      }
      panel.appendChild(optionsWrap);
    }

    function onAnswer(chosen, q, buttons) {
      const correct = q.correct_answer;
      const isRight = chosen === correct;
      if (isRight) {
        score += 1;
      } else {
        wrongWords.push(q.word);
      }

      for (const btn of buttons) {
        btn.disabled = true;
        if (btn.textContent === correct) btn.classList.add('der-correct');
        else if (btn.textContent === chosen) btn.classList.add('der-wrong');
      }

      const feedback = el('div', { className: 'der-quiz-feedback' });
      const mark = el('span', {
        className: 'der-feedback-mark ' + (isRight ? 'der-ok' : 'der-no'),
        text: isRight ? '✓ נכון! ' : '✗ לא נכון. ',
      });
      feedback.appendChild(mark);
      if (!isRight) {
        feedback.appendChild(el('span', { text: `התשובה הנכונה: ${correct}. ` }));
      }
      if (q.explanation_hebrew) {
        const exp = el('div', { text: q.explanation_hebrew });
        exp.style.marginTop = '6px';
        feedback.appendChild(exp);
      }
      panel.appendChild(feedback);

      const nextBtn = el('button', {
        className: 'der-quiz-next',
        text: current + 1 < total ? 'שאלה הבאה ←' : 'סיום וצפייה בתוצאה',
      });
      nextBtn.type = 'button';
      nextBtn.addEventListener('click', () => {
        current += 1;
        if (current < total) renderQuestion();
        else renderScore();
      });
      panel.appendChild(nextBtn);
    }

    function renderScore() {
      clear();
      saveResult();

      const box = el('div', { className: 'der-quiz-score' });
      box.appendChild(el('div', { className: 'der-score-big', text: `ניקוד: ${score}/${total}` }));

      if (wrongWords.length) {
        box.appendChild(el('div', { text: 'מילים לחזרה:' }));
        const list = el('ul', { className: 'der-wrong-list' });
        for (const w of wrongWords) list.appendChild(el('li', { text: w }));
        box.appendChild(list);
      } else {
        box.appendChild(el('div', { text: 'כל הכבוד! כל התשובות נכונות 🎉' }));
      }
      panel.appendChild(box);

      const restart = el('button', { className: 'der-quiz-restart', text: 'התחל חידון מחדש ↺' });
      restart.type = 'button';
      restart.addEventListener('click', () => {
        current = 0;
        score = 0;
        wrongWords.length = 0;
        renderQuestion();
      });
      panel.appendChild(restart);
    }

    renderQuestion();
    return panel;
  }

  // ── Tabs ────────────────────────────────────────────────────────────────────────

  function activateTab(name) {
    const sidebar = document.getElementById('der-sidebar');
    if (!sidebar) return;
    for (const tab of sidebar.querySelectorAll('.der-tab')) {
      tab.classList.toggle('der-tab-active', tab.dataset.tab === name);
    }
    for (const panel of sidebar.querySelectorAll('.der-panel')) {
      panel.classList.toggle('der-panel-active', panel.dataset.panel === name);
    }
  }

  // ── Sidebar ──────────────────────────────────────────────────────────────────

  function buildSidebar(data) {
    const words = data.words || [];
    const quizCount = Array.isArray(data.quiz) ? data.quiz.length : 0;
    const sidebar = document.createElement('div');
    sidebar.id = 'der-sidebar';
    sidebar.setAttribute('data-der', 'true');

    const closeBtn = document.createElement('button');
    closeBtn.id = 'der-close-btn';
    closeBtn.setAttribute('data-der', 'true');
    closeBtn.textContent = '✕';
    closeBtn.addEventListener('click', () => sidebar.classList.remove('der-open'));

    // Title shows the selected level, e.g. "Daily English Reader — Level A".
    const levelSuffix = data.level ? ` — Level ${data.level}` : '';
    const h2 = el('h2', { text: `📘 Daily English Reader${levelSuffix}` });

    sidebar.appendChild(closeBtn);
    sidebar.appendChild(h2);

    // Full level label badge (e.g. "A — Easier English"), when available.
    if (data.level_label) {
      sidebar.appendChild(el('div', { className: 'der-level-label', text: data.level_label }));
    }

    const meta = el('div', { className: 'der-meta' });
    meta.textContent = `${data.source || ''} · ${data.date || ''} · ${words.length} מילים · ${quizCount} שאלות`;
    sidebar.appendChild(meta);

    const link = document.createElement('a');
    link.className = 'der-article-link';
    link.setAttribute('data-der', 'true');
    link.href = data.url;
    link.textContent = 'פתח מאמר מקורי ↗';
    link.target = '_blank';
    link.rel = 'noopener';
    sidebar.appendChild(link);

    // Tabs
    const tabs = el('div', { className: 'der-tabs' });
    const wordsTab = el('button', { className: 'der-tab der-tab-active', text: `Words (${words.length})` });
    wordsTab.type = 'button';
    wordsTab.dataset.tab = 'words';
    wordsTab.addEventListener('click', () => activateTab('words'));
    const quizTab = el('button', { className: 'der-tab', text: `Quiz (${quizCount})` });
    quizTab.type = 'button';
    quizTab.dataset.tab = 'quiz';
    quizTab.addEventListener('click', () => activateTab('quiz'));
    tabs.appendChild(wordsTab);
    tabs.appendChild(quizTab);
    sidebar.appendChild(tabs);

    // Panels
    const wordsPanel = buildWordsPanel(words);
    wordsPanel.dataset.panel = 'words';
    const quizPanel = buildQuizPanel(data);
    quizPanel.dataset.panel = 'quiz';
    sidebar.appendChild(wordsPanel);
    sidebar.appendChild(quizPanel);

    return sidebar;
  }

  // Insert the toggle button + sidebar. Idempotent.
  function insertUI(data) {
    injectCSS();

    if (!document.getElementById('der-sidebar')) {
      document.body.appendChild(buildSidebar(data));
    }

    if (!document.getElementById('der-toggle-btn')) {
      const toggleBtn = document.createElement('button');
      toggleBtn.id = 'der-toggle-btn';
      toggleBtn.setAttribute('data-der', 'true');
      toggleBtn.textContent = '📘 Vocabulary';
      toggleBtn.addEventListener('click', () => {
        const sidebar = document.getElementById('der-sidebar');
        if (sidebar) sidebar.classList.toggle('der-open');
      });
      document.body.appendChild(toggleBtn);
    }
  }

  // ── Loading with fallback ──────────────────────────────────────────────────────

  function fetchJson(url) {
    return new Promise((resolve, reject) => {
      GM_xmlhttpRequest({
        method: 'GET',
        url,
        timeout: 20000,
        onload(resp) {
          if (resp.status >= 200 && resp.status < 300) {
            try {
              resolve(JSON.parse(resp.responseText));
            } catch (e) {
              reject(new Error('parse error: ' + e.message));
            }
          } else {
            reject(new Error('HTTP ' + resp.status));
          }
        },
        onerror() { reject(new Error('network error')); },
        ontimeout() { reject(new Error('timeout')); },
      });
    });
  }

  function resolveDataUrl(articleBase, dataUrl) {
    try {
      return new URL(dataUrl, articleBase).href;
    } catch {
      return articleBase.replace(/\/$/, '') + '/' + String(dataUrl || '').replace(/^\//, '');
    }
  }

  // Multi-level loading:
  //  1. Load today.json (3-article index) — try each base in order.
  //  2. Match the current page URL against the 3 selected article URLs.
  //  3. On a match, load that article's per-level data file (data_url).
  //  4. If today.json is unavailable everywhere, fall back to latest.json
  //     (backward compatibility) and match against it directly.
  // Returns { status, data? }. status is 'match' | 'no-match' | 'error'.
  async function loadForCurrentUrl(currentNorm) {
    let todayLoadedAnywhere = false;
    let lastErr;

    for (const base of SITE_BASES) {
      let today;
      try {
        today = await fetchJson(base.today);
      } catch (e) {
        lastErr = e;
        log('today.json failed at', base.today, '-', e.message);
        continue;
      }
      todayLoadedAnywhere = true;
      const articles = Array.isArray(today.articles) ? today.articles : [];
      log('today.json loaded:', articles.length, 'articles from', base.today);

      const match = articles.find(a => normalizeUrl(a.url) === currentNorm);
      if (!match) {
        // today.json is authoritative; latest.json is a subset (level B) of it,
        // so a miss here is a genuine "not today's selected article".
        log('current URL not among the 3 selected articles');
        return { status: 'no-match' };
      }

      log('matched selected article:', match.id, match.level, match.url);
      const dataUrl = resolveDataUrl(base.articleBase, match.data_url);
      try {
        const article = await fetchJson(dataUrl);
        // Ensure level fields are present even if the per-article file omits them.
        article.level = article.level || match.level || match.id;
        article.level_label = article.level_label || match.level_label || '';
        return { status: 'match', data: article };
      } catch (e) {
        lastErr = e;
        log('failed to load article data_url', dataUrl, '-', e.message);
        return { status: 'error', error: e };
      }
    }

    // today.json unavailable everywhere → backward-compat latest.json fallback.
    if (!todayLoadedAnywhere) {
      for (const base of SITE_BASES) {
        try {
          const latest = await fetchJson(base.latest);
          log('fell back to latest.json from', base.latest);
          if (normalizeUrl(latest.url) === currentNorm) {
            return { status: 'match', data: latest };
          }
          return { status: 'no-match' };
        } catch (e) {
          lastErr = e;
          log('latest.json failed at', base.latest, '-', e.message);
        }
      }
    }

    return { status: 'error', error: lastErr || new Error('all sources failed') };
  }

  // ── Main ─────────────────────────────────────────────────────────────────────

  async function main() {
    setPill('script started');
    log('script started');
    log('current URL:', window.location.href);

    const currentNorm = normalizeUrl(window.location.href);
    log('normalized current URL:', currentNorm);

    setPill('loading vocabulary');
    let result;
    try {
      result = await loadForCurrentUrl(currentNorm);
    } catch (e) {
      setPill('failed to load vocabulary');
      log('failed to load vocabulary:', e.message);
      return;
    }

    if (result.status === 'error') {
      setPill('failed to load vocabulary');
      log('failed to load vocabulary:', result.error && result.error.message);
      return;
    }

    if (result.status === 'no-match') {
      setPill("not today's selected article");
      return;
    }

    const data = result.data;
    if (!data || !Array.isArray(data.words)) {
      setPill('failed to load vocabulary');
      log('article data missing "words" array');
      return;
    }

    const levelTag = data.level ? ` · Level ${data.level}` : '';
    log('article URL:', data.url, 'level:', data.level);
    log('number of vocabulary words:', data.words.length);
    log('number of quiz questions:', Array.isArray(data.quiz) ? data.quiz.length : 0);

    // URL matches: always show the button + sidebar once the DOM is ready,
    // even with zero highlights.
    whenDomReady(() => {
      insertUI(data);

      const wordMap = new Map(data.words.map(w => [w.word.toLowerCase(), w]));
      const wordList = [...wordMap.keys()];

      function runHighlight() {
        if (wordList.length === 0) return 0;
        const regex = buildHighlightRegex(wordList);
        return walkAndHighlight(document.body, regex, wordMap);
      }

      let total = runHighlight();
      log('number of highlights inserted:', total);
      setPill('active — ' + total + ' highlights' + levelTag);

      // Re-run after 1500ms to catch late-rendered content.
      setTimeout(() => {
        const more = runHighlight();
        total += more;
        log('number of highlights inserted:', total);
        setPill('active — ' + total + ' highlights' + levelTag);
      }, 1500);
    });
  }

  try {
    main().catch(err => {
      setPill('script error — see console');
      console.error(LOG_PREFIX, 'unhandled error:', err);
    });
  } catch (err) {
    setPill('script error — see console');
    console.error(LOG_PREFIX, 'fatal error:', err);
  }
})();
