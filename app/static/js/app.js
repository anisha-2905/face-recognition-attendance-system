document.addEventListener("DOMContentLoaded", () => {
  const body = document.body;
  const sidebarToggle = document.getElementById("sidebarToggle");
  const closeButtons = document.querySelectorAll("[data-sidebar-close]");

  if (sidebarToggle) {
    sidebarToggle.addEventListener("click", () => {
      if (window.matchMedia("(max-width: 991.98px)").matches) {
        body.classList.toggle("sidebar-open");
        return;
      }
      body.classList.toggle("sidebar-collapsed");
    });
  }

  closeButtons.forEach((button) => {
    button.addEventListener("click", () => body.classList.remove("sidebar-open"));
  });

  document.querySelectorAll(".badge").forEach((badge) => {
    const value = badge.textContent.trim().toLowerCase();
    if (value === "present") badge.classList.add("status-present");
    if (value === "late") badge.classList.add("status-late");
    if (value === "absent") badge.classList.add("status-absent");
  });
});
