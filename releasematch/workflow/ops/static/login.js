/**
 * Ops 登录页脚本。
 * @file workflow/ops/static/login.js
 */

(function () {
  "use strict";

  /** @type {HTMLParagraphElement} */
  const errEl = document.getElementById("loginError");
  /** @type {HTMLParagraphElement} */
  const hintEl = document.getElementById("loginHint");
  /** @type {HTMLFormElement} */
  const form = document.getElementById("loginForm");
  /** @type {HTMLInputElement} */
  const pwdInput = document.getElementById("opsPassword");

  /**
   * 显示错误文案。
   * @param {string} msg
   */
  function showError(msg) {
    errEl.hidden = !msg;
    errEl.textContent = msg || "";
  }

  /**
   * 拉取认证状态；已登录或无需门禁则跳转控制台。
   * @returns {Promise<object>}
   */
  async function checkStatus() {
    const res = await fetch("/api/auth/status", { credentials: "same-origin" });
    const data = await res.json();
    if (data.authenticated) {
      window.location.replace("/");
      return data;
    }
    if (!data.password_configured) {
      hintEl.textContent =
        "尚未设置 RM_OPS_PASSWORD：门禁未启用，可直接打开控制台首页。";
    } else if (data.auth_disabled) {
      hintEl.textContent = "RM_OPS_AUTH_DISABLED=1，门禁已关闭。";
    } else {
      hintEl.textContent =
        "会话约 " + (data.session_hours || 72) + " 小时；Cookie 仅本机有效。";
    }
    return data;
  }

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    showError("");
    const password = pwdInput.value;
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: password }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        showError(data.error || "登录失败");
        return;
      }
      window.location.replace("/");
    } catch (e) {
      showError(String(e.message || e));
    }
  });

  checkStatus().catch((e) => showError(String(e.message || e)));
})();
