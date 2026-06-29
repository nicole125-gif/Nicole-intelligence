# ARCHITECTURE — Nicole Intelligence

> 系统结构参照。配套：`HANDOFF.md`（入口/状态/决策）、`ROADMAP.md`（下一步）。
> 最后更新 2026-06-29。

## 0. 一句话

阀门企业 ESG 青岛精锐的情报系统。**正在从「赛道热度中心」（老系统）重构为「事件中心」（新引擎）**——第一类对象从"行业热度"变成"会触发流体采购的 Capex 事件"。两套系统当前并存、物理隔离。

---

## 0.5 标准心智模型：5 层情报栈（2026-06-29 定调）

全系统按 5 层切分，**每层只回答一个问题，层间靠边界纪律分工**。这是产品的标准心智模型，漏斗（§HANDOFF 9）与 Nicole/CI Radar 两层（§HANDOFF 10）都是它的投影。

| 层 | 回答什么 | 现状落点 | 拥有 |
|---|---|---|---|
| **L1 Market Heat 行业热度** | 市场热不热（**不判 ESG 能不能赢**） | `index.html` 热力图 SCORE_MODEL | Nicole |
| **L2 Signal Intelligence 信号层** | 谁/什么行业/什么动作/来源/可信/工况/提前量 → 标准事件 | `engine/` 事件引擎（核心，已成熟） | Nicole（本仓） |
| **L3 ESG Fit 机会适配** | 信号对哪个 ESG 产品/真机会还是 NO_MATCH/国产替代空间 | Nicole 留 `winnability` 粗代理（冷启动），CI Radar 做精 | Codex（精）/ Nicole（粗代理） |
| **L4 Competitor Battle 竞品打法** | 谁在位/打什么/话术/必问/证据缺口 | CI Radar + 产品库（Bürkert/GEMÜ/Fujikin/ESG） | Codex |
| **L5 Sales Feedback 闭环** | 真项目?报价?赢输给谁?→ 回流修 L1权重/L2关键词/L3规则/L4威胁 | 处置闭环（采集已上线，消费未接） | Nicole 采集 / 两边消费 |

**两条关键边界纪律（2026-06-29 决策）**：
1. **L1 = 纯市场温度，W（ESG赢面）不进 Heat**。Heat = `Capex×.40 + Demand×.27 + Policy×.20 + Price×.13`（市场因子归一）。W 作为 **L3 的渲染层粗代理**单列展示、不烤进 Heat；`heatmap delta = W − Heat = 「ESG赢面 vs 市场热度」缺口`。（此前 PR#20/#22 曾把 W×25 烤进 Heat，本次按 5 层模型拆出。）
2. **L3 ESG Fit 归 Codex 做精；Nicole 的 `winnability` 只当冷启动粗代理**（事件排序够用），不在 Nicole 写 ESG 价格/库存/交期/装机/证书/竞品输赢结论（那是 L4/CI Radar）。

> **flywheel**：L5 反馈回流，闭合 L1↔L3↔L4 —— 赢面（L3）靠闭环（L5）攒数据校准，先粗代理冷启动（= §HANDOFF 决策6/15）。

---

## 1. 系统总览（两套并存）

```
┌─────────────────────────────────────────────────────────────┐
│  老系统（赛道中心，legacy，大部分停摆）                        │
│  RSS/制药/宏观/竞品 采集 → data/*.json → update_news.py 打分   │
│  → score_cache.json → inject_scores.py 注入 → 11 个 HTML 页    │
│  → Vercel 部署。6 个 GitHub Actions cron 驱动。                │
├─────────────────────────────────────────────────────────────┤
│  新引擎（事件中心，engine/，本次新建，自包含）                  │
│  cninfo/环评/招标 三源 → build_event 装配 → 排序事件队列        │
│  → data/events/<date>.json（数据契约）→ (未来) 前端队列         │
└─────────────────────────────────────────────────────────────┘
新引擎只读不写老系统；把老制药链当"设计参照"而非代码继承。
```

---

## 2. 新引擎（事件中心）— `engine/` 包

### 2.1 模块职责

| 模块 | 职责 | 来源 |
|---|---|---|
| `schema.py` | 事件契约：`SCHEMA_VERSION="1.0"` + review_flag/signal_type 枚举 + LEAD_MONTHS | 新写 |
| `classify.py` | `classify_lead_time`(→L0/L1/L2) + `classify_driver`(→D/C/P/Pol) | 移植 p4 |
| `valuation.py` | `parse_capex_cny` + `estimate_value`（capex×0.5-1.5%，三态；含量词负向 lookahead 防"万吨"误判） | 移植 p4 |
| `conditions.py` | 加载 `esg_conditions.yml` + `classify_condition`（工况打分，strong+1.5/mid+0.8 + 源加权）+ 阀型映射 | 新写 |
| `buyer_role.py` | `infer_buyer_role`：按工况推断买方角色（设备OEM/EPC/终端），替代别名客户匹配 | 新写 |
| `ranking.py` | `rank_score = 价值档×提前量×工况匹配×赢面`（相乘，任一为零沉底）+ 稳定多键排序 | 新写 |
| `winnability.py` | 赢面 v1：绿地无在位 + 工况级竞品密度 → rank 第四因子 | 新写 |
| `build.py` | `build_event`（装配单条，match_score=0 则丢弃）+ `build_pack`（排序+summary） | 重写（蓝本 p4） |
| `run.py` | 入口：跑三源→build→写 `data/events/<date>.json` + 健康检查（CORE 工况各≥3） | 新写 |
| `sources/base.py` | `safe_get`/`make_id`（requests **惰性导入**，离线模式无需联网） | 移植 |
| `sources/cninfo.py` | 巨潮募投，现行 `GET /new/fulltextSearch/full` API + 建设意图检索词 + 分页 + Capex意图闸 | 重写 |
| `sources/eia.py` | 环评（多行业遍历） | 移植（源死） |
| `sources/tender.py` | 招标（阀门词 OR 工况词双命中，bs4 惰性导入） | 移植（源死） |
| `sources/cde.py` | CDE 优先审评（Playwright 过瑞数 WAF + 截 `getPriorityApprovalList` API），pipeline 前兆，opt-in `--with-cde` | 新写 |
| `config/esg_conditions.yml` | **工况知识库**：5 工况 × {strong/mid 关键词, 阀型, 买方角色, 行业标签} + capex_ratio + source_boost | 新写 |

### 2.2 数据流（单次 run）

```
SEARCH_KEYS（建设意图词："年产"/"扩建项目"/"电池项目"…）
  → cninfo fulltextSearch API（分页）
  → 原始公告 → Capex意图闸（标题须含建设词）+ keyword_pool 粗过滤
  → raw signals[]
  → build_event 逐条：
       classify_condition（定工况；match=0 丢弃）
       owner 抽取（secName/constructionUnit，resolved=false）
       classify_lead_time / estimate_value / infer_buyer_role
       confidence + review_flag + urgency + rank_score
  → build_pack：sort_events + summary（by_condition/by_lead_time/质量计数）
  → data/events/<date>.json
```

### 2.3 事件 schema（产出契约）

`data/events/<date>.json` = `{schema_version, date, status, generated_at, events[], summary{}}`。
单条 `event`：
```
id · headline · owner{id,name,type,raw,resolved} · buyer_role{inferred,basis,confidence}
working_condition[] · industry_tag · signal_type(compliance|expansion|immediate)
driver(Pol|P|C|D) · lead_time{level:L0/L1/L2, months} · valve_type{primary[],basis}
est_value{status:model_estimate|manual_override|unknown, low,high,project_capex…}
value_band{band:大|中|小|未知, basis} · winnability{score:0.15-1.0, basis} · urgency(1-10) · match_score(0-10) · rank_score(float, 排序主键)
action · source{name,type,url,published_at} · confidence(0-100)
review_flag(ok|unresolved|needs_review|stale) · quality{has_capex,has_owner,stale}
```

### 2.4 5 工况 → 阀型 → 买方（`esg_conditions.yml`）

| 工况 id | 行业 | ESG 阀型 | 买方角色 |
|---|---|---|---|
| hygienic 卫生级工艺 | 食品饮料/医药/泡塑/饲料 | **角座阀**+卫生级隔膜阀 | 设备OEM |
| lithium_injection 锂电注液 | 电池/新能源 | 膜塞阀/注液阀/针阀 | 设备OEM |
| rubber_curing 橡塑硫化 | 轮胎/橡塑/印染 | 角座阀+疏水阀 | EPC |
| heavy_process 重过程 | 化工/冶金/电力 | 蝶阀/球阀/隔膜阀 | EPC |
| pharma_ref 制药参照 | 医药/生物制品 | 卫生级隔膜阀+角座阀 | 设备OEM |

---

## 3. 老系统（赛道中心，legacy）

### 3.1 组件
- **采集**：`fetch_rss.py`(7 垂直 RSS)、`fetch_pharma.py`(制药 5 源: NMPA/CDE/巨潮/环评/招标)、`scripts/update_macro.py`、`scrape_products.py`(竞品)。
- **研判**：`scripts/update_news.py`(20 赛道 D/C/P/Pol 打分→`data/score_cache.json`)、`scripts/p4_opportunities.py`(**制药机会模型，事件中心黄金蓝本**)、`scripts/completeness_audit.py`(SLA 健康审计)。
- **RAG**：`scripts/rag_helper.py`(bge-small-zh + BM25 + reranker，检索 `reports/` 40 份年报)。
- **前端**：11 个静态 HTML（`index.html` 主热力图 + `pharma/liquid/customers/competitor/...`），`scripts/inject_scores.py` 正则注入 JS 常量；`data.js` 全局常量；`nav.js`/`theme.css`/`styles/`。
- **数据**：`data/score_cache.json`(打分缓存)、`data/products_analysis.json`(竞品: Bürkert威胁4.3/Gemü4.0/ESG2.7)、`data/history.json`、`customers.html` 内嵌 HEATMAP_DATA(8 制药子赛道景气) + COMPANIES(70+ 客户)。

### 3.2 自动化（GitHub Actions cron）

| workflow | 节奏 | 作用 |
|---|---|---|
| `rss_fetch.yml` | 每日 00:00 UTC | RSS 抓取 → data/rss/ |
| `pharma_intel.yml` | 每日 01:00 UTC | 制药信号 → data.js/pharma.html |
| `update-news.yml` | 周一 00:00 UTC | RAG+打分+注入 |
| `update_macro.yml` | 周一 02:00 UTC | 宏观指标 |
| `competitor_monitor.yml` | 周一 02:00 UTC | 竞品爬取分析 |
| `monthly-intelligence.yml` | 每月 5 号 | 月报 + 完整性审计（开 Draft PR） |

> ⚠️ 老系统感知层基本停摆：RSS 停在 2026-05-22；engine 不依赖任何 workflow。

---

## 4. 数据源健康（决定哪些信号现在拿得到）

| 源 | 提前量 | 现状 | 备注 |
|---|---|---|---|
| cninfo 募投 `fulltextSearch/full` | L1 | ✅ 通 | 新引擎唯一跑通的源 |
| CDE 优先审评（Playwright） | pipeline | ✅ 已接 | 瑞数 WAF → Playwright 过墙 + `getPriorityApprovalList` API（带公司名）；opt-in |
| NMPA 飞检 `nmpa.gov.cn` | 替换切口 | ❌ 瑞数(严) | 同瑞数但严格实例，挑战解完仍 400 拒 headless → 需非 headless/反检测，CI 待办 |
| 环评 `eia.mee.gov.cn` | L2 | ❌ 本机 SSL 封 | 疑地域封；CI 环境验证 |
| 招标 `ccgp.gov.cn` | L0 | ❌ 频繁访问 | 端点已知 `search.ccgp.gov.cn/bxsearch`；IP 限频反爬，CI/干净 IP 待办 |
| RSS（7 垂直） | — | ❌ 停在 5-22 | 老系统 |

---

## 5. 技术栈 & 部署

- **Python 3.11**（CI）/ 本机 **3.14 缺 `requests`/`beautifulsoup4`**，需 `pip install requests beautifulsoup4`。
- 依赖（`requirements.txt`）：feedparser, requests, python-dateutil, pyyaml, beautifulsoup4。RAG 另需 chromadb/sentence-transformers。
- **前端**：纯手写 HTML/CSS/JS，无框架，无 build。
- **部署**：Vercel（`vercel.json`: cleanUrls）+ GitHub Pages 可选。
- **测试**：stdlib `unittest`（无 pytest）。`tests/test_engine.py`(18, 引擎) + `test_intelligence_pipeline.py` + `test_monthly_update.py`(老)。

---

## 6. 文件地图（速查）

```
engine/                  新事件引擎（自包含，828 行）
config/esg_conditions.yml 工况知识库
config/p4_opportunity_map.yml 老制药客户/竞品/系数配置
scripts/p4_opportunities.py   事件模型黄金蓝本
scripts/{update_news,update_macro,inject_scores,rag_helper,completeness_audit,monthly_update}.py
fetch_pharma.py fetch_rss.py  老采集（含制药 5 源代码，可复活 NMPA/CDE）
*.html (11)              老前端页
data/events/             新引擎产出（生成物）
data/{score_cache,products_analysis,history}.json  老数据
reports/ (40)            年报库（RAG 检索源）
.github/workflows/ (6)   老自动化
docs/INTELLIGENCE_OS.md  方法论北极星
HANDOFF.md ROADMAP.md ARCHITECTURE.md  交接三件套
```
