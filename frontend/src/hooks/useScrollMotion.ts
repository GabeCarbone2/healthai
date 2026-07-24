import { useEffect } from "react";

const REVEAL_SELECTORS = [
  "[data-reveal]",
  ".app-shell .page-header",
  ".app-shell .model-context",
  ".app-shell .assessment-layout",
  ".app-shell .results-filters",
  ".app-shell .patient-results",
  ".app-shell .account-grid > *",
  ".app-shell .crm-status-card",
  ".app-shell .privacy-card",
  ".app-shell .danger-zone",
  ".app-shell .review-filters",
  ".app-shell .review-list > *",
].join(",");

export function useScrollMotion() {
  useEffect(() => {
    const root = document.documentElement;
    const reducedMotion =
      typeof window.matchMedia === "function"
      && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (reducedMotion || typeof window.IntersectionObserver === "undefined") {
      document.querySelectorAll<HTMLElement>(REVEAL_SELECTORS).forEach((element) => {
        element.classList.add("is-visible");
      });
      return;
    }

    root.classList.add("scroll-motion-ready");
    const observed = new WeakSet<Element>();
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        });
      },
      {
        rootMargin: "0px 0px -10% 0px",
        threshold: 0.08,
      },
    );

    function register(container: ParentNode) {
      container.querySelectorAll<HTMLElement>(REVEAL_SELECTORS).forEach((element) => {
        if (observed.has(element)) return;
        observed.add(element);
        if (!element.dataset.reveal) element.dataset.reveal = "up";
        observer.observe(element);
      });
    }

    register(document);
    const mutations = new MutationObserver((records) => {
      records.forEach((record) => {
        record.addedNodes.forEach((node) => {
          if (!(node instanceof HTMLElement)) return;
          if (node.matches(REVEAL_SELECTORS)) {
            register(node.parentElement ?? document);
          } else {
            register(node);
          }
        });
      });
    });
    mutations.observe(document.body, { childList: true, subtree: true });

    let animationFrame = 0;
    function updateScrollState() {
      animationFrame = 0;
      const scrollRange = Math.max(
        1,
        document.documentElement.scrollHeight - window.innerHeight,
      );
      const progress = Math.min(1, Math.max(0, window.scrollY / scrollRange));
      const heroShift = Math.min(84, window.scrollY * 0.1);
      const heroProgress = Math.min(
        1,
        window.scrollY / Math.max(520, window.innerHeight * 0.82),
      );
      const heroCopyShift = heroProgress * -34;
      const heroCopyOpacity = 1 - heroProgress * 0.32;
      root.style.setProperty("--page-scroll-progress", progress.toFixed(4));
      root.style.setProperty("--hero-scroll-shift", `${heroShift.toFixed(1)}px`);
      root.style.setProperty(
        "--hero-copy-shift",
        `${heroCopyShift.toFixed(1)}px`,
      );
      root.style.setProperty(
        "--hero-copy-opacity",
        heroCopyOpacity.toFixed(3),
      );
      root.toggleAttribute("data-scrolled", window.scrollY > 20);
    }

    function requestScrollUpdate() {
      if (animationFrame) return;
      animationFrame = window.requestAnimationFrame(updateScrollState);
    }

    updateScrollState();
    window.addEventListener("scroll", requestScrollUpdate, { passive: true });
    window.addEventListener("resize", requestScrollUpdate);

    return () => {
      observer.disconnect();
      mutations.disconnect();
      window.removeEventListener("scroll", requestScrollUpdate);
      window.removeEventListener("resize", requestScrollUpdate);
      if (animationFrame) window.cancelAnimationFrame(animationFrame);
      root.classList.remove("scroll-motion-ready");
      root.removeAttribute("data-scrolled");
      root.style.removeProperty("--page-scroll-progress");
      root.style.removeProperty("--hero-scroll-shift");
      root.style.removeProperty("--hero-copy-shift");
      root.style.removeProperty("--hero-copy-opacity");
    };
  }, []);
}
