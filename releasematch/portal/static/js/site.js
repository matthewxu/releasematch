/**
 * ReleaseMatch 站点交互脚本
 * @file site.js
 * @description 移动端导航切换、表格响应式 data-label 注入等轻量 UI 行为。
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
   * 页面 DOM 就绪后执行全部初始化。
   */
  function init() {
    initMobileNav();
    initResponsiveTables();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
