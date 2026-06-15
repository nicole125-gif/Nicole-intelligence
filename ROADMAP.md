# ROADMAP — Nicole Intelligence

> 下一步路线。配套：`HANDOFF.md`（入口/状态/决策）、`ARCHITECTURE.md`（结构）。
> 最后更新 2026-06-15。**动手前先确认——用户当前处于"设计 > 执行"模式。**

## 北极星 & 交付顺序

情报价值 = 在客户下单前 6–18 个月捕捉 Capex 信号，指明该找谁/卖什么阀/何时/多少钱。
**交付顺序**：个人研判工具（试验场）→ 团队铺开 + 处置闭环（让赢面数据流起来）→ 管理面板（闭环副产品）。

---

## 框架 5 个洞的状态（麦肯锡+CEO review 结论）

| 洞 | 内容 | 状态 |
|---|---|---|
| **A 赢面轴** | rank_score 加 winnability 第四因子 | ✅ **v1 已实现**（绿地无在位 + 竞品密度，工况级）；渠道/spec 维度卡 spec 位=v2 |
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
- ✅ **赢面 v1 已实现**（2026-06-10）：`engine/winnability.py`，rank_score 第四因子 = 绿地无在位 + 竞品密度（工况级 `competitor_density` 配在 esg_conditions.yml）。效果：锂电/橡塑(国产友好)升，技改棕地/Gemü主场降。
- **赢面 v2（待办）**：① 渠道触达/spec 位维度（**卡 spec 位未知 + 客户档案匹配**，接 `p4_opportunity_map.yml`）；② 工况粒度——当前"卫生级/制药"一刀切 `竞品high`，但**生物合成/发酵**实际国产友好（甜点区被误降），需拆独立工况给低密度。
- **处置闭环（待办）**：线索卡 → 周会回标签(跟进中/赢/输/忽略/无效+原因) → 喂赢面表/指标树/管理视图——这才让赢面阈值可校准。

### 3. 补 L0/L2 源（修感知层）
- ✅ **CDE 优先审评已接**（2026-06-10）：`engine/sources/cde.py`，Playwright 过瑞数 WAF + 截获 `getPriorityApprovalList` API，产出带公司名的制药 pipeline 事件（band=未知/低 rank 的早期预警）。opt-in `--with-cde`（Playwright 慢）。
- **⛔ 其余源 = CI/生产环境待办**（2026-06-10 本机逐个实测均受阻，非代码问题）：
  - ② **ccgp 招标（L0）**：端点 `search.ccgp.gov.cn/bxsearch` 已确认，但"频繁访问"IP 限频反爬，本机 IP 已被探测限死 → 干净 IP/低频/CI 做。
  - ③ **NMPA 飞检（替换切口）**：瑞数 WAF **严格实例**——挑战解完仍返回 400 拒 headless（CDE 那个宽松实例可过，NMPA 不行）→ 需非 headless 浏览器/反检测指纹，CI 做。
  - 环评(eia)：本机 SSL/疑地域封 → CI 验证。
  - **教训**：剩余 L0/L2 政府源系统性反爬，无头开发机是最差攻坚地点；别在本机继续刚。
> CDE 增强（可选）：受理号→企业的 capex 关联（pipeline 转 capex 预警）；翻页拿更多记录。

### 4. 装备商订单簿监测（制药出海增量）
同 cninfo 源，盯固定 watchlist（楚天/森松/东富龙/奥星/正帆）的新签/海外/中标披露——捕捉"中企装备商出海"增量（成交在国内、算机会）。

---

## P2 — 产品化

5. ✅ **前端事件队列已实现**（2026-06-11）：`events.html`——纯 HTML/CSS/JS 研判信箱，fetch `data/events/<date>.json`（无 index，从今天往回找最近文件），渲染排序线索卡（rank/赢面表/工况/阀型/业主→买方/提前量/价值档/动作/来源链接），工况+提前量 chip 过滤，复用 `core.css` 工业暗色主题（accent 信号绿）。Playwright 验证：42 卡渲染、过滤生效。
   - **部署注意**：`data/events/` 已 gitignore→ Vercel/Pages 上无数据文件。要上线需：① CI 跑 engine 并 commit 当日 events（或去掉该 gitignore 提交样例），② 可选给 nav.js 加 events.html 链接 + 写 `data/events/index.json` 指针免去日期猜测。
   - **后续**：处置交互（点卡片标 跟进/赢/输）——接框架洞 D 闭环。
6. **region/省份字段 + 团队路由**：事件加地理（按**买方所在地**，不是工厂所在地）。
7. **DeepSeek 深度评分**（`score_pharma.py`，预留 `valve_intelligence` 字段位）、**est_value PDF 解析**（复用 `rag_helper.py` 读公告正文金额）。
8. **CI 自动化**：给 engine 加 workflow（cron + `python -m engine.run` + commit data/events）。

---

## P1.5 — 本体化（Ontology）工作流 ⭐

> **来源**：2026-06-14 用 Palantir Ontology 原理做的 CEO 战略审查。
> **判断**：项目赢在 *Function*（打分）、雏形赢在 *Action*（处置），但**输在 Object 和 Link**——核心实体退化成字符串、关系图近乎为零、闭环写了一半没合上。下一个真正的跃迁不是再加一个分数，是**把扁平 Event 长成一张实体图**。
> **元原则**：Object（实体）/ Link（关系边）/ Action（写回）/ Function（图上派生逻辑）+ 动能闭环（sense→decide→act→measure）+ 单一语义层。
> **现状定位**：Event 已是体面 Object；工况库=受控词表；处置=雏形 Action。短板在下面 5 阶。

### O1. ✅ 实体解析：Company/OEM/Competitor 升为一等 Object（地基）— 已完成 2026-06-15
- **症结**：`build.py` 的 `owner:{name,raw,resolved:false}` 自承业主只是逐条重述的字符串，无稳定身份/去重/历史。买方(设备OEM)仅是推断的角色字符串。竞品仅是 config 常量 `competitor_density`。
- **做了**：`engine/entities.py`（registry 加载 + `resolve` + `get` 寻址）+ `config/entities.yml`（战略实体种子：OEM/Competitor/self，id 对齐 p4_opportunity_map）。`build.py` 接进 `build_event`，`owner` 升为带 `id/type/resolved` 的实体引用：命中 registry → 正规 id + resolved=True；未命中 → 稳定 auto-id + resolved=False。`_normalize` 循环剥后缀保证同名同 id。
- **verify ✅**：别名+后缀变体收敛同 id（楚天科技股份有限公司=楚天=truking）；未登记业主拿稳定 auto-id；OEM/Competitor 经 `get()` 独立寻址；36 测试全过。
- **留给后续**：短名↔全称模糊匹配、统一信用代码、auto 实体人工提升进 registry；富属性（products/capex）走 O4 合并。

### O2. 建图：补承重 Link，先解 spec 位
- **症结**：事件是扁平记录，几乎无边。Palantir 威力在图遍历。
- **关键边**：`Event→Company`、`Company→OEM(供货)`、`OEM→ESG(spec位:进/没进)`、`Competitor→Site(在位于)`、`Disposition→Event`、`Company→Region`。
- **spec 位重判**：头号挂起不是「待问的事实」，是 `ESG—has-spec-position→{楚天/森松/东富龙}` 这条**承重边缺失**——整张图拓扑挂在它上。**当成「补一条边」来解。**
- **verify**：能从一个 Event 沿边走到「该业主的 OEM 及其 ESG spec 位」。

### O3. 合上动能闭环：处置写回 → 喂 winnability
- **症结**：处置现在是死写（存 KV，无人读回），是日记不是状态转移。闭环开着 → 价值锁死（决策15 先采集后消费）。
- **做**：消费侧读历史「赢/输给谁」反调 winnability 阈值；**把竞品密度从「工况」属性迁到「Competitor—装机于→Site」Link 属性**——这才根治 v1 生物合成误降（本会话的 biosynthesis 工况修复是治标，真因是密度挂错层级）。
- **verify**：一次处置标记后，相关 Event/Company 的赢面输入随之变化（环合上）。
- **依赖**：先攒够标签数据（决策15），故排在采足处置之后。

### O4. 本体合并：接回孤儿化的客户/竞品本体
- **症结**：两套本体并存，且更富的一套被孤儿化——`config/p4_opportunity_map.yml`（楚天/森松/东富龙档案+竞品+capex系数）、`data/products_analysis.json`（威胁 Bürkert4.3/Gemü4.0/ESG2.7）是全仓库最富实体数据，却作「灰色文件」未入库、没接进引擎。
- **做**：把这两份接成 O1 的 Company/Competitor 种子数据，终结双本体。
- **verify**：引擎里的 Company/Competitor 对象带上这些档案属性。

### O5.（后置）Person 维度 + 问责图
- 处置身份现为「区域」匿名（决策14）。后续加 Person Object，路由才真正落到「谁负责这条线索」，SLA/问责成图。

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
