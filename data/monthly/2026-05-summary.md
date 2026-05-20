# Nicole Intelligence Monthly Update · 2026-05

- 更新批次：2026-05
- 新增报告数量：0
- 数据源失败数量：0
- 最高 Heat：e2 82.8
- 最大下滑：m1 -16.3

## 赛道分数变化
- e2: Heat 82.8 / Delta +1.8
- p2: Heat 76.5 / Delta +1.3
- l2: Heat 76.5 / Delta -2.0
- l1: Heat 76.4 / Delta -5.8
- e1: Heat 74.6 / Delta +0.0
- g1: Heat 74.6 / Delta +4.2
- e3: Heat 73.1 / Delta +30.3
- e4: Heat 73.0 / Delta +2.9
- p1: Heat 72.2 / Delta +5.6
- p5: Heat 72.0 / Delta -1.6
- p3: Heat 71.8 / Delta +15.3
- f3: Heat 71.8 / Delta -6.2
- m2: Heat 71.5 / Delta -10.6
- f4: Heat 67.0 / Delta +7.7
- l3: Heat 66.0 / Delta +24.4
- f1: Heat 62.2 / Delta -10.6
- m3: Heat 62.2 / Delta -0.7
- m1: Heat 61.9 / Delta -16.3
- p4: Heat 52.2 / Delta -5.3
- f2: Heat 52.2 / Delta -15.6

## 数据源失败
- all: online refresh · CLAUDE_API_KEY missing; BRAVE_API_KEY missing
- system: network · outbound network unavailable
- external: public reports + RSS + scoring · Current environment blocks outbound proxy/network and lacks BRAVE/Claude API keys

## 人工覆盖项
- review_notes

## 执行备注
- offline mode: skipped report download, RSS refresh, RAG rebuild, and news scoring
- homepage injected from history snapshot 2026-05

## 需要重点审核
- 请重点核查自动抓取失败的数据源，以及 Heat 变化幅度最大的赛道。
- 本次运行未配置 CLAUDE_API_KEY 与 BRAVE_API_KEY，未执行在线抓取。
- 首页 index.html 与 data.js 已按 data/history.json 的 202605 数据做离线一致性更新.
- 当前运行环境无法访问外网，已跳过公开报告下载。
- 当前运行环境无法访问外网，已跳过 RSS 刷新。
- 当前运行环境无法访问外网，已跳过新闻页刷新。
- RAG 重建失败，向量库未更新。
