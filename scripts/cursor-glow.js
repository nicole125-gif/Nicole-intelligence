/* ══════════════════════════════════════════════
   PULSE 2026 · Cursor Glow Effect
   Usage: <script src="scripts/cursor-glow.js"></script>
   Requires: <div id="cursor-glow"></div> in body
   ══════════════════════════════════════════════ */

(function() {
  const glow = document.getElementById('cursor-glow');
  if (!glow) return;

  let mx = 0, my = 0, gx = 0, gy = 0;

  document.addEventListener('mousemove', function(e) {
    mx = e.clientX;
    my = e.clientY;
  });

  function tick() {
    gx += (mx - gx) * 0.12;
    gy += (my - gy) * 0.12;
    glow.style.left = gx + 'px';
    glow.style.top = gy + 'px';
    requestAnimationFrame(tick);
  }
  tick();

  // Hide on mobile (no cursor)
  if ('ontouchstart' in window) {
    glow.style.display = 'none';
  }
})();
