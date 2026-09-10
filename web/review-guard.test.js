// node --test web/review-guard.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const G = require("./review-guard.js");

test("a review under the requested profile is accepted", () => {
  assert.deepEqual(G.acceptReview("t3", { profile: "t3" }), { ok: true });
  assert.deepEqual(G.acceptReview("t4", { profile: "t4" }), { ok: true });
});

test("a response whose profile differs from the request is rejected", () => {
  const verdict = G.acceptReview("t4", { profile: "t3" });
  assert.equal(verdict.ok, false);
  assert.match(verdict.error, /T3.*T4.*discarded/);
});

test("a response with no profile is rejected", () => {
  assert.equal(G.acceptReview("t3", {}).ok, false);
  assert.equal(G.acceptReview("t3", null).ok, false);
});

test("reviewing without a selected profile is refused", () => {
  assert.equal(G.acceptReview(null, { profile: "t3" }).ok, false);
  assert.equal(G.acceptReview("auto", { profile: "t3" }).ok, false);
});

test("changing profile clears stale results, report and overrides but keeps the zip", () => {
  const zip = { name: "task.zip" };
  const before = { profile: "t3", results: new Map([["a", {}]]), report: { report_text: "x" },
                   overrides: [{ id: "a" }], reviewedProfile: "t3", zip };
  const after = G.resetForProfileChange(before, "t4");
  assert.equal(after.profile, "t4");
  assert.equal(after.results.size, 0);
  assert.equal(after.report, null);
  assert.deepEqual(after.overrides, []);
  assert.equal(after.reviewedProfile, null);
  assert.equal(after.zip, zip, "the zip stays in page memory");
  assert.equal(after.stale, true, "the user is told the old result no longer applies");
});

test("changing profile with nothing reviewed is not reported as stale", () => {
  assert.equal(G.resetForProfileChange({ results: new Map(), report: null }, "t4").stale, false);
});

test("relative time reads naturally", () => {
  const now = Date.parse("2026-09-10T12:00:00Z");
  assert.equal(G.relativeTime("2026-09-10T11:59:58Z", now), "just now");
  assert.equal(G.relativeTime("2026-09-10T11:59:30Z", now), "30s ago");
  assert.equal(G.relativeTime("2026-09-10T11:57:00Z", now), "3 min ago");
  assert.equal(G.relativeTime("2026-09-10T09:00:00Z", now), "3 hr ago");
  assert.equal(G.relativeTime("2026-09-01T12:00:00Z", now), "9 days ago");
  assert.equal(G.relativeTime("not a date", now), "");
});

test("only unknown static or rubric findings can be resolved by a reviewer", () => {
  assert.equal(G.canResolve({ status: "unknown", layer: "static" }), true);
  assert.equal(G.canResolve({ status: "unknown", layer: "rubric" }), true);
  assert.equal(G.canResolve({ status: "missing", layer: "static" }), false);
  assert.equal(G.canResolve({ status: "unknown", layer: "advisory" }), false);
  assert.equal(G.canResolve(null), false);
});
