(() => {
  if (customElements.get("zenrace-bottom-nav")) return;

  const scriptUrl = document.currentScript?.src || window.location.href;
  const appRoot = new URL("../", scriptUrl);
  const ROUTES = [
    {
      id: "home",
      label: "ホーム",
      path: "",
      icon: `<svg viewBox="0 0 96 96" aria-hidden="true">
          <path d="M10 47.5L48 14l38 33.5" fill="none" stroke="currentColor" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M20 45v36h20V58h16v23h20V45L48 20 20 45z" fill="currentColor"/>
        </svg>`,
    },
    {
      id: "schedule",
      label: "開催情報",
      path: "gradedraces/",
      icon: `<svg viewBox="0 0 96 96" aria-hidden="true">
          <rect x="15" y="17" width="66" height="64" rx="8" fill="none" stroke="currentColor" stroke-width="8"/>
          <path d="M15 33h66" stroke="currentColor" stroke-width="8" stroke-linecap="round"/>
          <path d="M31 12v16M65 12v16" stroke="currentColor" stroke-width="8" stroke-linecap="round"/>
          <rect x="28" y="44" width="10" height="10" rx="2" fill="currentColor"/>
          <rect x="43" y="44" width="10" height="10" rx="2" fill="currentColor"/>
          <rect x="58" y="44" width="10" height="10" rx="2" fill="currentColor"/>
          <rect x="28" y="59" width="10" height="10" rx="2" fill="currentColor"/>
          <rect x="43" y="59" width="10" height="10" rx="2" fill="currentColor"/>
          <rect x="58" y="59" width="10" height="10" rx="2" fill="currentColor"/>
        </svg>`,
    },
    {
      id: "vote",
      label: "投票",
      path: "vote/",
      featured: true,
      icon: `<svg viewBox="0 0 96 96" aria-hidden="true">
          <rect x="15" y="18" width="66" height="60" rx="7" fill="none" stroke="currentColor" stroke-width="8"/>
          <path d="M28 33h40M28 49h18M28 64h18" stroke="currentColor" stroke-width="7" stroke-linecap="round"/>
          <rect x="55" y="47" width="16" height="20" rx="3" fill="currentColor"/>
        </svg>`,
    },
    {
      id: "onair",
      label: "ONAIR",
      path: "onair/",
      icon: `<svg viewBox="0 0 112 96" aria-hidden="true">
          <rect x="15" y="17" width="82" height="55" rx="5" fill="none" stroke="currentColor" stroke-width="8"/>
          <path d="M27 29h28L27 57V29z" fill="currentColor"/>
          <path d="M56 72v10M39 84h34" stroke="currentColor" stroke-width="8" stroke-linecap="round"/>
        </svg>`,
    },
    {
      id: "mypage",
      label: "マイページ",
      path: "mypage/",
      icon: `<svg viewBox="0 0 96 96" aria-hidden="true">
          <circle cx="48" cy="27" r="18" fill="currentColor"/>
          <path d="M17 83c2.5-20 15-33 31-33s28.5 13 31 33H17z" fill="currentColor"/>
        </svg>`,
    },
  ];

  class ZenraceBottomNav extends HTMLElement {
    connectedCallback() {
      if (this.shadowRoot) return;
      const active = this.getAttribute("active") || "home";
      const available = new Set((this.getAttribute("available") || "home schedule").split(/[\s,]+/).filter(Boolean));
      available.add(active);
      const standalone = window.matchMedia?.("(display-mode: standalone)").matches || window.navigator.standalone === true;

      const shadow = this.attachShadow({ mode: "open" });
      const items = ROUTES.map((route) => {
        const isActive = route.id === active;
        const isAvailable = available.has(route.id);
        const href = new URL(route.path, appRoot).href;
        const classes = [
          'item',
          isActive ? 'active' : '',
          route.featured ? 'featured' : '',
          !isAvailable ? 'disabled' : '',
        ].filter(Boolean).join(' ');
        const ariaCurrent = isActive ? 'aria-current="page"' : '';
        const ariaDisabled = !isAvailable ? 'aria-disabled="true" tabindex="-1"' : '';
        return `<a class="${classes}" href="${href}" ${ariaCurrent} ${ariaDisabled}><span class="icon">${route.icon}</span><span class="label">${route.label}</span></a>`;
      }).join('');

      shadow.innerHTML = `
        <style>
          :host{
            --safe:max(env(safe-area-inset-bottom),0px);
            position:fixed;left:0;right:0;bottom:var(--visual-bottom,0px);z-index:5000;display:block;
            height:calc(${standalone ? '58px' : '62px'} + var(--safe));
            transform:translateZ(0);backface-visibility:hidden;
            font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Yu Gothic UI","Hiragino Kaku Gothic ProN",Meiryo,sans-serif;
            -webkit-text-size-adjust:100%;text-size-adjust:100%;
          }
          *{box-sizing:border-box}
          nav{
            width:100%;height:100%;display:grid;grid-template-columns:repeat(5,minmax(0,1fr));align-items:start;
            padding:4px 4px var(--safe);
            color:#d7dce3;
            background:
              linear-gradient(110deg,rgba(213,171,67,.08),transparent 27%,transparent 72%,rgba(213,171,67,.07)),
              linear-gradient(180deg,#151515,#070707);
            border-top:1px solid rgba(213,171,67,.4);
            box-shadow:0 -5px 18px rgba(0,0,0,.25);
          }
          .item{
            min-width:0;height:${standalone ? '53px' : '57px'};display:flex;flex-direction:column;align-items:center;justify-content:center;
            gap:4px;color:inherit;text-decoration:none;-webkit-tap-highlight-color:transparent;touch-action:manipulation;
            position:relative;border-radius:12px;
          }
          .item.featured{
            color:#f3e1ae;
          }
          .item.featured::before{
            content:"";position:absolute;left:2px;right:2px;top:2px;bottom:2px;
            border-radius:16px;
            border:1px solid rgba(240,204,112,.52);
            background:
              linear-gradient(115deg,rgba(255,255,255,.12),transparent 28%,transparent 68%,rgba(240,204,112,.10)),
              radial-gradient(circle at 50% 0%,rgba(240,204,112,.24),transparent 58%),
              linear-gradient(180deg,rgba(240,204,112,.15),rgba(240,204,112,.045));
            box-shadow:
              inset 0 1px 0 rgba(255,255,255,.18),
              inset 0 -1px 0 rgba(0,0,0,.28),
              0 0 0 1px rgba(240,204,112,.08),
              0 5px 16px rgba(0,0,0,.22),
              0 0 18px rgba(240,204,112,.13);
            z-index:0;
          }
          .item > *{position:relative;z-index:1}
          .item.featured .icon{transform:translateY(-1px) scale(1.04)}
          .icon{width:${standalone ? '25px' : '27px'};height:${standalone ? '25px' : '27px'};display:grid;place-items:center;flex:none}
          svg{width:100%;height:100%;display:block;overflow:visible}
          .label{font-size:${standalone ? '9.5px' : '10px'};line-height:1;font-weight:750;white-space:nowrap;letter-spacing:-.02em}
          .active{color:#f0cc70}
          .active .icon{filter:drop-shadow(0 0 5px rgba(213,171,67,.28))}
          .active .label{font-weight:900}
          .disabled{opacity:.38;pointer-events:none}
          @media(max-width:380px){
            .icon{width:25px;height:25px}
            .label{font-size:9px}
            .item{gap:3px}
          }
        </style>
        <nav aria-label="メインナビゲーション">${items}</nav>
      `;
    }
  }

  customElements.define("zenrace-bottom-nav", ZenraceBottomNav);
})();
