import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const DEFAULT_DIRECTIONS = [
  "furniture_configuration_observation",
  "wait_before_buy",
  "global_furniture_observation",
  "image_mix_home",
  "space_diagnosis",
];

const DEFAULT_CONFIG = {
  minimum_observation_hours: 24,
  minimum_views: 50,
  minimum_samples_per_direction: 3,
  learning_rate: 0.35,
  maximum_weight_change_per_cycle: 0.08,
  minimum_direction_weight: 0.08,
  planned_posts_next_cycle: 10,
  exploration_share: 0.2,
  constructive_debate: {
    maximum_share: 0.12,
    cooldown_days: 7,
    maximum_slots_per_cycle: 1,
  },
};

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function finiteNumber(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : fallback;
}

function clamp(value, minimum, maximum) {
  return Math.min(maximum, Math.max(minimum, value));
}

function round(value, digits = 6) {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}

function normalizeWeights(weights, directions, minimumWeight) {
  const floor = Math.min(minimumWeight, 1 / directions.length);
  const prepared = Object.fromEntries(
    directions.map((direction) => [
      direction,
      Math.max(floor, finiteNumber(weights?.[direction], 0)),
    ]),
  );
  const total = Object.values(prepared).reduce((sum, value) => sum + value, 0);
  return Object.fromEntries(
    directions.map((direction) => [
      direction,
      round(prepared[direction] / total),
    ]),
  );
}

function latestPostSnapshots(posts) {
  const latest = new Map();
  for (const post of posts) {
    const postId = String(post?.post_id ?? "").trim();
    if (!postId) continue;
    const previous = latest.get(postId);
    const observationHours = finiteNumber(post?.observation_hours);
    const previousHours = finiteNumber(previous?.observation_hours);
    const observedAt = Date.parse(post?.observed_at ?? "") || 0;
    const previousObservedAt = Date.parse(previous?.observed_at ?? "") || 0;
    if (
      !previous ||
      observationHours > previousHours ||
      (observationHours === previousHours && observedAt > previousObservedAt)
    ) {
      latest.set(postId, post);
    }
  }
  return [...latest.values()];
}

function metricSignal(valuePerThousand, strongAt) {
  return clamp(valuePerThousand / strongAt, 0, 1);
}

function evaluatePost(post, config) {
  const metrics = post?.metrics ?? {};
  const qualitative = post?.qualitative ?? {};
  const views = finiteNumber(metrics.views);
  const impressions = finiteNumber(metrics.impressions);
  const likes = finiteNumber(metrics.likes);
  const saves = finiteNumber(metrics.saves);
  const comments = finiteNumber(metrics.comments);
  const shares = finiteNumber(metrics.shares);
  const profileVisits = finiteNumber(metrics.profile_visits);
  const follows = finiteNumber(metrics.follows);
  const inboundDms = finiteNumber(metrics.inbound_dms);
  const negativeFeedback = finiteNumber(metrics.negative_feedback);
  const reports = finiteNumber(metrics.reports);
  const meaningfulComments = Math.min(
    comments,
    finiteNumber(qualitative.meaningful_comments),
  );
  const hostileComments = Math.min(
    comments,
    finiteNumber(qualitative.hostile_comments),
  );
  const denominator = Math.max(views, 1);
  const perThousand = (value) => (value / denominator) * 1000;

  const reachSignal =
    impressions > 0
      ? clamp(views / impressions / 0.35, 0, 1)
      : clamp(Math.log10(views + 1) / 4, 0, 1);
  const saveSignal = metricSignal(perThousand(saves), 40);
  const discussionSignal = metricSignal(perThousand(comments), 30);
  const intentSignal = metricSignal(
    perThousand(profileVisits + follows * 3 + inboundDms * 5),
    45,
  );
  const qualitySignal =
    comments > 0 ? clamp(meaningfulComments / comments, 0, 1) : 0.5;
  const appreciationSignal = metricSignal(
    perThousand(likes * 0.35 + shares * 1.5),
    65,
  );
  const hostileRatio = comments > 0 ? hostileComments / comments : 0;
  const negativeRate = (negativeFeedback + reports * 5) / denominator;
  const safetyPenalty = clamp(hostileRatio * 0.7 + negativeRate * 25, 0, 1);

  const score = clamp(
    reachSignal * 0.16 +
      appreciationSignal * 0.14 +
      saveSignal * 0.22 +
      discussionSignal * 0.12 +
      intentSignal * 0.22 +
      qualitySignal * 0.14 -
      safetyPenalty * 0.45,
    0,
    1,
  );
  const eligible =
    finiteNumber(post?.observation_hours) >=
      config.minimum_observation_hours && views >= config.minimum_views;
  const contentMode = String(post?.content_mode ?? "evergreen");
  const attentionOnly =
    contentMode === "constructive_debate" &&
    discussionSignal >= 0.6 &&
    (saveSignal + intentSignal) / 2 < 0.25;
  const brandRisk =
    reports > 0 || hostileRatio > 0.35 || negativeRate > 0.012;

  return {
    post_id: String(post?.post_id ?? "").trim(),
    account_id: String(post?.account_id ?? "").trim(),
    direction: String(post?.direction ?? "").trim(),
    topic_cluster: String(post?.topic_cluster ?? "").trim(),
    content_mode: contentMode,
    observation_hours: finiteNumber(post?.observation_hours),
    eligible,
    score: round(score),
    signals: {
      reach: round(reachSignal),
      appreciation: round(appreciationSignal),
      save: round(saveSignal),
      discussion: round(discussionSignal),
      intent: round(intentSignal),
      comment_quality: round(qualitySignal),
      safety_penalty: round(safetyPenalty),
    },
    attention_only: attentionOnly,
    brand_risk: brandRisk,
    diagnostic:
      !eligible
        ? "数据窗口或浏览量不足，只记录不调权"
        : brandRisk
          ? "讨论带来品牌风险，本轮不因评论量上调"
          : attentionOnly
            ? "评论高但收藏、主页访问、关注或私信弱，判定为注意力型流量"
            : "可进入方向权重计算",
  };
}

function aggregateDirections(evaluated, directions) {
  return Object.fromEntries(
    directions.map((direction) => {
      const records = evaluated.filter(
        (record) =>
          record.eligible &&
          record.direction === direction &&
          !record.brand_risk &&
          !record.attention_only,
      );
      const score =
        records.length > 0
          ? records.reduce((sum, record) => sum + record.score, 0) /
            records.length
          : null;
      return [
        direction,
        {
          eligible_samples: records.length,
          mean_score: score === null ? null : round(score),
        },
      ];
    }),
  );
}

function updateDirectionWeights(
  priorWeights,
  aggregates,
  directions,
  config,
) {
  const scored = directions.filter(
    (direction) => aggregates[direction].mean_score !== null,
  );
  const scoreTotal = scored.reduce(
    (sum, direction) => sum + aggregates[direction].mean_score + 0.05,
    0,
  );
  const desired = {};
  for (const direction of directions) {
    const aggregate = aggregates[direction];
    if (aggregate.mean_score === null || scoreTotal === 0) {
      desired[direction] = priorWeights[direction];
      continue;
    }
    const performanceTarget =
      config.minimum_direction_weight +
      (1 - config.minimum_direction_weight * directions.length) *
        ((aggregate.mean_score + 0.05) / scoreTotal);
    const confidence = clamp(
      aggregate.eligible_samples / config.minimum_samples_per_direction,
      0,
      1,
    );
    desired[direction] =
      priorWeights[direction] * (1 - confidence) +
      performanceTarget * confidence;
  }

  const bounded = {};
  for (const direction of directions) {
    const proposedDelta =
      (desired[direction] - priorWeights[direction]) * config.learning_rate;
    const delta = clamp(
      proposedDelta,
      -config.maximum_weight_change_per_cycle,
      config.maximum_weight_change_per_cycle,
    );
    bounded[direction] = Math.max(
      config.minimum_direction_weight,
      priorWeights[direction] + delta,
    );
  }
  return normalizeWeights(
    bounded,
    directions,
    config.minimum_direction_weight,
  );
}

function allocatePosts(weights, totalPosts) {
  const entries = Object.entries(weights).map(([direction, weight]) => {
    const exact = weight * totalPosts;
    return {
      direction,
      exact,
      count: Math.floor(exact),
      remainder: exact - Math.floor(exact),
    };
  });
  let remaining =
    totalPosts - entries.reduce((sum, entry) => sum + entry.count, 0);
  entries
    .sort((left, right) => right.remainder - left.remainder)
    .forEach((entry) => {
      if (remaining > 0) {
        entry.count += 1;
        remaining -= 1;
      }
    });
  return Object.fromEntries(
    entries
      .sort((left, right) => left.direction.localeCompare(right.direction))
      .map((entry) => [entry.direction, entry.count]),
  );
}

function evaluateDebateMode(evaluated, config, plannedPosts) {
  const debatePosts = evaluated.filter(
    (record) => record.content_mode === "constructive_debate",
  );
  const risky = debatePosts.filter((record) => record.brand_risk);
  const attentionOnly = debatePosts.filter((record) => record.attention_only);
  const status =
    risky.length > 0
      ? "paused_brand_risk"
      : debatePosts.length > 0 &&
          attentionOnly.length / debatePosts.length >= 0.5
        ? "hold_attention_only"
        : "limited_test";
  const maximumByShare = Math.floor(
    plannedPosts * config.constructive_debate.maximum_share,
  );
  const slots =
    status === "limited_test"
      ? Math.min(
          config.constructive_debate.maximum_slots_per_cycle,
          Math.max(0, maximumByShare),
        )
      : 0;
  return {
    status,
    reviewed_posts: debatePosts.length,
    attention_only_posts: attentionOnly.length,
    brand_risk_posts: risky.length,
    recommended_slots_next_cycle: slots,
    maximum_share: config.constructive_debate.maximum_share,
    cooldown_days: config.constructive_debate.cooldown_days,
    reply_policy:
      "只回应真实观点和条件差异；不使用小号唱反调，不虚构争执，不反复追问煽动",
  };
}

export function buildFeedbackPlan(
  payload,
  generatedAt = new Date().toISOString(),
) {
  const config = {
    ...DEFAULT_CONFIG,
    ...(payload?.config ?? {}),
    constructive_debate: {
      ...DEFAULT_CONFIG.constructive_debate,
      ...(payload?.config?.constructive_debate ?? {}),
    },
  };
  const directions =
    Array.isArray(payload?.directions) && payload.directions.length > 0
      ? [...new Set(payload.directions.map(String))]
      : DEFAULT_DIRECTIONS;
  const posts = Array.isArray(payload?.posts) ? payload.posts : [];
  const latest = latestPostSnapshots(posts);
  const evaluated = latest.map((post) => evaluatePost(post, config));
  const priorWeights = normalizeWeights(
    payload?.current_direction_weights,
    directions,
    config.minimum_direction_weight,
  );
  const aggregates = aggregateDirections(evaluated, directions);
  const nextWeights = updateDirectionWeights(
    priorWeights,
    aggregates,
    directions,
    config,
  );
  const plannedPosts = Math.max(
    1,
    Math.floor(finiteNumber(config.planned_posts_next_cycle, 10)),
  );
  const allocation = allocatePosts(nextWeights, plannedPosts);
  const directionRecommendations = Object.fromEntries(
    directions.map((direction) => {
      const delta = nextWeights[direction] - priorWeights[direction];
      const sampleCount = aggregates[direction].eligible_samples;
      return [
        direction,
        {
          ...aggregates[direction],
          previous_weight: priorWeights[direction],
          next_weight: nextWeights[direction],
          weight_delta: round(delta),
          action:
            sampleCount < config.minimum_samples_per_direction
              ? "explore_until_sample_gate"
              : delta > 0.01
                ? "increase_carefully"
                : delta < -0.01
                  ? "reduce_carefully"
                  : "hold",
        },
      ];
    }),
  );

  return {
    schema_version: 1,
    generated_at: generatedAt,
    system: "panse_xiaohongshu_post_feedback_optimizer",
    execution_scope: "local_analysis_only",
    network_access_performed: false,
    analytics_import_performed: false,
    automatic_publication_enabled: false,
    summary: {
      input_snapshots: posts.length,
      unique_latest_posts: latest.length,
      eligible_posts: evaluated.filter((record) => record.eligible).length,
      attention_only_posts: evaluated.filter(
        (record) => record.attention_only,
      ).length,
      brand_risk_posts: evaluated.filter((record) => record.brand_risk).length,
      planned_posts_next_cycle: plannedPosts,
    },
    scoring_policy: {
      primary_signals: [
        "views_or_impressions",
        "saves",
        "profile_visits",
        "follows",
        "inbound_dms",
        "meaningful_comments",
      ],
      comment_count_alone_can_increase_direction: false,
      maximum_weight_change_per_cycle:
        config.maximum_weight_change_per_cycle,
      minimum_samples_per_direction:
        config.minimum_samples_per_direction,
      exploration_share: config.exploration_share,
    },
    directions: directionRecommendations,
    next_cycle: {
      direction_weights: nextWeights,
      direction_allocation: allocation,
      constructive_debate: evaluateDebateMode(
        evaluated,
        config,
        plannedPosts,
      ),
      human_approval_required: true,
      publish_allowed: false,
    },
    posts: evaluated,
  };
}

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 1) {
    const current = argv[index];
    if (current === "--input" || current === "--output") {
      args[current.slice(2)] = argv[index + 1];
      index += 1;
    } else if (current === "--compact") {
      args.compact = true;
    } else {
      throw new Error(`Unknown argument: ${current}`);
    }
  }
  return args;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.input) {
    throw new Error(
      "Usage: node scripts/build_xhs_post_feedback_plan.mjs --input <metrics.json> [--output <plan.json>] [--compact]",
    );
  }
  const result = buildFeedbackPlan(readJson(path.resolve(args.input)));
  const serialized = `${JSON.stringify(result, null, args.compact ? 0 : 2)}\n`;
  if (args.output) {
    const outputPath = path.resolve(args.output);
    fs.mkdirSync(path.dirname(outputPath), { recursive: true });
    fs.writeFileSync(outputPath, serialized, "utf8");
    process.stdout.write(
      `${JSON.stringify({ output: outputPath, ...result.summary }, null, 2)}\n`,
    );
    return;
  }
  process.stdout.write(serialized);
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  try {
    main();
  } catch (error) {
    process.stderr.write(`${error instanceof Error ? error.message : error}\n`);
    process.exitCode = 1;
  }
}
