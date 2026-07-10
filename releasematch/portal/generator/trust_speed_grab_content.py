#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测速可信度与 RM Grab 指数说明页正文（Trust 页双语 HTML）。

@module portal.generator.trust_speed_grab_content
@description
  供 ``trust_content.TRUST_PAGES`` 中 ``speed-and-grab`` 条目引用；
  表格内容与 ``grab_index.py``、``compute_test_freshness()``、``reachability.py`` 算法一致。
"""

from __future__ import annotations

# 英文正文 HTML
SPEED_GRAB_BODY_EN: str = """
<p>ReleaseMatch runs <strong>libtorrent segment download tests</strong> on the Hero Recommended torrent only. This page documents how <strong>RM Grab Index</strong> and <strong>speed credibility</strong> labels are derived—so you can interpret scores on episode and movie pages.</p>

<h2 id="grab-index">RM Grab Index</h2>
<p>A composite score from <strong>0 to 100</strong> for the Recommended release on that page. Four dimensions are scored 0–100 each, then combined with fixed weights:</p>
<table class="rm-spec-table">
<thead><tr><th>Dimension</th><th>Weight</th><th>Input</th><th>Scoring logic</th><th>IG ref</th></tr></thead>
<tbody>
<tr><td>Speed</td><td>35%</td><td>Phase 2 avg &amp; max KiB/s</td><td>Log curve on avg speed (≈15 at 1 KB/s → ≈100 at 5 MB/s); +5 if peak ≥ 2× avg</td><td>S-06</td></tr>
<tr><td>Reachability</td><td>25%</td><td>Phase 1 <code>peers_total</code>, test status</td><td>≥10 → High (100) · 3–9 → Medium (65) · 1–2 → Low (35) · 0 / timeout / error → Unreachable (0)</td><td>A-01</td></tr>
<tr><td>Connect rate</td><td>20%</td><td><code>peers_reachable</code> / <code>peers_total</code></td><td>Round(connected ÷ observed × 100), capped at 100</td><td>A-02</td></tr>
<tr><td>Freshness</td><td>20%</td><td>Hours since last test + validity level</td><td>≤24h Fresh · ≤48h Valid · ≤72h Stale · &gt;72h Older — see <a href="#speed-credibility">Speed credibility</a></td><td>A-03</td></tr>
</tbody>
</table>
<p><strong>Formula:</strong> Grab = round(speed×0.35 + reach×0.25 + connect×0.20 + freshness×0.20), clamped 0–100.</p>

<h3>Overall tiers</h3>
<table class="rm-spec-table">
<thead><tr><th>Score</th><th>Tier label</th><th>Meaning</th></tr></thead>
<tbody>
<tr><td>≥ 90</td><td>Excellent</td><td>Strong measured download experience</td></tr>
<tr><td>75 – 89</td><td>Great</td><td>Reliable for most users</td></tr>
<tr><td>60 – 74</td><td>Good</td><td>Usable with some caveats</td></tr>
<tr><td>40 – 59</td><td>Fair</td><td>Mixed signals—check breakdown</td></tr>
<tr><td>20 – 39</td><td>Weak</td><td>Limited swarm or stale data</td></tr>
<tr><td>&lt; 20</td><td>Poor</td><td>Not recommended for grab decisions</td></tr>
</tbody>
</table>

<h2 id="speed-credibility">Speed test credibility (A-03)</h2>
<p>Every test timestamp is classified by age. This drives the freshness badge, validity label, and the freshness sub-score inside Grab Index. <strong>Older than 72h is labeled “Older”, not “Expired”</strong> — we do not assert the swarm is dead.</p>
<table class="rm-spec-table">
<thead><tr><th>Status</th><th>Age window</th><th>Validity</th><th>Freshness sub-score</th><th>Page guidance</th></tr></thead>
<tbody>
<tr><td>Fresh</td><td>≤ 24 h</td><td>High</td><td>100</td><td>Safe to cite as live measured evidence (S-07)</td></tr>
<tr><td>Valid</td><td>24 – 48 h</td><td>Medium</td><td>78 (−5 if validity Medium)</td><td>Still useful; re-test when convenient</td></tr>
<tr><td>Stale</td><td>48 – 72 h</td><td>Low</td><td>42 (−15 if validity Low)</td><td>Peers/speed may have changed</td></tr>
<tr><td>Older</td><td>&gt; 72 h</td><td>Uncertain</td><td>12</td><td>Swarm may have shifted — re-test before relying (not marked expired)</td></tr>
<tr><td>Unknown</td><td>No timestamp</td><td>Unknown</td><td>0</td><td>No libtorrent test on record</td></tr>
</tbody>
</table>

<h2 id="speed-metrics">Speed test metrics</h2>
<p>Shown in the collapsible <strong>Speed evidence</strong> panel and six metric cards:</p>
<table class="rm-spec-table">
<thead><tr><th>Metric</th><th>Definition</th><th>How it is measured</th></tr></thead>
<tbody>
<tr><td>Tested at</td><td>UTC time of last successful slot test</td><td>Written to <code>slot_speed_summary.tested_at</code></td></tr>
<tr><td>Avg speed</td><td>Mean KiB/s over 256 KB segment samples</td><td>Phase 2 libtorrent download (strategy A2)</td></tr>
<tr><td>Max speed</td><td>Peak KiB/s in the same run</td><td>Phase 2; spread vs avg shown when available</td></tr>
<tr><td>Peers observed</td><td>Distinct peers seen in tracker/DHT</td><td>Phase 1 peer sampling</td></tr>
<tr><td>Peers connected</td><td>Peers that completed handshake</td><td>Phase 1; pair shown as connected / observed</td></tr>
<tr><td>Connect rate</td><td>connected ÷ observed</td><td>Percentage; feeds Grab connect dimension</td></tr>
<tr><td>Latency</td><td>Round-trip style delay summary</td><td>Derived from peer handshake timing when available</td></tr>
</tbody>
</table>

<h2 id="reachability">Peer reachability (A-01)</h2>
<p>Reachability is <strong>not</strong> a separate crawl—it is derived from Phase 1 peer counts and test status:</p>
<table class="rm-spec-table">
<thead><tr><th>peers_total</th><th>Reachability</th><th>Sub-score</th><th>Typical interpretation</th></tr></thead>
<tbody>
<tr><td>≥ 10</td><td>High</td><td>100</td><td>Healthy swarm for partial download test</td></tr>
<tr><td>3 – 9</td><td>Medium</td><td>65</td><td>Enough peers to attempt measurement</td></tr>
<tr><td>1 – 2</td><td>Low</td><td>35</td><td>Fragile swarm—speed may be unstable</td></tr>
<tr><td>0 or timeout/error</td><td>Unreachable</td><td>0</td><td>No usable peers during test</td></tr>
</tbody>
</table>

<p>Method note on each page states the libtorrent segment strategy (e.g. 256 KB, A2). Indexer seed counts (B-02) are shown separately and do not replace measured peers (A-02).</p>
<p><a href="/trust/how-matching-works/">How release matching works →</a></p>
""".strip()

# 中文正文 HTML
SPEED_GRAB_BODY_ZH: str = """
<p>ReleaseMatch 仅对 Hero <strong>Recommended</strong> 条目的 torrent 执行 <strong>libtorrent 片段下载测速</strong>。本页说明 <strong>RM Grab 指数</strong>与<strong>测速可信度</strong>标签如何计算，便于理解剧集/电影页上的分数。</p>

<h2 id="grab-index">RM Grab 指数</h2>
<p>针对该页 Recommended release 的 <strong>0–100 综合分</strong>。四个维度各自 0–100 分，再按固定权重合成：</p>
<table class="rm-spec-table">
<thead><tr><th>维度</th><th>权重</th><th>输入</th><th>计分逻辑</th><th>IG</th></tr></thead>
<tbody>
<tr><td>速度</td><td>35%</td><td>Phase 2 均速 / 峰值 KiB/s</td><td>均速对数曲线（约 1 KB/s→15 分至 5 MB/s→100 分）；峰值 ≥ 2× 均速时 +5</td><td>S-06</td></tr>
<tr><td>可达性</td><td>25%</td><td>Phase 1 <code>peers_total</code>、测速状态</td><td>≥10→高(100) · 3–9→中(65) · 1–2→低(35) · 0/超时/错误→不可达(0)</td><td>A-01</td></tr>
<tr><td>连接率</td><td>20%</td><td><code>peers_reachable</code> / <code>peers_total</code></td><td>round(已连÷观测×100)，上限 100</td><td>A-02</td></tr>
<tr><td>时效</td><td>20%</td><td>距上次测速小时数 + 效力等级</td><td>≤24h 新鲜 · ≤48h 有效 · ≤72h 陈旧 · &gt;72h 较久 — 见 <a href="#speed-credibility">测速可信度</a></td><td>A-03</td></tr>
</tbody>
</table>
<p><strong>公式：</strong>Grab = round(速度×0.35 + 可达×0.25 + 连接×0.20 + 时效×0.20)，限制在 0–100。</p>

<h3>综合等级</h3>
<table class="rm-spec-table">
<thead><tr><th>分数</th><th>等级</th><th>含义</th></tr></thead>
<tbody>
<tr><td>≥ 90</td><td>极佳</td><td>实测下载体验优秀</td></tr>
<tr><td>75 – 89</td><td>优秀</td><td>多数场景可靠</td></tr>
<tr><td>60 – 74</td><td>良好</td><td>可用，注意分项</td></tr>
<tr><td>40 – 59</td><td>一般</td><td>信号混杂，建议看 breakdown</td></tr>
<tr><td>20 – 39</td><td>偏弱</td><td>swarm 弱或数据偏旧</td></tr>
<tr><td>&lt; 20</td><td>较差</td><td>不宜作为抓取决策依据</td></tr>
</tbody>
</table>

<h2 id="speed-credibility">测速可信度（A-03）</h2>
<p>每次测速时间戳按距现在的间隔分级，驱动页面「数据时效」徽章、可信度文案，以及 Grab 中的时效子分。<strong>超过 72h 标记为「较久」，而非「过期」</strong>——我们不断言 swarm 已失效。</p>
<table class="rm-spec-table">
<thead><tr><th>状态</th><th>时间窗口</th><th>可信度</th><th>时效子分</th><th>页面指引</th></tr></thead>
<tbody>
<tr><td>新鲜</td><td>≤ 24 h</td><td>高</td><td>100</td><td>可作为当前实测背书（S-07）</td></tr>
<tr><td>有效</td><td>24 – 48 h</td><td>中</td><td>78（效力「中」再 −5）</td><td>仍可参考；方便时安排复测</td></tr>
<tr><td>陈旧</td><td>48 – 72 h</td><td>低</td><td>42（效力「低」再 −15）</td><td>peer/速度可能已变化</td></tr>
<tr><td>较久</td><td>&gt; 72 h</td><td>待确认</td><td>12</td><td>swarm 可能已有变化，建议复测后再作主要依据（非断言已失效）</td></tr>
<tr><td>未知</td><td>无时间戳</td><td>未知</td><td>0</td><td>尚无 libtorrent 实测记录</td></tr>
</tbody>
</table>

<h2 id="speed-metrics">测速指标</h2>
<p>展示于折叠区 <strong>测速证据</strong> 与六项指标卡：</p>
<table class="rm-spec-table">
<thead><tr><th>指标</th><th>定义</th><th>测量方式</th></tr></thead>
<tbody>
<tr><td>测速时间</td><td>最近一次成功槽位测试的 UTC 时间</td><td>写入 <code>slot_speed_summary.tested_at</code></td></tr>
<tr><td>均速</td><td>256 KB 片段采样平均 KiB/s</td><td>Phase 2 libtorrent 下载（策略 A2）</td></tr>
<tr><td>峰值</td><td>同次运行最高 KiB/s</td><td>Phase 2；可与均速对比展示</td></tr>
<tr><td>观测 peers</td><td>tracker/DHT 见到的 peer 数</td><td>Phase 1 采样</td></tr>
<tr><td>已连 peers</td><td>完成握手的 peer 数</td><td>Phase 1；展示为 已连/观测</td></tr>
<tr><td>连接率</td><td>已连 ÷ 观测</td><td>百分比；计入 Grab 连接维度</td></tr>
<tr><td>延迟</td><td>往返时延摘要</td><td>握手计时可得时展示</td></tr>
</tbody>
</table>

<h2 id="reachability">Peer 可达性（A-01）</h2>
<p>可达性<strong>非</strong>独立爬取，由 Phase 1 peer 数与测速状态派生：</p>
<table class="rm-spec-table">
<thead><tr><th>peers_total</th><th>可达性</th><th>子分</th><th>典型含义</th></tr></thead>
<tbody>
<tr><td>≥ 10</td><td>高</td><td>100</td><td>swarm 健康，可做片段测速</td></tr>
<tr><td>3 – 9</td><td>中</td><td>65</td><td>可尝试测量</td></tr>
<tr><td>1 – 2</td><td>低</td><td>35</td><td>swarm 脆弱，速度可能不稳</td></tr>
<tr><td>0 或 超时/错误</td><td>不可达</td><td>0</td><td>测试时无可用 peer</td></tr>
</tbody>
</table>

<p>各页 method note 注明 libtorrent 片段策略（如 256 KB、A2）。索引站 seeders（B-02）单独展示，不替代实测 peers（A-02）。</p>
<p><a href="/trust/how-matching-works/">了解对版如何工作 →</a></p>
""".strip()
