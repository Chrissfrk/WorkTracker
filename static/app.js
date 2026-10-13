const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

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

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

const form = document.getElementById("entry-form");
if (form) {
  const start = form.querySelector("#start");
  const end = form.querySelector("#end");
  const times = form.querySelector("#time-fields");
  const preview = form.querySelector("#preview");

  const currentType = () => form.querySelector("input[name=type]:checked").value;

  function renderPreview(label, value, pay) {
    const head = el("div", "preview-head");
    head.append(el("span", "", label));
    if (value) head.append(el("strong", "", value));
    const grid = el("dl", "preview-grid");
    const keys = { Σύνολο: "key-total", Άμεση: "key-direct", Ταμείο: "key-fund" };
    for (const [name, amount] of [["Σύνολο", pay.total], ["Άμεση", pay.direct], ["Ταμείο", pay.fund]]) {
      const item = el("div");
      item.append(el("dt", `key ${keys[name]}`, name), el("dd", "", eur(amount)));
      grid.append(item);
    }
    preview.replaceChildren(head, grid);
  }

  function update() {
    const isShift = currentType() === "shift";
    start.disabled = !isShift;
    end.disabled = !isShift;
    times.classList.toggle("is-collapsed", !isShift);
    preview.dataset.type = isShift ? "shift" : "transfer";

    if (!isShift) {
      renderPreview("Σταθερή αμοιβή", "", calculatePay("transfer", 0));
      return;
    }
    let minutes = toMinutes(end.value) - toMinutes(start.value);
    if (minutes < 0) minutes += 24 * 60;
    const hours = Math.round((minutes / 60) * 100) / 100;
    if (hours === 0) {
      delete preview.dataset.type;
      preview.replaceChildren(el("div", "preview-empty", "Ορίστε ώρα έναρξης και λήξης"));
      return;
    }
    renderPreview("Διάρκεια", formatClock(hours), calculatePay("shift", hours));
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
  const hero = revenue.querySelector(".overview-hero");
  const metrics = revenue.querySelector(".metrics");
  const bars = [...chart.querySelectorAll(".bar")];
  const steps = [...revenue.querySelectorAll("[data-step]")];
  const fields = {};
  revenue.querySelectorAll("[data-field]").forEach((node) => (fields[node.dataset.field] = node));
  let index = months.findIndex((m) => m.key === select.value);

  // Κρατά την επιλεγμένη στήλη ορατή όταν το γράφημα κυλάει οριζόντια (χωρίς να μετακινεί τη σελίδα)
  function reveal(bar, smooth) {
    const left = bar.offsetLeft;
    const right = left + bar.offsetWidth;
    if (left < chart.scrollLeft || right > chart.scrollLeft + chart.clientWidth) {
      chart.scrollTo({
        left: left - (chart.clientWidth - bar.offsetWidth) / 2,
        behavior: smooth && !reduceMotion.matches ? "smooth" : "auto",
      });
    }
  }

  // Σβήσιμο στις άκρες μόνο όταν υπάρχουν κι άλλοι μήνες προς εκείνη την πλευρά
  function updateEdges() {
    const max = chart.scrollWidth - chart.clientWidth;
    chart.classList.toggle("fade-start", chart.scrollLeft > 1);
    chart.classList.toggle("fade-end", chart.scrollLeft < max - 1);
  }

  function show(i) {
    if (i < 0 || i >= months.length || i === index) return;
    const forward = i > index;
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
    reveal(bars[i], true);

    // Οι νέες τιμές έρχονται από την κατεύθυνση του μήνα (αριστερά = παλαιότερος)
    if (!reduceMotion.matches && hero.animate) {
      const offset = forward ? 12 : -12;
      const frames = [{ opacity: 0.2, transform: `translateX(${offset}px)` }, { opacity: 1, transform: "none" }];
      const timing = { duration: 260, easing: "cubic-bezier(.22, 1, .36, 1)" };
      hero.animate(frames, timing);
      metrics.animate(frames, timing);
    }

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
  chart.addEventListener("scroll", updateEdges, { passive: true });
  window.addEventListener("resize", updateEdges);
  reveal(bars[index], false);
  updateEdges();
}

// Επιβεβαίωση πριν τη διαγραφή — διάλογος, με το confirm() του browser ως εναλλακτική
const dialog = document.getElementById("confirm-dialog");
const canUseDialog = dialog && typeof dialog.showModal === "function";
let pendingDelete = null;

function closeDialog(value) {
  if (!dialog.open || dialog.classList.contains("is-closing")) return;
  if (reduceMotion.matches) {
    dialog.close(value);
    return;
  }
  dialog.classList.add("is-closing");
  setTimeout(() => {
    dialog.classList.remove("is-closing");
    dialog.close(value);
  }, 140);
}

if (canUseDialog) {
  dialog.querySelector("form").addEventListener("submit", (e) => {
    e.preventDefault();
    closeDialog(e.submitter ? e.submitter.value : "cancel");
  });
  dialog.addEventListener("cancel", (e) => {
    e.preventDefault();
    closeDialog("cancel");
  });
  // Κλικ στο σκοτεινό φόντο = Ακύρωση
  dialog.addEventListener("click", (e) => {
    if (e.target === dialog) {
      const r = dialog.getBoundingClientRect();
      const inside = e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom;
      if (!inside) closeDialog("cancel");
    }
  });
  dialog.addEventListener("close", () => {
    const target = pendingDelete;
    pendingDelete = null;
    if (target && dialog.returnValue === "confirm") {
      target.querySelector("button").setAttribute("aria-busy", "true");
      target.submit();
    } else if (target) {
      target.querySelector("button").focus();
    }
  });
}

document.querySelectorAll(".delete-form").forEach((f) => {
  f.addEventListener("submit", (e) => {
    e.preventDefault();
    // Ο τίτλος και το κουμπί αλλάζουν ανά φόρμα (data-confirm-title / data-confirm-action), π.χ. στη Διαχείριση
    const title = f.dataset.confirmTitle || "Διαγραφή εγγραφής;";
    if (canUseDialog) {
      pendingDelete = f;
      dialog.querySelector("#confirm-title").textContent = title;
      dialog.querySelector("#confirm-message").textContent = f.dataset.confirm;
      dialog.querySelector("button[value=confirm]").textContent = f.dataset.confirmAction || "Διαγραφή";
      dialog.returnValue = "";
      dialog.showModal();
    } else if (confirm(`${title}\n\n${f.dataset.confirm}`)) {
      f.submit();
    }
  });
});

// Ειδοποιήσεις: κουμπί κλεισίματος· οι επιτυχίες κλείνουν μόνες τους, τα σφάλματα μένουν μέχρι να τα κλείσεις
document.querySelectorAll(".notices .notice").forEach((notice) => {
  const close = el("button", "icon-btn");
  close.type = "button";
  close.setAttribute("aria-label", "Κλείσιμο");
  close.innerHTML = '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m7 7 10 10M17 7 7 17"/></svg>';
  notice.append(close);

  let timer = null;
  const dismiss = () => {
    clearTimeout(timer);
    notice.classList.add("is-leaving");
    setTimeout(() => {
      const list = notice.parentElement;
      notice.remove();
      if (list && !list.children.length) list.remove();
    }, reduceMotion.matches ? 0 : 240);
  };
  close.addEventListener("click", dismiss);

  if (notice.classList.contains("notice-success")) {
    const schedule = () => (timer = setTimeout(dismiss, 6000));
    // Δεν κλείνει όσο ο χρήστης το διαβάζει ή το έχει εστιάσει
    notice.addEventListener("pointerenter", () => clearTimeout(timer));
    notice.addEventListener("pointerleave", schedule);
    notice.addEventListener("focusin", () => clearTimeout(timer));
    notice.addEventListener("focusout", schedule);
    schedule();
  }
});

// Γραμμή πλοήγησης: διαχωριστική γραμμή μόνο όταν το περιεχόμενο κυλά από κάτω
const navbar = document.getElementById("navbar");
if (navbar) {
  let scrolled = null;
  const onScroll = () => {
    const now = window.scrollY > 2;
    if (now !== scrolled) navbar.classList.toggle("is-scrolled", (scrolled = now));
  };
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
}

// Κουμπιά υποβολής: ένδειξη φόρτωσης και προστασία από διπλή υποβολή
document.querySelectorAll("form[method=post]:not(.delete-form)").forEach((f) => {
  f.addEventListener("submit", (e) => {
    const button = e.submitter || f.querySelector("button[type=submit]");
    if (!button) return;
    if (button.getAttribute("aria-busy") === "true") {
      e.preventDefault();
      return;
    }
    button.setAttribute("aria-busy", "true");
    if (button.dataset.busyLabel) {
      button.dataset.idleLabel = button.textContent;
      button.textContent = button.dataset.busyLabel;
    }
  });
});
// Επιστροφή με το κουμπί «Πίσω» (bfcache): τα κουμπιά ξαναγίνονται ενεργά
window.addEventListener("pageshow", (e) => {
  if (!e.persisted) return;
  document.querySelectorAll("[aria-busy=true]").forEach((button) => {
    button.removeAttribute("aria-busy");
    if (button.dataset.idleLabel) button.textContent = button.dataset.idleLabel;
  });
});

// Επιλογή PDF: εμφανίζει τα αρχεία που επιλέχθηκαν και δέχεται σύρσιμο αρχείων
document.querySelectorAll("[data-dropzone]").forEach((zone) => {
  const input = zone.querySelector("input[type=file]");
  const title = zone.querySelector("[data-dropzone-title]");
  const hint = zone.querySelector("[data-dropzone-hint]");
  const idle = { title: title.textContent, hint: hint.textContent };

  function render() {
    const files = [...input.files];
    zone.classList.toggle("has-files", files.length > 0);
    if (!files.length) {
      title.textContent = idle.title;
      hint.textContent = idle.hint;
      return;
    }
    title.textContent = files.length === 1 ? files[0].name : `${files.length} αρχεία PDF`;
    hint.textContent = files.length === 1 ? "Πατήστε για αλλαγή" : files.map((f) => f.name).join(", ");
  }

  input.addEventListener("change", render);
  ["dragenter", "dragover"].forEach((type) =>
    zone.addEventListener(type, (e) => {
      e.preventDefault();
      zone.classList.add("is-dragging");
    })
  );
  ["dragleave", "dragend"].forEach((type) =>
    zone.addEventListener(type, (e) => {
      if (!zone.contains(e.relatedTarget)) zone.classList.remove("is-dragging");
    })
  );
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("is-dragging");
    const pdfs = [...e.dataTransfer.files].filter((f) => f.type === "application/pdf" || /\.pdf$/i.test(f.name));
    if (!pdfs.length) return;
    const transfer = new DataTransfer();
    pdfs.forEach((f) => transfer.items.add(f));
    input.files = transfer.files;
    render();
  });
  render();
});

// Σύνδεσμοι που μεταφέρουν την εστίαση σε πεδίο (π.χ. «Νέα Καταχώριση» στην κενή λίστα)
document.querySelectorAll("a[data-focus]").forEach((link) =>
  link.addEventListener("click", () => {
    const target = document.getElementById(link.dataset.focus);
    if (target) setTimeout(() => target.focus({ preventScroll: true }), 0);
  })
);
