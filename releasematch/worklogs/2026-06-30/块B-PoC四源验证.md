# 块 B — PoC 四源验证

> **日期：** 2026-06-30  
> **结论：** **T0 通过（3/4 必达源 OK）**；Nyaa 延后至 T1

---

## 最终结果

| # | 源 | 结果 | 说明 |
|---|-----|------|------|
| 1 | Jackett | ✅ HTTP 200, ~487 bytes | 服务正常；indexer 仍偏少，建议加 1337x |
| 2 | EZTV | ✅ HTTP 200 | 正常 |
| 3 | YTS | ✅ HTTP 200 | 镜像 `yts.lt`（`yts.mx` DNS 不可用） |
| 4 | Nyaa | ⚠️ 跳过 T0 | 直连超时；Jackett `nyaasi` 返回 400（未添加 indexer） |

**Summary: 3/4 passed** — 满足 T0 块 B 验收（Nyaa 属 T1-5，非 T0 阻塞项）。

---

## 可选后续（不阻塞块 D）

1. Jackett Dashboard → **Add indexer** → **1337x** / **EZTV**（增大 Torznab 结果）
2. 若需 Nyaa：添加 **Nyaa.si** indexer，或开 VPN 后重跑 PoC `[4/4]`
3. 默认 YTS 已改为 `https://yts.lt`（`workflow/config.py` + `accounts.local.json`）

---

## 验收勾选

```
【块 B - T0 必达】
[x] D-A3 / B1  Jackett OK（非 SKIPPED）
[x] D-A4 / B2  EZTV OK
[x] D-A5 / B3  YTS OK（yts.lt）
[~] D-A6 / B4  Nyaa — T1 再做
```

**下一步：块 D — `jackett_client.py`**
