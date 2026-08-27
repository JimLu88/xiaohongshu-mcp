import assert from "node:assert/strict";
import fs from "node:fs";

import {
  validateFirstWaveCandidates,
} from "./validate_xhs_first_wave_candidates.mjs";


const payload = JSON.parse(
  fs.readFileSync(
    new URL(
      "../research/panse_multi_direction/first_wave_article_candidates_v1.json",
      import.meta.url,
    ),
    "utf8",
  ),
);

const result = validateFirstWaveCandidates(payload);
assert.equal(result.passed, true);
assert.equal(result.errors.length, 0);
assert.equal(result.input_candidates, 5);
assert.equal(result.verified_local_sources.length, 7);
assert.equal(result.verified_snapshot_sources.length, 11);
assert.equal(result.queue.summary.preconditions_ready, 4);
assert.equal(result.queue.summary.awaiting_style_lab_generation, 4);
assert.equal(result.queue.summary.ready_but_generation_disabled_during_warmup, 0);
assert.equal(result.queue.summary.rejected_by_precondition, 1);
assert.equal(result.queue.text_generated, false);
assert.equal(result.queue.external_posting_enabled, false);
assert.equal(result.queue.publish_allowed, false);
assert.ok(
  result.queue.records.every(
    (record) =>
      record.style_generation.required_model_id === "gpt-5.6-sol" &&
      record.style_generation.fallback_model_allowed === false &&
      record.eligible_for_style_generation === record.preconditions_ready &&
      record.publish_allowed === false,
  ),
);

const rejected = result.queue.records.filter((record) => !record.preconditions_ready);
assert.equal(rejected.length, 1);
assert.equal(rejected[0].candidate_id, "fw04-one-table-three-homes");
assert.deepEqual(rejected[0].failed_gates, ["场景合成专属门"]);

const changedBrief = structuredClone(payload);
changedBrief.candidates[0].sourced_article_brief += "改动";
assert.equal(validateFirstWaveCandidates(changedBrief).passed, false);
assert.ok(
  validateFirstWaveCandidates(changedBrief).errors.some((error) =>
    error.includes("brief_sha256 mismatch"),
  ),
);

const changedSnapshot = structuredClone(payload);
changedSnapshot.candidates[2].evidence_pack[0].source_snapshot += " changed";
assert.equal(validateFirstWaveCandidates(changedSnapshot).passed, false);
assert.ok(
  validateFirstWaveCandidates(changedSnapshot).errors.some((error) =>
    error.includes("source_snapshot SHA-256 mismatch"),
  ),
);

const changedLocalHash = structuredClone(payload);
changedLocalHash.candidates[1].evidence_pack[0].content_sha256 = "0".repeat(64);
assert.equal(validateFirstWaveCandidates(changedLocalHash).passed, false);
assert.ok(
  validateFirstWaveCandidates(changedLocalHash).errors.some((error) =>
    error.includes("local body SHA-256 mismatch"),
  ),
);

const changedPolicyHash = structuredClone(payload);
changedPolicyHash.candidates[3].evidence_pack[2].content_sha256 = "0".repeat(64);
assert.equal(validateFirstWaveCandidates(changedPolicyHash).passed, false);
assert.ok(
  validateFirstWaveCandidates(changedPolicyHash).errors.some((error) =>
    error.includes("local file SHA-256 mismatch"),
  ),
);

process.stdout.write(
  `${JSON.stringify(
    {
      passed: true,
      tests: 20,
      queue_summary: result.queue.summary,
      rejected_candidate: rejected[0].candidate_id,
      failed_gate: rejected[0].failed_gates[0],
    },
    null,
    2,
  )}\n`,
);
