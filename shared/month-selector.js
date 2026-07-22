(() => {
  "use strict";

  const toolbar = document.querySelector("[data-zenrace-month-selector]");
  if (!toolbar) return;

  const currentMonth = new Date();
  currentMonth.setDate(1);
  currentMonth.setHours(0, 0, 0, 0);
  const selectedMonth = new Date(currentMonth);
  const title = toolbar.querySelector("[data-month-title]");
  const previous = toolbar.querySelector("[data-month-prev]");
  const next = toolbar.querySelector("[data-month-next]");
  const current = toolbar.querySelector("[data-month-current]");

  const sameMonth = (a, b) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth();
  const render = () => {
    if (title) title.textContent = `${selectedMonth.getFullYear()}年 ${selectedMonth.getMonth() + 1}月`;
    const isCurrent = sameMonth(selectedMonth, currentMonth);
    current?.classList.toggle("is-current", isCurrent);
    if (current) current.disabled = isCurrent;
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

  render();
})();
