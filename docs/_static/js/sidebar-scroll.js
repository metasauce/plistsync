(() => {
  const storageKey = "plistsync.sidebar-state";

  function getSidebar() {
    return document.querySelector(".sidebar-scroll");
  }

  function saveSidebarState() {
    const sidebar = getSidebar();
    if (!sidebar) return;

    const checkboxes = {};
    sidebar.querySelectorAll("input.toctree-checkbox[id]").forEach((checkbox) => {
      checkboxes[checkbox.id] = checkbox.checked;
    });

    try {
      sessionStorage.setItem(
        storageKey,
        JSON.stringify({ scrollTop: sidebar.scrollTop, checkboxes }),
      );
    } catch {
      // Storage may be unavailable; navigation should still work normally.
    }
  }

  function restoreSidebarState() {
    const sidebar = getSidebar();
    if (!sidebar) return;

    let savedState;
    try {
      const storedState = sessionStorage.getItem(storageKey);
      if (!storedState) return;
      savedState = JSON.parse(storedState);
    } catch {
      return;
    }

    if (!savedState || typeof savedState !== "object") return;

    const savedCheckboxes = savedState.checkboxes || {};
    sidebar.querySelectorAll("input.toctree-checkbox[id]").forEach((checkbox) => {
      if (Object.prototype.hasOwnProperty.call(savedCheckboxes, checkbox.id)) {
        checkbox.checked = savedCheckboxes[checkbox.id];
      }
    });

    const maxScrollTop = Math.max(0, sidebar.scrollHeight - sidebar.clientHeight);
    const savedScrollTop = Number.isFinite(savedState.scrollTop)
      ? savedState.scrollTop
      : 0;
    const scrollBehavior = sidebar.style.scrollBehavior;

    // Restore immediately rather than animating from the top on every page load.
    sidebar.style.scrollBehavior = "auto";
    sidebar.scrollTop = Math.max(0, Math.min(savedScrollTop, maxScrollTop));
    requestAnimationFrame(() => {
      sidebar.style.scrollBehavior = scrollBehavior;
    });
  }

  function initialize() {
    restoreSidebarState();
    window.addEventListener("pagehide", saveSidebarState);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialize, { once: true });
  } else {
    initialize();
  }
})();
