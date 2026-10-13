// Σελίδα παρουσίασης. Φορτώνεται μετά το app.js και χρησιμοποιεί τα calculatePay, toMinutes, formatClock, eur
// και reduceMotion του, ώστε ο υπολογισμός να είναι ακριβώς ίδιος με της εφαρμογής.
{
  // --- Μενού κινητού: ανοίγει από το κουμπί, κλείνει με Esc, με κλικ έξω ή όταν επιλεγεί ενότητα
  const nav = document.getElementById("navbar");
  const toggle = nav && nav.querySelector(".menu-toggle");
  const menu = document.getElementById("site-menu");

  if (toggle && menu) {
    const isOpen = () => nav.classList.contains("menu-open");
    const setOpen = (open, { focusMenu = false } = {}) => {
      nav.classList.toggle("menu-open", open);
      toggle.setAttribute("aria-expanded", String(open));
      toggle.setAttribute("aria-label", open ? "Κλείσιμο μενού" : "Μενού");
      if (open && focusMenu) menu.querySelector("a").focus({ preventScroll: true });
    };

    // detail === 0: ενεργοποίηση από το πληκτρολόγιο, οπότε η εστίαση περνά στο μενού
    toggle.addEventListener("click", (e) => setOpen(!isOpen(), { focusMenu: e.detail === 0 }));
    menu.querySelectorAll("a").forEach((link) => link.addEventListener("click", () => setOpen(false)));
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && isOpen()) {
        setOpen(false);
        toggle.focus();
      }
    });
    document.addEventListener("pointerdown", (e) => {
      if (isOpen() && !nav.contains(e.target)) setOpen(false);
    });
    // Στο φαρδύ layout δεν υπάρχει μενού κινητού
    window.matchMedia("(min-width: 861px)").addEventListener("change", (e) => e.matches && setOpen(false));
  }

  // --- Υπολογισμός πληρωμής (ίδιοι κανόνες με το core.calculate_pay)
  const calc = document.getElementById("calc");
  if (calc) {
    const start = calc.querySelector("#calc-start");
    const end = calc.querySelector("#calc-end");
    const times = calc.querySelector("#calc-times");
    const fields = {};
    calc.querySelectorAll("[data-calc]").forEach((node) => (fields[node.dataset.calc] = node));

    function update() {
      const isShift = calc.querySelector("input[name=calc-type]:checked").value === "shift";
      start.disabled = !isShift;
      end.disabled = !isShift;
      times.classList.toggle("is-collapsed", !isShift);

      let pay;
      if (isShift) {
        let minutes = toMinutes(end.value) - toMinutes(start.value);
        if (minutes < 0) minutes += 24 * 60; // βάρδια που περνά τα μεσάνυχτα
        const hours = Math.round((minutes / 60) * 100) / 100;
        pay = calculatePay("shift", hours);
        fields.label.textContent = "Διάρκεια";
        fields.hours.textContent = formatClock(hours);
      } else {
        pay = calculatePay("transfer", 0);
        fields.label.textContent = "Σταθερή αμοιβή";
        fields.hours.textContent = "";
      }
      fields.total.textContent = eur(pay.total);
      fields.direct.textContent = eur(pay.direct);
      fields.fund.textContent = eur(pay.fund);
    }

    calc.addEventListener("submit", (e) => e.preventDefault());
    calc.addEventListener("input", update);
    calc.addEventListener("change", update);
    update();
  }

  // --- Εμφάνιση των ενοτήτων καθώς έρχονται στην οθόνη (μία φορά· όχι με «λιγότερη κίνηση»)
  const items = document.querySelectorAll("[data-reveal]");
  if ("IntersectionObserver" in window && !reduceMotion.matches) {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      },
      { rootMargin: "0px 0px -6% 0px", threshold: 0.06 }
    );
    items.forEach((item) => observer.observe(item));
  } else {
    items.forEach((item) => item.classList.add("is-visible"));
  }
}
