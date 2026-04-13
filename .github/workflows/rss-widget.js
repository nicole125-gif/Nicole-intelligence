/**
 * PULSE 2026 — RSS News Widget
 * 用法：在各垂直页面 HTML 里加入：
 *   <div id="rss-feed" data-vertical="semiconductor"></div>
 *   <script src="/js/rss-widget.js"></script>
 */

(function () {
  const BASE_URL =
    "https://nicole125-gif.github.io/Nicole-intelligence/data/rss";

  // ── 工具函数 ──────────────────────────────────────────
  function relativeTime(isoString) {
    const diff = (Date.now() - new Date(isoString).getTime()) / 1000;
    if (diff < 3600)  return `${Math.floor(diff / 60)}分钟前`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`;
    return `${Math.floor(diff / 86400)}天前`;
  }

  function langBadge(lang) {
    return lang === "zh"
      ? `<span class="rss-badge rss-badge--zh">中</span>`
      : `<span class="rss-badge rss-badge--en">EN</span>`;
  }

  // ── 渲染单条新闻 ──────────────────────────────────────
  function renderItem(item) {
    return `
      <article class="rss-item">
        <div class="rss-item__meta">
          ${langBadge(item.lang)}
          <span class="rss-item__source">${item.source}</span>
          <span class="rss-item__time">${relativeTime(item.pub_date)}</span>
        </div>
        <a class="rss-item__title" href="${item.url}" target="_blank" rel="noopener">
          ${item.title}
        </a>
        ${item.summary
          ? `<p class="rss-item__summary">${item.summary}</p>`
          : ""}
      </article>`;
  }

  // ── 渲染整个 widget ───────────────────────────────────
  function renderWidget(container, data) {
    const updatedAt = new Date(data.updated_at).toLocaleString("zh-CN", {
      timeZone: "Asia/Shanghai",
      month: "numeric",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });

    container.innerHTML = `
      <section class="rss-widget">
        <div class="rss-widget__header">
          <span class="rss-widget__dot" style="background:${data.color}"></span>
          <h3 class="rss-widget__title">行业动态 · ${data.vertical_name}</h3>
          <span class="rss-widget__updated">更新于 ${updatedAt}</span>
        </div>
        <div class="rss-widget__list">
          ${data.items.length
            ? data.items.map(renderItem).join("")
            : `<p class="rss-empty">暂无近期动态</p>`}
        </div>
      </section>`;
  }

  // ── 加载数据 ──────────────────────────────────────────
  async function init() {
    const container = document.getElementById("rss-feed");
    if (!container) return;

    const vertical = container.dataset.vertical;
    if (!vertical) {
      console.warn("[RSS Widget] data-vertical 未设置");
      return;
    }

    container.innerHTML = `<p class="rss-loading">Loading news…</p>`;

    try {
      const res = await fetch(`${BASE_URL}/${vertical}.json`, {
        cache: "no-cache",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      renderWidget(container, data);
    } catch (err) {
      console.error("[RSS Widget]", err);
      container.innerHTML = `<p class="rss-error">⚠ 动态加载失败，请稍后刷新</p>`;
    }
  }

  // DOM ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
