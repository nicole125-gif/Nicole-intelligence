# HANDOFF — Nicole Intelligence ｜ 接手入口

> **新 Claude 会话从这里开始。** 三件套分工：
> - **HANDOFF.md**（本文）— 项目状态、关键决策、挂起未知、怎么跑、互动纪律。
> - **ARCHITECTURE.md** — 系统结构、模块职责、数据流、事件 schema、源健康。
> - **ROADMAP.md** — 下一步路线（P0/P1/P2）、框架 5 洞状态、阻塞依赖。
>
> 另：方法论北极星 `docs/INTELLIGENCE_OS.md`；实现计划 `~/.claude/plans/https-www-esgvalve-cn-gleaming-stroustrup.md`；项目记忆 `~/.claude/projects/.../memory/esg-event-engine.md` + `esg-spec-position.md`。
> 最后更新 2026-07-02 ｜ 引擎主体在 `main`：里程碑1 + winnability + **O1/O2-A/O3/O4** 本体化 + 本体图谱 + 订单簿源（PR #23）｜ 处置闭环已上线（Vercel+Upstash）｜ 漏斗 B1/B2（PR #18）｜ 热力图 ESG 化（PR #20/#22）｜ 5 层栈 + RSS源 + 评估集（PR #30/#31/#32 已合）。Brave key 已 park（§7）。WIP/自动化在 `automation/monthly-update`。
>
> **✅ 近期已全部合入 main**（changelog 见 §12）：5 层栈(PR#31) / RSS源(#30) / 评估集(#32) / 热力图对齐+heat rubric+L2 派生(#33) / 本体实例化 ER+闭环(#34)。70 测试全过。
>
> **🔑 下次开机关键词**：`读 HANDOFF §12(已做) + §13(下一步)`。**最优先 = §13 的下一个真坎：持久对象存储（跨 run 稳定身份）**——架构大改需单独 scope（本会话只做了人工提升那半）。次优先见 §13。P1.6 漏斗为既往主线（下）：
>
> **P1.6 漏斗串链**（热力图入口→下钻事件→带 方案/竞品/产品推荐，先 B 后 A）：
> - **✅ B1/B2 已完成**（PR #18）：事件卡带 推荐产品 + 在位竞品（具名+威胁分/绿地"无外资在位"）；events.html 加行业过滤 + `?industry=` deep-link（B3 下钻入口已备）。
> - **下一步 = B3**（热力图改"混合+可点入口"：广度续用老 RSS/Brave 行业情绪，叠 engine 事件机会深度，点格 → `events.html?industry=X`）。**依赖 B0 数据 + 老管线热度** → B0 是 Codex 在做，B3 等数据到位再动；现在做会悬空。可先做的旁路：O2-B/图谱 enrich。
> - **B0（CI 出数据）= Codex 在做**，本仓只作下游依赖，别重复实现。
> - **竞品层复用** 兄弟产品 knowledge-center / "Pharma CI Radar"（`knowledge-center-omega.vercel.app/sales-intel`，竞品库更全），不重建。
> - 纪律：从 `main` 切新分支，**开 PR 前先 `git fetch`**（bot 直推 main）；引擎活在 main，WIP/自动化在 automation。

---

## 1. 项目一句话

阀门企业 **ESG 青岛精锐**（esgvalve.cn，旗舰角座阀，气动卫生级）的情报系统。本质：在客户下单前 **6–18 个月捕捉会触发流体采购的 Capex 事件**，指明该找谁/卖什么阀/何时/多少钱。正在**从「赛道热度中心」重构为「事件中心」**。

## 2. 当前状态（一屏）

- **里程碑 1（后端事件引擎）已完成 + 真数据验收通过**：`engine/` 包（自包含），cninfo 实时 ~40 条真实事件，核心工况均≥3，`--strict` 健康检查过。
- **✅ P0#1 est_value 分档已实现并验证**（2026-06-10）：value_band 大/中/小/未知，把"标题没写金额的大项目"（璞泰来/东华科技）从沉底捞到 Top；**24 单测全过**。详见 ROADMAP P0#1。
- **整体框架 review 已做完**（麦肯锡战略 + CEO 双视角），制药赛道分析（首个试验田）已做完。结论见第 4 节 + ROADMAP。
- **✅ CDE 优先审评源已接**（2026-06-10，opt-in `--with-cde`）：`engine/sources/cde.py` 用 Playwright 过瑞数 WAF + 截获 `getPriorityApprovalList` API，产出带公司名的制药 pipeline 事件（band=未知/低 rank 的早期预警）。
- **✅ winnability 赢面轴 v1 已实现**（2026-06-10）：`engine/winnability.py`，rank_score 第四因子（绿地无在位 + 工况级竞品密度）。锂电/橡塑升、技改棕地/Gemü主场降。
- **✅ O1 实体解析已落地**（2026-06-15，框架 P1.5 本体化第一阶/地基）：`engine/entities.py` + `config/entities.yml`，业主字符串解析到稳定 Company/OEM/Competitor 对象——命中战略 registry（楚天/东富龙/森松/奥星/正帆/Bürkert/Gemü/ESG）→ 正规 id + `resolved=True`；未命中 → 稳定 auto-id（同名同 id）+ `resolved=False` 待人工提升。`build.py` 接进 `build_event`：`owner` 从裸 `{name,raw,resolved:false}` 升为带 `id/type/resolved` 的实体引用，**消灭自承业主**。registry id 已对齐 `p4_opportunity_map.yml`，O4 合并同 id 直接接档案。**bugfix**：`_normalize` 改循环剥后缀，修核心名以"公司"结尾时长短变体不收敛（auto-id 不稳）。36 测试全过。**仍是字符串→对象的地基，承重边（O2）+ 写回闭环（O3）未做。**
- **✅ 甜点区误降已修**（2026-06-14，commit `dde13f6`）：`config/esg_conditions.yml` 新增 `biosynthesis`（生物合成/发酵）工况 density=low，纯增量认领 `发酵/生物反应器`+新增 `生物合成/合成生物/发酵罐/菌种`，靠排序赢平局——无菌制剂仍归 pharma_ref(high)、食品发酵仍归 hygienic(high)。winnability 0.55→0.95。31 测试全过。**取舍**：density 选 low（主动上浮，依据决策8 优先甜点区）而非 mid（仅中性），可一行改回。winnability v2 仍欠 spec 位维度（卡挂起未知）。
- **⛔ 源攻坚已到头（2026-06-10 逐个实测）**：cninfo✅/CDE✅ 已接；**eia(SSL/地域封)、ccgp(频繁访问反爬+本机IP已限)、NMPA(瑞数严格实例，挑战解完仍 400 拒 headless) 全在反爬墙后，本无头开发机破不了**。不是做不了，是**得在 CI/生产环境**（非 headless / 干净 IP / 反检测）做——已标 ROADMAP。**别在本机继续刚这几个源。**
- **✅ 前端事件队列已实现**（2026-06-11）：`events.html` 研判信箱——fetch `data/events/<date>.json` 渲染排序线索卡（rank/赢面/工况/阀型/业主→买方/提前量/价值档/动作/来源），工况+提前量过滤，复用 core.css 工业暗色主题。Playwright 验证 42 卡渲染+过滤生效。**这就是"第一交付物：个人研判工具"，引擎产出终于可看可用。** 部署注意见 ROADMAP P2#5（data/events gitignore，上线需 CI 出数据）。
- **✅ 处置闭环采集层已实现**（2026-06-12，网页版，框架洞 D 前半）：`events.html` 每张线索卡加 5 态处置控件（跟进/赢/输/忽略/无效）+ 原因框（输/无效必填）；写 **Vercel KV**（`api/dispositions.js` Serverless 函数 GET/POST，key 级写避并发覆盖）→ 多人/跨设备同步同一份；身份=**区域**（存 localStorage，每次标记带上，对齐区域×行业销售组织）；加处置态过滤 + 已处置/待处置统计 + 已处置卡左缘色标。Playwright 验过：7 过滤 chip / 5 态按钮 / 区域+原因必填拦截 / POST 接线（本机 501→Vercel 上 200 入库）。**本轮只采集，未动 winnability（消费=下轮）。**
- **⚠ 处置闭环上线前置（阻塞，用户做，2026-06-18 推进中）**：**Vercel 控制台 → Storage → 建 Redis（Upstash，原 KV）store → Connect to Project → redeploy**。注入 `KV_REST_API_*` 或 `UPSTASH_REDIS_REST_*` 均可（见下，代码两套都读）。没建 store，`/api/dispositions` 返回 500「KV 未配置」。本机无凭证→真写入链路本机验不了，只验过 UI/交互。**注意：处置只在 Vercel 部署上可用，GitHub Pages（`nicole125-gif.github.io/Nicole-intelligence/`）无 /api。**
- **✅ @vercel/kv 废弃已修**（2026-06-18，PR 待记）：`api/dispositions.js` 改用 `@upstash/redis`，url/token 同时读 `KV_REST_API_*` 和 `UPSTASH_REDIS_REST_*`（控制台注入哪套都行），缺凭证返回清晰 500。`package.json` 依赖换 `@upstash/redis ^1.34.3`。
- **⚠ 处置闭环剩余风险**：①无鉴权，有 URL 即可读写处置（内部工具可接受，要收紧加共享口令）；②`kv.keys('disp:*')` 扫全键，量级到数千条需改维护 id 集合；③部署绑死 Vercel（GitHub Pages 跑不了 /api）。
- **🔴 安全（2026-06-18 体检发现）**：`brave_search_scraper.py` 硬编码 Brave API key 且已推到公开 origin/main。**本 PR 删该死文件**（无人引用，已被 `scripts/monthly_update.py`/`update_news.py` 的 env 版取代）。**但 key 已进 git 历史→必须轮换（用户去 Brave 控制台吊销旧 key、发新 key，存 GitHub Actions secret `BRAVE_API_KEY`）**，删文件不能挽回历史泄漏。
- **✅ O4 本体合并已落地**（2026-06-16，框架 P1.5 第四阶）：把孤儿化的两套富本体折叠进 `config/entities.yml` 的 `profile:` 块——OEM（楚天/森松/东富龙）带 match_keywords/target_roles/esg_products/competitor_products/capex_ratio（源 p4_opportunity_map）；竞品+self 带 avg_threat_level/product_count/high_threat_products（源 products_analysis：Bürkert4.3/Gemü4.0/ESG2.7）。`load_registry` 本就按 id 存整条 dict，**`get(id)` 自动带出 profile，零 join 代码**；`resolve()` 仍轻量（profile 不进每条 event 的 owner）。终结双本体，entities.yml 升为实体数据单一语义层。**`p4_opportunity_map.yml` 仍被 legacy `scripts/p4_opportunities.py` 读，保留不删**。38 测试全过（+2）。
- **✅ O2 spec 位切片 A 已落地**（2026-06-16，框架 P1.5 第二阶/承重边）：头号挂起已解（§5）——**ESG 只进东富龙 BOM，楚天/森松未进**。`config/entities.yml` 三 OEM 加 `spec_position`（东富龙 `in`/楚天/森松 `target`）；`build.py` 当 owner 解析为 OEM 实体时沿 owner→OEM 边取 spec 位，喂 winnability（in +0.2 顺风 / target −0.1 需 design-in）+ 分流 action（in→盯订单簿；target→主推 design-in）；event 加 `spec_position` 字段。实测东富龙扩产 win 0.5 > 通用 0.3 > 楚天 0.2。43 测试全过（+5）。**切片 B（headline 具名识别买方 OEM）后置**——多数 event 不点名 OEM。
- **✅ 本体图谱已落地**（2026-06-17）：`ontology.html` —— Gotham 风力导向图把 O1/O2/O4 可视化：ESG 居中引力核、OEM/竞品/业主/事件分型节点、**spec 位边为主角**（绿实=已进/琥珀虚=待 design-in）、竞品光晕=威胁分、点节点出 O4 属性卡。纯 vanilla canvas（零 CDN，守国内可达），复用 core.css。数据由 `scripts/build_ontology.py`（entities.yml 单一来源 + 最新 events → `data/ontology.json`，已 gitignore）编译。**部署缺数据同 events 的 P2#5**（CI 需跑 build_ontology）。视觉/过滤待节点变多（O2-B/O3）再 enrich。
- **✅ O3 竞品密度迁层级已落地**（2026-06-17，框架 P1.5 第三阶前半）：竞品密度从「工况」硬编码迁到「竞品—据点→工况」关系——`config/entities.yml` 竞品加 `strongholds`，`winnability.density_from_strongholds()` 派生（full→high/partial→mid/无→low），`build.py` 改用派生值。**根治生物合成误降**（不在任何据点→自然 low，band-aid 退役；esg_conditions 的 density 字段降级为参照）。派生值与旧常量对齐无回归，47 测试全过（+4）。**O3 第 1 半（处置写回反调 winnability）仍挂起**——依赖真实处置标签（决策15）。
- **下一个自然动作（O2-A 后，2026-06-16）**：
  - **O3 赢面消费链路（旁路，需先攒处置标签）**：competitor profile 威胁分 + spec 位都已可读，winnability 可继续从 config 常量升级为读实体属性；完整闭环要先攒处置标签（决策15）。
  - **O2 切片 B**：headline 具名识别买方 OEM，让非 OEM 自建但用东富龙设备的 event 也走到 spec 位。
  - 旁路备选：源攻坚挪 CI；P2#6 region 字段（见下）。
- **⚠ P2#6 region 字段有 spec-vs-数据冲突（2026-06-14 发现，待用户定）**：ROADMAP 要"按**买方所在地**"，但买方=推断的设备OEM，所在地**不在文本里**抽不出；能抽的只有它明确要避开的"项目/业主所在地省份"（headline 省市关键词）。三条路：①硬做不可行；②务实抽「项目地省份」当 region，语义诚实标注（推荐，且对齐处置闭环的区域身份）；③搁置等销售确认路由口径。**别替用户假设**。
- 结构细节见 `ARCHITECTURE.md`，下一步见 `ROADMAP.md`。

## 3. 怎么跑 / 验证

```bash
pip install requests beautifulsoup4        # 本机 py3.14 缺这俩；CI 环境已有
python3 -m engine.run                       # 真数据（需网络），写 data/events/<date>.json
python3 -m engine.run --with-cde            # 额外抓 CDE 优先审评（Playwright 过瑞数 WAF，慢）
python3 -m engine.run --sample              # 离线样例，端到端演示，无需联网
python3 -m engine.run --strict              # 健康检查不达标 exit 1
python3 -m unittest tests.test_engine        # 51 个离线单测（截至 P1#4 订单簿）
python3 -m engine.run --sample && python3 -m http.server 8765  # 本地预览 events.html 研判信箱
python3 scripts/build_ontology.py             # 从 entities.yml + 最新 events 编译 data/ontology.json（看图前先跑）
#   然后 http.server 打开 ontology.html —— P1.5 本体图谱（O1/O2/O4 可视化）

# Vercel 部署（项目未连 GitHub，从干净 main worktree CLI 部署）：
#   ⚠ 必须 NODE_USE_ENV_PROXY=1 —— 本机走 privoxy(127.0.0.1:8118)，但 Node 24 内置 fetch
#   默认不读 HTTPS_PROXY → vercel deploy 报 TLS 断连。加这个 env 才成。
NODE_USE_ENV_PROXY=1 npx vercel@latest deploy --prod --yes   # 公开别名见 §7
```

## 4. 关键决策（带 WHY，不要轻易推翻）

1. **事件中心 > 赛道中心**：研判输出（找谁/卖什么/多少钱）天生是事件，热度把具体性丢光。
2. **架构从零重写**（用户明确）；老制药链 `fetch_pharma.py`/`p4_opportunities.py` 只作设计参照。
3. **主营收引擎 = 新建/扩建项目销售**（CEO 拍板）→ 事件宇宙以新建 Capex 为中心；MRO/OEM 导入作侧流标签。
4. **"只看国内" = "只看国内可成交渠道"**，不是"只看国内工厂"。中企装备商出海（森松海外 87%）算机会，监测其**国内披露**（cninfo），不抓境外环评。
5. **中企海外建厂保留，不加海外过滤**（用户明确）。
6. **赢面（A）与处置闭环（D）是同一飞轮**：赢面靠闭环攒数据，先粗代理冷启动。
7. **个人工具 = 试点不是终点**；闭环需团队回处置标签才闭。销售组织 = **区域/行业团队**（已确认）→ 路由按区域×行业 + 关键 OEM 具名负责人。
8. **制药甜点区反直觉**：优先生物合成/发酵 + GLP-1 原料药端（角座阀对口），避开无菌制剂（Gemü 护城河）。
9. **NMPA 飞检 = 替换切口**（非合规噪声），权重应调高。
10. **est_value 用档不用点**：假精度毁信任，且当前逻辑埋掉大项目。
11. **归因测 access-advantage（更早接触权），不测 causation**（提前量长 + 走 OEM，归因难）。
12. **处置闭环做成网页版 + 多人共享**（用户明确）→ 必须有后端，纯静态存不住跨设备标签。
13. **后端选 Vercel 函数 + KV**（非 Supabase）：站点已在 Vercel、同域无跨域、密钥在服务端、国内可达性与现站一致；代价=**部署必须 Vercel（GitHub Pages 跑不了函数）**。
14. **处置身份 = 区域**（非人名）：对齐"区域×行业"销售组织（决策7），比人名更贴路由；无真鉴权（内部工具，anon+区域轻身份够用）。
15. **处置先采集、后消费**（用户明确）：赢面是冷启动，要先攒"赢/输给谁"标签才谈得上校准。闭环**消费机制已建但 gated 无标签**（PR #34，`engine/feedback.py`），等标签攒够再解封。
16. **Capex 口径 = 中资企业 capex（含中企出海建厂）**，非"只算国内工厂"（对齐决策4；出海经国内披露监测=机会）。是 heat rubric 的 C 维定义。
17. **L2 事件派生热度 = 并行印证层、不替换 rubric heat**：源稀疏时纯 L2 会误降到 0；按 α-blend 随覆盖成熟逐步接管（终局纯 events）。详见 memory `heat-rubric-l2`。
18. **ER 先人工提升进 registry**（跑 `unresolved_owners.py` 出清单再提，别盲提噪声）；**持久对象存储（跨 run 稳定身份）是架构大改、单独立项**——不擅自开。详见 memory `ontology-instantiation`。

## 5. ✅ 头号挂起未知 — 已解（2026-06-16 Nicole 确认）

**ESG 只进了东富龙的标准 BOM（spec 位）；楚天、森松未进。**
- 东富龙（已进）→ 盯其订单簿/扩产立刻有用，它出海=ESG 顺风；
- 楚天/森松（未进）→ 第一优先级是先拿下设计导入（design-in），否则其扩产/出海全便宜 Gemü。
- 已固化进 O2 切片 A（`config/entities.yml` 的 `spec_position`）+ 项目记忆 `esg-spec-position.md`。

## 6. 互动纪律（用户偏好）

- 中文交流、代码/commit 用英文；复杂任务先出计划再动手；做减法、surgical change、不过度抽象、默认不加注释。
- **外向/不可逆动作（commit/push/发外部）先确认**；不 force push main、不 skip hooks。
- **git：精确 stage 目标文件，绝不 `git add -A`**；commit 前给清单确认。

## 7. git 现状

- **✅ 引擎/可视化/处置闭环全部已在 `main`**，本会话 PR #6–#16 全部合并（皆从最新 `main` 切分支、合后删分支）：
  - **PR #6**（merge `2d9c99b`）：引擎/本体——从 `main` 干净切 `feat/event-engine`，cherry-pick 11 个引擎 commit（里程碑1 + winnability v1 + O1 + O4 + 三件套 docs + biosynthesis 修复 + research inbox/处置采集层），27 文件 / +2401。
  - **PR #7**（merge `a26d962`）：HANDOFF 同步到 main。
  - **PR #8**（merge `037d819`）：**O2 spec 位切片 A**（entities.yml spec_position + build.py owner→OEM 边 + winnability spec 因子 + action 分流）。
  - **PR #9**（merge `d320a37`）：HANDOFF 收尾（O2-A）。
  - **PR #10**（merge `470b600`）：**本体图谱 `ontology.html`** + `scripts/build_ontology.py`（data/ontology.json 已 gitignore）+ 样例 OEM 信号。
  - **PR #11**（merge `5ab76a5`）：**O3 竞品密度迁层级**（竞品 strongholds + winnability.density_from_strongholds，根治生物合成误降），47 测试全过。
  - **PR #12**（merge `44b6037`）：HANDOFF 收尾（O3 + 图谱）。
  - **PR #13**（merge `db37174`）：处置 API 改 `@upstash/redis`（弃废弃 `@vercel/kv`，KV_/UPSTASH_ 两套变量名都读）。
  - **PR #14**（merge `2ff3e31`）：删 `brave_search_scraper.py`（硬编码 key 的死文件）。
  - **PR #15**（merge `f9d075c`）：固化 Vercel 部署配置（`.vercelignore` 排 reports/python；`vercel.json` framework:null 防 Python 误判）。
  - **PR #16**（merge `52508da`）：ROADMAP 加 P1.6 漏斗工作流。
  - **main 自此为引擎/可视化/处置 API 的权威。**
- **✅ 处置闭环已上线**（2026-06-22）：Vercel 项目 `nicole-intelligence`（`wangxia1225-ai` 账号，**未连 GitHub**，目前 CLI 从干净 main 部署）+ Upstash Redis store `upstash-kv-almond-helmet`，注入 `KV_REST_API_*`。已关 Deployment Protection（决策14 无鉴权）。验活过：GET `{}` / POST 持久化 / DEL。**公开稳定别名（无登录墙）：`https://nicole-intelligence-wangxia1225-ais-projects.vercel.app`**（带 hash 的单次部署 URL 有保护墙，别给用户；这个项目-团队别名才公开）。部署用 `NODE_USE_ENV_PROXY=1 npx vercel deploy --prod`（见 §3 部署坑）。**注意：`data/events`/`data/ontology.json` gitignore，线上无数据 → events/ontology 页空白；但首页 index.html 热力图自包含、完整可看，待 B0 CI 出数据（Codex）补 events/ontology。**
- **🟡 Brave key 已 park**（2026-06-22 Nicole 决定以后重设）：旧 key 已 revoke（公开泄漏止血）；老管线 monthly_update/update_news 的 Brave 抓取会优雅 skip；以后重配新 key 进 GitHub Actions secret `BRAVE_API_KEY`。
- **`automation/monthly-update`（远端 `f825fad`）**：仍带同一串引擎 commit 的**旧 SHA**（O1-O4 在此分支早已提交并 push），但已被 PR #6 的 curated 版本取代——**别再从这条分支合引擎到 main**。这条分支本职是放自动化更新（RSS/竞品/monthly）+ 本会话前的 WIP。
- **⚠ 本仓库 bot 会直推 `main`**（RSS/竞品自动提交）：开 PR 前先 `git fetch`，否则本地 main 落后 → PR 报冲突（本轮踩过）。
- **灰色文件（仍未入库，待用户定夺）**：`docs/INTELLIGENCE_OS.md`（方法论北极星）、`config/p4_opportunity_map.yml`、`scripts/p4_opportunities.py`（§8 关键参照）。注：O4 已把 p4_opportunity_map / products_analysis 的实体数据折叠进 `config/entities.yml`（已入 main），这两份源文件仅 legacy 脚本仍读。
- **会话前本地 WIP（勿打包，仍在 automation 工作区）**：`M` fetch_pharma / fetch_rss / scripts/update_news / monthly_update + 2 workflow；`??` completeness_audit.py、tests/test_intelligence_pipeline.py、.gtrconfig、agent.md、pulse_mcp_server.py、data/watchlist.json。
- 提交纪律：精确 stage、commit 前给清单、push/合并前确认。

## 8. 关键参照文件

- `scripts/p4_opportunities.py` — 事件模型黄金蓝本。
- `fetch_pharma.py` — 三源抓取骨架 + 制药 NMPA/CDE 源代码（可复活）。
- `config/p4_opportunity_map.yml` — 楚天/东富龙/森松客户档案 + 竞品 + capex 系数。
- `customers.html` L239-284 — HEATMAP 8 制药子赛道真实景气数据。
- `data/products_analysis.json` — 竞品威胁：Bürkert 4.3 / Gemü 4.0 / ESG 2.7。

## 9. 产品形态：漏斗（2026-06-22 定调，当前主线）

**行业热力图(入口) → 下钻到事件 → 每条带 我方方案/竞品/产品推荐。** 热度与事件是**上下两层、不是对手**（修正决策1对赛道热度的单纯降级）——热度负责"往哪看"，事件负责"具体怎么打"。关节 = **行业/工况**（event 已带 `industry_tag`，热力图格子=行业，三页面是同一份引擎数据的三种切法）。

- **路线见 ROADMAP P1.6**（先 B 后 A）；细节+取舍见记忆 `product-vision-funnel.md`。
- **进度**：**✅ B1**（事件卡带 推荐产品 + 在位竞品，引擎加 `competitors` 字段）、**✅ B2**（events.html 行业过滤 + `?industry=` deep-link）已落地（PR #18）。**⏭ B3** = 热力图混合+点击下钻（依赖 B0 数据 + 老管线热度，等 Codex 的 B0；B2 的 deep-link 入口已备好接它）。A 阶段后置。
- **✅ 热力图 ESG 化已落地**（2026-06-23，PR #20，首页 `index.html` Market Heatmap 评分逻辑深度优化）｜**⚠ 本条 Heat 公式已被 PR #31 取代**——W 已从 Heat 拆出（现行 Heat=`Capex×.40+需求×.27+政策×.20+价格×.13` 纯市场，W 降为 L3 单列、`delta=W−Heat`，见 §12 / ARCHITECTURE §0.5）；下文①②③④保留作 PR #20 历史。：① **重锚 Heat Score** = `Capex×30 + W×25 + Demand×20 + Policy×15 + Price×10`（Capex 销售触发器领权、Price 降权）；② **新增 W=ESG 赢面/国产替代空间**（渲染层 `TRACK_W` 逐赛道种子，依据决策8 甜点区/竞品护城河/阀门相关性；heat 渲染层重算覆盖 bot 旧值，bot 月度更 D/C/P/Pol 照常流入、W 不被清）；③ **Color/Size By: ESG赢面 W**（甜点区绿/护城河红一眼可见）；④ delta 重定义为「ESG vs 市场」偏移。效果:排名从"市场热"翻成"ESG 能赢"(合成生物 TOP1、基因测序/宏观下沉)。**注**:改的是渲染层非 bot 数据,若 bot 整文件重生成 index.html 需留意；W 是手工种子,后续可考虑从 engine winnability 派生(接 B3/漏斗)。
- **B0 数据 CI = Codex 做**；**竞品层复用 knowledge-center / Pharma CI Radar**（别重建）；月度更新 B 阶段保留喂热力图广度、A2 退役。

## 10. CI Radar 对接（跨产品接缝，2026-06-25）

**两层架构**（被竞品调研验证，见记忆 `ci-competitor-lessons.md`）：**Nicole = 信号/结构化层（上游）**，**CI Radar（`竞品/` = knowledge-center / Pharma CI Radar）= 赋能/battlecards 层（下游）**。文件交接、非实时 API。

- **数据流**：Nicole 发现 事件/Capex/招标/工况/订单簿 → CI Radar 判断 ESG 卖什么/谁竞争/怎么问。
- **共享契约**（竞品仓 `docs/research/`）：`esg-intelligence-source-fields.csv`（35 字段/17 必填）+ `2026-06-esg-intelligence-source-contract.md` + 交接交付 `2026-06-claude-code-esg-data-source-handoff.md`。**两边以此为准。**
- **边界纪律**：Nicole **只发"发现了什么"**；**绝不写 ESG 价格/库存/交期/装机/证书/竞品输赢结论**（那些是 CI Radar 证据库承接）；无法归类不强行匹配 → `review_flag=needs_review` + `extraction_notes` NO_MATCH。
- **真正的接缝 = `data/events/<date>.json` 事件 schema**。**✅ 已做成契约就绪**（PR #25）：事件带 `working_condition_ids`（枚举，与中文 label 平行，id↔label 精确对齐契约）；signal_type/review_flag/lead_time/value_band 枚举本就对齐；订单簿事件 ids=[]（NO_MATCH）。Codex 的导出（JSON→CSV `exports/esg-ci-radar-event-intake-YYYY-MM-DD.csv`）可逐字段直接映射。
- **✅ richer output 已落地**（PR #28，2026-06-29）：① **L1 事件直读字段**——`capex_amount`/`capex_currency`/`extraction_notes`（非-ok 给理由；OEM 订单簿即使 ok 也标 NO_MATCH）/`matched_keywords`（命中证据），Codex 导出无需再派生。② **L2 `pack.clusters`**——按 `owner_id` 聚合的账户级信号簇（`corroboration`/`event_ids`/`in_motion`/`confidence`/spec位），`summary` 加 `accounts`/`corroborated`；可直接喂 CI Radar 账户视图 / `related_event_ids`（`event_ids`=同主体去重链）。交接文档映射表已同步更新。
- **⏸ 两个待 Codex/Nicole 协调点（非代码能定）**：① **导出脚本住哪**——Nicole 仓 vs CI Radar 仓读 events JSON（倾向后者，更干净不撞）；② **B0 数据管线统一**——一条 CI 既出 events.html 数据又喂导出，别两套。
- **分工现状**：CI Radar 导出 + B0 数据 CI = **Codex 在做**；Nicole 上游引擎/前端/契约就绪 = 本仓（我）。
- **📄 给 Codex 的交接文档**：`竞品/docs/research/2026-06-25-nicole-to-ci-radar-handoff.md`（含 events JSON→契约 CSV **逐字段映射表** + 怎么产出 events JSON + Codex 待做 + 两个协调点）。映射表已对真实 `--sample` events JSON 逐字段核对通过（2026-06-25）。**Codex 拿它 + events JSON 即可机械映射,无需再问。**

## 11. 信息流扩量：RSS/微信公众号源（2026-06-29，PR #30）

**目标**：给引擎扩"信息流量"，更早捕捉建厂/扩产/招标信号（用户定调：**微信出信息快，先搞定公众号**）。

- **✅ 管道已通（我做完，零引擎改动可加号）**：`engine/sources/rss.py` —— 吃 `fetch_rss.py` 已落盘的 `data/rss/*.json`（条目多为微信公众号文章），按 阀型/工况词过滤 → `source_type=news` 事件。零重复抓取、离线可跑。`run.py collect()` 已接；`esg_conditions.yml` 加 `news:0.3`（最弱）。58 测试全过。
- **✅ 已联网调研选号 + 预接**：`rss_sources.json` 新增 `capex_signals` vertical，预接 8 个**真正发项目动态**的号（蒲公英/制药网/食品板/食业头条/高工锂电/上海化工区/中国化工报/电池中国），url 为 `TODO-WECHAT-RELAY` 占位。完整选号清单 + 中转方案对比见 `docs/wechat-rss-source-plan.md`。
- **⚠ 卡点（非代码，用户/Codex 做）= 中转服务**：微信→RSS 必须有中转（推荐 **wechat2rss 托管版**，最快/24h 更新；备选自建 RSSHub）。**得在 CI/服务器跑，不在本机**（同招标/环评教训）。**下一步 = 用户去订阅那 8 个号 → 把 feed url 发回 → 替换 `rss_sources.json` 的 8 个占位** → 整条链 `fetch_rss → data/rss → 引擎` 自动通。
- **⚠ 重要实情**：现有 28 个 RSS feed 是**宏观趋势号**（半导体并购/氢能创业），喂进引擎 **0 命中**——扩量真杠杆 = **选对号**（发项目的），不是管道。
- **🔧 调研中挖到的更优旁路**：`制药网`（gc.zyzhan.com）有**结构化招标/项目页、是普通网页可直接爬**，比微信中转稳——可做 `engine/sources/zyzhan.py` 直抓（同 cninfo/tender 写法），跳过微信不确定性。同类：中项网/招标搜索。**未做，留作备选。**
- **配套欠账**：量上来需配 **去重（event_id 跨天账本）+ 新鲜度排序因子**，否则信箱被新闻刷屏（`ranking` 现无 recency 因子，`build_pack` 无跨天去重）。

## 12. 近期里程碑（已合入 main · changelog）

> 只留一句定位；明细在 git + `ARCHITECTURE §0.5` + `docs/heat-scoring-rubric.md` + 项目 memory。

- **5 层情报栈**（PR #31，固化进 `ARCHITECTURE §0.5`）：L1 市场热 / L2 信号(Nicole 核心 `engine/`) / L3 ESG Fit / L4 竞品（L3/L4 均 Codex 本职）/ L5 反馈闭环。全系统标准心智模型。
- **RSS/微信新闻源**（PR #30）：`engine/sources/rss.py` + `capex_signals` 预接 8 号（§11）。
- **黄金评估集 + 抽取接地**（PR #32）：`tests/golden/` 回归门禁 + `conditions.matched_sentence`。
- **热力图对齐 ESG 业务 + heat 可复现/可派生**（PR #33，明细 memory `heat-rubric-l2`）：+9 赛道/新板块「过程工业」；`docs/heat-scoring-rubric.md`（指标→档、Capex 含出海）；全 14 老赛道按 2026 真数据重评（纠偏 FAI 62→46 等）；L2 事件派生热度 `engine/industry_heat.py`（并行印证层）；泛词降权 `weak` 词层；3 新工况（空分/核电/环保）。
- **本体实例化 · ER + 动能闭环**（PR #34，明细 memory `ontology-instantiation`）：`scripts/unresolved_owners.py` 未解析业主报告 + 提升 6 真公司进 registry（去碎片化 L2 簇/L5 回流）；`engine/feedback.py` 处置→winnability 消费机制（gated 无标签=no-op）。
- **heat 逻辑纠偏 + L2 覆盖徽标**（PR #37/#38）：按 /goal 审计全 29 赛道「证据够+打分符合行业逻辑」——p1出海/p3融资/f3消费 3 个金融/消费先行指标从虚高72重评（C 诚实压低=离买阀≥2步，f3→49.7 等）；`index.html` 每赛道加 **L2 覆盖徽标**（✓有货/◑热但无货/○无工况/·待数据），把"热度→有没有线索可打"的 L1→L2 断裂一眼可见。

## 13. 下一步 / 未决（按优先级）

**🔴 下一个真坎 = 持久对象存储（跨 run 稳定身份 + 对象历史）** —— CTO review 步骤1 完整版、"从 demo 到 Foundry"的门槛。现在对象活不过一次 run（`event_id=md5`、`entities.yml` 静态）。架构大改，需单独立项（决策18，不擅自开）。

**闭环 / heat 自动刷新（非本仓纯前端能独立完成）**
- **CI 接线**：`build_industry_heat.py` + `build_ontology.py` 并入 B0 数据 CI（Codex），L2 信号/图谱才上线、heat 才自动刷新。
- **KV→`data/feedback.json` 导出**：闭环输入端（消费端已建，PR #34）；等处置标签攒够（决策15）。
- **源扩量**（§11）：微信中转（用户订 wechat2rss 换 8 个 `TODO-WECHAT-RELAY`）+ `zyzhan.py` 直抓 → L2 覆盖成熟、heat 的 α 才能下调。**进度可视化锚点已就位**：热力图 L2 覆盖徽标（PR #38）——目标是把 ◑热但无货/○无工况 逐步变 ✓有货，即"补源"的验收信号。现状 9 有货 / 6 热但无货 / 14 无工况（多数 TOP 热行业无线索可打，这就是"提升销售"的头号瓶颈）。

**本体深化（CTO review 剩余）**
- 边升一等公民：`spec_position` 带 `{source, asof, confidence}`（步骤3）。
- 逐子分 provenance：heat 每个 C/D/Pol/P 挂 指标+来源+asof（rubric §7）。

**小改 / 遗留**
- `nav.js` 顶竞品 Bürkert 品牌｜旗舰页 events/ontology 主导航进不去｜`ontology.html` 零错误处理。
- GNE 全文富化（`git stash: GNE-enrich-parked`，未提交，L1→L2 毕业桥）｜events.html 显示 matched_sentence。
- martinfowler 剩余：运行质量日志 `_runlog.jsonl`｜接 DeepSeek/RAG 前先建 RAGAS 评估+供应商兜底（写 ROADMAP）｜「引擎保持确定性」立原则。
