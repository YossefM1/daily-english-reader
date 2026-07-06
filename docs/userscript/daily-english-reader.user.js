// ==UserScript==
// @name         Daily English Reader
// @namespace    https://github.com/YossefM1/daily-english-reader
// @version      1.0.2
// @description  Highlights vocabulary and shows Hebrew sidebar on today's article
// @author       YossefM1
// @match        https://www.bbc.co.uk/news/*
// @match        https://bbc.co.uk/news/*
// @match        https://www.bbc.com/news/*
// @match        https://bbc.com/news/*
// @match        https://www.theguardian.com/*
// @match        https://theguardian.com/*
// @match        https://www.npr.org/*
// @match        https://npr.org/*
// @match        https://arstechnica.com/*
// @grant        GM_xmlhttpRequest
// @connect      yossefm1.github.io
// @connect      raw.githubusercontent.com
// @run-at       document-idle
// ==/UserScript==

(function () {
  'use strict';

  const LOG_PREFIX = '[Daily English Reader]';

  const PRIMARY_JSON_URL =
    'https://YossefM1.github.io/daily-english-reader/data/latest.json';
  const FALLBACK_JSON_URL =
    'https://raw.githubusercontent.com/YossefM1/daily-english-reader/main/docs/data/latest.json';

  // Tags whose text we must never touch, plus media/embeds.
  const SKIP_TAGS = new Set([
    'script', 'style', 'textarea', 'input', 'button',
    'nav', 'footer', 'noscript', 'svg', 'select', 'option',
    'img', 'video', 'picture', 'audio', 'canvas', 'iframe', 'object', 'embed',
  ]);

  // Ids/classes of elements we inject and must never re-process.
  const INJECTED_IDS = new Set([
    'der-sidebar', 'der-toggle-btn', 'der-status-pill',
  ]);

  function log(...args) {
    console.log(LOG_PREFIX, ...args);
  }

  // ── Status pill ───────────────────────────────────────────────────────────────

  function ensureBody(cb) {
    if (document.body) { cb(); return; }
    const obs = new MutationObserver(() => {
      if (document.body) { obs.disconnect(); cb(); }
    });
    obs.observe(document.documentElement, { childList: true });
  }

  function getPill() {
    let pill = document.getElementById('der-status-pill');
    if (!pill) {
      pill = document.createElement('div');
      pill.id = 'der-status-pill';
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
      document.body.appendChild(pill);
    }
    return pill;
  }

  function setPill(text) {
    ensureBody(() => {
      const pill = getPill();
      pill.textContent = 'Daily Reader: ' + text;
    });
  }

  // ── CSS ─────────────────────────────────────────────────────────────────────

  function injectCSS() {
    if (document.getElementById('der-style')) return;
    const style = document.createElement('style');
    style.id = 'der-style';
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
      #der-sidebar .der-empty {
        direction: rtl;
        text-align: right;
        color: #777;
        font-size: 13px;
        margin: 8px 0;
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
    `;
    document.head.appendChild(style);
  }

  // ── URL matching ─────────────────────────────────────────────────────────────
  // Compare only origin + pathname. Ignore query strings, hashes, trailing slash.

  function normalizeUrl(u) {
    try {
      const url = new URL(u);
      // Treat www and non-www as equivalent by dropping a leading "www.".
      const host = url.hostname.replace(/^www\./i, '');
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
    card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    card.style.outline = '2px solid #1a5276';
    setTimeout(() => { card.style.outline = ''; }, 1500);
  }

  function buildSidebar(data) {
    const words = data.words || [];
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
    meta.textContent = `${data.source || ''} · ${data.date || ''} · ${words.length} מילים`;

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

    if (words.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'der-empty';
      empty.textContent = 'אין מילים זמינות למאמר זה.';
      sidebar.appendChild(empty);
    }

    for (const entry of words) {
      sidebar.appendChild(buildCard(entry));
    }

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

  async function loadVocabulary() {
    const sources = [PRIMARY_JSON_URL, FALLBACK_JSON_URL];
    let lastErr;
    for (const url of sources) {
      try {
        const data = await fetchJson(url);
        log('latest.json loaded from', url);
        return data;
      } catch (e) {
        lastErr = e;
        log('source failed', url, '-', e.message);
      }
    }
    throw lastErr || new Error('all sources failed');
  }

  // ── Main ─────────────────────────────────────────────────────────────────────

  async function main() {
    setPill('script started');
    log('script started');
    log('current URL:', window.location.href);

    const currentNorm = normalizeUrl(window.location.href);
    log('normalized current URL:', currentNorm);

    setPill('loading vocabulary');
    let data;
    try {
      data = await loadVocabulary();
    } catch (e) {
      setPill('failed to load vocabulary');
      log('failed to load vocabulary:', e.message);
      return;
    }

    if (!data || !Array.isArray(data.words)) {
      setPill('failed to load vocabulary');
      log('latest.json missing "words" array');
      return;
    }

    log('latest.json article URL:', data.url);
    const latestNorm = normalizeUrl(data.url);
    log('normalized latest URL:', latestNorm);

    const matched = currentNorm === latestNorm;
    log('URL matched:', matched);
    log('number of vocabulary words:', data.words.length);

    if (!matched) {
      setPill("not today's article");
      return;
    }

    // URL matches: always show the button + sidebar, even with zero highlights.
    insertUI(data);

    const wordMap = new Map(data.words.map(w => [w.word.toLowerCase(), w]));
    const wordList = [...wordMap.keys()];

    function runHighlight() {
      if (wordList.length === 0) return 0;
      const regex = buildHighlightRegex(wordList);
      return walkAndHighlight(document.body, regex, wordMap);
    }

    // Run now (page is at document-idle) and again after 1500ms to catch
    // late-rendered content.
    let total = runHighlight();
    log('number of highlights inserted:', total);
    setPill('active — ' + total + ' highlights');

    setTimeout(() => {
      const more = runHighlight();
      total += more;
      log('number of highlights inserted:', total);
      setPill('active — ' + total + ' highlights');
    }, 1500);
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
