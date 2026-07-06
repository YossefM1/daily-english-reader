// ==UserScript==
// @name         Daily English Reader
// @namespace    https://github.com/YossefM1/daily-english-reader
// @version      1.0.0
// @description  Highlights vocabulary and shows Hebrew sidebar on today's article
// @author       YossefM1
// @match        https://www.bbc.co.uk/news/*
// @match        https://www.bbc.com/news/*
// @match        https://www.theguardian.com/*
// @match        https://www.npr.org/*
// @match        https://arstechnica.com/*
// @grant        GM_xmlhttpRequest
// @connect      yossefm1.github.io
// @run-at       document-idle
// ==/UserScript==

(function () {
  'use strict';

  const LATEST_JSON_URL =
    'https://YossefM1.github.io/daily-english-reader/data/latest.json';

  const SKIP_TAGS = new Set([
    'script', 'style', 'textarea', 'input', 'button',
    'nav', 'footer', 'noscript', 'svg', 'select', 'option',
  ]);

  // ── CSS ─────────────────────────────────────────────────────────────────────

  function injectCSS() {
    const style = document.createElement('style');
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
        bottom: 24px;
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
        width: 340px;
        height: 100vh;
        overflow-y: auto;
        background: #fafafa;
        border-left: 2px solid #1a5276;
        z-index: 2147483645;
        padding: 16px 12px 80px 12px;
        font-family: Arial, sans-serif;
        font-size: 14px;
        box-shadow: -4px 0 16px rgba(0,0,0,0.15);
        display: none;
        box-sizing: border-box;
      }
      #der-sidebar.der-open { display: block; }
      #der-sidebar h2 {
        font-size: 16px;
        color: #1a5276;
        margin: 0 0 4px 0;
        font-family: Arial, sans-serif;
      }
      #der-sidebar .der-meta {
        font-size: 12px;
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
      .der-card {
        background: #fff;
        border: 1px solid #ddd;
        border-radius: 6px;
        margin-bottom: 10px;
        padding: 10px 12px;
      }
      .der-card .der-word {
        font-weight: bold;
        font-size: 15px;
        color: #1a5276;
        direction: ltr;
        display: inline-block;
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
        font-size: 15px;
        font-weight: bold;
        direction: rtl;
        text-align: right;
        margin: 4px 0 2px 0;
        color: #222;
      }
      .der-card .der-pronun {
        direction: rtl;
        text-align: right;
        color: #555;
        font-size: 13px;
        margin-bottom: 2px;
      }
      .der-card .der-explain {
        direction: rtl;
        text-align: right;
        color: #444;
        font-size: 13px;
        margin-bottom: 4px;
      }
      .der-card .der-example {
        direction: ltr;
        text-align: left;
        color: #555;
        font-size: 12px;
        font-style: italic;
        border-top: 1px solid #eee;
        padding-top: 4px;
        margin-top: 4px;
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
      #der-no-match {
        position: fixed;
        bottom: 80px;
        right: 24px;
        z-index: 2147483646;
        background: rgba(26,82,118,0.85);
        color: #fff;
        border-radius: 8px;
        padding: 8px 14px;
        font-size: 13px;
        font-family: Arial, sans-serif;
        pointer-events: none;
      }
    `;
    document.head.appendChild(style);
  }

  // ── URL matching ─────────────────────────────────────────────────────────────

  function urlsMatch(a, b) {
    try {
      const clean = u => new URL(u).href.replace(/\/$/, '').replace(/#.*$/, '');
      return clean(a) === clean(b);
    } catch {
      return false;
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

  function isInsideSidebar(node) {
    let el = node.parentElement;
    while (el) {
      if (el.id === 'der-sidebar') return true;
      el = el.parentElement;
    }
    return false;
  }

  function highlightTextNode(node, regex, wordMap) {
    const text = node.nodeValue;
    const parent = node.parentNode;
    if (!text || !parent) return;
    if (SKIP_TAGS.has(parent.tagName?.toLowerCase())) return;
    if (isInsideSidebar(node)) return;

    regex.lastIndex = 0;
    if (!regex.test(text)) return;

    regex.lastIndex = 0;
    const frag = document.createDocumentFragment();
    let last = 0;
    let m;

    while ((m = regex.exec(text)) !== null) {
      if (m.index > last) {
        frag.appendChild(document.createTextNode(text.slice(last, m.index)));
      }
      const span = document.createElement('span');
      span.className = 'der-highlight';
      span.textContent = m[0];
      const entry = wordMap.get(m[0].toLowerCase());
      if (entry) {
        span.dataset.word = entry.word;
        span.addEventListener('click', () => scrollToCard(entry.word));
      }
      frag.appendChild(span);
      last = m.index + m[0].length;
    }

    if (last < text.length) {
      frag.appendChild(document.createTextNode(text.slice(last)));
    }

    parent.replaceChild(frag, node);
  }

  function walkAndHighlight(root, regex, wordMap) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    let node;
    while ((node = walker.nextNode())) {
      const tag = node.parentElement?.tagName?.toLowerCase();
      if (!SKIP_TAGS.has(tag)) nodes.push(node);
    }
    for (const n of nodes) highlightTextNode(n, regex, wordMap);
  }

  // ── Sidebar ──────────────────────────────────────────────────────────────────

  function buildCard(entry) {
    const card = document.createElement('div');
    card.className = 'der-card';
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
    const id = `der-card-${word.replace(/\s+/g, '-')}`;
    const card = document.getElementById(id);
    if (!card) return;
    const sidebar = document.getElementById('der-sidebar');
    if (sidebar && !sidebar.classList.contains('der-open')) {
      sidebar.classList.add('der-open');
    }
    card?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    card.style.outline = '2px solid #1a5276';
    setTimeout(() => { card.style.outline = ''; }, 1500);
  }

  function buildSidebar(data) {
    const sidebar = document.createElement('div');
    sidebar.id = 'der-sidebar';

    const closeBtn = document.createElement('button');
    closeBtn.id = 'der-close-btn';
    closeBtn.textContent = '✕';
    closeBtn.addEventListener('click', () => sidebar.classList.remove('der-open'));

    const h2 = document.createElement('h2');
    h2.textContent = '📘 Daily English Reader';

    const meta = document.createElement('div');
    meta.className = 'der-meta';
    meta.textContent = `${data.source || ''} · ${data.date || ''} · ${data.words.length} מילים`;

    const link = document.createElement('a');
    link.className = 'der-article-link';
    link.href = data.url;
    link.textContent = 'פתח מאמר מקורי ↗';
    link.target = '_blank';
    link.rel = 'noopener';

    sidebar.appendChild(closeBtn);
    sidebar.appendChild(h2);
    sidebar.appendChild(meta);
    sidebar.appendChild(link);

    for (const entry of data.words) {
      sidebar.appendChild(buildCard(entry));
    }

    return sidebar;
  }

  // ── Main ─────────────────────────────────────────────────────────────────────

  function run(data) {
    if (!urlsMatch(window.location.href, data.url)) {
      const notice = document.createElement('div');
      notice.id = 'der-no-match';
      notice.textContent = '📘 Daily Reader: not today\'s article';
      document.body.appendChild(notice);
      setTimeout(() => notice.remove(), 5000);
      return;
    }

    injectCSS();

    const wordMap = new Map(data.words.map(w => [w.word.toLowerCase(), w]));
    const wordList = [...wordMap.keys()];
    const regex = buildHighlightRegex(wordList);

    walkAndHighlight(document.body, regex, wordMap);

    const sidebar = buildSidebar(data);
    document.body.appendChild(sidebar);

    const toggleBtn = document.createElement('button');
    toggleBtn.id = 'der-toggle-btn';
    toggleBtn.textContent = '📘 Vocabulary';
    toggleBtn.addEventListener('click', () => {
      sidebar.classList.toggle('der-open');
    });
    document.body.appendChild(toggleBtn);
  }

  GM_xmlhttpRequest({
    method: 'GET',
    url: LATEST_JSON_URL,
    onload(resp) {
      try {
        const data = JSON.parse(resp.responseText);
        if (!data || !data.words) {
          console.warn('[DER] latest.json missing words');
          return;
        }
        run(data);
      } catch (e) {
        console.error('[DER] Failed to parse latest.json:', e);
      }
    },
    onerror(e) {
      console.error('[DER] Failed to load latest.json:', e);
    },
  });
})();
