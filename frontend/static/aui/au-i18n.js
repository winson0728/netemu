/* Atayalan UI Kit — 輕量多語切換（無相依、無建置步驟）
 *
 * 用法：
 *   <script src="au-i18n.dict.js"></script>   // 共用字典（build.py 由 i18n/*.json 產生；離線、file:// 都能用）
 *   <script src="au-i18n.js"></script>
 *   HTML 直接寫繁中，並標上 key：<button data-i18n="btn.save">儲存</button>
 *   屬性：<input data-i18n-attr="placeholder:field.search.placeholder;title:btn.search">
 *   含變數：<span data-i18n="app.updated" data-i18n-vars='{"time":"12:00"}'>更新於 12:00</span>
 *   切換器：<select class="au-lang" data-au-lang></select>（自動填入三語選項）
 *   專案自己的字串：AUI18n.extend({"zh-TW":{...},"ja":{...},"en":{...}})，再 AUI18n.apply()
 *   JS 內取字：AUI18n.t("time.minutesAgo", {n: 5})
 *
 * 語言決定順序：網址 ?lang= → localStorage au_lang → cookie au_lang → <html lang> → zh-TW。
 *   不看瀏覽器語言：場域電腦多半是英文 Windows，但使用者要的是繁中。
 * 選擇會寫進 localStorage 與 cookie au_lang（cookie 讓 Python／Go 伺服器端渲染也能用同一個選擇）。
 * 沒有 JavaScript 時：頁面維持 HTML 原文（繁中）。
 */
(function (global) {
  'use strict';
  var LANGS = ['zh-TW', 'ja', 'en'];
  var LABELS = { 'zh-TW': '繁體中文', 'ja': '日本語', 'en': 'English' };
  var HTML_LANG = { 'zh-TW': 'zh-Hant-TW', 'ja': 'ja', 'en': 'en' };
  var FALLBACK = 'zh-TW';
  var dict = { 'zh-TW': {}, 'ja': {}, 'en': {} };
  var current = FALLBACK;
  var originals = typeof WeakMap === 'function' ? new WeakMap() : null;

  function normalize(code) {
    if (!code) return null;
    var c = String(code).trim().toLowerCase().replace('_', '-');
    if (c === 'zh' || c.indexOf('zh-tw') === 0 || c.indexOf('zh-hant') === 0 || c === 'zh-hk') return 'zh-TW';
    if (c.indexOf('ja') === 0) return 'ja';
    if (c.indexOf('en') === 0) return 'en';
    return null;
  }
  function readStore() { try { return global.localStorage.getItem('au_lang'); } catch (e) { return null; } }
  function writeStore(v) { try { global.localStorage.setItem('au_lang', v); } catch (e) { /* 私密視窗等情況 */ } }
  function readCookie() {
    var m = (global.document && document.cookie || '').match(/(?:^|;\s*)au_lang=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : null;
  }
  function writeCookie(v) {
    try { document.cookie = 'au_lang=' + encodeURIComponent(v) + ';path=/;max-age=31536000;SameSite=Lax'; } catch (e) { /* ignore */ }
  }
  function detect() {
    var q = null;
    try { q = new URLSearchParams(global.location.search).get('lang'); } catch (e) { /* 舊瀏覽器 */ }
    return normalize(q) || normalize(readStore()) || normalize(readCookie()) ||
      normalize(document.documentElement.getAttribute('lang')) || FALLBACK;
  }

  function format(s, vars) {
    if (!vars) return s;
    return s.replace(/\{(\w+)\}/g, function (m, k) { return vars[k] !== undefined && vars[k] !== null ? String(vars[k]) : m; });
  }
  function t(key, vars, lang) {
    var l = lang || current;
    var s = (dict[l] && dict[l][key]);
    if (s === undefined) s = dict[FALLBACK][key];
    if (s === undefined) return key;
    return format(s, vars);
  }
  function has(key) { return dict[current][key] !== undefined || dict[FALLBACK][key] !== undefined; }

  /* 片語模式：以繁中原文當 key，給既有大量中文字串的頁面（Python 直出 HTML、舊 JS）。
   * AUI18n.phrases({ja:{'儲存':'保存'}, en:{'儲存':'Save'}})；AUI18n.p('已選 {n} 項', {n:3})
   * HTML：<button data-i18n-p>儲存</button>、<input data-i18n-p-attr="placeholder;title">
   * 繁中或查無時原樣回傳，所以漏翻只會顯示中文，不會壞。 */
  var phr = { 'zh-TW': {}, 'ja': {}, 'en': {} };  // zh-TW 也可放：原文是英文的頁面（如 netemu）
  function p(s, vars, lang) {
    var l = lang || current, m = phr[l];
    var out = (m && m[s] !== undefined) ? m[s] : s;
    return format(out, vars);
  }
  function phrases(more) {
    for (var l in more) {
      if (!Object.prototype.hasOwnProperty.call(more, l)) continue;
      var n = normalize(l); if (!n || !phr[n]) continue;
      for (var k in more[l]) if (Object.prototype.hasOwnProperty.call(more[l], k)) phr[n][k] = more[l][k];
    }
  }
  function translatePhraseEl(el) {
    if (el.hasAttribute('data-i18n-p')) {
      remember(el, 'p', el.textContent.trim());
      el.textContent = p(original(el, 'p'));
    }
    var names = el.getAttribute('data-i18n-p-attr');
    if (names) names.split(';').forEach(function (n) {
      n = n.trim(); if (!n || !el.hasAttribute(n)) return;
      remember(el, '@p' + n, el.getAttribute(n));
      el.setAttribute(n, p(original(el, '@p' + n)));
    });
  }

  function remember(el, slot, value) {
    if (!originals) return;
    var o = originals.get(el) || {};
    if (!(slot in o)) { o[slot] = value; originals.set(el, o); }
  }
  function original(el, slot) { var o = originals && originals.get(el); return o ? o[slot] : undefined; }

  function translateEl(el) {
    var key = el.getAttribute('data-i18n');
    if (key) {
      var vars = null, raw = el.getAttribute('data-i18n-vars');
      if (raw) { try { vars = JSON.parse(raw); } catch (e) { vars = null; } }
      var html = el.hasAttribute('data-i18n-html');
      remember(el, 'text', html ? el.innerHTML : el.textContent);
      // 字典缺 key 時保留 HTML 原文（伺服器端已渲染的繁中），不要顯示 key 名稱
      var val = has(key) ? t(key, vars) : original(el, 'text');
      if (val !== undefined) { if (html) el.innerHTML = val; else el.textContent = val; }
    }
    var attrs = el.getAttribute('data-i18n-attr');
    if (attrs) {
      attrs.split(';').forEach(function (pair) {
        var p = pair.split(':'); if (p.length < 2) return;
        var name = p[0].trim(), k = p.slice(1).join(':').trim();
        remember(el, '@' + name, el.getAttribute(name));
        var v = has(k) ? t(k) : original(el, '@' + name);
        if (v !== undefined && v !== null) el.setAttribute(name, v);
      });
    }
  }
  function apply(root) {
    root = root || document;
    var nodes = root.querySelectorAll('[data-i18n],[data-i18n-attr]');
    for (var i = 0; i < nodes.length; i++) translateEl(nodes[i]);
    if (root.nodeType === 1 && (root.hasAttribute('data-i18n') || root.hasAttribute('data-i18n-attr'))) translateEl(root);
    var pn = root.querySelectorAll('[data-i18n-p],[data-i18n-p-attr]');
    for (var q = 0; q < pn.length; q++) translatePhraseEl(pn[q]);
    var sw = document.querySelectorAll('[data-au-lang]');
    for (var j = 0; j < sw.length; j++) sw[j].value = current;
  }
  function set(lang, opts) {
    var l = normalize(lang) || FALLBACK;
    current = l;
    document.documentElement.setAttribute('lang', HTML_LANG[l]);
    document.documentElement.setAttribute('data-au-current-lang', l);
    if (!opts || opts.persist !== false) { writeStore(l); writeCookie(l); }
    apply();
    try { document.dispatchEvent(new CustomEvent('au:langchange', { detail: { lang: l } })); } catch (e) { /* IE */ }
    return l;
  }
  function extend(more) {
    for (var l in more) {
      if (!Object.prototype.hasOwnProperty.call(more, l)) continue;
      var n = normalize(l); if (!n) continue;
      for (var k in more[l]) if (Object.prototype.hasOwnProperty.call(more[l], k)) dict[n][k] = more[l][k];
    }
  }
  function wireSwitchers() {
    var sw = document.querySelectorAll('[data-au-lang]');
    for (var i = 0; i < sw.length; i++) {
      var s = sw[i];
      if (s.getAttribute('data-au-wired')) continue;
      s.setAttribute('data-au-wired', '1');
      if (s.tagName === 'SELECT' && !s.options.length) {
        LANGS.forEach(function (l) { var o = document.createElement('option'); o.value = l; o.textContent = LABELS[l]; s.appendChild(o); });
      }
      if (!s.getAttribute('aria-label')) s.setAttribute('aria-label', 'Language / 語言 / 言語');
      s.addEventListener('change', function (e) { set(e.target.value); });
    }
  }
  /* 主題：data-au-theme-toggle 按鈕在 auto → light → dark 之間循環，存在 au_theme */
  function setTheme(mode) {
    var root = document.documentElement;
    if (mode === 'light' || mode === 'dark') root.setAttribute('data-theme', mode); else root.removeAttribute('data-theme');
    try { global.localStorage.setItem('au_theme', mode || 'auto'); } catch (e) { /* ignore */ }
  }
  function initTheme() {
    var m = null; try { m = global.localStorage.getItem('au_theme'); } catch (e) { /* ignore */ }
    if (m === 'light' || m === 'dark') document.documentElement.setAttribute('data-theme', m);
    var btns = document.querySelectorAll('[data-au-theme-toggle]');
    for (var i = 0; i < btns.length; i++) btns[i].addEventListener('click', function () {
      var cur = document.documentElement.getAttribute('data-theme') || 'auto';
      setTheme(cur === 'auto' ? 'light' : cur === 'light' ? 'dark' : 'auto');
    });
  }

  if (global.AU_I18N_DICT) extend(global.AU_I18N_DICT);
  if (global.AU_I18N_PHRASES) phrases(global.AU_I18N_PHRASES);
  var api = { t: t, has: has, p: p, phrases: phrases, set: set, apply: apply, extend: extend, setTheme: setTheme,
    get lang() { return current; }, langs: LANGS.slice(), labels: LABELS };
  global.AUI18n = api;

  function boot() { wireSwitchers(); initTheme(); set(detect(), { persist: false }); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})(typeof window !== 'undefined' ? window : this);
