/**
 * Ops 控制台前端 — 四段流程与跟踪表。
 * @file workflow/ops/static/ops.js
 */

(function () {
  "use strict";

  /** @type {object|null} 最近一次 /api/state */
  let state = null;

  /** @type {Array<object>} 最近一次日导出搜索结果 */
  let exportHits = [];

  /** 并发忙碌计数（嵌套 withBusy 时保持面板） */
  let busyDepth = 0;

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
   * 显示进度条。
   * @param {string} title 标题
   * @param {object} [opts]
   * @param {number|null} [opts.percent] 0-100；null=不确定进度
   * @param {string} [opts.message] 明细
   */
  function showProgress(title, opts) {
    const box = document.getElementById("opsProgress");
    const bar = document.getElementById("opsProgressBar");
    const pctEl = document.getElementById("opsProgressPct");
    const msgEl = document.getElementById("opsProgressMsg");
    box.hidden = false;
    document.getElementById("opsProgressTitle").textContent = title || "处理中…";
    const percent = opts && opts.percent;
    const message = (opts && opts.message) || "";
    msgEl.textContent = message;
    if (percent == null || Number.isNaN(percent)) {
      bar.classList.add("is-indeterminate");
      bar.style.width = "36%";
      pctEl.textContent = "";
    } else {
      bar.classList.remove("is-indeterminate");
      const p = Math.max(0, Math.min(100, Number(percent)));
      bar.style.width = p + "%";
      pctEl.textContent = Math.round(p) + "%";
    }
  }

  /** 隐藏进度条。 */
  function hideProgress() {
    document.getElementById("opsProgress").hidden = true;
    const bar = document.getElementById("opsProgressBar");
    bar.classList.remove("is-indeterminate");
    bar.style.width = "0%";
  }

  /**
   * 包一层忙碌态：立即给反馈，结束后清理。
   * @param {string} title
   * @param {() => Promise<*>} fn
   * @param {object} [opts] { indeterminate?: boolean }
   */
  async function withBusy(title, fn, opts) {
    busyDepth += 1;
    document.body.classList.add("ops-busy");
    showProgress(title, {
      percent: opts && opts.indeterminate === false ? 0 : null,
      message: "已开始，请稍候…",
    });
    log(title);
    try {
      return await fn();
    } finally {
      busyDepth = Math.max(0, busyDepth - 1);
      if (busyDepth === 0) {
        document.body.classList.remove("ops-busy");
        hideProgress();
      }
    }
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
   * sleep。
   * @param {number} ms
   */
  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * 启动日导出索引加载并轮询进度直到完成。
   * @param {object} body ensure 参数
   * @returns {Promise<object>} 最终 progress
   */
  /**
   * 格式化 badge：导出日 + 规模 + 增量统计。
   * @param {object} meta
   * @returns {string}
   */
  function formatExportBadge(meta) {
    if (!meta || !meta.export_date) return "MySQL 未入库";
    const mode = meta.ingest_mode || "incremental";
    const modeTag = mode === "replace" ? "全量重建" : "增量";
    let text =
      `MySQL · ${meta.export_date} · movie ${meta.movie_count ?? meta.cached_movie_count ?? 0}` +
      ` · tv ${meta.tv_count ?? meta.cached_tv_count ?? 0} · ${modeTag}`;
    if (meta.last_deleted != null && meta.last_scanned) {
      text += ` · 扫 ${meta.last_scanned} / 删 ${meta.last_deleted}`;
    } else if (meta.db && meta.db.last_scanned) {
      text += ` · 扫 ${meta.db.last_scanned} / 删 ${meta.db.last_deleted || 0}`;
    }
    return text;
  }

  async function ensureExportWithProgress(body) {
    const title = body.daily
      ? "日同步：全量下载 → 增量入库"
      : body.force_reload
        ? "全量重建 TMDB 导出"
        : "全量下载 → 增量入库";
    showProgress(title, {
      percent: 1,
      message: "启动后台任务…",
    });
    document.body.classList.add("ops-busy");
    busyDepth += 1;
    log(title + "…", body);
    try {
      const start = await api("/api/source/export/ensure", {
        method: "POST",
        body: { async: true, ...body },
      });
      if (start.already_ready && start.result) {
        showProgress("MySQL 已是最新", { percent: 100, message: start.progress.message || "" });
        document.getElementById("exportIndexBadge").textContent = formatExportBadge(start.result);
        await sleep(400);
        return start.progress;
      }
      for (;;) {
        const prog = await api("/api/source/export/progress");
        showProgress(title, {
          percent: prog.percent != null ? prog.percent : null,
          message: prog.message || prog.phase || "",
        });
        document.getElementById("exportIndexBadge").textContent =
          prog.status === "done"
            ? formatExportBadge({
                export_date: prog.export_date,
                movie_count: prog.cached_movie_count,
                tv_count: prog.cached_tv_count,
                ingest_mode: prog.db && prog.db.ingest_mode,
                last_scanned: prog.db && prog.db.last_scanned,
                last_deleted: prog.db && prog.db.last_deleted,
              })
            : `入库中 ${prog.percent || 0}% · ${prog.phase || ""}`;
        if (prog.status === "done") {
          log("日导出已同步 MySQL", {
            export_date: prog.export_date,
            movies: prog.cached_movie_count,
            tv: prog.cached_tv_count,
            ingest_mode: prog.db && prog.db.ingest_mode,
            last_scanned: prog.db && prog.db.last_scanned,
            last_deleted: prog.db && prog.db.last_deleted,
            storage: "mysql",
          });
          return prog;
        }
        if (prog.status === "error") {
          throw new Error(prog.error || prog.message || "索引加载失败");
        }
        await sleep(600);
      }
    } finally {
      busyDepth = Math.max(0, busyDepth - 1);
      if (busyDepth === 0) {
        document.body.classList.remove("ops-busy");
        hideProgress();
      }
    }
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
   * 渲染日导出搜索结果表。
   * @param {Array<object>} hits
   * @param {number} totalMatched
   */
  function renderExportHits(hits, totalMatched) {
    exportHits = hits || [];
    renderMetrics(document.getElementById("exportSearchMetrics"), [
      ["命中", totalMatched != null ? totalMatched : exportHits.length],
      ["本页", exportHits.length],
    ]);
    const tbody = document.querySelector("#exportHitTable tbody");
    tbody.innerHTML = exportHits
      .map((h, idx) => {
        const tier = h.source_tier || "pop";
        const isTv = (h.media_type || "") === "tv";
        const seasonCell = isTv
          ? `<input type="number" class="export-se" data-idx="${idx}" data-field="season" value="${
              h.season != null ? h.season : 1
            }" min="1" style="width:56px" />`
          : "—";
        const episodeCell = isTv
          ? `<input type="number" class="export-se" data-idx="${idx}" data-field="episode" value="${
              h.episode != null ? h.episode : 1
            }" min="1" style="width:56px" />`
          : "—";
        return `<tr>
          <td><input type="checkbox" class="export-hit-check" data-idx="${idx}" /></td>
          <td class="tier-${tier}">${tier}</td>
          <td>${escapeHtml(h.title || h.label || "")}</td>
          <td><code>${escapeHtml(h.page_id || "")}</code></td>
          <td>${escapeHtml(h.media_type || "")}</td>
          <td>${h.popularity != null ? h.popularity : "—"}</td>
          <td>${seasonCell}</td>
          <td>${episodeCell}</td>
        </tr>`;
      })
      .join("");
  }

  /**
   * 收集搜索结果中勾选的 selections。
   * @returns {Array<object>}
   */
  function collectExportSelections() {
    const checks = document.querySelectorAll("#exportHitTable .export-hit-check:checked");
    const out = [];
    checks.forEach((el) => {
      const idx = Number(el.dataset.idx);
      const base = exportHits[idx];
      if (!base) return;
      const sel = {
        tmdb_id: base.tmdb_id,
        media_type: base.media_type,
        title: base.title,
        popularity: base.popularity,
      };
      if (base.media_type === "tv") {
        const sInput = document.querySelector(
          `.export-se[data-idx="${idx}"][data-field="season"]`
        );
        const eInput = document.querySelector(
          `.export-se[data-idx="${idx}"][data-field="episode"]`
        );
        sel.season = sInput ? Number(sInput.value || 1) : 1;
        sel.episode = eInput ? Number(eInput.value || 1) : 1;
      }
      out.push(sel);
    });
    return out;
  }

  /**
   * 绑定事件。
   */
  function bind() {
    document.querySelectorAll(".ops-step-tab").forEach((btn) => {
      btn.addEventListener("click", () => showStep(btn.dataset.step));
    });

    document.getElementById("btnRefresh").addEventListener("click", () => {
      withBusy("刷新状态", () => refresh(), { indeterminate: true }).catch((e) =>
        log(String(e))
      );
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
      try {
        await withBusy("生成 TMDB 清单（锚点/curated/pop）", async () => {
          showProgress("生成 TMDB 清单", {
            percent: null,
            message: "下载导出 / 选槽中，可能需要数十秒…",
          });
          const data = await api("/api/source/build-tmdb", { method: "POST", body });
          log("清单已生成", data.result);
          await refresh();
          showStep("2");
        });
      } catch (e) {
        log(String(e));
      }
    });

    document.getElementById("btnLoadPath").addEventListener("click", async () => {
      const path = document.getElementById("slotsPath").value.trim();
      if (!path) return;
      try {
        await withBusy("加载 slots JSON", async () => {
          await api("/api/source/load", { method: "POST", body: { path } });
          await refresh();
          showStep("2");
        });
      } catch (e) {
        log(String(e));
      }
    });

    document.getElementById("fileList").addEventListener("click", async (ev) => {
      const btn = ev.target.closest(".btn-load-file");
      if (!btn) return;
      document.getElementById("slotsPath").value = btn.dataset.path;
      try {
        await withBusy("加载 slots JSON", async () => {
          await api("/api/source/load", { method: "POST", body: { path: btn.dataset.path } });
          await refresh();
          showStep("2");
        });
      } catch (e) {
        log(String(e));
      }
    });

    document.getElementById("btnEnsureExport").addEventListener("click", async () => {
      try {
        await ensureExportWithProgress({
          download: true,
          force_download: document.getElementById("exportForceDownload").checked,
          force_reload: document.getElementById("exportForceReload").checked,
          daily: false,
        });
      } catch (e) {
        log(String(e));
        hideProgress();
        document.body.classList.remove("ops-busy");
        busyDepth = 0;
      }
    });

    document.getElementById("btnDailySyncExport").addEventListener("click", async () => {
      try {
        await ensureExportWithProgress({
          download: true,
          daily: true,
          force_reload: document.getElementById("exportForceReload").checked,
        });
      } catch (e) {
        log(String(e));
        hideProgress();
        document.body.classList.remove("ops-busy");
        busyDepth = 0;
      }
    });

    document.getElementById("btnSearchExport").addEventListener("click", async () => {
      const body = {
        q: document.getElementById("exportQ").value || null,
        media_types: multiValues("exportMedia"),
        exclude_adult: document.getElementById("exportExcludeAdult").checked,
        exclude_video: document.getElementById("exportExcludeVideo").checked,
        limit: Number(document.getElementById("exportLimit").value || 50),
        offset: 0,
        download: false,
      };
      const pmin = document.getElementById("exportPopMin").value;
      const pmax = document.getElementById("exportPopMax").value;
      if (pmin !== "") body.pop_min = Number(pmin);
      if (pmax !== "") body.pop_max = Number(pmax);
      try {
        // 索引未就绪时先带进度加载，再搜索
        const ready = await api("/api/source/export/progress");
        if (!ready.ready) {
          await ensureExportWithProgress({ download: true, force_reload: false });
        }
        await withBusy("从 MySQL 搜索日导出", async () => {
          showProgress("MySQL 搜索", { percent: null, message: JSON.stringify(body) });
          const data = await api("/api/source/export/search", { method: "POST", body });
          if (data.meta && data.meta.export_date) {
            document.getElementById("exportIndexBadge").textContent =
              `MySQL · ${data.meta.export_date} · 命中 ${data.total_matched}`;
          }
          renderExportHits(data.hits || [], data.total_matched);
          log("搜索完成", { total_matched: data.total_matched, page: (data.hits || []).length });
        });
      } catch (e) {
        log(String(e));
        hideProgress();
        document.body.classList.remove("ops-busy");
        busyDepth = 0;
      }
    });

    document.getElementById("checkAllExportHits").addEventListener("change", (ev) => {
      document.querySelectorAll("#exportHitTable .export-hit-check").forEach((c) => {
        c.checked = ev.target.checked;
      });
    });

    async function addExportSelections(mode) {
      const selections = collectExportSelections();
      if (!selections.length) {
        log("请先勾选搜索结果中的条目");
        return;
      }
      await withBusy(`并入工作区（${mode}）`, async () => {
        const data = await api("/api/source/export/add", {
          method: "POST",
          body: { selections, mode },
        });
        log("已加入工作区", { added: data.added, mode: data.mode });
        await refresh();
      });
    }

    document.getElementById("btnAddExportAppend").addEventListener("click", () => {
      addExportSelections("append").catch((e) => log(String(e)));
    });
    document.getElementById("btnAddExportReplace").addEventListener("click", () => {
      if (!window.confirm("将用勾选结果覆盖当前工作区候选清单？")) return;
      addExportSelections("replace").catch((e) => log(String(e)));
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
        await withBusy("应用筛选", async () => {
          const data = await api("/api/filter", { method: "POST", body });
          log("筛选完成", { before: data.count_before, after: data.count_after });
          await refresh();
        });
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
        await withBusy("导入跟踪表", async () => {
          const data = await api("/api/track/import", {
            method: "POST",
            body: { selected_page_ids: ids },
          });
          log("已导入跟踪表", {
            imported: data.imported,
            batch_id: data.batch && data.batch.meta.batch_id,
          });
          await refresh();
          showStep("3");
        });
      } catch (e) {
        log(String(e));
      }
    });

    /**
     * ③ 一键跑生成流程：Pipeline（自动刷新门禁）→ Generate 选中页 → 测速 write。
     * 任一步 API 失败（ok===false）即中止后续步骤；「跳过已有 ≥2 magnet」仅作用于 Pipeline。
     */
    document.getElementById("btnRunGenerationFlow").addEventListener("click", async () => {
      /** @type {boolean} Pipeline 是否跳过已有 ≥2 magnet 的槽 */
      const skipExisting = document.getElementById("skipExisting").checked;
      try {
        await withBusy("一键跑生成流程", async () => {
          // 步骤 1/3：Jackett 拉源 + 写库（后端会自动 refresh_gates）
          showProgress("一键跑生成流程 · 1/3 Pipeline", {
            percent: 5,
            message: "Jackett 拉取 / 评分 / 写库，请勿关闭页面…",
          });
          const pipeData = await api("/api/actions/pipeline", {
            method: "POST",
            body: {
              fetch: true,
              skip_existing: skipExisting,
              mode: "live",
            },
          });
          log("一键 · Pipeline 完成", pipeData.pipeline_report || pipeData);
          await refresh();

          // 步骤 2/3：烘焙选中槽静态页（非 generate all）
          showProgress("一键跑生成流程 · 2/3 Generate", {
            percent: 45,
            message: "烘焙选中页静态 HTML…",
          });
          const genData = await api("/api/actions/generate", {
            method: "POST",
            body: { generate_all: false },
          });
          log("一键 · Generate 完成", {
            ok_count: genData.ok_count,
            fail_count: genData.fail_count,
          });
          await refresh();

          // 步骤 3/3：批量测速并写回
          showProgress("一键跑生成流程 · 3/3 测速", {
            percent: 75,
            message: "批量测速 write 进行中…",
          });
          const speedData = await api("/api/actions/speedtest", {
            method: "POST",
            body: {},
          });
          log("一键 · Speedtest 结束", { ok: speedData.ok, report: speedData.report });
          showProgress("一键跑生成流程完成", {
            percent: 100,
            message: "Pipeline → Generate → 测速 均已跑完",
          });
          await refresh();
        });
      } catch (e) {
        log("一键跑生成流程中断：" + String(e));
      }
    });

    document.getElementById("btnPipeline").addEventListener("click", async () => {
      try {
        await withBusy("Pipeline（Jackett 拉源，可能较久）", async () => {
          showProgress("Pipeline 运行中", {
            percent: null,
            message: "拉取 / 评分 / 写库，请勿关闭页面…",
          });
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
        });
      } catch (e) {
        log(String(e));
      }
    });

    document.getElementById("btnRefreshGates").addEventListener("click", async () => {
      try {
        await withBusy("刷新门禁", async () => {
          await api("/api/track/refresh-gates", { method: "POST", body: {} });
          await refresh();
        });
      } catch (e) {
        log(String(e));
      }
    });

    document.getElementById("btnGeneratePages").addEventListener("click", async () => {
      try {
        await withBusy("Generate 选中页", async () => {
          const data = await api("/api/actions/generate", {
            method: "POST",
            body: { generate_all: false },
          });
          log("Generate 完成", { ok_count: data.ok_count, fail_count: data.fail_count });
          await refresh();
        });
      } catch (e) {
        log(String(e));
      }
    });

    document.getElementById("btnGenerateAll").addEventListener("click", async () => {
      try {
        await withBusy("Generate all", async () => {
          showProgress("Generate all", { percent: null, message: "烘焙全站静态页…" });
          await api("/api/actions/generate", { method: "POST", body: { generate_all: true } });
          await refresh();
        });
      } catch (e) {
        log(String(e));
      }
    });

    document.getElementById("btnSpeedtest").addEventListener("click", async () => {
      try {
        await withBusy("测速 write", async () => {
          showProgress("Speedtest", { percent: null, message: "批量测速进行中…" });
          const data = await api("/api/actions/speedtest", { method: "POST", body: {} });
          log("Speedtest 结束", { ok: data.ok, report: data.report });
          await refresh();
        });
      } catch (e) {
        log(String(e));
      }
    });

    document.getElementById("btnSeo").addEventListener("click", async () => {
      try {
        await withBusy("seo_c2_checklist", async () => {
          const data = await api("/api/actions/seo", { method: "POST", body: {} });
          log("seo_c2 结束", { ok: data.ok, returncode: data.returncode });
          await refresh();
          showStep("4");
        });
      } catch (e) {
        log(String(e));
      }
    });

    document.getElementById("btnDeployPrepare").addEventListener("click", async () => {
      try {
        await withBusy("Deploy prepare-only", async () => {
          const data = await api("/api/actions/deploy", {
            method: "POST",
            body: { prepare_only: true },
          });
          log("prepare 结束", { ok: data.ok });
          await refresh();
        });
      } catch (e) {
        log(String(e));
      }
    });

    document.getElementById("btnDeployReal").addEventListener("click", async () => {
      if (!window.confirm("确认执行正式 wrangler deploy？将影响公网站点。")) return;
      try {
        await withBusy("正式 wrangler deploy", async () => {
          showProgress("Deploy", { percent: null, message: "wrangler 上传中…" });
          const data = await api("/api/actions/deploy", {
            method: "POST",
            body: { prepare_only: false },
          });
          log("deploy 结束", { ok: data.ok });
          await refresh();
        });
      } catch (e) {
        log(String(e));
      }
    });
  }

  bind();
  loadFiles().catch((e) => log(String(e)));
  refresh().catch((e) => log(String(e)));
})();
