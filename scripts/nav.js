/* ══════════════════════════════════════════════
   PULSE 2026 · Shared Navigation
   Usage: <script src="scripts/nav.js"></script>
          injectNav('page-key', '#accentColor');
   ══════════════════════════════════════════════ */

const NAV_PAGES = [
  { key:'index',  href:'index.html',          label:'总览',       en:'Overview' },
  { key:'macro',  href:'macro.html',           label:'宏观脉搏',   en:'Macro' },
  { key:'liquid', href:'liquid.html',          label:'AI 液冷',    en:'AI Cooling' },
  { key:'semi',   href:'semiconductor.html',   label:'半导体 SBU', en:'Semiconductor' },
  { key:'mscc',   href:'mscc.html',            label:'质谱色谱',   en:'MS·CC' },
  { key:'pharma', href:'pharma.html',          label:'制药装备',   en:'Pharma' },
  { key:'food',   href:'food.html',            label:'食品饮料',   en:'F&B' },
  { key:'hydro',  href:'hydrogen.html',        label:'氢能行业',   en:'Hydrogen' },
  { key:'cust',   href:'customers.html',       label:'客户监控',   en:'Customers' },
  { key:'comp',   href:'competitor.html',      label:'竞品监控',   en:'Competitors' },
];

function injectNav(activeKey, accent) {
  // Set accent color
  const ac = accent || '#E30613';
  document.documentElement.style.setProperty('--accent', ac);

  // Build nav links HTML
  const linksHtml = NAV_PAGES.map(p =>
    `<a href="${p.href}" class="nav-link${p.key === activeKey ? ' active' : ''}" data-page="${p.key}">${p.label}</a>`
  ).join('\n      ');

  // Build hamburger links
  const mobileLinksHtml = NAV_PAGES.map(p =>
    `<a href="${p.href}" class="nav-link${p.key === activeKey ? ' active' : ''}" data-page="${p.key}">${p.label}</a>`
  ).join('\n      ');

  // Insert nav HTML
  const nav = document.createElement('nav');
  nav.id = 'site-nav';
  nav.innerHTML = `
    <div class="nav-inner">
      <div class="nav-brand">
        <span class="nav-dot"></span>
        <span class="nav-logo">BÜRKERT</span>
        <span class="nav-sub">· PULSE 2026</span>
      </div>
      <div class="nav-links">
        ${linksHtml}
      </div>
      <div class="nav-status">
        <span class="status-dot"></span>
        <span class="status-txt">LIVE</span>
      </div>
      <button class="nav-hamburger" id="nav-hamburger" aria-label="Menu">&#9776;</button>
    </div>
    <div class="nav-mobile-menu" id="nav-mobile-menu">
      ${mobileLinksHtml}
    </div>
    <div class="nav-progress" id="nav-progress"></div>
  `;
  document.body.prepend(nav);

  // Hamburger toggle
  const hamburger = document.getElementById('nav-hamburger');
  const mobileMenu = document.getElementById('nav-mobile-menu');
  if (hamburger && mobileMenu) {
    hamburger.addEventListener('click', () => {
      mobileMenu.classList.toggle('open');
    });
    // Close on link click
    mobileMenu.querySelectorAll('.nav-link').forEach(a => {
      a.addEventListener('click', () => mobileMenu.classList.remove('open'));
    });
  }

  // Scroll progress
  const bar = document.getElementById('nav-progress');
  if (bar) {
    const update = () => {
      const h = document.documentElement.scrollHeight - window.innerHeight;
      bar.style.width = h > 0 ? (window.scrollY / h * 100) + '%' : '0%';
    };
    window.addEventListener('scroll', update, { passive: true });
    update();
  }
}
