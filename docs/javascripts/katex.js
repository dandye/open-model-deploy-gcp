const renderMath = (root) => {
  if (typeof renderMathInElement !== "function") {
    return;
  }
  renderMathInElement(root || document.body, {
    delimiters: [
      { left: "\\(", right: "\\)", display: false },
      { left: "\\[", right: "\\]", display: true },
    ],
    throwOnError: false,
  });
};

if (typeof document$ !== "undefined") {
  document$.subscribe(({ body }) => {
    renderMath(body);
  });
} else if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => renderMath(document.body));
} else {
  renderMath(document.body);
}
