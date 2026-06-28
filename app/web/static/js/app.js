document.documentElement.classList.add("js");

function scrollConversationToBottom() {
  document.querySelectorAll('[data-autoscroll="bottom"]').forEach((element) => {
    element.scrollTop = element.scrollHeight;
  });
}

function wireConfirmForms() {
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      const message = form.getAttribute("data-confirm");
      if (message && !window.confirm(message)) {
        event.preventDefault();
      }
    });
  });
}

function wireSubmitState() {
  document.querySelectorAll("form").forEach((form) => {
    form.addEventListener("submit", () => {
      form.classList.add("is-submitting");
      form.querySelectorAll('button[type="submit"]').forEach((button) => {
        button.setAttribute("aria-busy", "true");
      });
    });
  });
}

function autoGrowTextareas() {
  document.querySelectorAll("textarea").forEach((textarea) => {
    const resize = () => {
      textarea.style.height = "auto";
      textarea.style.height = `${textarea.scrollHeight}px`;
    };
    textarea.addEventListener("input", resize);
    resize();
  });
}

document.addEventListener("DOMContentLoaded", () => {
  scrollConversationToBottom();
  wireConfirmForms();
  wireSubmitState();
  autoGrowTextareas();
});
