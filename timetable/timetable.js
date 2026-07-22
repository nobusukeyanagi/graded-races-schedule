(() => {
  "use strict";

  const TARGET_DATE = "2026-02-23";
  const TARGET_HOUR = 16;
  const board = document.getElementById("timetableBoard");
  const toolbar = document.querySelector("[data-zenrace-date-selector]");
  const shell = document.querySelector(".zenrace-content-shell");
  const races = Array.isArray(window.ZENRACE_RACES) ? window.ZENRACE_RACES : [];
  const FEATURED_RACES = new Set([
    "keirin:熊本:12R",
    "auto:浜松:12R",
    "nar:名古屋:7R",
  ]);
  const isFeaturedRace = (race) => FEATURED_RACES.has(`${race.sport}:${race.venue}:${race.race}`);

  const timeParts = (value) => {
    const match = /^(\d{1,2}):(\d{2})$/.exec(String(value || ""));
    if (!match) return null;
    return { hour: Number(match[1]), minute: Number(match[2]) };
  };

  const raceNumber = (race) => Number.parseInt(String(race.race), 10) || 0;
  const raceMinutes = (race) => {
    const parts = timeParts(race.time);
    return parts ? (parts.hour * 60) + parts.minute : Number.POSITIVE_INFINITY;
  };

  const showPreparingToast = () => {
    let toast = document.querySelector(".timetable-toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.className = "timetable-toast";
      toast.setAttribute("role", "status");
      toast.setAttribute("aria-live", "polite");
      document.body.append(toast);
    }
    toast.textContent = "遷移先ページは準備中です";
    toast.classList.add("is-visible");
    window.clearTimeout(Number(toast.dataset.timer || 0));
    toast.dataset.timer = String(window.setTimeout(() => toast.classList.remove("is-visible"), 1800));
  };

  const raceCard = (race) => {
    const parts = timeParts(race.time);
    const minute = String(parts?.minute ?? "").padStart(2, "0");
    const featured = isFeaturedRace(race);
    const label = `${race.venue} ${race.race} ${race.time}${featured ? " 注目レース" : ""}`;
    return `
      <a class="timetable-race sport-${race.sport}${featured ? " featured-race" : ""}" href="#" aria-label="${label}">
        <span class="race-minute">${minute}</span>
        <span class="race-sport-line" aria-hidden="true"></span>
        <span class="race-detail"><span class="race-venue">${race.venue}</span><span class="race-no">${race.race}</span></span>
      </a>`;
  };

  const buildHourGroups = () => {
    const validRaces = races
      .filter((race) => timeParts(race.time))
      .sort((a, b) => (raceMinutes(a) - raceMinutes(b)) || (raceNumber(a) - raceNumber(b)));
    const grouped = new Map();

    validRaces.forEach((race) => {
      const { hour } = timeParts(race.time);
      if (!grouped.has(hour)) grouped.set(hour, []);
      grouped.get(hour).push(race);
    });

    const hourMarkup = [...grouped.entries()]
      .sort(([a], [b]) => a - b)
      .map(([hour, hourRaces]) => `
        <section class="hour-group${hour === TARGET_HOUR ? " current-hour" : ""}" data-hour="${hour}" aria-label="${hour}時台">
          <div class="hour-label">${hour}</div>
          <div class="hour-races">${hourRaces.map((race) => raceCard(race)).join("")}</div>
        </section>`)
      .join("");

    return hourMarkup;
  };

  const scrollToCurrentHour = () => {
    const target = board?.querySelector(`[data-hour="${TARGET_HOUR}"]`);
    if (!shell || !target) return;
    const shellRect = shell.getBoundingClientRect();
    const targetRect = target.getBoundingClientRect();
    const top = shell.scrollTop + targetRect.top - shellRect.top - 5;
    shell.scrollTo({ top: Math.max(0, top), behavior: "auto" });
  };

  const bindCards = () => {
    board?.querySelectorAll(".timetable-race").forEach((card) => {
      card.addEventListener("click", (event) => {
        event.preventDefault();
        showPreparingToast();
      });
    });
  };

  const render = (date, resetPosition = true) => {
    if (!board) return;
    if (date !== TARGET_DATE) {
      const [, month, day] = date.split("-").map(Number);
      board.innerHTML = `
        <section class="timetable-empty">
          <strong>${month}月${day}日の時刻表</strong>
          <span>作成中</span>
        </section>`;
      if (shell) shell.scrollTop = 0;
      return;
    }

    board.innerHTML = buildHourGroups();
    bindCards();
    if (!resetPosition) return;
    requestAnimationFrame(() => requestAnimationFrame(scrollToCurrentHour));
    window.setTimeout(scrollToCurrentHour, 80);
    window.setTimeout(scrollToCurrentHour, 180);
  };

  document.addEventListener("DOMContentLoaded", () => {
    const selectedDate = toolbar?.dataset.selectedDate || TARGET_DATE;
    render(selectedDate, true);

    window.addEventListener("zenrace-date-refresh", (event) => {
      const date = event.detail?.date || toolbar?.dataset.selectedDate || TARGET_DATE;
      render(date, true);
    });

    window.addEventListener("resize", () => {
      const date = toolbar?.dataset.selectedDate || TARGET_DATE;
      if (date === TARGET_DATE) window.setTimeout(scrollToCurrentHour, 60);
    }, { passive: true });
  });
})();
