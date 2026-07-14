/**
 * Ops 控制台前端 — 四段流程与跟踪表。
 * @file workflow/ops/static/ops.js
 */

(function () {
  "use strict";

  /** @type {object|null} 最近一次 /api/state */
  let state = null;

  /**
   * 写底部日志。
   * @param {string} msg 消息
   * @param {object} [extra] 可选 JSON
   */
  function log(msg, extra) {
    const el = document.getElementById("opsLog");
    const ts = new Date().toISOString().slice(11, 19);
    let line = `[${ts}] ${msg}`;
    if (extra !== undefined) {
      try {
        line += "\n" + JSON.stringify(extra, null, 2).slice(0, 1200);
      } catch (_) {
        /* ignore */
      }
    }
    el.textContent = line + (el.textContent ? "\n\n" + el.textContent : "");
  }

  /**
   * JSON API 封装。
   * @param {string} path 路径
   * @param {object} [opts] fetch 选项
   * @returns {Promise<object>}
   */
  async function api(path, opts) {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...opts,
      body: opts && opts.body ? JSON.stringify(opts.body) : undefined,
    });
    const data = await res.json();
    if (!res.ok || data.ok === false) {
      log("API 失败 " + path, data);
      throw new Error((data && data.error) || res.statusText);
    }
    return data;
  }

  /**
   * 切换流程面板。
   * @param {string} step 1-4
   */
  function showStep(step) {
    document.querySelectorAll(".ops-step-tab").forEach((btn) => {
      btn.setAttribute("aria-selected", btn.dataset.step === step ? "true" : "false");
    });
    document.querySelectorAll(".ops-panel").forEach((panel) => {
      panel.classList.toggle("is-active", panel.dataset.panel === step);
    });
  }

  /**
   * 渲染状态徽章。
   * @param {string} status 阶段状态
   * @returns {string} HTML
   */
  function statusBadge(status) {
    const s = status || "pending";
    return `<span class="st st-${s}">${s}</span>`;
  }

  /**
   * 渲染指标条。
   * @param {HTMLElement} host 容器
   * @param {Array<[string, string|number]>} items 键值对
   */
  function renderMetrics(host, items) {
    host.innerHTML = items
      .map(
        ([k, v]) =>
          `<div class="ops-metric"><div class="v">${v ?? "—"}</div><div class="k">${k}</div></div>`
      )
      .join("");
  }

  /**
   * 渲染候选 / 筛选表行。
   * @param {HTMLTableSectionElement} tbody
   * @param {Array<object>} slots
   * @param {boolean} withCheck
   */
  function renderSlotRows(tbody, slots, withCheck) {
    tbody.innerHTML = (slots || [])
      .map((s) => {
        const tier = s.source_tier || "file";
        const check = withCheck
          ? `<td><input type="checkbox" class="slot-check" data-page-id="${escapeHtml(
              s.page_id
            )}" checked /></td>`
          : "";
        return `<tr>
          ${check}
          <td class="tier-${tier}">${tier}</td>
          <td>${escapeHtml(s.label || "")}</td>
          <td><code>${escapeHtml(s.page_id || "")}</code></td>
          <td>${escapeHtml(s.media_type || "")}</td>
          ${withCheck ? "" : `<td>${s.popularity != null ? s.popularity : "—"}</td>`}
        </tr>`;
      })
      .join("");
  }

  /**
   * HTML 转义。
   * @param {string} s
   * @returns {string}
   */
  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /**
   * 构建跟踪表 HTML（③④共用）。
   * @param {object|null} batch
   * @returns {string}
   */
  function buildTrackTableHtml(batch) {
    if (!batch || !batch.slots || !batch.slots.length) {
      return '<p class="lead">尚未导入跟踪表。请在「筛选」完成后点击「导入跟踪表」。</p>';
    }
    const rows = batch.slots
      .map((s) => {
        const g = s.gate || {};
        const st = s.stages || {};
        return `<tr>
          <td><code>${escapeHtml(s.page_id)}</code></td>
          <td class="tier-${s.source_tier || ""}">${escapeHtml(s.source_tier || "")}</td>
          <td>${escapeHtml(s.label || "")}</td>
          <td>${statusBadge(st.pipeline && st.pipeline.status)}</td>
          <td>${g.magnet_count != null ? g.magnet_count : "—"}</td>
          <td>${g.has_recommended == null ? "—" : g.has_recommended ? "Y" : "N"}</td>
          <td>${escapeHtml(g.page_status || "—")}</td>
          <td>${g.indexable ? "Y" : "N"}</td>
          <td>${statusBadge(st.generate && st.generate.status)}</td>
          <td>${statusBadge(st.speedtest && st.speedtest.status)}</td>
          <td>${escapeHtml((s.error || (st.pipeline && st.pipeline.detail) || "").slice(0, 40))}</td>
        </tr>`;
      })
      .join("");
    return `<div class="ops-table-wrap"><table class="ops-table">
      <thead><tr>
        <th>page_id</th><th>tier</th><th>label</th>
        <th>pipeline</th><th>magnet</th><th>Rec</th><th>status</th><th>indexable</th>
        <th>generate</th><th>speedtest</th><th>detail</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table></div>`;
  }

  /**
   * 刷新跟踪表到③④两个挂载点。
   * @param {object|null} batch
   */
  function renderTrack(batch) {
    const html = buildTrackTableHtml(batch);
    document.getElementById("trackTableHost").innerHTML = html;
    document.getElementById("trackTableHost2").innerHTML = html;

    const summary = batch ? summarizeClient(batch) : null;
    const badge = document.getElementById("activeBatchBadge");
    if (batch && batch.meta) {
      badge.textContent = "batch " + batch.meta.batch_id;
    } else {
      badge.textContent = "无活跃批次";
    }

    if (summary) {
      renderMetrics(document.getElementById("trackMetrics"), [
        ["选中", summary.selected],
        ["pipeline ok", summary.pipeline_ok],
        ["pipeline fail", summary.pipeline_failed],
        ["indexable", summary.indexable],
        ["generate ok", summary.generate_ok],
        ["speed ok", summary.speedtest_ok],
      ]);
      renderMetrics(document.getElementById("launchMetrics"), [
        ["indexable", summary.indexable],
        ["seo_c2", (summary.batch_steps.seo_c2 || {}).status || "pending"],
        ["deploy", (summary.batch_steps.deploy || {}).status || "pending"],
      ]);
      const steps = summary.batch_steps || {};
      document.getElementById("batchSteps").innerHTML = `
        <div class="ops-row">
          <span>seo_c2 ${statusBadge((steps.seo_c2 || {}).status)}</span>
          <span>deploy ${statusBadge((steps.deploy || {}).status)}</span>
        </div>
        <div class="ops-log" style="max-height:100px">${escapeHtml(
          ((steps.seo_c2 || {}).detail || "") + "\n" + ((steps.deploy || {}).detail || "")
        ).trim()}</div>`;
    }
  }

  /**
   * 客户端汇总（与 track_store.summarize_batch 对齐）。
   * @param {object} batch
   * @returns {object}
   */
  function summarizeClient(batch) {
    const slots = (batch.slots || []).filter((s) => s.selected !== false);
    const stage = (name, st) =>
      slots.filter((s) => ((s.stages || {})[name] || {}).status === st).length;
    return {
      selected: slots.length,
      pipeline_ok: stage("pipeline", "ok") + stage("pipeline", "skipped"),
      pipeline_failed: stage("pipeline", "failed"),
      generate_ok: stage("generate", "ok"),
      speedtest_ok: stage("speedtest", "ok"),
      indexable: slots.filter((s) => (s.gate || {}).indexable).length,
      batch_steps: (batch.meta && batch.meta.batch_steps) || {},
    };
  }

  /**
   * 渲染完整 state。
   * @param {object} data
   */
  function renderState(data) {
    state = data;
    const ws = data.workspace || {};
    const logic = data.source_logic || {};
    const logicEl = document.getElementById("sourceLogic");
    logicEl.innerHTML = (logic.steps || [])
      .map(
        (s) =>
          `<li><strong>${escapeHtml(s.name)}</strong> — ${escapeHtml(s.desc || "")}</li>`
      )
      .join("");

    const candidates = ws.candidates || [];
    const filtered = ws.filtered || [];
    renderMetrics(document.getElementById("sourceMetrics"), [
      ["候选", ws.candidates_count || 0],
      ["来源", (ws.source && ws.source.kind) || "—"],
      ["路径", (ws.source && ws.source.path) || "—"],
    ]);
    renderSlotRows(document.querySelector("#candidateTable tbody"), candidates, false);

    renderMetrics(document.getElementById("filterMetrics"), [
      ["筛选前", (ws.filter && ws.filter.count_before) || ws.candidates_count || 0],
      ["筛选后", ws.filtered_count || 0],
    ]);
    renderSlotRows(document.querySelector("#filteredTable tbody"), filtered, true);

    renderTrack(data.batch);
  }

  /**
   * 拉取 /api/state。
   */
  async function refresh() {
    const data = await api("/api/state");
    renderState(data);
    log("状态已刷新", {
      candidates: data.workspace && data.workspace.candidates_count,
      batch: data.active_batch_id,
    });
  }

  /**
   * 加载文件列表。
   */
  async function loadFiles() {
    const data = await api("/api/source/files");
    const ul = document.getElementById("fileList");
    ul.innerHTML = (data.files || [])
      .map(
        (f) => `<li>
          <span title="${escapeHtml(f.path)}">${escapeHtml(f.path)}</span>
          <button type="button" class="secondary btn-load-file" data-path="${escapeHtml(
            f.path
          )}">载入</button>
        </li>`
      )
      .join("");
  }

  /**
   * 读取多选 select 值。
   * @param {string} id
   * @returns {string[]}
   */
  function multiValues(id) {
    const el = document.getElementById(id);
    return Array.from(el.selectedOptions).map((o) => o.value);
  }

  /**
   * 读取筛选表勾选 page_id。
   * @returns {string[]}
   */
  function checkedPageIds() {
    return Array.from(document.querySelectorAll("#filteredTable .slot-check:checked")).map(
      (el) => el.dataset.pageId
    );
  }

  /**
   * 绑定事件。
   */
  function bind() {
    document.querySelectorAll(".ops-step-tab").forEach((btn) => {
      btn.addEventListener("click", () => showStep(btn.dataset.step));
    });

    document.getElementById("btnRefresh").addEventListener("click", () => {
      refresh().catch((e) => log(String(e)));
    });

    document.getElementById("btnBuildTmdb").addEventListener("click", async () => {
      const body = {
        total: Number(document.getElementById("tmdbTotal").value || 20),
        download: document.getElementById("tmdbDownload").checked,
      };
      const movies = document.getElementById("tmdbMovies").value;
      const tv = document.getElementById("tmdbTv").value;
      if (movies !== "") body.movies = Number(movies);
      if (tv !== "") body.tv = Number(tv);
      log("生成 TMDB 清单…", body);
      try {
        const data = await api("/api/source/build-tmdb", { method: "POST", body });
        log("清单已生成", data.result);
        await refresh();
        showStep("2");
      } catch (e) {
        log(String(e));
      }
    });

    document.getElementById("btnLoadPath").addEventListener("click", async () => {
      const path = document.getElementById("slotsPath").value.trim();
      if (!path) return;
      try {
        await api("/api/source/load", { method: "POST", body: { path } });
        await refresh();
        showStep("2");
      } catch (e) {
        log(String(e));
      }
    });

    document.getElementById("fileList").addEventListener("click", async (ev) => {
      const btn = ev.target.closest(".btn-load-file");
      if (!btn) return;
      document.getElementById("slotsPath").value = btn.dataset.path;
      try {
        await api("/api/source/load", { method: "POST", body: { path: btn.dataset.path } });
        await refresh();
        showStep("2");
      } catch (e) {
        log(String(e));
      }
    });

    document.getElementById("btnApplyFilter").addEventListener("click", async () => {
      const body = {
        q: document.getElementById("filterQ").value || null,
        media_types: multiValues("filterMedia"),
        tiers: multiValues("filterTier"),
        exclude_published: document.getElementById("excludePublished").checked,
        exclude_failed: document.getElementById("excludeFailed").checked,
        only_failed: document.getElementById("onlyFailed").checked,
      };
      const pmin = document.getElementById("filterPopMin").value;
      const pmax = document.getElementById("filterPopMax").value;
      if (pmin !== "") body.pop_min = Number(pmin);
      if (pmax !== "") body.pop_max = Number(pmax);
      try {
        const data = await api("/api/filter", { method: "POST", body });
        log("筛选完成", { before: data.count_before, after: data.count_after });
        await refresh();
      } catch (e) {
        log(String(e));
      }
    });

    document.getElementById("checkAllFiltered").addEventListener("change", (ev) => {
      document.querySelectorAll("#filteredTable .slot-check").forEach((c) => {
        c.checked = ev.target.checked;
      });
    });

    document.getElementById("btnImportTrack").addEventListener("click", async () => {
      const ids = checkedPageIds();
      try {
        const data = await api("/api/track/import", {
          method: "POST",
          body: { selected_page_ids: ids },
        });
        log("已导入跟踪表", { imported: data.imported, batch_id: data.batch && data.batch.meta.batch_id });
        await refresh();
        showStep("3");
      } catch (e) {
        log(String(e));
      }
    });

    document.getElementById("btnPipeline").addEventListener("click", async () => {
      log("Pipeline 运行中（可能较久）…");
      try {
        const data = await api("/api/actions/pipeline", {
          method: "POST",
          body: {
            fetch: true,
            skip_existing: document.getElementById("skipExisting").checked,
            mode: "live",
          },
        });
        log("Pipeline 完成", data.pipeline_report || data);
        await refresh();
      } catch (e) {
        log(String(e));
      }
    });

    document.getElementById("btnRefreshGates").addEventListener("click", async () => {
      try {
        await api("/api/track/refresh-gates", { method: "POST", body: {} });
        await refresh();
      } catch (e) {
        log(String(e));
      }
    });

    document.getElementById("btnGeneratePages").addEventListener("click", async () => {
      log("Generate pages…");
      try {
        const data = await api("/api/actions/generate", {
          method: "POST",
          body: { generate_all: false },
        });
        log("Generate 完成", { ok_count: data.ok_count, fail_count: data.fail_count });
        await refresh();
      } catch (e) {
        log(String(e));
      }
    });

    document.getElementById("btnGenerateAll").addEventListener("click", async () => {
      log("Generate all…");
      try {
        await api("/api/actions/generate", { method: "POST", body: { generate_all: true } });
        await refresh();
      } catch (e) {
        log(String(e));
      }
    });

    document.getElementById("btnSpeedtest").addEventListener("click", async () => {
      log("Speedtest 运行中…");
      try {
        const data = await api("/api/actions/speedtest", { method: "POST", body: {} });
        log("Speedtest 结束", { ok: data.ok, report: data.report });
        await refresh();
      } catch (e) {
        log(String(e));
      }
    });

    document.getElementById("btnSeo").addEventListener("click", async () => {
      log("seo_c2…");
      try {
        const data = await api("/api/actions/seo", { method: "POST", body: {} });
        log("seo_c2 结束", { ok: data.ok, returncode: data.returncode });
        await refresh();
        showStep("4");
      } catch (e) {
        log(String(e));
      }
    });

    document.getElementById("btnDeployPrepare").addEventListener("click", async () => {
      log("deploy --prepare-only…");
      try {
        const data = await api("/api/actions/deploy", {
          method: "POST",
          body: { prepare_only: true },
        });
        log("prepare 结束", { ok: data.ok });
        await refresh();
      } catch (e) {
        log(String(e));
      }
    });

    document.getElementById("btnDeployReal").addEventListener("click", async () => {
      if (!window.confirm("确认执行正式 wrangler deploy？将影响公网站点。")) return;
      log("正式 deploy…");
      try {
        const data = await api("/api/actions/deploy", {
          method: "POST",
          body: { prepare_only: false },
        });
        log("deploy 结束", { ok: data.ok });
        await refresh();
      } catch (e) {
        log(String(e));
      }
    });
  }

  bind();
  loadFiles().catch((e) => log(String(e)));
  refresh().catch((e) => log(String(e)));
})();
