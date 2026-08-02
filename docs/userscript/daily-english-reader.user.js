// ==UserScript==
// @name         Daily English Reader
// @namespace    https://github.com/YossefM1/daily-english-reader
// @version      1.3.4
// @description  Runs the Daily English Reader vocabulary and quiz overlay on selected BBC News and BBC Weather articles while preserving BBC navigation/header UI.
// @author       YossefM1
// @match        https://bbc.com/news
// @match        https://www.bbc.com/news
// @match        https://bbc.co.uk/news
// @match        https://www.bbc.co.uk/news
// @match        https://www.bbc.co.uk/news/*
// @match        https://bbc.co.uk/news/*
// @match        https://www.bbc.com/news/*
// @match        https://bbc.com/news/*
// @match        https://www.bbc.co.uk/weather/*
// @match        https://bbc.co.uk/weather/*
// @match        https://www.bbc.com/weather/*
// @match        https://bbc.com/weather/*
// @grant        GM_xmlhttpRequest
// @grant        GM_registerMenuCommand
// @connect      yossefm1.github.io
// @connect      raw.githubusercontent.com
// @run-at       document-start
// ==/UserScript==

(function () {
  'use strict';

  const IMPLEMENTATION_URL =
    'https://raw.githubusercontent.com/YossefM1/daily-english-reader/' +
    'd127340e9c6564f24c5eb56b44f93332ef80279f/' +
    'docs/userscript/daily-english-reader.user.js';

  const LOG_PREFIX = '[Daily English Reader loader]';

  function replaceRequired(source, oldText, newText, label) {
    if (!source.includes(oldText)) {
      throw new Error('Could not apply patch: ' + label);
    }
    return source.replace(oldText, newText);
  }

  function replaceRegexRequired(source, regex, replacement, label) {
    if (!regex.test(source)) {
      throw new Error('Could not apply regex patch: ' + label);
    }
    regex.lastIndex = 0;
    return source.replace(regex, replacement);
  }

  function patchImplementation(source) {
    let patched = source;

    // 1) Do not mutate the BBC DOM at document-start.
    patched = replaceRequired(
      patched,
      `  console.log('[Daily English Reader] BOOT');\n  createStatusPill('Daily Reader: BOOT');`,
      `  console.log('[Daily English Reader] BOOT — DOM mutation deferred');`,
      'defer boot pill'
    );

    // 2) Wait until BBC has fully completed its initial page render.
    patched = replaceRequired(
      patched,
      `  function whenDomReady(cb) {\n    if (document.body) { cb(); return; }\n    document.addEventListener('DOMContentLoaded', cb, { once: true });\n  }`,
      `  function whenDomReady(cb) {\n    const runAfterHydration = () => setTimeout(cb, 1800);\n    if (document.readyState === 'complete') {\n      runAfterHydration();\n      return;\n    }\n    window.addEventListener('load', runAfterHydration, { once: true });\n  }`,
      'post-hydration startup'
    );

    // 3) Explicitly protect BBC chrome from any vocabulary processing.
    patched = replaceRequired(
      patched,
      `  function isInsideInjected(node) {\n    let el = node.parentElement;\n    while (el) {\n      if (el.id && INJECTED_IDS.has(el.id)) return true;\n      if (el.dataset && el.dataset.der === 'true') return true;\n      if (el.classList && el.classList.contains('der-highlight')) return true;\n      el = el.parentElement;\n    }\n    return false;\n  }`,
      `  function isInsideInjected(node) {\n    let el = node.parentElement;\n    while (el) {\n      const tag = el.tagName ? el.tagName.toLowerCase() : '';\n      const role = el.getAttribute ? (el.getAttribute('role') || '').toLowerCase() : '';\n      if (tag === 'header' || tag === 'nav' || tag === 'footer') return true;\n      if (role === 'banner' || role === 'navigation' || role === 'contentinfo') return true;\n      if (el.id && INJECTED_IDS.has(el.id)) return true;\n      if (el.dataset && el.dataset.der === 'true') return true;\n      if (el.classList && el.classList.contains('der-highlight')) return true;\n      el = el.parentElement;\n    }\n    return false;\n  }`,
      'protect BBC chrome'
    );

    // 4) Replace span-based highlighting with the CSS Custom Highlight API.
    // This highlights text without replacing BBC text nodes, so React/hydration
    // never sees its managed article DOM rewritten by the userscript.
    patched = replaceRegexRequired(
      patched,
      /  function highlightTextNode\(node, regex, wordMap\) \{[\s\S]*?  function walkAndHighlight\(root, regex, wordMap\) \{[\s\S]*?    return count;\n  \}/,
      `  const DER_HIGHLIGHT_NAME = 'der-vocab';\n  const derHighlightMeta = [];\n  let derHighlightClickAttached = false;\n\n  function derMetaAtPoint(x, y) {\n    let node = null;\n    let offset = 0;\n\n    if (document.caretPositionFromPoint) {\n      const pos = document.caretPositionFromPoint(x, y);\n      if (pos) {\n        node = pos.offsetNode;\n        offset = pos.offset;\n      }\n    } else if (document.caretRangeFromPoint) {\n      const caret = document.caretRangeFromPoint(x, y);\n      if (caret) {\n        node = caret.startContainer;\n        offset = caret.startOffset;\n      }\n    }\n\n    if (!node) return null;\n\n    for (const item of derHighlightMeta) {\n      const range = item.range;\n      if (\n        range.startContainer === node &&\n        range.endContainer === node &&\n        offset >= range.startOffset &&\n        offset <= range.endOffset\n      ) {\n        return item;\n      }\n    }\n    return null;\n  }\n\n  window.__derMetaAtPoint = derMetaAtPoint;\n\n  function highlightTextNode(node, regex, wordMap) {\n    const text = node.nodeValue;\n    const parent = node.parentNode;\n    if (!text || !parent) return 0;\n    if (SKIP_TAGS.has(parent.tagName?.toLowerCase())) return 0;\n    if (isInsideInjected(node)) return 0;\n\n    regex.lastIndex = 0;\n    let m;\n    let count = 0;\n\n    while ((m = regex.exec(text)) !== null) {\n      const entry = wordMap.get(m[0].toLowerCase());\n      if (!entry) continue;\n\n      const range = document.createRange();\n      range.setStart(node, m.index);\n      range.setEnd(node, m.index + m[0].length);\n\n      const anchor = {\n        getBoundingClientRect: () => range.getBoundingClientRect(),\n      };\n\n      derHighlightMeta.push({ range, entry, anchor });\n      count += 1;\n    }\n\n    return count;\n  }\n\n  function walkAndHighlight(root, regex, wordMap) {\n    derHighlightMeta.length = 0;\n\n    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);\n    const nodes = [];\n    let node;\n    while ((node = walker.nextNode())) {\n      const tag = node.parentElement?.tagName?.toLowerCase();\n      if (SKIP_TAGS.has(tag)) continue;\n      if (isInsideInjected(node)) continue;\n      nodes.push(node);\n    }\n\n    let count = 0;\n    for (const n of nodes) count += highlightTextNode(n, regex, wordMap);\n\n    if (window.CSS && CSS.highlights && typeof Highlight !== 'undefined') {\n      CSS.highlights.delete(DER_HIGHLIGHT_NAME);\n      const ranges = derHighlightMeta.map(item => item.range);\n      if (ranges.length) {\n        CSS.highlights.set(DER_HIGHLIGHT_NAME, new Highlight(...ranges));\n      }\n\n      if (!document.getElementById('der-css-highlight-style')) {\n        const style = document.createElement('style');\n        style.id = 'der-css-highlight-style';\n        style.setAttribute('data-der', 'true');\n        style.textContent = '::highlight(der-vocab){background:#d0d0d0;color:inherit;}';\n        (document.head || document.documentElement).appendChild(style);\n      }\n    }\n\n    if (!derHighlightClickAttached) {\n      derHighlightClickAttached = true;\n      document.addEventListener('click', (ev) => {\n        const item = derMetaAtPoint(ev.clientX, ev.clientY);\n        if (!item) return;\n        onHighlightClick(item.anchor, item.entry);\n      }, true);\n    }\n\n    return count;\n  }`,
      'non-mutating CSS highlights'
    );

    // 5) Keep outside-click behaviour compatible with CSS highlights.
    patched = replaceRequired(
      patched,
      `      if (t.closest && (t.closest('#der-popup') || t.closest('.der-highlight'))) return;`,
      `      if (t.closest && (t.closest('#der-popup') || t.closest('.der-highlight'))) return;\n      if (window.__derMetaAtPoint && window.__derMetaAtPoint(ev.clientX, ev.clientY)) return;`,
      'CSS highlight popup outside-click protection'
    );

    // 6) Traverse only the article/main content, never the entire document body.
    patched = replaceRequired(
      patched,
      `        return walkAndHighlight(document.body, regex, wordMap);`,
      `        const articleRoot =\n          document.querySelector('main article') ||\n          document.querySelector('main') ||\n          document.querySelector('article') ||\n          document.body;\n        return walkAndHighlight(articleRoot, regex, wordMap);`,
      'article-only highlighting'
    );

    return patched;
  }

  GM_xmlhttpRequest({
    method: 'GET',
    url: IMPLEMENTATION_URL,
    timeout: 20000,
    onload(resp) {
      if (resp.status < 200 || resp.status >= 300) {
        console.error(LOG_PREFIX, 'implementation download failed:', resp.status);
        return;
      }

      try {
        const patched = patchImplementation(resp.responseText);
        eval(patched);
        console.log(LOG_PREFIX, 'v1.3.4 non-mutating highlight patch active');
      } catch (error) {
        console.error(LOG_PREFIX, 'failed to patch/execute implementation:', error);
      }
    },
    onerror() {
      console.error(LOG_PREFIX, 'network error while loading implementation');
    },
    ontimeout() {
      console.error(LOG_PREFIX, 'timeout while loading implementation');
    },
  });
})();
