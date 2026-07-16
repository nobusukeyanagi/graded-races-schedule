(() => {
  class ZenraceRaceInfo extends HTMLElement {
    connectedCallback() {
      if (this.dataset.ready === "true") return;
      this.dataset.ready = "true";
      this.innerHTML = `
        <section class="shared-race-info" aria-label="浜松12R レース情報">
          <div class="race-info-primary">
            <strong class="race-info-venue">浜松</strong>
            <span class="race-info-number">12R</span>
            <span class="race-info-icon auto" aria-label="オートレース"></span>
            <span class="race-info-icon sg" aria-label="SG">SG</span>
          </div>
          <h1 class="race-info-title">第39回全日本選抜オートレース</h1>
          <div class="race-info-status">
            <strong class="race-info-final">優勝戦</strong>
            <span class="race-info-time"><span class="race-info-time-label">投票締切</span><time datetime="2026-02-23T16:41:00+09:00">16:41</time></span>
            <span class="race-info-time"><span class="race-info-time-label">発走</span><time datetime="2026-02-23T16:41:00+09:00">16:41</time></span>
          </div>
          <p class="race-info-date">2026年2月23日(月祝)　最終日　5,100m</p>
        </section>`;
    }
  }
  if (!customElements.get("zenrace-race-info")) {
    customElements.define("zenrace-race-info", ZenraceRaceInfo);
  }
})();
