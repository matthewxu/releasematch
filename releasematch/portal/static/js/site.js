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
        showToast("无 Magnet 链接可复制", true);
        return;
      }

      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(magnet).then(
          function () {
            showToast("Magnet 已复制到剪贴板");
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
      showToast("Magnet 已复制到剪贴板");
    } catch (err) {
      showToast("复制失败，请手动复制 Magnet 链接", true);
    }
    textarea.remove();
  }

  /**
   * 首页目录客户端搜索（UX-04）。
   */
  function initCatalogSearch() {
    var input = document.querySelector("[data-rm-catalog-search]");
    var grid = document.querySelector(".rm-show-grid");
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
      input.setAttribute(
        "aria-label",
        query ? "搜索作品，当前显示 " + visible + " 项" : "搜索作品"
      );
    });
  }

  /**
   * 页面 DOM 就绪后执行全部初始化。
   */
  function init() {
    initMobileNav();
    initResponsiveTables();
    initCopyMagnet();
    initCatalogSearch();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
