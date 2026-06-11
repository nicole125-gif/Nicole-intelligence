# ROADMAP — Nicole Intelligence

> 下一步路线。配套：`HANDOFF.md`（入口/状态/决策）、`ARCHITECTURE.md`（结构）。
> 最后更新 2026-06-10。**动手前先确认——用户当前处于"设计 > 执行"模式。**

## 北极星 & 交付顺序

情报价值 = 在客户下单前 6–18 个月捕捉 Capex 信号，指明该找谁/卖什么阀/何时/多少钱。
**交付顺序**：个人研判工具（试验场）→ 团队铺开 + 处置闭环（让赢面数据流起来）→ 管理面板（闭环副产品）。

---

## 框架 5 个洞的状态（麦肯锡+CEO review 结论）

| 洞 | 内容 | 状态 |
|---|---|---|
| **A 赢面轴** | rank_score 要加 winnability（渠道触达×规模档×绿地/在位×竞品 threat） | 设计完，靠 D 喂数据，**未实现** |
| **B event_type** | 新建为主，MRO/OEM设计导入作侧流标签 | 已降级，记着 |
| **C est_value 分档** | 大/中/小代替假精度的"元"数字 | **设计完，待实现（P0 首选）** |
| **D 行动层闭环** | 路由(区域×行业×OEM具名) + 线索卡 + SLA + 处置标签回流 | 设计透，**未实现** |
| **E 北极星指标** | 指标树 + access-advantage 归因（别测 causation） | 已构思 |

**核心洞察**：A 与 D 是**同一个飞轮**——赢面第一天算不出，靠闭环"赢了/输给谁/OEM拒用国产"攒数据；先用粗代理冷启动。

---

## P0 — 立即可做、立竿见影、独立于挂起未知

### 1. ✅ est_value 分档（大/中/小/未知）— 已完成 2026-06-10
**做了什么**：`valuation.value_band()` 综合 [金额 + 产能规模(`capacity_scale`捡回万吨/GWh) + 项目类型词] 给价值档（**不掺工况阀密度**——那是排序里独立的 `condition_factor`，避免双重计数）；`ranking.value_factor` 改成档分（大1.0/中0.6/小0.3/未知0.35）；事件加 `value_band{band,basis}` 字段，summary 加 `by_band`。
**改了**：`engine/valuation.py`、`engine/ranking.py`、`engine/build.py`、`tests/test_engine.py`（24 测试全过）。
**验收（真实数据）**：璞泰来(72亿㎡隔膜)、东华科技(30万吨乙二醇)等"标题没写金额"的大项目从沉底升到 Top1/2；by_band 大6/中3/小8/未知23。
> 后续可选增强：金额区间 [low-high] 已在 `est_value` 字段，前端线索卡可展示；档阈值待真实赢单数据校准（接 D 闭环）。

---

## P1 — 核心价值

### 2. winnability 赢面轴 + 处置闭环（同飞轮）
先粗代理（规模档×绿地/在位×渠道触达×竞品 threat_level）做进 rank_score 当**入口闸门**（不只排序，低赢面鲸鱼到人前就滤掉）；同步设计最小处置闭环：线索卡 → 周会回标签(跟进中/赢/输/忽略/无效+原因) → 喂赢面表/指标树/管理视图。
**前置**：需要 `owner.resolved`（客户档案匹配，接 `config/p4_opportunity_map.yml`）。

### 3. 补 L0/L2 源（修感知层）
- ✅ **CDE 优先审评已接**（2026-06-10）：`engine/sources/cde.py`，Playwright 过瑞数 WAF + 截获 `getPriorityApprovalList` API，产出带公司名的制药 pipeline 事件（band=未知/低 rank 的早期预警）。opt-in `--with-cde`（Playwright 慢）。
- 待办：② ccgp 新入口（L0 招标，站点改版）→ ③ NMPA 反爬（412，替换切口，战略价值高，同属瑞数级 WAF，可仿 cde.py 用 Playwright）；环评(eia)本机不可达，**在 CI 环境验证**。
> CDE 增强（可选）：受理号→企业的 capex 关联（pipeline 转 capex 预警）；翻页拿更多记录。

### 4. 装备商订单簿监测（制药出海增量）
同 cninfo 源，盯固定 watchlist（楚天/森松/东富龙/奥星/正帆）的新签/海外/中标披露——捕捉"中企装备商出海"增量（成交在国内、算机会）。

---

## P2 — 产品化

5. **前端事件队列**（研判信箱）：复用老系统 CSS 主题，把 `data/events/<date>.json` 渲染成排序队列 + 处置交互。
6. **region/省份字段 + 团队路由**：事件加地理（按**买方所在地**，不是工厂所在地）。
7. **DeepSeek 深度评分**（`score_pharma.py`，预留 `valve_intelligence` 字段位）、**est_value PDF 解析**（复用 `rag_helper.py` 读公告正文金额）。
8. **CI 自动化**：给 engine 加 workflow（cron + `python -m engine.run` + commit data/events）。

---

## 阻塞 / 依赖

- **⏸ 头号挂起（等用户 Nicole 确认）**：**ESG 有没有进楚天/森松/东富龙的标准 BOM（spec 位）？**
  - 已进 → P1#4 装备商订单簿立刻有用，它们出海=ESG顺风；
  - 没进 → 制药第一优先级变成"先拿下设计导入"，否则其扩产/出海全便宜 Gemü。
  - **不要替用户假设。**
- **死源**（见 ARCHITECTURE §4）：现仅 cninfo（L1）跑通，缺 L0/L2。
- **本机 py3.14 缺依赖**：`pip install requests beautifulsoup4`（CI 环境具备）。

---

## 制药赛道（首个试验田）结论

- 子赛道严重分化：多肽GLP-1/CDMO/生物合成/ADC 热且在扩产值得追；**疫苗崩盘别碰**。
- ESG 在制药是**国产挑战者**（Gemü/Bürkert 在位）。
- **反直觉甜点区**：优先打**生物合成/发酵 + GLP-1 原料药端**（角座阀对口 CIP/SIP/发酵 + 中端国产友好 + 十五五），而非最火的无菌注射剂/生物药制剂（Gemü 隔膜阀护城河，赢面低）。
- **NMPA 飞检 = 替换切口**（在位者出问题=挑战者进入窗口），权重应调高。
- **"只看国内"重定义为"只看国内可成交渠道"**——中企装备商出海算机会，监测其国内披露而非境外环评。
