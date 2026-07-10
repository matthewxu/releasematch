/**
 * ReleaseMatch 页面内联 i18n 引导脚本（由 i18n_script.html 注入）。
 * @file i18n_bootstrap.js
 * @description
 *   不依赖 /static/js/site.js 即可切换中英文。
 *   纯静态 ``python -m http.server`` 预览时，若 dist/static 未同步，site.js 会 404；
 *   本脚本与 rm-i18n-data 同页注入，保证语言按钮始终可用。
 */
(function () {
  "use strict";

  /**
   * 初始化双语切换；若已存在 RM_I18N（site.js 已执行）则跳过。
   */
  function bootstrapI18n() {
    if (window.RM_I18N) {
      return;
    }

    var dataEl = document.getElementById("rm-i18n-data");
    if (!dataEl || !dataEl.textContent) {
      return;
    }

    var payload;
    try {
      payload = JSON.parse(dataEl.textContent);
    } catch (err) {
      return;
    }

    var messages = payload.messages || {};
    var dynamicContent = payload.dynamic || {};
    var defaultLocale = payload.defaultLocale || "en";
    var storageKey = "rm_locale";

    /**
     * 读取当前 locale（localStorage 优先）。
     * @returns {string} en | zh
     */
    function currentLocale() {
      var saved = window.localStorage.getItem(storageKey);
      if (saved === "en" || saved === "zh") {
        return saved;
      }
      return defaultLocale === "zh" ? "zh" : "en";
    }

    /**
     * 简单占位符替换 {name}。
     * @param {string} template - 文案模板
     * @param {Object|null} vars - 占位符对象
     * @returns {string}
     */
    function formatMessage(template, vars) {
      if (!vars) {
        return template;
      }
      return template.replace(/\{(\w+)\}/g, function (_match, key) {
        if (Object.prototype.hasOwnProperty.call(vars, key)) {
          return String(vars[key]);
        }
        return "{" + key + "}";
      });
    }

    /**
     * 将 locale 应用到 DOM。
     * @param {string} locale - en | zh
     */
    function applyLocale(locale) {
      var bucket = messages[locale] || messages.en || {};

      document.querySelectorAll("[data-i18n]").forEach(function (el) {
        var key = el.getAttribute("data-i18n");
        if (!key || !bucket[key]) {
          return;
        }
        var varsRaw = el.getAttribute("data-i18n-vars");
        var vars = null;
        if (varsRaw) {
          try {
            vars = JSON.parse(varsRaw);
          } catch (parseErr) {
            vars = null;
          }
        }
        el.textContent = formatMessage(bucket[key], vars);
      });

      document.querySelectorAll("[data-i18n-placeholder]").forEach(function (el) {
        var pKey = el.getAttribute("data-i18n-placeholder");
        if (pKey && bucket[pKey]) {
          el.setAttribute("placeholder", bucket[pKey]);
        }
      });

      document.querySelectorAll("[data-i18n-aria-label]").forEach(function (el) {
        var aKey = el.getAttribute("data-i18n-aria-label");
        if (aKey && bucket[aKey]) {
          el.setAttribute("aria-label", bucket[aKey]);
        }
      });

      document.querySelectorAll("[data-i18n-dynamic]").forEach(function (el) {
        var dKey = el.getAttribute("data-i18n-dynamic");
        if (!dKey) {
          return;
        }
        var entry = dynamicContent[dKey];
        if (!entry || !entry[locale]) {
          return;
        }
        if (el.hasAttribute("data-i18n-html")) {
          el.innerHTML = entry[locale];
        } else {
          el.textContent = entry[locale];
        }
      });

      document.documentElement.lang = locale === "zh" ? "zh-CN" : "en";

      var titleEl = document.querySelector("title[data-i18n]");
      if (titleEl) {
        var titleKey = titleEl.getAttribute("data-i18n");
        if (titleKey && bucket[titleKey]) {
          document.title = bucket[titleKey];
        }
      }

      var switchRoot = document.querySelector("[data-rm-lang-switch]");
      if (switchRoot) {
        switchRoot.querySelectorAll("[data-locale]").forEach(function (btn) {
          var active = btn.getAttribute("data-locale") === locale;
          btn.classList.toggle("is-active", active);
          btn.setAttribute("aria-pressed", active ? "true" : "false");
        });
      }
    }

    applyLocale(currentLocale());

    var switchRoot = document.querySelector("[data-rm-lang-switch]");
    if (switchRoot) {
      switchRoot.addEventListener("click", function (event) {
        var target = event.target;
        if (!(target instanceof HTMLElement)) {
          return;
        }
        var button = target.closest("[data-locale]");
        if (!button) {
          return;
        }
        var next = button.getAttribute("data-locale");
        if (next !== "en" && next !== "zh") {
          return;
        }
        window.localStorage.setItem(storageKey, next);
        applyLocale(next);
        document.dispatchEvent(new CustomEvent("rm-locale-change", { detail: { locale: next } }));
      });
    }

    window.RM_I18N = {
      t: function (key, locale) {
        var loc = locale || currentLocale();
        var bucket = messages[loc] || messages.en || {};
        return bucket[key] || key;
      },
      currentLocale: currentLocale,
      applyLocale: applyLocale,
    };
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootstrapI18n);
  } else {
    bootstrapI18n();
  }
})();
