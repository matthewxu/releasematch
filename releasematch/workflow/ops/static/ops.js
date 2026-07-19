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

  /**
   * 前端 TV 季集缓存（key = tmdb_id）。
   * @type {Object.<string, {seasons: Array<object>, episodesBySeason: Object.<string, Array<object>>, name?: string}>}
   */
  let tvCatalogById = {};

  /**
   * TV 分集多选状态：key = ``{tmdb_id}:{season}`` → 已选 episode_number 数组。
   * @type {Object.<string, number[]>}
   */
  let tvEpisodeSelection = {};

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
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      ...opts,
      body: opts && opts.body ? JSON.stringify(opts.body) : undefined,
    });
    if (res.status === 401 && path !== "/api/auth/status") {
      window.location.replace("/login.html");
      throw new Error("未登录或会话已过期");
    }
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
   * @param {string} step 1-5
   */
  function showStep(step) {
    document.querySelectorAll(".ops-step-tab").forEach((btn) => {
      btn.setAttribute("aria-selected", btn.dataset.step === step ? "true" : "false");
    });
    document.querySelectorAll(".ops-panel").forEach((panel) => {
      panel.classList.toggle("is-active", panel.dataset.panel === step);
    });
    if (String(step) === "5") {
      loadConfig().catch((e) => log(String(e)));
    }
  }

  /**
   * 最近一次配置包（/api/config）。
   * @type {object|null}
   */
  let configBundle = null;

  /**
   * 更新顶栏配置徽章。
   * @param {object|null} status /api/config.status
   */
  function renderConfigStatusBadge(status) {
    const el = document.getElementById("configStatusBadge");
    if (!el) return;
    if (!status) {
      el.textContent = "配置 · …";
      return;
    }
    const mysqlOk = status.release_mysql_configured;
    const jackettOk = status.jackett_key_configured;
    const parts = [];
    parts.push(mysqlOk ? "MySQL✓" : "MySQL✗");
    parts.push(jackettOk ? "Jackett✓" : "Jackett✗");
    el.textContent = "配置 · " + parts.join(" · ");
    el.title = JSON.stringify(status);
  }

  /**
   * 渲染 .env 表单字段。
   * @param {Array<object>} fields 字段定义+当前值
   */
  function renderConfigEnvFields(fields) {
    const host = document.getElementById("configEnvFields");
    if (!host) return;
    let html = "";
    let lastGroup = "";
    (fields || []).forEach((f) => {
      if (f.group !== lastGroup) {
        lastGroup = f.group;
        html += `<div class="ops-config-group-title">${escapeHtml(f.group)}</div>`;
      }
      const inputType = f.secret ? "password" : "text";
      html += `<div class="ops-config-field">
        <label for="cfg-${escapeHtml(f.key)}">${escapeHtml(f.label)}
          <span class="ops-config-key">${escapeHtml(f.key)}</span>
        </label>
        <input type="${inputType}" id="cfg-${escapeHtml(f.key)}"
          data-env-key="${escapeHtml(f.key)}"
          value="${escapeHtml(f.value == null ? "" : String(f.value))}"
          autocomplete="off" />
        ${f.hint ? `<div class="ops-config-hint">${escapeHtml(f.hint)} · 来源 ${escapeHtml(f.source || "")}</div>` : `<div class="ops-config-hint">来源 ${escapeHtml(f.source || "")}</div>`}
      </div>`;
    });
    host.innerHTML = html || "<p class='lead'>无字段</p>";
  }

  /**
   * 从配置表单收集键值。
   * @returns {Object.<string, string>}
   */
  function collectEnvFormValues() {
    /** @type {Object.<string, string>} */
    const values = {};
    document.querySelectorAll("#configEnvFields [data-env-key]").forEach((input) => {
      const key = input.getAttribute("data-env-key");
      if (key) values[key] = input.value;
    });
    return values;
  }

  /**
   * 用 /api/config 响应填充配置页。
   * @param {object} bundle get_config_bundle 结果
   */
  function applyConfigBundle(bundle) {
    configBundle = bundle;
    const env = bundle.env || {};
    const accounts = bundle.accounts || {};
    const status = bundle.status || {};
    document.getElementById("configEnvPath").textContent = env.path || ".env";
    document.getElementById("configAccountsPath").textContent =
      accounts.path || "workflow/torrent_sources/accounts.local.json";
    const badge = document.getElementById("configAccountsBadge");
    if (accounts.using_example) {
      badge.textContent = "正在读 example（请保存为 local）";
    } else if (accounts.exists_local) {
      badge.textContent = "accounts.local.json";
    } else {
      badge.textContent = "未找到 local";
    }
    renderConfigEnvFields(env.fields || []);
    document.getElementById("configEnvRaw").value = env.raw || "";
    try {
      document.getElementById("configAccountsRaw").value = JSON.stringify(
        accounts.data || {},
        null,
        2
      );
    } catch (_) {
      document.getElementById("configAccountsRaw").value = "";
    }
    renderConfigStatusBadge(status);
    const probe = status.jackett_probe || {};
    renderMetrics(document.getElementById("configMetrics"), [
      [".env", env.exists ? "已存在" : "缺失"],
      ["accounts.local", accounts.exists_local ? "已存在" : "缺失"],
      ["Release MySQL", status.release_mysql_configured ? "已配置" : "未配置"],
      ["Jackett Key", status.jackett_key_configured ? "已配置" : "未配置"],
      [
        "Jackett 探测",
        probe.skipped
          ? "跳过"
          : probe.reachable
            ? "可达 " + (probe.status_code || "")
            : "不可达",
      ],
      ["后端", status.storage_backend || "—"],
    ]);
  }

  /**
   * 从磁盘加载配置到 UI。
   * @returns {Promise<object>}
   */
  async function loadConfig() {
    const data = await api("/api/config");
    applyConfigBundle(data);
    log("配置已从磁盘加载", {
      env: data.env && data.env.path,
      accounts: data.accounts && data.accounts.path,
    });
    return data;
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
   * 分集多选缓存键。
   * @param {number|string} tmdbId
   * @param {number|string} season
   * @returns {string}
   */
  function episodeSelKey(tmdbId, season) {
    return String(tmdbId) + ":" + String(season);
  }

  /**
   * 读取已选分集号（升序）。
   * @param {number|string} tmdbId
   * @param {number|string} season
   * @returns {number[]}
   */
  function getSelectedEpisodes(tmdbId, season) {
    const arr = tvEpisodeSelection[episodeSelKey(tmdbId, season)] || [];
    return arr
      .map((n) => Number(n))
      .filter((n) => n > 0)
      .sort((a, b) => a - b);
  }

  /**
   * 写入已选分集号（去重排序）。
   * @param {number|string} tmdbId
   * @param {number|string} season
   * @param {number[]} episodes
   */
  function setSelectedEpisodes(tmdbId, season, episodes) {
    const uniq = Array.from(
      new Set((episodes || []).map((n) => Number(n)).filter((n) => n > 0))
    ).sort((a, b) => a - b);
    tvEpisodeSelection[episodeSelKey(tmdbId, season)] = uniq;
  }

  /**
   * 渲染日导出搜索结果表。
   * TV 行：Season 下拉 +「季集」；Episode 列为批量勾选面板。
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
        const tid = h.tmdb_id;
        const cat = tid != null ? tvCatalogById[String(tid)] : null;
        let seasonCell = "—";
        let episodeCell = "—";
        if (isTv) {
          const seasonVal = h.season != null ? Number(h.season) : 1;
          const seasonOpts = buildSeasonOptionsHtml(cat && cat.seasons, seasonVal);
          const epList =
            cat && cat.episodesBySeason
              ? cat.episodesBySeason[String(seasonVal)]
              : null;
          seasonCell = `<div class="tv-se-cell">
            <select class="export-season" data-idx="${idx}" data-tmdb="${tid}" title="选择季">
              ${seasonOpts}
            </select>
            <button type="button" class="secondary btn-fetch-tv" data-idx="${idx}" data-tmdb="${tid}" title="经 crawler_tmdb 拉取并写入 MySQL tmdb_tv_*">季集</button>
          </div>`;
          episodeCell = buildEpisodeBatchHtml(idx, tid, seasonVal, epList);
        }
        return `<tr data-idx="${idx}">
          <td><input type="checkbox" class="export-hit-check" data-idx="${idx}" /></td>
          <td class="tier-${tier}">${tier}</td>
          <td>${escapeHtml(h.title || h.label || "")}</td>
          <td><code class="export-page-id" data-idx="${idx}">${escapeHtml(
            h.page_id || ""
          )}</code></td>
          <td>${escapeHtml(h.media_type || "")}</td>
          <td>${h.popularity != null ? h.popularity : "—"}</td>
          <td>${seasonCell}</td>
          <td class="export-ep-cell" data-idx="${idx}">${episodeCell}</td>
        </tr>`;
      })
      .join("");
    // 渲染后同步 page_id 预览（批量选集时显示条数）
    exportHits.forEach((h, idx) => {
      if ((h.media_type || "") === "tv") syncExportHitPageId(idx);
    });
  }

  /**
   * 生成季 `<option>` HTML。
   * @param {Array<object>|null|undefined} seasons
   * @param {number} selected
   * @returns {string}
   */
  function buildSeasonOptionsHtml(seasons, selected) {
    if (seasons && seasons.length) {
      return seasons
        .map((s) => {
          const n = Number(s.season_number);
          const label = `S${String(n).padStart(2, "0")}${
            s.episode_count != null ? ` (${s.episode_count}ep)` : ""
          }${s.name ? " · " + escapeHtml(String(s.name)) : ""}`;
          return `<option value="${n}" ${n === selected ? "selected" : ""}>${label}</option>`;
        })
        .join("");
    }
    return `<option value="${selected}" selected>S${String(selected).padStart(
      2,
      "0"
    )}（点「季集」拉取）</option>`;
  }

  /**
   * 生成分集批量勾选面板 HTML。
   * @param {number} idx 搜索行下标
   * @param {number|string} tmdbId
   * @param {number} season
   * @param {Array<object>|null|undefined} episodes
   * @returns {string}
   */
  function buildEpisodeBatchHtml(idx, tmdbId, season, episodes) {
    if (!episodes || !episodes.length) {
      return `<div class="tv-ep-batch tv-ep-batch--empty" data-idx="${idx}" data-tmdb="${tmdbId}" data-season="${season}">
        <span class="tv-ep-hint">先点「季集」加载分集，再多选</span>
      </div>`;
    }
    const selected = new Set(getSelectedEpisodes(tmdbId, season));
    // 首次加载且未选过：默认不预勾，避免误加一整季；用户点「全选本季」
    const checks = episodes
      .map((ep) => {
        const n = Number(ep.episode_number);
        const name = ep.name ? " · " + escapeHtml(String(ep.name)) : "";
        const checked = selected.has(n) ? "checked" : "";
        return `<label class="tv-ep-item" title="${escapeHtml(
          ep.name || "E" + n
        )}">
          <input type="checkbox" class="export-ep-check" data-idx="${idx}" data-tmdb="${tmdbId}" data-season="${season}" data-ep="${n}" ${checked} />
          <span>E${String(n).padStart(2, "0")}${name}</span>
        </label>`;
      })
      .join("");
    const count = selected.size;
    return `<div class="tv-ep-batch" data-idx="${idx}" data-tmdb="${tmdbId}" data-season="${season}">
      <div class="tv-ep-batch-actions">
        <button type="button" class="secondary btn-ep-all" data-idx="${idx}" data-tmdb="${tmdbId}" data-season="${season}">全选本季</button>
        <button type="button" class="secondary btn-ep-none" data-idx="${idx}" data-tmdb="${tmdbId}" data-season="${season}">清空</button>
        <span class="tv-ep-count" data-idx="${idx}">已选 ${count}</span>
      </div>
      <div class="tv-ep-list">${checks}</div>
    </div>`;
  }

  /**
   * 刷新某行分集批量面板 DOM（保留当前季选择状态）。
   * @param {number} idx
   * @param {number} season
   * @param {Array<object>} episodes
   */
  function refreshEpisodeBatchCell(idx, season, episodes) {
    const base = exportHits[idx];
    if (!base) return;
    const cell = document.querySelector(`.export-ep-cell[data-idx="${idx}"]`);
    if (!cell) return;
    cell.innerHTML = buildEpisodeBatchHtml(idx, base.tmdb_id, season, episodes);
    syncExportHitPageId(idx);
  }

  /**
   * 更新某行「已选 N」计数。
   * @param {number} idx
   * @param {number|string} tmdbId
   * @param {number|string} season
   */
  function updateEpisodeSelectedCount(idx, tmdbId, season) {
    const n = getSelectedEpisodes(tmdbId, season).length;
    const el = document.querySelector(`.tv-ep-count[data-idx="${idx}"]`);
    if (el) el.textContent = "已选 " + n;
  }

  /**
   * 按当前季 + 批量已选集刷新 page_id 预览。
   * @param {number} idx
   */
  function syncExportHitPageId(idx) {
    const base = exportHits[idx];
    if (!base || base.media_type !== "tv") return;
    const sEl = document.querySelector(`.export-season[data-idx="${idx}"]`);
    const season = sEl ? Number(sEl.value || 1) : Number(base.season || 1);
    const selected = getSelectedEpisodes(base.tmdb_id, season);
    base.season = season;
    const ss = String(season).padStart(2, "0");
    const code = document.querySelector(`.export-page-id[data-idx="${idx}"]`);
    if (selected.length === 0) {
      base.episode = null;
      base.page_id = `tv:${base.tmdb_id}:s${ss}e??`;
      base.label = `${(base.title || "").slice(0, 24)} S${ss}（未选集）`.trim();
      if (code) code.textContent = base.page_id + " · 未选集";
      return;
    }
    if (selected.length === 1) {
      const episode = selected[0];
      base.episode = episode;
      const ee = String(episode).padStart(2, "0");
      base.page_id = `tv:${base.tmdb_id}:s${ss}e${ee}`;
      base.label = `${(base.title || "").slice(0, 24)} S${ss}E${ee}`.trim();
      if (code) code.textContent = base.page_id;
      return;
    }
    base.episode = selected[0];
    const lo = String(selected[0]).padStart(2, "0");
    const hi = String(selected[selected.length - 1]).padStart(2, "0");
    base.page_id = `tv:${base.tmdb_id}:s${ss}×${selected.length}`;
    base.label = `${(base.title || "").slice(0, 24)} S${ss} E${lo}–E${hi} (${selected.length})`.trim();
    if (code) {
      code.textContent = `tv:${base.tmdb_id}:s${ss}e${lo}…e${hi} ×${selected.length}`;
    }
  }

  /**
   * 拉取 TV 季列表并填充该行下拉；默认再拉当前季的分集。
   * @param {number} idx 搜索结果行下标
   * @param {object} [opts]
   * @param {boolean} [opts.forceRefresh]
   * @returns {Promise<void>}
   */
  async function fetchTvSeasonsForRow(idx, opts) {
    const base = exportHits[idx];
    if (!base || base.media_type !== "tv") return;
    const tid = Number(base.tmdb_id);
    const forceRefresh = !!(opts && opts.forceRefresh);
    const data = await api("/api/source/tv/seasons", {
      method: "POST",
      body: { tmdb_id: tid, force_refresh: forceRefresh, include_specials: false },
    });
    const key = String(tid);
    if (!tvCatalogById[key]) {
      tvCatalogById[key] = { seasons: [], episodesBySeason: {}, name: "" };
    }
    tvCatalogById[key].seasons = data.seasons || [];
    tvCatalogById[key].name = data.name || tvCatalogById[key].name || "";

    const sEl = document.querySelector(`.export-season[data-idx="${idx}"]`);
    const cur =
      sEl && sEl.value
        ? Number(sEl.value)
        : base.season != null
          ? Number(base.season)
          : tvCatalogById[key].seasons[0]
            ? Number(tvCatalogById[key].seasons[0].season_number)
            : 1;
    if (sEl) {
      sEl.innerHTML = buildSeasonOptionsHtml(tvCatalogById[key].seasons, cur);
      sEl.value = String(cur);
    }
    log(`TV ${tid} 季列表已就绪`, {
      count: (data.seasons || []).length,
      source: data.source,
      storage: data.storage,
    });
    await fetchTvEpisodesForRow(idx, cur, { forceRefresh: false });
  }

  /**
   * 拉取指定季分集并填充批量勾选面板。
   * @param {number} idx
   * @param {number} season
   * @param {object} [opts]
   * @param {boolean} [opts.forceRefresh]
   * @param {boolean} [opts.selectAll] 拉取后自动全选本季
   * @returns {Promise<void>}
   */
  async function fetchTvEpisodesForRow(idx, season, opts) {
    const base = exportHits[idx];
    if (!base || base.media_type !== "tv") return;
    const tid = Number(base.tmdb_id);
    const sn = Number(season);
    const forceRefresh = !!(opts && opts.forceRefresh);
    const selectAll = !!(opts && opts.selectAll);
    const data = await api("/api/source/tv/episodes", {
      method: "POST",
      body: { tmdb_id: tid, season: sn, force_refresh: forceRefresh },
    });
    const key = String(tid);
    if (!tvCatalogById[key]) {
      tvCatalogById[key] = { seasons: [], episodesBySeason: {}, name: "" };
    }
    const episodes = data.episodes || [];
    tvCatalogById[key].episodesBySeason[String(sn)] = episodes;

    if (selectAll && episodes.length) {
      setSelectedEpisodes(
        tid,
        sn,
        episodes.map((ep) => Number(ep.episode_number))
      );
    }

    base.season = sn;
    refreshEpisodeBatchCell(idx, sn, episodes);
    log(`TV ${tid} S${String(sn).padStart(2, "0")} 分集已就绪`, {
      count: episodes.length,
      selected: getSelectedEpisodes(tid, sn).length,
      source: data.source,
    });
  }

  /**
   * 收集搜索结果中勾选的 selections。
   * TV：按已勾选分集展开为多条（可批量）；未选集则跳过并记日志。
   * @returns {Array<object>}
   */
  function collectExportSelections() {
    const checks = document.querySelectorAll("#exportHitTable .export-hit-check:checked");
    const out = [];
    /** @type {string[]} */
    const skipped = [];
    checks.forEach((el) => {
      const idx = Number(el.dataset.idx);
      const base = exportHits[idx];
      if (!base) return;
      if (base.media_type === "tv") {
        const sInput = document.querySelector(`.export-season[data-idx="${idx}"]`);
        const season = sInput ? Number(sInput.value || 1) : 1;
        const eps = getSelectedEpisodes(base.tmdb_id, season);
        if (!eps.length) {
          skipped.push(String(base.title || base.tmdb_id) + "（未选分集）");
          return;
        }
        eps.forEach((episode) => {
          out.push({
            tmdb_id: base.tmdb_id,
            media_type: "tv",
            title: base.title,
            popularity: base.popularity,
            season: season,
            episode: episode,
          });
        });
        return;
      }
      out.push({
        tmdb_id: base.tmdb_id,
        media_type: base.media_type,
        title: base.title,
        popularity: base.popularity,
      });
    });
    if (skipped.length) {
      log("以下 TV 行已勾选但未选集，已跳过", { skipped });
    }
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

    document.getElementById("btnLogout").addEventListener("click", async () => {
      try {
        await api("/api/auth/logout", { method: "POST", body: {} });
      } catch (_) {
        /* 即使失败也跳转登录页 */
      }
      window.location.replace("/login.html");
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

    // TV 季集：拉取 / 全选本季 / 清空（委托到表格）
    document.getElementById("exportHitTable").addEventListener("click", (ev) => {
      const fetchBtn = ev.target.closest(".btn-fetch-tv");
      if (fetchBtn) {
        const idx = Number(fetchBtn.dataset.idx);
        withBusy(`拉取 TV 季集 (tmdb=${fetchBtn.dataset.tmdb})`, async () => {
          showProgress("拉取 TV 季/集", {
            percent: null,
            message: "crawler_tmdb → MySQL tmdb_tv_* …",
          });
          await fetchTvSeasonsForRow(idx, { forceRefresh: false });
        }).catch((e) => log(String(e)));
        return;
      }

      const allBtn = ev.target.closest(".btn-ep-all");
      if (allBtn) {
        const idx = Number(allBtn.dataset.idx);
        const tid = allBtn.dataset.tmdb;
        const season = Number(allBtn.dataset.season || 1);
        const cat = tvCatalogById[String(tid)];
        const eps =
          cat && cat.episodesBySeason
            ? cat.episodesBySeason[String(season)] || []
            : [];
        if (!eps.length) {
          withBusy("先拉取分集再全选", async () => {
            await fetchTvEpisodesForRow(idx, season, {
              forceRefresh: false,
              selectAll: true,
            });
            const rowCheck = document.querySelector(
              `.export-hit-check[data-idx="${idx}"]`
            );
            if (rowCheck) rowCheck.checked = true;
          }).catch((e) => log(String(e)));
          return;
        }
        setSelectedEpisodes(
          tid,
          season,
          eps.map((ep) => Number(ep.episode_number))
        );
        refreshEpisodeBatchCell(idx, season, eps);
        const rowCheck = document.querySelector(`.export-hit-check[data-idx="${idx}"]`);
        if (rowCheck) rowCheck.checked = true;
        log(`已全选 S${String(season).padStart(2, "0")} 共 ${eps.length} 集`);
        return;
      }

      const noneBtn = ev.target.closest(".btn-ep-none");
      if (noneBtn) {
        const idx = Number(noneBtn.dataset.idx);
        const tid = noneBtn.dataset.tmdb;
        const season = Number(noneBtn.dataset.season || 1);
        setSelectedEpisodes(tid, season, []);
        const cat = tvCatalogById[String(tid)];
        const eps =
          cat && cat.episodesBySeason
            ? cat.episodesBySeason[String(season)] || []
            : [];
        refreshEpisodeBatchCell(idx, season, eps);
        return;
      }
    });

    document.getElementById("exportHitTable").addEventListener("change", (ev) => {
      const t = ev.target;
      if (!(t instanceof HTMLElement)) return;

      if (t instanceof HTMLSelectElement && t.classList.contains("export-season")) {
        const idx = Number(t.dataset.idx);
        const season = Number(t.value || 1);
        withBusy(`加载 S${String(season).padStart(2, "0")} 分集`, async () => {
          await fetchTvEpisodesForRow(idx, season, { forceRefresh: false });
        }).catch((e) => log(String(e)));
        return;
      }

      if (t instanceof HTMLInputElement && t.classList.contains("export-ep-check")) {
        const idx = Number(t.dataset.idx);
        const tid = t.dataset.tmdb;
        const season = Number(t.dataset.season || 1);
        const ep = Number(t.dataset.ep);
        let selected = getSelectedEpisodes(tid, season);
        if (t.checked) {
          if (!selected.includes(ep)) selected.push(ep);
        } else {
          selected = selected.filter((n) => n !== ep);
        }
        setSelectedEpisodes(tid, season, selected);
        updateEpisodeSelectedCount(idx, tid, season);
        syncExportHitPageId(idx);
        // 选了分集则自动勾选该行，便于一键并入工作区
        if (selected.length > 0) {
          const rowCheck = document.querySelector(`.export-hit-check[data-idx="${idx}"]`);
          if (rowCheck) rowCheck.checked = true;
        }
      }
    });

    async function addExportSelections(mode) {
      const selections = collectExportSelections();
      if (!selections.length) {
        log("请先勾选条目，并对 TV 勾选至少一个分集（或点「全选本季」）");
        return;
      }
      await withBusy(`并入工作区（${mode}，${selections.length} 条）`, async () => {
        const data = await api("/api/source/export/add", {
          method: "POST",
          body: { selections, mode },
        });
        log("已加入工作区", { added: data.added, mode: data.mode, slots: selections.length });
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

    // ── ⑤ 配置 ──────────────────────────────────────────
    document.getElementById("btnConfigLoad").addEventListener("click", () => {
      withBusy("从磁盘加载配置", () => loadConfig(), { indeterminate: true }).catch((e) =>
        log(String(e))
      );
    });

    document.getElementById("btnConfigInit").addEventListener("click", async () => {
      try {
        await withBusy("从模板初始化缺失配置文件", async () => {
          const data = await api("/api/config/init", {
            method: "POST",
            body: { which: "both" },
          });
          if (data.config) applyConfigBundle(data.config);
          log("初始化完成", { env: data.env, accounts: data.accounts });
        });
      } catch (e) {
        log(String(e));
      }
    });

    document.getElementById("btnConfigReload").addEventListener("click", async () => {
      try {
        await withBusy("加载配置到当前进程", async () => {
          const data = await api("/api/config/reload", { method: "POST", body: {} });
          if (data.config) applyConfigBundle(data.config);
          log("已热加载到进程", data.runtime);
        });
      } catch (e) {
        log(String(e));
      }
    });

    document.getElementById("btnConfigSaveEnv").addEventListener("click", async () => {
      try {
        await withBusy("保存 .env 并加载到进程", async () => {
          const values = collectEnvFormValues();
          const data = await api("/api/config/env", {
            method: "POST",
            body: { values: values, reload: true },
          });
          if (data.config) applyConfigBundle(data.config);
          log("已保存 .env", {
            updated_keys: data.updated_keys,
            runtime: data.runtime,
          });
        });
      } catch (e) {
        log(String(e));
      }
    });

    document.getElementById("btnConfigSaveEnvRaw").addEventListener("click", async () => {
      try {
        await withBusy("保存 .env 全文并加载", async () => {
          const raw = document.getElementById("configEnvRaw").value;
          const data = await api("/api/config/env", {
            method: "POST",
            body: { raw: raw, reload: true },
          });
          if (data.config) applyConfigBundle(data.config);
          log("已保存 .env 全文", { key_count: data.key_count, runtime: data.runtime });
        });
      } catch (e) {
        log(String(e));
      }
    });

    document.getElementById("btnConfigSaveAccounts").addEventListener("click", async () => {
      try {
        await withBusy("保存 accounts.local.json 并加载", async () => {
          const text = document.getElementById("configAccountsRaw").value;
          let parsed;
          try {
            parsed = JSON.parse(text);
          } catch (err) {
            throw new Error("accounts JSON 解析失败: " + err.message);
          }
          const data = await api("/api/config/accounts", {
            method: "POST",
            body: { data: parsed, reload: true },
          });
          if (data.config) applyConfigBundle(data.config);
          log("已保存 accounts.local.json", { path: data.path, runtime: data.runtime });
        });
      } catch (e) {
        log(String(e));
      }
    });
  }

  bind();
  loadFiles().catch((e) => log(String(e)));
  refresh().catch((e) => log(String(e)));
  // 顶栏配置徽章：静默拉取一次
  loadConfig().catch(() => {
    /* 缺 MySQL 时仍可能读 .env；忽略首屏失败 */
  });
})();
