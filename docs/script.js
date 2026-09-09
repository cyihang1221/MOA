(() => {
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce) return;

  const targets = document.querySelectorAll(
    ".section h2, .flow li, .agent, .feature-list > div, .chips"
  );
  targets.forEach((el) => el.classList.add("reveal"));

  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          io.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.15, rootMargin: "0px 0px -8% 0px" }
  );

  targets.forEach((el) => io.observe(el));

  const peaks = document.querySelectorAll(".hero-spectrum .peaks path");
  peaks.forEach((path, i) => {
    path.style.strokeDasharray = "400";
    path.style.strokeDashoffset = "400";
    path.animate(
      [
        { strokeDashoffset: 400, opacity: 0.2 },
        { strokeDashoffset: 0, opacity: 1 },
      ],
      {
        duration: 1100,
        delay: 120 + i * 70,
        fill: "forwards",
        easing: "cubic-bezier(0.22, 1, 0.36, 1)",
      }
    );
  });
})();
