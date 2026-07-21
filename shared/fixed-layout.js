(() => {
  "use strict";

  const root = document.documentElement;

  // bottom-nav.js を読み込まないページでもピンチを無効化するためのフォールバック。
  if (!window.__ZENRACE_PINCH_DISABLED__) {
    window.__ZENRACE_PINCH_DISABLED__ = true;
    const stopPinch = (event) => {
      if (event.touches && event.touches.length < 2) return;
      event.preventDefault();
      event.stopImmediatePropagation();
    };
    for (const type of ["touchstart", "touchmove"]) {
      window.addEventListener(type, stopPinch, { capture: true, passive: false });
    }
    for (const type of ["gesturestart", "gesturechange", "gestureend"]) {
      window.addEventListener(type, (event) => {
        event.preventDefault();
        event.stopImmediatePropagation();
      }, { capture: true, passive: false });
    }
    window.addEventListener("wheel", (event) => {
      if (!event.ctrlKey) return;
      event.preventDefault();
      event.stopImmediatePropagation();
    }, { capture: true, passive: false });
  }

  root.style.setProperty("--page-content-scale", "1");

  const syncVisualViewport = () => {
    const viewport = window.visualViewport;
    const layoutHeight = Math.max(root.clientHeight, window.innerHeight || 0);
    const top = viewport ? Math.max(0, viewport.offsetTop) : 0;
    const visibleHeight = viewport ? viewport.height : (window.innerHeight || layoutHeight);
    const bottom = viewport ? Math.max(0, layoutHeight - visibleHeight - top) : 0;
    root.style.setProperty("--visual-top", `${Math.round(top)}px`);
    root.style.setProperty("--visual-bottom", `${Math.round(bottom)}px`);
  };

  syncVisualViewport();
  window.addEventListener("resize", syncVisualViewport, { passive: true });
  window.addEventListener("orientationchange", () => setTimeout(syncVisualViewport, 80), { passive: true });
  if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", syncVisualViewport, { passive: true });
    window.visualViewport.addEventListener("scroll", syncVisualViewport, { passive: true });
  }

  const shell = document.querySelector("[data-zenrace-pinch-shell]");
  const sizer = document.querySelector("[data-zenrace-pinch-sizer]");
  const stage = document.querySelector("[data-zenrace-pinch-stage]");
  if (!shell || !sizer || !stage) return;

  let baseWidth = 0;
  const measure = (resetWidth = false) => {
    if (resetWidth || !baseWidth) baseWidth = shell.clientWidth;
    stage.style.width = `${baseWidth}px`;
    requestAnimationFrame(() => {
      const contentWidth = Math.max(baseWidth, stage.scrollWidth);
      const contentHeight = Math.max(1, stage.scrollHeight);
      sizer.style.width = `${Math.max(shell.clientWidth, contentWidth)}px`;
      sizer.style.height = `${Math.max(shell.clientHeight, contentHeight)}px`;
      shell.scrollLeft = Math.min(shell.scrollLeft, Math.max(0, sizer.scrollWidth - shell.clientWidth));
      shell.scrollTop = Math.min(shell.scrollTop, Math.max(0, sizer.scrollHeight - shell.clientHeight));
    });
  };

  if ("ResizeObserver" in window) {
    const observer = new ResizeObserver(() => measure(false));
    observer.observe(stage);
  }
  window.addEventListener("resize", () => measure(true), { passive: true });
  window.addEventListener("load", () => measure(true), { once: true });
  measure(true);
})();
