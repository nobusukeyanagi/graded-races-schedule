(() => {
  "use strict";

  const toolbar = document.querySelector("[data-zenrace-month-selector]");
  if (!toolbar) return;

  const monthStart = (value = new Date()) => {
    const date = new Date(value);
    date.setDate(1);
    date.setHours(0, 0, 0, 0);
    return date;
  };
  const parseMonth = (value, fallback) => {
    const match = /^(\d{4})-(\d{2})$/.exec(value || "");
    return match ? new Date(Number(match[1]), Number(match[2]) - 1, 1) : new Date(fallback);
  };
  const monthKey = (value) => `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}`;

  const currentMonth = monthStart();
  const selectedMonth = parseMonth(toolbar.dataset.initialMonth, currentMonth);
  const title = toolbar.querySelector("[data-month-title]");
  const previous = toolbar.querySelector("[data-month-prev]");
  const next = toolbar.querySelector("[data-month-next]");
  const current = toolbar.querySelector("[data-month-current]");

  const sameMonth = (a, b) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth();
  const render = (notify = true) => {
    if (title) title.textContent = `${selectedMonth.getFullYear()}年 ${selectedMonth.getMonth() + 1}月`;
    const isCurrent = sameMonth(selectedMonth, currentMonth);
    current?.classList.toggle("is-current", isCurrent);
    if (current) current.disabled = isCurrent;
    toolbar.dataset.selectedMonth = monthKey(selectedMonth);
    if (notify) {
      window.dispatchEvent(new CustomEvent("zenrace-month-change", {
        detail: { month: monthKey(selectedMonth) },
      }));
    }
  };

  previous?.addEventListener("click", () => {
    selectedMonth.setMonth(selectedMonth.getMonth() - 1);
    render();
  });
  next?.addEventListener("click", () => {
    selectedMonth.setMonth(selectedMonth.getMonth() + 1);
    render();
  });
  current?.addEventListener("click", () => {
    selectedMonth.setTime(currentMonth.getTime());
    render();
  });

  render(false);
})();
