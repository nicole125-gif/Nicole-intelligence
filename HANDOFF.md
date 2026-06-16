# HANDOFF — Nicole Intelligence ｜ 接手入口

> **新 Claude 会话从这里开始。** 三件套分工：
> - **HANDOFF.md**（本文）— 项目状态、关键决策、挂起未知、怎么跑、互动纪律。
> - **ARCHITECTURE.md** — 系统结构、模块职责、数据流、事件 schema、源健康。
> - **ROADMAP.md** — 下一步路线（P0/P1/P2）、框架 5 洞状态、阻塞依赖。
>
> 另：方法论北极星 `docs/INTELLIGENCE_OS.md`；实现计划 `~/.claude/plans/https-www-esgvalve-cn-gleaming-stroustrup.md`；项目记忆 `~/.claude/projects/.../memory/esg-event-engine.md`。
> 最后更新 2026-06-16 ｜ 引擎/本体工作（里程碑1 + winnability + O1 + O4）已合进 `main`（PR #6，merge `2d9c99b`）｜ 自动化/WIP 仍在 `automation/monthly-update`。

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
- **⚠ 处置闭环上线前置（阻塞，用户做）**：**Vercel 控制台 → Storage → 建 KV store**（自动注入 `KV_REST_API_URL`/`KV_REST_API_TOKEN`），然后 `vercel deploy`。没建 KV，处置写入会 500。本机无 KV 凭证→真写入链路本机验不了，只验过 UI/交互。
- **⚠ 处置闭环已知风险**：①`@vercel/kv` 版本写的 `^3.0.0`，Vercel 构建时若不兼容需调；②无鉴权，有 URL 即可读写处置（内部工具可接受，要收紧加共享口令）；③`kv.keys('disp:*')` 扫全键，量级到数千条需改维护 id 集合；④部署绑死 Vercel（GitHub Pages 出局）。
- **✅ O4 本体合并已落地**（2026-06-16，框架 P1.5 第四阶）：把孤儿化的两套富本体折叠进 `config/entities.yml` 的 `profile:` 块——OEM（楚天/森松/东富龙）带 match_keywords/target_roles/esg_products/competitor_products/capex_ratio（源 p4_opportunity_map）；竞品+self 带 avg_threat_level/product_count/high_threat_products（源 products_analysis：Bürkert4.3/Gemü4.0/ESG2.7）。`load_registry` 本就按 id 存整条 dict，**`get(id)` 自动带出 profile，零 join 代码**；`resolve()` 仍轻量（profile 不进每条 event 的 owner）。终结双本体，entities.yml 升为实体数据单一语义层。**`p4_opportunity_map.yml` 仍被 legacy `scripts/p4_opportunities.py` 读，保留不删**。38 测试全过（+2）。
- **✅ O2 spec 位切片 A 已落地**（2026-06-16，框架 P1.5 第二阶/承重边）：头号挂起已解（§5）——**ESG 只进东富龙 BOM，楚天/森松未进**。`config/entities.yml` 三 OEM 加 `spec_position`（东富龙 `in`/楚天/森松 `target`）；`build.py` 当 owner 解析为 OEM 实体时沿 owner→OEM 边取 spec 位，喂 winnability（in +0.2 顺风 / target −0.1 需 design-in）+ 分流 action（in→盯订单簿；target→主推 design-in）；event 加 `spec_position` 字段。实测东富龙扩产 win 0.5 > 通用 0.3 > 楚天 0.2。43 测试全过（+5）。**切片 B（headline 具名识别买方 OEM）后置**——多数 event 不点名 OEM。
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
python3 -m unittest tests.test_engine        # 24 个离线单测
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
15. **处置先采集、后消费**（用户明确）：赢面是冷启动，要先攒"赢/输给谁"标签才谈得上校准，所以这轮不动 `engine/winnability.py`。

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

- **✅ 引擎/本体工作已合进 `main`**（2026-06-16，PR #6，merge commit `2d9c99b`）：从 `main` 干净切 `feat/event-engine`，cherry-pick 11 个引擎 commit（里程碑1引擎 + winnability v1 + O1 + O4 + 三件套 docs + biosynthesis 修复 + research inbox/处置采集层），27 文件 / +2401，38 测试全过。已 rebase 过 origin/main（只 `.gitignore` add/add 取并集）、合并、删分支（本地+远端）。**main 自此为引擎数据的权威。**
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
