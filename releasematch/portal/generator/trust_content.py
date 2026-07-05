#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trust 五页双语正文（生成器用）。

@module portal.generator.trust_content
@description
  供 ``render_trust`` 渲染 ``/trust/*`` 静态页；``RM_SITE_I18N_ENABLED=true`` 时
  正文写入 ``i18n_dynamic.trust_body`` 供前端切换。
"""

from __future__ import annotations

from typing import Any, Dict, List

# Trust 页定义：slug、SEO、正文 HTML（en / zh）
TRUST_PAGES: List[Dict[str, Any]] = [
    {
        "slug": "about",
        "title_key": "trust.about.title",
        "meta_key": "trust.about.meta",
        "canonical": "/trust/about/",
        "body": {
            "en": """
<p>ReleaseMatch is an independent <strong>Release navigation</strong> site. We help users choose among many BitTorrent releases for a given TV episode or film—with evidence, not link spam.</p>
<h2>What we do</h2>
<ul>
  <li>Aggregate public indexer <strong>metadata</strong> (infohash, title, seeders, etc.)</li>
  <li>Publish a <strong>Recommended Release</strong> per slot with matching rationale</li>
  <li>Cross-check sources, group reputation tiers, and speed-test summaries</li>
</ul>
<h2>What we do not do</h2>
<ul>
  <li>Host or distribute video files</li>
  <li>Provide download or streaming services</li>
  <li>Guarantee availability or legality of any magnet—you must comply with local law</li>
</ul>
<h2>Relationship to subtitle sites</h2>
<p>ReleaseMatch uses a separate domain and infrastructure from our subtitle property. The subtitle site may link to us <strong>once per episode context</strong>; we do not use sitewide cross-linking for SEO.</p>
<p><a href="/trust/how-matching-works/">How release matching works →</a></p>
<p><a href="/trust/contact/">Contact →</a></p>
""".strip(),
            "zh": """
<p>ReleaseMatch 是独立的 <strong>Release 导航站</strong>，帮助用户在某一集/电影的众多 BitTorrent release 中做出有依据的选择，而不是链接堆砌。</p>
<h2>我们做什么</h2>
<ul>
  <li>聚合公开索引器<strong>元数据</strong>（infohash、标题、seeders 等）</li>
  <li>为每个槽位发布 <strong>Recommended Release</strong> 及可索引的推荐理由</li>
  <li>多源交叉验证、压制组信誉档位与测速摘要</li>
</ul>
<h2>我们不做什么</h2>
<ul>
  <li>不托管或分发视频文件</li>
  <li>不提供下载或流媒体服务</li>
  <li>不保证任何 magnet 的可用性或合法性——请遵守当地法律</li>
</ul>
<h2>与字幕站的关系</h2>
<p>ReleaseMatch 与字幕站在域名与基础设施上分离。字幕站可在<strong>单集语境</strong>下单链至本站；我们不采用全站互链做 SEO。</p>
<p><a href="/trust/how-matching-works/">了解对版如何工作 →</a></p>
<p><a href="/trust/contact/">联系我们 →</a></p>
""".strip(),
        },
    },
    {
        "slug": "how-matching-works",
        "title_key": "trust.how.title",
        "meta_key": "trust.how.meta",
        "canonical": "/trust/how-matching-works/",
        "body": {
            "en": """
<p>“Release matching” means verifying that a release actually corresponds to the target episode or film—audio sync, quality tier, cut version, etc. Most magnet sites only list links; we add verifiable incremental signals.</p>
<h2>Scoring dimensions</h2>
<ol>
  <li><strong>Group reputation</strong> — tiers L0~L4 based on historical encode quality</li>
  <li><strong>Cross-source verification</strong> — whether the same infohash appears consistently across sources</li>
  <li><strong>Swarm health &amp; speed tests</strong> — seeders plus connectivity / partial download summaries</li>
  <li><strong>Encode metadata</strong> — source, codec, and audio inferred from release names</li>
</ol>
<h2>Recommended Release</h2>
<p>For each slot (e.g. Breaking Bad S04E06), the engine scores all candidates and marks the top pick as recommended, with an embedded <code>recommend_reason</code> on the page.</p>
<h2>Thin-page gate</h2>
<ul>
  <li>0 magnets: no page</li>
  <li>1 magnet: noindex</li>
  <li>≥2 magnets with IG modules: eligible for index</li>
</ul>
<p><a href="/breaking-bad/s4e6/">See an example page →</a></p>
""".strip(),
            "zh": """
<p>「对版匹配」指验证 release 是否真正对应目标集/电影——音画同步、画质档位、剪辑版本等。多数 magnet 站只列链接；我们补充可验证的增量信号。</p>
<h2>评分维度</h2>
<ol>
  <li><strong>压制组信誉</strong> — 基于历史编码质量的 L0~L4 档位</li>
  <li><strong>多源交叉验证</strong> — 同一 infohash 是否在多源一致出现</li>
  <li><strong>Swarm 健康与测速</strong> — seeders 与连接性/片段下载摘要</li>
  <li><strong>编码元数据</strong> — 从 release 名推断 source、codec、音轨</li>
</ol>
<h2>Recommended Release</h2>
<p>每个槽位（如 Breaking Bad S04E06），引擎对全部候选打分并标记最优为推荐，页面嵌入可索引的 <code>recommend_reason</code>。</p>
<h2>薄页门禁</h2>
<ul>
  <li>0 条 magnet：不生成页面</li>
  <li>1 条 magnet：noindex</li>
  <li>≥2 条 magnet 且含 IG 模块：可 index</li>
</ul>
<p><a href="/breaking-bad/s4e6/">查看示例页 →</a></p>
""".strip(),
        },
    },
    {
        "slug": "contact",
        "title_key": "trust.contact.title",
        "meta_key": "trust.contact.meta",
        "canonical": "/trust/contact/",
        "body": {
            "en": """
<p>ReleaseMatch is a metadata-only Release navigation site. We do not host video files or operate a download service.</p>
<h2>Functional email</h2>
<p>For general contact, copyright (DMCA) notices, and privacy-related requests, use our operational mailbox:</p>
<p><a href="mailto:ReleaseMatch@hotmail.com">ReleaseMatch@hotmail.com</a></p>
<h2>Response time</h2>
<p>We aim to acknowledge valid DMCA notices within a reasonable timeframe and return <strong>410 Gone</strong> for removed URLs. General inquiries are handled on a best-effort basis.</p>
<h2>Related policies</h2>
<ul>
  <li><a href="/trust/dmca/">DMCA / Copyright</a></li>
  <li><a href="/trust/privacy/">Privacy Policy</a></li>
  <li><a href="/trust/about/">About ReleaseMatch</a></li>
</ul>
""".strip(),
            "zh": """
<p>ReleaseMatch 是仅索引元数据的 Release 导航站。我们不托管视频，也不提供下载服务。</p>
<h2>功能邮箱</h2>
<p>一般咨询、版权（DMCA）通知与隐私相关请求，请使用运营邮箱：</p>
<p><a href="mailto:ReleaseMatch@hotmail.com">ReleaseMatch@hotmail.com</a></p>
<h2>响应时间</h2>
<p>我们会在合理时间内确认有效的 DMCA 通知，并对已移除 URL 返回 <strong>410 Gone</strong>。一般咨询尽力回复。</p>
<h2>相关政策</h2>
<ul>
  <li><a href="/trust/dmca/">DMCA / 版权</a></li>
  <li><a href="/trust/privacy/">隐私政策</a></li>
  <li><a href="/trust/about/">关于 ReleaseMatch</a></li>
</ul>
""".strip(),
        },
    },
    {
        "slug": "privacy",
        "title_key": "trust.privacy.title",
        "meta_key": "trust.privacy.meta",
        "canonical": "/trust/privacy/",
        "body": {
            "en": """
<p><em>Draft for operational use—legal review recommended before production launch.</em></p>
<h2>Information we collect</h2>
<ul>
  <li>Standard web server logs (IP address, User-Agent, request path)</li>
  <li>If you opt in to a browser speed-test extension: anonymous speed results only</li>
</ul>
<h2>What we do not collect</h2>
<ul>
  <li>We do not track your downloads via magnet links</li>
  <li>We do not store video content</li>
</ul>
<h2>Third parties</h2>
<p>This site is hosted on Cloudflare. Analytics, if enabled, use a separate property from our subtitle site.</p>
<h2>Contact</h2>
<p>Privacy questions: <a href="mailto:ReleaseMatch@hotmail.com">ReleaseMatch@hotmail.com</a></p>
""".strip(),
            "zh": """
<p><em>运营草案——正式上线前建议法律审阅。</em></p>
<h2>我们收集的信息</h2>
<ul>
  <li>标准 Web 服务器日志（IP、User-Agent、请求路径）</li>
  <li>若您启用浏览器测速扩展：仅匿名测速结果</li>
</ul>
<h2>我们不收集</h2>
<ul>
  <li>不通过 magnet 链接追踪您的下载行为</li>
  <li>不存储视频内容</li>
</ul>
<h2>第三方</h2>
<p>本站托管于 Cloudflare。若启用分析，与字幕站使用独立属性。</p>
<h2>联系</h2>
<p>隐私问题：<a href="mailto:ReleaseMatch@hotmail.com">ReleaseMatch@hotmail.com</a></p>
""".strip(),
        },
    },
    {
        "slug": "dmca",
        "title_key": "trust.dmca.title",
        "meta_key": "trust.dmca.meta",
        "canonical": "/trust/dmca/",
        "body": {
            "en": """
<p>ReleaseMatch indexes public torrent metadata only. We do not host media files. If you believe a page on this site improperly references your rights, please contact us using the details below.</p>
<h2>Notice requirements</h2>
<ol>
  <li>Signature of the rights holder or authorized agent</li>
  <li>Specific URL(s) on ReleaseMatch that you claim are infringing</li>
  <li>Identification of the copyrighted work</li>
  <li>Your contact email and mailing address</li>
</ol>
<h2>Our process</h2>
<p>After we receive a valid notice, we will return <strong>410 Gone</strong> for the affected URL(s) and remove them from our sitemap within a reasonable time.</p>
<h2>Contact</h2>
<p>Send DMCA notices to: <a href="mailto:ReleaseMatch@hotmail.com">ReleaseMatch@hotmail.com</a></p>
<p>General contact: <a href="/trust/contact/">Contact page</a></p>
""".strip(),
            "zh": """
<p>ReleaseMatch 仅索引公开 torrent 元数据，不托管媒体文件。若您认为本站某页不当涉及您的权利，请按下列方式联系我们。</p>
<h2>通知要求</h2>
<ol>
  <li>权利人或其授权代理人签名</li>
  <li>您主张侵权的 ReleaseMatch 具体 URL</li>
  <li>被侵权作品标识</li>
  <li>您的联系邮箱与邮寄地址</li>
</ol>
<h2>处理流程</h2>
<p>收到有效通知后，我们对相关 URL 返回 <strong>410 Gone</strong>，并在合理时间内从 sitemap 移除。</p>
<h2>联系</h2>
<p>DMCA 通知请发至：<a href="mailto:ReleaseMatch@hotmail.com">ReleaseMatch@hotmail.com</a></p>
<p>一般联系：<a href="/trust/contact/">联系页</a></p>
""".strip(),
        },
    },
]
