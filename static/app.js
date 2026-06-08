(() => {
  const isTypingTarget = (element) => {
    if (!element) {
      return false;
    }
    const tag = element.tagName;
    return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || element.isContentEditable;
  };

  const focusFirst = (selector) => {
    const target = document.querySelector(selector);
    if (!target) {
      return false;
    }
    target.focus();
    if (typeof target.select === "function") {
      target.select();
    }
    return true;
  };

  document.addEventListener("keydown", (event) => {
    if (event.defaultPrevented) {
      return;
    }

    if (event.key === "/" && !isTypingTarget(document.activeElement)) {
      if (focusFirst("[data-shortcut-search]")) {
        event.preventDefault();
      }
      return;
    }

    if (event.altKey && !event.ctrlKey && !event.metaKey && event.key.toLowerCase() === "n") {
      window.location.assign("/employees/new");
      event.preventDefault();
      return;
    }

    if (event.altKey && !event.ctrlKey && !event.metaKey && event.key.toLowerCase() === "l") {
      if (focusFirst("[data-shortcut-leave-days]")) {
        event.preventDefault();
      }
    }
  });
})();
