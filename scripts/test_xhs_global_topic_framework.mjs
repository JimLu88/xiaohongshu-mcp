import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import {
  GLOBAL_DEBATE_BASES,
  buildGlobalTopicQueue,
} from "./build_xhs_global_topic_queue.mjs";

const registryPath = path.resolve(
  "research",
  "panse_multi_direction",
  "global_furniture_craft_culture_framework_v1.json",
);
const registry = JSON.parse(fs.readFileSync(registryPath, "utf8"));
const queue = buildGlobalTopicQueue(
  registry,
  "2026-07-31T00:00:00.000Z",
);

assert.equal(queue.summary.content_domain_count, 6);
assert.equal(queue.summary.macro_theme_count, 18);
assert.equal(queue.summary.subtopic_family_count, 72);
assert.equal(queue.summary.article_seed_count, 18);
assert.equal(queue.summary.debate_eligible_macro_themes, 11);
assert.equal(queue.summary.constructive_debate_article_seeds, 7);
assert.equal(queue.summary.evergreen_article_seeds, 11);
assert.equal(queue.framework.account_id, "global_furniture_editor");
assert.equal(queue.external_platform_write_performed, false);
assert.equal(queue.scheduling_policy.publish_allowed, false);
assert.equal(
  queue.scheduling_policy.constructive_debate_maximum_per_ten_posts,
  1,
);
assert.equal(queue.scheduling_policy.constructive_debate_cooldown_days, 7);
assert.ok(
  queue.macro_theme_records.every(
    (record) =>
      record.hierarchy_level === "macro_theme" &&
      record.subtopic_families.length >= 4 &&
      record.write_allowed === false &&
      record.publish_allowed === false,
  ),
);
assert.ok(
  queue.article_seed_records.every(
    (record) =>
      record.queue_status === "awaiting_source_pack" &&
      record.write_allowed === false &&
      record.publish_allowed === false &&
      record.human_review_required === true,
  ),
);
assert.ok(
  queue.article_seed_records.every(
    (record) =>
      record.evidence_requirements.length >= 3 &&
      record.account_id === "global_furniture_editor" &&
      record.macro_theme_ids.length >= 2,
  ),
);
assert.equal(GLOBAL_DEBATE_BASES.has("regional_language"), false);
assert.equal(
  GLOBAL_DEBATE_BASES.has("material_aesthetic_difference"),
  true,
);
const realTradeoff = queue.macro_theme_records.find(
  (record) => record.theme_id === "real_tradeoff",
);
assert.equal(realTradeoff.name, "真实取舍");
assert.ok(realTradeoff.subtopic_families.includes("通道与大尺寸家具"));
const contextDifference = queue.macro_theme_records.find(
  (record) => record.theme_id === "context_difference",
);
assert.equal(contextDifference.name, "场景差异");
const preferenceDivergence = queue.macro_theme_records.find(
  (record) => record.theme_id === "preference_divergence",
);
assert.equal(preferenceDivergence.name, "偏好分歧");
const knots = queue.article_seed_records.find(
  (record) => record.topic_id === "global_01_wood_knots",
);
assert.equal(knots.content_mode, "constructive_debate_candidate");
assert.match(knots.core_question, /分级/u);
assert.ok(knots.red_lines.some((line) => /结构安全/u.test(line)));
assert.deepEqual(queue.summary.first_wave_macro_theme_ids, [
  "real_tradeoff",
  "context_difference",
  "preference_divergence",
  "cognitive_contrast",
  "craft_misreading",
  "material_attitudes",
]);
assert.deepEqual(queue.summary.first_wave_article_seed_ids, [
  "global_01_wood_knots",
  "global_02_color_variation",
  "global_03_veneer_and_solid_wood",
  "global_04_oil_wax_lacquer",
  "global_05_patina_and_scratches",
  "global_07_visible_joinery",
]);

const invalidRegistry = structuredClone(registry);
invalidRegistry.macro_themes[0].example_questions[0] =
  "国外对木头结疤的接受度更高";
assert.throws(
  () => buildGlobalTopicQueue(invalidRegistry),
  /一级主题出现笼统群体或工艺优越判断/u,
);

process.stdout.write(
  `${JSON.stringify(
    {
      passed: true,
      tests: 27,
      summary: queue.summary,
    },
    null,
    2,
  )}\n`,
);
