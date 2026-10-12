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

// Επιβεβαίωση πριν τη διαγραφή
document.querySelectorAll(".delete-form").forEach((f) => {
  f.addEventListener("submit", (e) => {
    if (!confirm(f.dataset.confirm)) e.preventDefault();
  });
});
