# HANDOFF — Nicole Intelligence ｜ 接手入口

> **新 Claude 会话从这里开始。** 三件套分工：
> - **HANDOFF.md**（本文）— 项目状态、关键决策、挂起未知、怎么跑、互动纪律。
> - **ARCHITECTURE.md** — 系统结构、模块职责、数据流、事件 schema、源健康。
> - **ROADMAP.md** — 下一步路线（P0/P1/P2）、框架 5 洞状态、阻塞依赖。
>
> 另：方法论北极星 `docs/INTELLIGENCE_OS.md`；实现计划 `~/.claude/plans/https-www-esgvalve-cn-gleaming-stroustrup.md`；项目记忆 `~/.claude/projects/.../memory/esg-event-engine.md`。
> 最后更新 2026-06-10 ｜ 分支 `automation/monthly-update` ｜ **全部新工作未 commit。**

---

## 1. 项目一句话

阀门企业 **ESG 青岛精锐**（esgvalve.cn，旗舰角座阀，气动卫生级）的情报系统。本质：在客户下单前 **6–18 个月捕捉会触发流体采购的 Capex 事件**，指明该找谁/卖什么阀/何时/多少钱。正在**从「赛道热度中心」重构为「事件中心」**。

## 2. 当前状态（一屏）

- **里程碑 1（后端事件引擎）已完成 + 真数据验收通过**：`engine/` 包（自包含），cninfo 实时 ~40 条真实事件，核心工况均≥3，`--strict` 健康检查过。
- **✅ P0#1 est_value 分档已实现并验证**（2026-06-10）：value_band 大/中/小/未知，把"标题没写金额的大项目"（璞泰来/东华科技）从沉底捞到 Top；**24 单测全过**。详见 ROADMAP P0#1。
- **整体框架 review 已做完**（麦肯锡战略 + CEO 双视角），制药赛道分析（首个试验田）已做完。结论见第 4 节 + ROADMAP。
- **✅ CDE 优先审评源已接**（2026-06-10，opt-in `--with-cde`）：`engine/sources/cde.py` 用 Playwright 过瑞数 WAF + 截获 `getPriorityApprovalList` API，产出带公司名的制药 pipeline 事件（band=未知/低 rank 的早期预警）。
- **✅ winnability 赢面轴 v1 已实现**（2026-06-10）：`engine/winnability.py`，rank_score 第四因子（绿地无在位 + 工况级竞品密度）。锂电/橡塑升、技改棕地/Gemü主场降。28 测试全过。**注意已知局限**：生物合成/发酵被一刀切进"制药竞品high"误降，是 v2 细化项（见 ROADMAP P1#2）。
- **⛔ 源攻坚已到头（2026-06-10 逐个实测）**：cninfo✅/CDE✅ 已接；**eia(SSL/地域封)、ccgp(频繁访问反爬+本机IP已限)、NMPA(瑞数严格实例，挑战解完仍 400 拒 headless) 全在反爬墙后，本无头开发机破不了**。不是做不了，是**得在 CI/生产环境**（非 headless / 干净 IP / 反检测）做——已标 ROADMAP。**别在本机继续刚这几个源。**
- **下一个自然动作（强烈推荐）**：**前端事件队列（研判信箱）**——把 `data/events/<date>.json` 渲染成排序队列（rank/赢面/工况/阀型/业主/动作/来源链接），复用老系统 CSS 主题。这是当初定的"第一交付物：个人研判工具"，也是**最大的未兑现价值**（引擎产出至今无人能看/用）。备选：处置闭环、赢面 v2（卡 spec 位）。
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

## 5. ⏸ 头号挂起未知（等用户 Nicole 确认）

**ESG 现在有没有进楚天/森松/东富龙的标准 BOM（spec 位）？**
- 已进 → 盯装备商订单簿立刻有用，它们出海=ESG 顺风；
- 没进 → 制药第一优先级是先拿下设计导入，否则其扩产/出海全便宜 Gemü。
- **不要替用户假设，等她来定。**

## 6. 互动纪律（用户偏好）

- 中文交流、代码/commit 用英文；复杂任务先出计划再动手；做减法、surgical change、不过度抽象、默认不加注释。
- **外向/不可逆动作（commit/push/发外部）先确认**；不 force push main、不 skip hooks。
- **git：精确 stage 目标文件，绝不 `git add -A`**；commit 前给清单确认。

## 7. git 现状

- **已提交 checkpoint**（2026-06-10，未 push，分支 `automation/monthly-update`）：
  `d3b2787 feat(engine)`（engine/ 含 est_value 分档 + CDE + esg_conditions.yml + test_engine + .gitignore）、`e234ac8 docs`（HANDOFF/ARCHITECTURE/ROADMAP）。
- **⏳ 待 commit（winnability 批次，commit 之后新增）**：`engine/winnability.py`(新) + `engine/{build,ranking,conditions}.py`、`config/esg_conditions.yml`(加 competitor_density)、`tests/test_engine.py`、三件套文档 的修改。`data/events/` 已 gitignore。
- **会话前本地 WIP（勿打包）**：`M` fetch_pharma / fetch_rss / scripts/update_news / monthly_update + 2 workflow；`??` scripts/p4_opportunities.py、completeness_audit.py、config/p4_opportunity_map.yml、tests/test_intelligence_pipeline.py、.gtrconfig、agent.md、pulse_mcp_server.py、data/watchlist.json、docs/。
- 提交纪律：精确 stage、commit 前给清单、不 push。

## 8. 关键参照文件

- `scripts/p4_opportunities.py` — 事件模型黄金蓝本。
- `fetch_pharma.py` — 三源抓取骨架 + 制药 NMPA/CDE 源代码（可复活）。
- `config/p4_opportunity_map.yml` — 楚天/东富龙/森松客户档案 + 竞品 + capex 系数。
- `customers.html` L239-284 — HEATMAP 8 制药子赛道真实景气数据。
- `data/products_analysis.json` — 竞品威胁：Bürkert 4.3 / Gemü 4.0 / ESG 2.7。
