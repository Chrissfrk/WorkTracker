// Ζωντανή προεπισκόπηση πληρωμής — ίδιοι κανόνες με core.calculate_pay
function calculatePay(type, hours) {
  if (type === "transfer") return { total: 40, direct: 30, fund: 10 };
  const total = hours * 10;
  return { total, direct: total * 0.75, fund: total * 0.25 };
}

function toMinutes(value) {
  if (!value) return 0;
  const [h, m] = value.split(":").map(Number);
  return h * 60 + m;
}

function formatClock(hours) {
  const h = Math.floor(hours);
  const m = Math.round((hours - h) * 60);
  return `${h}:${String(m).padStart(2, "0")}`;
}

const eur = (v) => `${v.toFixed(2)} €`;

const form = document.getElementById("entry-form");
if (form) {
  const start = form.querySelector("#start");
  const end = form.querySelector("#end");
  const preview = form.querySelector("#preview");

  const currentType = () => form.querySelector("input[name=type]:checked").value;

  function update() {
    const type = currentType();
    const isShift = type === "shift";
    start.disabled = !isShift;
    end.disabled = !isShift;

    if (!isShift) {
      const pay = calculatePay("transfer", 0);
      preview.textContent = `Σταθερή αμοιβή ${eur(pay.total)}\nΆμεση ${eur(pay.direct)} · Ταμείο ${eur(pay.fund)}`;
      return;
    }
    let minutes = toMinutes(end.value) - toMinutes(start.value);
    if (minutes < 0) minutes += 24 * 60;
    const hours = Math.round((minutes / 60) * 100) / 100;
    if (hours === 0) {
      preview.textContent = "Ορίστε ώρα έναρξης και λήξης";
      return;
    }
    const pay = calculatePay("shift", hours);
    preview.textContent = `Διάρκεια ${formatClock(hours)} · Σύνολο ${eur(pay.total)}\nΆμεση ${eur(pay.direct)} · Ταμείο ${eur(pay.fund)}`;
  }

  form.addEventListener("input", update);
  form.addEventListener("change", update);
  update();
}

// Μηνιαία έσοδα — αλλαγή μήνα επί τόπου (οι τιμές έρχονται έτοιμες από το core.get_month_overview)
const revenue = document.getElementById("revenue");
if (revenue) {
  const months = JSON.parse(document.getElementById("revenue-data").textContent);
  const select = revenue.querySelector("select");
  const chart = revenue.querySelector(".chart");
  const bars = [...chart.querySelectorAll(".bar")];
  const steps = [...revenue.querySelectorAll("[data-step]")];
  const fields = {};
  revenue.querySelectorAll("[data-field]").forEach((el) => (fields[el.dataset.field] = el));
  let index = months.findIndex((m) => m.key === select.value);

  // Κρατά την επιλεγμένη στήλη ορατή όταν το γράφημα κυλάει οριζόντια (χωρίς να μετακινεί τη σελίδα)
  function reveal(bar) {
    const left = bar.offsetLeft;
    const right = left + bar.offsetWidth;
    if (left < chart.scrollLeft || right > chart.scrollLeft + chart.clientWidth) {
      chart.scrollLeft = left - (chart.clientWidth - bar.offsetWidth) / 2;
    }
  }

  function show(i) {
    if (i < 0 || i >= months.length || i === index) return;
    index = i;
    const m = months[i];
    for (const key of ["label", "direct", "total", "fund", "hours", "counts"]) fields[key].textContent = m[key];
    fields.delta.className = `delta-change ${m.delta ? m.delta.trend : ""}`;
    fields.delta.textContent = m.delta ? m.delta.text : "";
    fields.vs.textContent = m.delta ? m.delta.vs : fields.vs.dataset.empty;
    select.value = m.key;

    steps.forEach((link) => {
      const target = months[i + Number(link.dataset.step)];
      if (target) {
        link.href = `?month=${target.key}#revenue`;
        link.removeAttribute("aria-disabled");
      } else {
        link.removeAttribute("href");
        link.setAttribute("aria-disabled", "true");
      }
    });
    bars.forEach((bar, j) => bar.setAttribute("aria-current", String(j === i)));
    reveal(bars[i]);

    // Ο μήνας μένει στη διεύθυνση, ώστε η ανανέωση της σελίδας να δείχνει τον ίδιο μήνα
    const url = new URL(location.href);
    if (m.current) url.searchParams.delete("month");
    else url.searchParams.set("month", m.key);
    history.replaceState(null, "", url);
  }

  select.addEventListener("change", () => show(months.findIndex((m) => m.key === select.value)));
  steps.forEach((link) =>
    link.addEventListener("click", (e) => {
      e.preventDefault();
      show(index + Number(link.dataset.step));
    })
  );
  bars.forEach((bar, j) =>
    bar.addEventListener("click", (e) => {
      e.preventDefault();
      show(j);
    })
  );
  reveal(bars[index]);
}

// Επιβεβαίωση πριν τη διαγραφή
document.querySelectorAll(".delete-form").forEach((f) => {
  f.addEventListener("submit", (e) => {
    if (!confirm(f.dataset.confirm)) e.preventDefault();
  });
});
