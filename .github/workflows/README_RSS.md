# PULSE 2026 — RSS 自动抓取系统

## 文件清单

```
├── rss_sources.json          # RSS 源配置（行业垂直 + URL）
├── fetch_rss.py              # Python 抓取脚本
├── .github/
│   └── workflows/
│       └── rss_fetch.yml     # GitHub Actions 定时任务
├── js/
│   └── rss-widget.js         # 前端读取 + 渲染
├── css/
│   └── rss-widget.css        # Widget 样式
└── data/
    └── rss/
        ├── index.json         # 汇总索引（自动生成）
        ├── macro.json         # 宏观经济（自动生成）
        ├── semiconductor.json # 半导体（自动生成）
        ├── ai_liquid_cooling.json
        ├── hydrogen.json
        ├── pharma_equipment.json
        ├── food_beverage.json
        └── mass_spec.json
```

---

## 部署步骤

### 第一步：把文件放到 repo

1. `rss_sources.json` → repo 根目录
2. `fetch_rss.py` → repo 根目录
3. `rss_fetch.yml` → `.github/workflows/rss_fetch.yml`
4. `rss-widget.js` → `js/rss-widget.js`
5. `rss-widget.css` → `css/rss-widget.css`
6. 创建空目录 `data/rss/`（放一个 `.gitkeep`）

### 第二步：首次手动触发

GitHub repo → Actions → "PULSE 2026 — RSS Daily Fetch" → Run workflow

确认 data/rss/ 下生成了 JSON 文件后继续。

### 第三步：在各垂直页面嵌入 Widget

在对应页面 HTML 的合适位置加入：

```html
<!-- 在 <head> 里 -->
<link rel="stylesheet" href="/css/rss-widget.css">

<!-- 在页面内容区 -->
<div id="rss-feed" data-vertical="semiconductor"></div>

<!-- 在 </body> 前 -->
<script src="/js/rss-widget.js"></script>
```

`data-vertical` 可选值：
- `macro`
- `semiconductor`
- `ai_liquid_cooling`
- `hydrogen`
- `pharma_equipment`
- `food_beverage`
- `mass_spec`

---

## 运行时间

GitHub Actions 每天 **北京时间 08:00** 自动抓取。
也可以在 Actions 页面手动点 **Run workflow** 即时更新。

如需调整时间，编辑 `rss_fetch.yml` 里的 cron 表达式：
```yaml
- cron: "0 0 * * *"   # UTC 00:00 = 北京 08:00
```

---

## 调试单个垂直

手动触发时在 "target_vertical" 输入框填入垂直 ID，例如 `semiconductor`，
则只抓取该垂直，速度更快。

---

## 添加新 RSS 源

编辑 `rss_sources.json`，在对应垂直的 `sources` 数组里添加：

```json
{
  "name": "来源名称",
  "url": "https://example.com/rss.xml",
  "lang": "zh",
  "priority": 1
}
```

`priority` 越小越优先抓取（1=最高）。

---

## 注意事项

- 部分 RSS 源可能因网络限制在 GitHub Actions（境外服务器）无法访问（尤其国内源）
- 如发现某源长期无数据，可在 `rss_sources.json` 里删除或换源
- `data/rss/` 目录下的 JSON 文件会随每次 workflow 运行自动更新并 git commit
