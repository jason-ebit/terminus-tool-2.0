// Decisions the page makes about review state, kept free of the DOM so they can
// be tested with `node --test web/review-guard.test.js`.
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.ReviewGuard = api;
})(typeof self !== "undefined" ? self : this, function () {
  const PROFILES = new Set(["t3", "t4"]);

  // Reject results from a different policy profile.
  function acceptReview(requestedProfile, payload) {
    if (!PROFILES.has(requestedProfile)) {
      return { ok: false, error: "Choose Terminus 3 or Terminus 4 before reviewing." };
    }
    if (!payload || typeof payload !== "object") {
      return { ok: false, error: "The server returned no review." };
    }
    if (payload.profile !== requestedProfile) {
      return {
        ok: false,
        error: `Review was produced under ${String(payload.profile || "no profile").toUpperCase()} ` +
          `but ${requestedProfile.toUpperCase()} was requested. The result was discarded.`,
      };
    }
    return { ok: true };
  }

  // Clear old results on profile changes; retain the ZIP in page memory.
  function resetForProfileChange(state, nextProfile) {
    return {
      ...state,
      profile: nextProfile,
      results: new Map(),
      report: null,
      overrides: [],
      reviewedProfile: null,
      zip: state.zip || null,
      stale: Boolean(state.report),
    };
  }

  // "updated 3 min ago" for glanceability; the exact time goes in a tooltip.
  function relativeTime(iso, now) {
    const then = Date.parse(iso);
    if (!Number.isFinite(then)) return "";
    const seconds = Math.max(0, Math.round(((now ?? Date.now()) - then) / 1000));
    if (seconds < 10) return "just now";
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.round(seconds / 60);
    if (minutes < 60) return `${minutes} min ago`;
    const hours = Math.round(minutes / 60);
    if (hours < 48) return `${hours} hr ago`;
    return `${Math.round(hours / 24)} days ago`;
  }

  // Only an unknown finding may be resolved by a reviewer (owner decision 2).
  function canResolve(result) {
    return Boolean(result) && result.status === "unknown" &&
      (result.layer === "static" || result.layer === "rubric");
  }

  return { acceptReview, resetForProfileChange, relativeTime, canResolve };
});
