// Διαχείριση — μικρές βελτιώσεις πάνω σε φόρμες που λειτουργούν και χωρίς JavaScript

// Τα φίλτρα (select, μήνας) εφαρμόζονται μόλις αλλάξουν
document.querySelectorAll("[data-autosubmit]").forEach((input) =>
  input.addEventListener("change", () => input.form.requestSubmit())
);

// Διαγραφή χρήστη: το κουμπί ενεργοποιείται μόνο όταν το όνομα πληκτρολογηθεί σωστά (ο server το ελέγχει ξανά)
document.querySelectorAll("input[data-match]").forEach((input) => {
  const button = input.form.querySelector("[data-requires-match]");
  const update = () => {
    button.disabled = input.value.trim().toLocaleLowerCase() !== input.dataset.match.toLocaleLowerCase();
  };
  input.addEventListener("input", update);
  update();
});

// Αντιγραφή προσωρινού κωδικού, με επιβεβαίωση πάνω στο ίδιο το κουμπί
document.querySelectorAll("[data-copy]").forEach((button) => {
  const label = button.textContent;
  button.addEventListener("click", async () => {
    const text = document.getElementById(button.dataset.copy).textContent;
    try {
      await navigator.clipboard.writeText(text);
      button.textContent = "Αντιγράφηκε";
    } catch {
      // Χωρίς πρόσβαση στο πρόχειρο: επιλέγεται το κείμενο για χειροκίνητη αντιγραφή
      const range = document.createRange();
      range.selectNodeContents(document.getElementById(button.dataset.copy));
      getSelection().removeAllRanges();
      getSelection().addRange(range);
      button.textContent = "Επιλέχθηκε";
    }
    setTimeout(() => (button.textContent = label), 2000);
  });
});
