/**
 * ReleaseMatch 站点交互脚本
 * @file site.js
 * @description 移动端导航、响应式表格、Magnet 复制、首页目录搜索。
 */

(function () {
  "use strict";

  /**
   * 初始化移动端顶栏菜单展开/收起。
   */
  function initMobileNav() {
    var toggle = document.querySelector("[data-rm-nav-toggle]");
    var mobileNav = document.querySelector("[data-rm-nav-mobile]");
    if (!toggle || !mobileNav) {
      return;
    }

    toggle.addEventListener("click", function () {
      var isOpen = mobileNav.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
    });
  }

  /**
   * 为响应式表格单元格注入 data-label，供移动端 CSS 显示列名。
   */
  function initResponsiveTables() {
    var tables = document.querySelectorAll(".rm-table--responsive");
    tables.forEach(function (table) {
      var headers = [];
      table.querySelectorAll("thead th").forEach(function (th) {
        headers.push(th.textContent.trim());
      });

      table.querySelectorAll("tbody tr").forEach(function (row) {
        row.querySelectorAll("td").forEach(function (td, index) {
          if (headers[index]) {
            td.setAttribute("data-label", headers[index]);
          }
        });
      });
    });
  }

  /**
   * 显示复制反馈 toast（含 aria-live 供读屏）。
   * @param {string} message - 提示文案
   * @param {boolean} isError - 是否为错误样式
   */
  function showToast(message, isError) {
    var existing = document.querySelector(".rm-toast");
    if (existing) {
      existing.remove();
    }

    var toast = document.createElement("div");
    toast.className = "rm-toast" + (isError ? " rm-toast--error" : "");
    toast.setAttribute("role", "status");
    toast.setAttribute("aria-live", "polite");
    toast.textContent = message;
    document.body.appendChild(toast);

    window.setTimeout(function () {
      toast.classList.add("is-visible");
    }, 10);

    window.setTimeout(function () {
      toast.classList.remove("is-visible");
      window.setTimeout(function () {
        toast.remove();
      }, 300);
    }, 2500);
  }

  /**
   * 复制 Magnet URI 到剪贴板（UX-01）。
   */
  function initCopyMagnet() {
    document.addEventListener("click", function (event) {
      var target = event.target;
      if (!(target instanceof HTMLElement)) {
        return;
      }
      var button = target.closest("[data-copy-magnet]");
      if (!button) {
        return;
      }
      event.preventDefault();
      var magnet = button.getAttribute("data-copy-magnet") || "";
      if (!magnet) {
        showToast(window.RM_I18N ? window.RM_I18N.t("toast.no_magnet") : "无 Magnet 链接可复制", true);
        return;
      }

      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(magnet).then(
          function () {
            showToast(window.RM_I18N ? window.RM_I18N.t("toast.copied") : "Magnet 已复制到剪贴板");
          },
          function () {
            fallbackCopy(magnet);
          }
        );
      } else {
        fallbackCopy(magnet);
      }
    });
  }

  /**
   * 剪贴板 API 不可用时的降级复制。
   * @param {string} text - 待复制文本
   */
  function fallbackCopy(text) {
    var textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "absolute";
    textarea.style.left = "-9999px";
    document.body.appendChild(textarea);
    textarea.select();
    try {
      document.execCommand("copy");
      showToast(window.RM_I18N ? window.RM_I18N.t("toast.copied") : "Magnet 已复制到剪贴板");
    } catch (err) {
      showToast(window.RM_I18N ? window.RM_I18N.t("toast.copy_failed") : "复制失败，请手动复制 Magnet 链接", true);
    }
    textarea.remove();
  }

  /**
   * 首页目录客户端搜索（UX-04）+ 无结果提示。
   */
  function initCatalogSearch() {
    var input = document.querySelector("[data-rm-catalog-search]");
    var grid = document.querySelector(".rm-show-grid");
    var emptyHint = document.querySelector("[data-rm-catalog-empty]");
    if (!input || !grid) {
      return;
    }

    var cards = grid.querySelectorAll(".rm-show-card");
    input.addEventListener("input", function () {
      var query = input.value.trim().toLowerCase();
      var visible = 0;
      cards.forEach(function (card) {
        var titleEl = card.querySelector(".rm-show-card__title");
        var title = titleEl ? titleEl.textContent.toLowerCase() : "";
        var match = !query || title.indexOf(query) !== -1;
        card.style.display = match ? "" : "none";
        if (match) {
          visible += 1;
        }
      });
      if (emptyHint) {
        emptyHint.hidden = visible > 0 || !query;
      }
      input.setAttribute(
        "aria-label",
        query ? "搜索作品，当前显示 " + visible + " 项" : "搜索作品"
      );
    });
  }

  /**
   * All Sources 表格客户端排序（UX-11）：Seed / Size。
   */
  function initTableSort() {
    var tables = document.querySelectorAll("[data-rm-table-sort]");
    tables.forEach(function (table) {
      var tbody = table.querySelector("tbody");
      if (!tbody) {
        return;
      }
      var headers = table.querySelectorAll(".rm-table__sort");

      /**
       * 按列排序表格行。
       * @param {HTMLButtonElement} button - 排序按钮
       * @param {string} direction - asc | desc
       */
      function applySort(button, direction) {
        var sortType = button.getAttribute("data-sort-type") || "string";
        headers.forEach(function (other) {
          other.classList.remove("is-active");
          other.removeAttribute("data-sort-dir");
        });
        button.classList.add("is-active");
        button.setAttribute("data-sort-dir", direction);

        var colIndex = Array.prototype.indexOf.call(
          button.parentElement.parentElement.children,
          button.parentElement
        );
        var rows = Array.prototype.slice.call(tbody.querySelectorAll("tr"));
        rows.sort(function (a, b) {
          var aCell = a.children[colIndex];
          var bCell = b.children[colIndex];
          var aVal = aCell ? aCell.getAttribute("data-sort-value") || aCell.textContent : "";
          var bVal = bCell ? bCell.getAttribute("data-sort-value") || bCell.textContent : "";
          if (sortType === "number") {
            var aNum = parseFloat(aVal) || 0;
            var bNum = parseFloat(bVal) || 0;
            return direction === "asc" ? aNum - bNum : bNum - aNum;
          }
          aVal = String(aVal).toLowerCase();
          bVal = String(bVal).toLowerCase();
          if (aVal < bVal) {
            return direction === "asc" ? -1 : 1;
          }
          if (aVal > bVal) {
            return direction === "asc" ? 1 : -1;
          }
          return 0;
        });
        rows.forEach(function (row) {
          tbody.appendChild(row);
        });
      }

      headers.forEach(function (button) {
        button.addEventListener("click", function () {
          var currentDir = button.getAttribute("data-sort-dir") || "asc";
          var nextDir = currentDir === "asc" ? "desc" : "asc";
          applySort(button, nextDir);
        });
      });

      var defaultSort = table.querySelector('.rm-table__sort[data-sort-key="seed"]');
      if (defaultSort) {
        applySort(defaultSort, "desc");
      }
    });
  }

  /**
   * 页面 UI 国际化：读取 catalog、应用 locale、绑定切换器。
   */
  function initI18n() {
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
     * Python format 风格占位符替换（仅支持 {name}）。
     * @param {string} template - 文案模板
     * @param {Object} vars - 占位符
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
     * 设置 html lang 属性。
     * @param {string} locale - en | zh
     */
    function applyHtmlLang(locale) {
      document.documentElement.lang = locale === "zh" ? "zh-CN" : "en";
    }

    /**
     * 将 locale 应用到带 data-i18n 的元素。
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

      applyHtmlLang(locale);

      var switchRoot = document.querySelector("[data-rm-lang-switch]");
      if (switchRoot) {
        switchRoot.querySelectorAll("[data-locale]").forEach(function (btn) {
          var active = btn.getAttribute("data-locale") === locale;
          btn.classList.toggle("is-active", active);
          btn.setAttribute("aria-pressed", active ? "true" : "false");
        });
      }
    }

    var locale = currentLocale();
    applyLocale(locale);

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
        initResponsiveTables();
      });
    }

    window.RM_I18N = {
      t: function (key, locale) {
        var loc = locale || currentLocale();
        var bucket = messages[loc] || messages.en || {};
        return bucket[key] || key;
      },
    };
  }

  /**
   * 页面 DOM 就绪后执行全部初始化。
   */
  function init() {
    initI18n();
    initMobileNav();
    initResponsiveTables();
    initCopyMagnet();
    initCatalogSearch();
    initTableSort();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
