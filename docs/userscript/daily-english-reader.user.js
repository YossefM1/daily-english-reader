// ==UserScript==
// @name         Daily English Reader
// @namespace    https://github.com/YossefM1/daily-english-reader
// @version      1.3.3
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

  function patchImplementation(source) {
    let patched = source;

    // Never inject the BOOT status pill while BBC is still hydrating. The pinned
    // implementation originally appended a new element to <html>/<body> at
    // document-start, which can disturb BBC's own hydration/navigation render.
    patched = replaceRequired(
      patched,
      `  console.log('[Daily English Reader] BOOT');\n  createStatusPill('Daily Reader: BOOT');`,
      `  console.log('[Daily English Reader] BOOT — DOM mutation deferred');`,
      'defer boot pill'
    );

    // Run UI/highlighting only after BBC has completed its initial load/hydration.
    patched = replaceRequired(
      patched,
      `  function whenDomReady(cb) {\n    if (document.body) { cb(); return; }\n    document.addEventListener('DOMContentLoaded', cb, { once: true });\n  }`,
      `  function whenDomReady(cb) {\n    const runAfterHydration = () => setTimeout(cb, 900);\n    if (document.readyState === 'complete') {\n      runAfterHydration();\n      return;\n    }\n    window.addEventListener('load', runAfterHydration, { once: true });\n  }`,
      'post-hydration startup'
    );

    // Protect all BBC chrome, not only direct text nodes inside nav tags.
    patched = replaceRequired(
      patched,
      `  function isInsideInjected(node) {\n    let el = node.parentElement;\n    while (el) {\n      if (el.id && INJECTED_IDS.has(el.id)) return true;\n      if (el.dataset && el.dataset.der === 'true') return true;\n      if (el.classList && el.classList.contains('der-highlight')) return true;\n      el = el.parentElement;\n    }\n    return false;\n  }`,
      `  function isInsideInjected(node) {\n    let el = node.parentElement;\n    while (el) {\n      const tag = el.tagName ? el.tagName.toLowerCase() : '';\n      const role = el.getAttribute ? (el.getAttribute('role') || '').toLowerCase() : '';\n      if (tag === 'header' || tag === 'nav' || tag === 'footer') return true;\n      if (role === 'banner' || role === 'navigation' || role === 'contentinfo') return true;\n      if (el.id && INJECTED_IDS.has(el.id)) return true;\n      if (el.dataset && el.dataset.der === 'true') return true;\n      if (el.classList && el.classList.contains('der-highlight')) return true;\n      el = el.parentElement;\n    }\n    return false;\n  }`,
      'protect BBC chrome'
    );

    // Restrict vocabulary mutations to the article/main content.
    patched = replaceRequired(
      patched,
      `        return walkAndHighlight(document.body, regex, wordMap);`,
      `        const articleRoot =\n          document.querySelector('main article') ||\n          document.querySelector('main') ||\n          document.querySelector('article') ||\n          document.body;\n        return walkAndHighlight(articleRoot, regex, wordMap);`,
      'article-only highlighting'
    );

    // Delay the entire main routine until BBC's load event has completed. This is
    // intentionally stronger than only delaying highlighting because main() calls
    // setPill() before the highlight pass and that also mutates the DOM.
    patched = replaceRequired(
      patched,
      `  try {\n    main().catch(err => {\n      setPill('script error — see console');\n      console.error(LOG_PREFIX, 'unhandled error:', err);\n    });\n  } catch (err) {\n    setPill('script error — see console');\n    console.error(LOG_PREFIX, 'fatal error:', err);\n  }`,
      `  function startDailyReader() {\n    setTimeout(() => {\n      try {\n        main().catch(err => {\n          setPill('script error — see console');\n          console.error(LOG_PREFIX, 'unhandled error:', err);\n        });\n      } catch (err) {\n        setPill('script error — see console');\n        console.error(LOG_PREFIX, 'fatal error:', err);\n      }\n    }, 900);\n  }\n\n  if (document.readyState === 'complete') {\n    startDailyReader();\n  } else {\n    window.addEventListener('load', startDailyReader, { once: true });\n  }`,
      'delay entire reader startup'
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
        console.log(LOG_PREFIX, 'v1.3.3 BBC-hydration-safe patch active');
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
