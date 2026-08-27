import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import {
  buildFeedbackPlan,
} from "./build_xhs_post_feedback_plan.mjs";
import {
  DM_INTENTS,
  buildDmReviewQueue,
} from "./build_xhs_dm_review_queue.mjs";

const base = path.resolve(
  "research",
  "panse_multi_direction",
  "strategy_runtime_v2",
);
const metrics = JSON.parse(
  fs.readFileSync(path.join(base, "synthetic_post_metrics.json"), "utf8"),
);
const dmThreads = JSON.parse(
  fs.readFileSync(path.join(base, "synthetic_dm_threads.json"), "utf8"),
);

const feedback = buildFeedbackPlan(
  metrics,
  "2026-07-31T00:00:00.000Z",
);
assert.equal(feedback.summary.input_snapshots, 11);
assert.equal(feedback.summary.unique_latest_posts, 10);
assert.equal(feedback.summary.eligible_posts, 10);
assert.equal(feedback.summary.attention_only_posts, 1);
assert.equal(feedback.summary.brand_risk_posts, 0);
assert.equal(feedback.automatic_publication_enabled, false);
assert.equal(feedback.analytics_import_performed, false);
assert.equal(feedback.next_cycle.publish_allowed, false);
assert.equal(feedback.next_cycle.human_approval_required, true);
assert.equal(
  feedback.scoring_policy.comment_count_alone_can_increase_direction,
  false,
);
assert.ok(
  feedback.directions.image_mix_home.next_weight >
    feedback.directions.image_mix_home.previous_weight,
);
assert.ok(
  feedback.directions.global_furniture_observation.next_weight <
    feedback.directions.global_furniture_observation.previous_weight,
);
assert.equal(
  Object.values(feedback.next_cycle.direction_allocation).reduce(
    (sum, count) => sum + count,
    0,
  ),
  10,
);
assert.equal(
  feedback.next_cycle.constructive_debate.status,
  "hold_attention_only",
);
assert.equal(
  feedback.next_cycle.constructive_debate.recommended_slots_next_cycle,
  0,
);

const dmQueue = buildDmReviewQueue(
  dmThreads,
  "2026-07-31T00:00:00.000Z",
);
assert.equal(dmQueue.summary.input_threads, 10);
assert.equal(dmQueue.summary.unique_threads, 9);
assert.equal(dmQueue.summary.duplicates_removed, 1);
assert.equal(dmQueue.summary.awaiting_human_review, 7);
assert.equal(dmQueue.summary.rejected_by_policy, 2);
assert.equal(dmQueue.summary.deferred_to_next_batch, 0);
assert.equal(dmQueue.summary.urgent, 1);
assert.deepEqual(
  [...dmQueue.summary.intents_present].sort(),
  [...DM_INTENTS].sort(),
);
assert.equal(dmQueue.external_sending_enabled, false);
assert.equal(dmQueue.send_allowed, false);
assert.ok(dmQueue.records.every((record) => record.send_allowed === false));
const afterSales = dmQueue.records.find(
  (record) => record.intent === "after_sales_order",
);
assert.equal(afterSales.route_account_id, "panse_official");
assert.equal(afterSales.contains_sensitive_data, true);
assert.match(afterSales.incoming_excerpt_redacted, /手机号已遮蔽/u);
assert.match(afterSales.incoming_excerpt_redacted, /订单号已遮蔽/u);
assert.equal(afterSales.raw_message_retained, false);
assert.match(afterSales.reply_draft, /畔色官方/u);
assert.ok(
  dmQueue.records
    .filter((record) => record.queue_status === "awaiting_human_review")
    .every((record) => record.human_review_required),
);

const limitedDmQueue = buildDmReviewQueue(
  {
    ...dmThreads,
    config: {
      daily_review_limit: 3,
    },
  },
  "2026-07-31T00:00:00.000Z",
);
assert.equal(limitedDmQueue.summary.awaiting_human_review, 3);
assert.equal(limitedDmQueue.summary.deferred_to_next_batch, 4);
assert.ok(
  limitedDmQueue.records.some(
    (record) =>
      record.intent === "after_sales_order" &&
      record.queue_status === "awaiting_human_review",
  ),
);

const riskyMetrics = structuredClone(metrics);
const riskyDebate = riskyMetrics.posts.find(
  (post) => post.post_id === "p-space-1",
);
riskyDebate.metrics.reports = 2;
const riskyFeedback = buildFeedbackPlan(
  riskyMetrics,
  "2026-07-31T00:00:00.000Z",
);
assert.equal(riskyFeedback.summary.brand_risk_posts, 1);
assert.equal(
  riskyFeedback.next_cycle.constructive_debate.status,
  "paused_brand_risk",
);
assert.equal(
  riskyFeedback.next_cycle.constructive_debate.recommended_slots_next_cycle,
  0,
);

process.stdout.write(
  `${JSON.stringify(
    {
      passed: true,
      tests: 38,
      feedback_summary: feedback.summary,
      dm_summary: dmQueue.summary,
    },
    null,
    2,
  )}\n`,
);
