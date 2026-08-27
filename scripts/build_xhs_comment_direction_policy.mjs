import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  classifyCommentIntent,
  normalizeCommentText,
} from "./lib/xhs_comment_intent_policy.mjs";

const INTENT_POLICY_VERSION = "xhs-comment-intent.v3";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(SCRIPT_DIR, "..");
const RESEARCH = path.join(REPO, "research", "panse_multi_direction");
const TARGET_PER_ROLE = 150;

const paths = {
  slot2: path.join(RESEARCH, "day05_deep_reads_2026-08-06.json"),
  slot3a: path.join(RESEARCH, "batch05_anti_consumption_deep.json"),
  slot3b: path.join(RESEARCH, "batch05_transparent_validation_deep.json"),
  slot4: path.join(RESEARCH, "day06_live_deep_reads_54_2026-08-07.json"),
  slot5: path.join(RESEARCH, "fresh_global_comments_2026-08-09.json"),
  corpus: path.join(RESEARCH, "comment_direction_corpus_600_2026-08-09.json"),
  analysis: path.join(RESEARCH, "comment_direction_analysis_2026-08-09.json"),
  report: path.join(RESEARCH, "comment_direction_analysis_2026-08-09.md"),
  policy: path.join(RESEARCH, "xhs_comment_intent_policy_v3.json"),
};

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function writeJson(file, value) {
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function cleanVisibleComment(raw, sourceType) {
  let text = normalizeCommentText(typeof raw === "string" ? raw : raw?.content);
  if (sourceType === "fresh_global") {
    text = text
      .replace(/^回复\s+[^:：]{1,40}\s*[:：]\s*["“]?/u, "")
      .replace(
        /\s+(?:20\d{2}-\d{2}-\d{2}|\d{2}-\d{2}|\d+小时前)(?:[^\s"]{0,8})?(?:\s+["“]?\d+(?:\.\d+)?(?:万)?["”]?)*.*$/u,
        "",
      )
      .replace(/\s+(?:评论|说点什么|活动)(?:\s+.*)?$/u, "")
      .trim();
  }
  if (
    text.length < 2 ||
    text.length > 180 ||
    /^(作者|回复|关注一下发给你|发给你啦|说点什么|\d{2}-\d{2}[^\s]{0,8})$/u.test(text) ||
    /^[\d\s"“”'.+-]+$/u.test(text) ||
    /^[A-Za-z\s\W]{1,5}$/u.test(text)
  ) {
    return "";
  }
  return text;
}

function fromDay05() {
  return readJson(paths.slot2).records.map((note) => ({
    note_id: note.note_id,
    title: note.title,
    query: note.query,
    comments: (note.visible_comments ?? [])
      .map((value) => cleanVisibleComment(value, "day05"))
      .filter(Boolean),
  }));
}

function fromBatch05(file, sourceGroup) {
  return readJson(file).notes.map((note) => ({
    note_id: note.note_id,
    title: note.title,
    query: (note.found_by ?? []).map((item) => item.query).filter(Boolean).join(" / "),
    source_group: sourceGroup,
    comments: (note.first_page_comments ?? [])
      .filter(
        (comment) =>
          !note.author?.user_id ||
          !comment.author_user_id ||
          comment.author_user_id !== note.author.user_id,
      )
      .map((value) => cleanVisibleComment(value, "batch05"))
      .filter(Boolean),
  }));
}

function fromDay06() {
  return readJson(paths.slot4).notes.map((note) => ({
    note_id: note.note_id,
    title: note.title,
    query: note.query,
    comments: (note.visible_comments ?? [])
      .map((value) => cleanVisibleComment(value, "day06"))
      .filter(Boolean),
  }));
}

function fromFreshGlobal() {
  return readJson(paths.slot5).notes.map((note) => ({
    note_id: note.note_id,
    title: note.title,
    query: "国外家具设计 / 海外真实住宅",
    comments: (note.comments ?? [])
      .map((value) => cleanVisibleComment(value, "fresh_global"))
      .filter(Boolean),
  }));
}

function roundRobinSample(notes, target) {
  const seen = new Set();
  const selected = [];
  const maxDepth = Math.max(0, ...notes.map((note) => note.comments.length));
  for (let depth = 0; depth < maxDepth && selected.length < target; depth += 1) {
    for (const note of notes) {
      const text = note.comments[depth];
      if (!text || seen.has(text)) continue;
      seen.add(text);
      selected.push({
        note_id: note.note_id,
        note_title: note.title,
        query: note.query,
        source_group: note.source_group ?? "",
        comment_text: text,
        ...classifyCommentIntent(text),
      });
      if (selected.length >= target) break;
    }
  }
  if (selected.length < target) {
    throw new Error(`Only ${selected.length} unique comments available; need ${target}`);
  }
  return selected;
}

const roleInputs = [
  {
    slot: 2,
    account_id: "mix_home_editor",
    voice_id: "stylist",
    public_role: "空间生活提案编辑",
    sources: [paths.slot2],
    notes: fromDay05(),
  },
  {
    slot: 3,
    account_id: "furniture_decision_editor",
    voice_id: "evaluation_judgment",
    public_role: "理性家具决策编辑",
    sources: [paths.slot3a, paths.slot3b],
    notes: [
      ...fromBatch05(paths.slot3a, "anti_consumption"),
      ...fromBatch05(paths.slot3b, "transparent_validation"),
    ],
  },
  {
    slot: 4,
    account_id: "space_clinic",
    voice_id: "space_advisor",
    public_role: "户型、尺寸与动线顾问",
    sources: [paths.slot4],
    notes: fromDay06(),
  },
  {
    slot: 5,
    account_id: "global_furniture_editor",
    voice_id: "global_design_observer",
    public_role: "全球家具工艺与居住偏好观察编辑",
    sources: [paths.slot5],
    notes: fromFreshGlobal(),
  },
];

const corpusRoles = roleInputs.map((role) => ({
  ...role,
  notes: undefined,
  source_files: role.sources.map((file) => path.relative(REPO, file).replaceAll("\\", "/")),
  samples: roundRobinSample(role.notes, TARGET_PER_ROLE),
}));

function countBy(items, key) {
  const counts = {};
  for (const item of items) counts[item[key]] = (counts[item[key]] ?? 0) + 1;
  return counts;
}

function shareMap(counts, total) {
  return Object.fromEntries(
    Object.entries(counts).map(([key, count]) => [key, Number((count / total).toFixed(3))]),
  );
}

function roleSummary(role) {
  const intentCounts = countBy(role.samples, "primary_intent");
  const allLabels = role.samples.flatMap((sample) => sample.labels);
  const labelCounts = Object.fromEntries(
    [...new Set(allLabels)].map((label) => [
      label,
      role.samples.filter((sample) => sample.labels.includes(label)).length,
    ]),
  );
  const pragmaticCount = role.samples.filter((sample) => sample.pragmatic).length;
  const goalDirectedCount = role.samples.filter(
    (sample) => sample.primary_intent !== "neutral_social",
  ).length;
  const teacherCount = role.samples.filter((sample) => sample.teacher_posture).length;
  const critiqueFirstCount = role.samples.filter((sample) => sample.critique_first).length;
  return {
    slot: role.slot,
    account_id: role.account_id,
    voice_id: role.voice_id,
    public_role: role.public_role,
    sample_count: role.samples.length,
    source_note_count: new Set(role.samples.map((sample) => sample.note_id)).size,
    intent_counts: intentCounts,
    intent_shares: shareMap(intentCounts, role.samples.length),
    signal_counts: labelCounts,
    signal_shares: shareMap(labelCounts, role.samples.length),
    pragmatic_count: pragmaticCount,
    pragmatic_share: Number((pragmaticCount / role.samples.length).toFixed(3)),
    goal_directed_count: goalDirectedCount,
    goal_directed_share: Number((goalDirectedCount / role.samples.length).toFixed(3)),
    teacher_posture_count: teacherCount,
    critique_first_count: critiqueFirstCount,
  };
}

const summaries = corpusRoles.map(roleSummary);
const corpus = {
  schema_version: 1,
  project: "panse_xiaohongshu_four_editorial_accounts",
  created_at: "2026-08-09",
  purpose: "Observed public-comment direction corpus; preserve natural frequency instead of balancing categories.",
  sampling_method: {
    target_total: TARGET_PER_ROLE * corpusRoles.length,
    target_per_role: TARGET_PER_ROLE,
    duplicate_text_removed_within_role: true,
    broad_note_round_robin: true,
    category_balancing: false,
    author_reply_exclusion_when_author_ids_available: true,
    caveat: "Keyword labels describe interaction signals and are not demographic or sentiment ground truth.",
  },
  total_samples: TARGET_PER_ROLE * corpusRoles.length,
  roles: corpusRoles,
  network_access_performed_by_builder: false,
  external_posting_performed: false,
};

const analysis = {
  schema_version: 1,
  created_at: "2026-08-09",
  source_corpus: path.relative(REPO, paths.corpus).replaceAll("\\", "/"),
  total_samples: corpus.total_samples,
  role_summaries: summaries,
  cross_role: {
    pragmatic_count: corpusRoles.flatMap((role) => role.samples).filter((sample) => sample.pragmatic).length,
    pragmatic_share: Number((corpusRoles.flatMap((role) => role.samples).filter((sample) => sample.pragmatic).length / corpus.total_samples).toFixed(3)),
    goal_directed_count: corpusRoles.flatMap((role) => role.samples).filter((sample) => sample.primary_intent !== "neutral_social").length,
    goal_directed_share: Number((corpusRoles.flatMap((role) => role.samples).filter((sample) => sample.primary_intent !== "neutral_social").length / corpus.total_samples).toFixed(3)),
    intent_counts: countBy(corpusRoles.flatMap((role) => role.samples), "primary_intent"),
  },
  finding: "Real comments are led by concrete self-interest, utility fit, acquisition questions, grounded praise and self-reference; teacher-style evaluation is not a desirable generation target.",
};

const allowedByVoice = {
  stylist: ["acquisition_question", "utility_fit_question", "request_more", "grounded_praise", "self_reference_verified", "self_display_verified", "light_humor", "neutral_social"],
  evaluation_judgment: ["acquisition_question", "utility_fit_question", "request_more", "grounded_praise", "self_reference_verified", "self_display_verified", "peer_tip_invited", "contextual_disagreement", "neutral_social"],
  space_advisor: ["acquisition_question", "utility_fit_question", "request_more", "grounded_praise", "self_reference_verified", "self_display_verified", "peer_tip_invited", "light_humor", "neutral_social"],
  global_design_observer: ["acquisition_question", "utility_fit_question", "request_more", "grounded_praise", "self_reference_verified", "self_display_verified", "contextual_disagreement", "light_humor", "neutral_social"],
  official_explanation: ["acquisition_question", "utility_fit_question", "request_more", "grounded_praise", "peer_tip_invited", "contextual_disagreement", "neutral_social"],
  principal_sincere_signed: ["utility_fit_question", "request_more", "grounded_praise", "self_reference_verified", "peer_tip_invited", "contextual_disagreement", "neutral_social"],
};

const generationSequenceByVoice = {
  stylist: [
    ...Array(5).fill("utility_fit_question"),
    ...Array(4).fill("acquisition_question"),
    ...Array(5).fill("grounded_praise"),
    ...Array(2).fill("self_reference_verified"),
    "self_display_verified",
    "request_more",
    "light_humor",
    "neutral_social",
  ],
  evaluation_judgment: [
    ...Array(6).fill("utility_fit_question"),
    ...Array(5).fill("acquisition_question"),
    ...Array(3).fill("grounded_praise"),
    "self_reference_verified",
    "self_display_verified",
    ...Array(2).fill("request_more"),
    "peer_tip_invited",
    "neutral_social",
  ],
  space_advisor: [
    ...Array(7).fill("utility_fit_question"),
    ...Array(3).fill("acquisition_question"),
    ...Array(4).fill("grounded_praise"),
    ...Array(2).fill("self_reference_verified"),
    "self_display_verified",
    "request_more",
    "light_humor",
    "neutral_social",
  ],
  global_design_observer: [
    ...Array(4).fill("utility_fit_question"),
    ...Array(4).fill("acquisition_question"),
    ...Array(5).fill("grounded_praise"),
    ...Array(2).fill("self_reference_verified"),
    "self_display_verified",
    "request_more",
    "contextual_disagreement",
    "light_humor",
    "neutral_social",
  ],
  official_explanation: [
    ...Array(6).fill("utility_fit_question"),
    ...Array(4).fill("acquisition_question"),
    ...Array(4).fill("grounded_praise"),
    ...Array(2).fill("request_more"),
    "peer_tip_invited",
    "contextual_disagreement",
    ...Array(2).fill("neutral_social"),
  ],
  principal_sincere_signed: [
    ...Array(5).fill("utility_fit_question"),
    ...Array(6).fill("grounded_praise"),
    ...Array(2).fill("request_more"),
    ...Array(2).fill("self_reference_verified"),
    ...Array(2).fill("peer_tip_invited"),
    "contextual_disagreement",
    ...Array(2).fill("neutral_social"),
  ],
};

function targetShares(sequence) {
  return shareMap(countBy(sequence.map((primary_intent) => ({ primary_intent })), "primary_intent"), sequence.length);
}

const policy = {
  schema_version: 3,
  policy_version: INTENT_POLICY_VERSION,
  created_at: "2026-08-09",
  source_corpus: path.relative(REPO, paths.corpus).replaceAll("\\", "/"),
  source_analysis: path.relative(REPO, paths.analysis).replaceAll("\\", "/"),
  source_sample_count: corpus.total_samples,
  selection_rule: "Choose the interaction intent before drafting; use observed role frequency without fabricating motives, ownership or experience.",
  tachikoma_interaction_mode_map: {
    acquisition_question: "curiosity_question",
    utility_fit_question: "curiosity_question",
    request_more: "curiosity_question",
    grounded_praise: "support_only",
    self_reference_verified: "soft_observation",
    self_display_verified: "soft_observation",
    peer_tip_invited: "soft_observation",
    contextual_disagreement: "soft_observation",
    light_humor: "light_humor_or_neutral",
    neutral_social: "light_humor_or_neutral",
  },
  hard_rules: {
    declared_intent_required_before_generation: true,
    source_grounded_praise_required: true,
    unanswered_question_required: true,
    teacher_or_judge_posture_forbidden: true,
    critique_first_forbidden: true,
    advice_requires_author_invitation: true,
    self_reference_requires_verified_firsthand: true,
    self_display_requires_verified_firsthand: true,
    contextual_disagreement_max_share: 0.05,
    category_balancing_against_observed_distribution_forbidden: true,
    generated_goal_directed_min_share: 0.8,
  },
  roles: {
    ...Object.fromEntries(summaries.map((summary) => [
      summary.voice_id,
      {
        account_id: summary.account_id,
        public_role: summary.public_role,
        observed_intent_shares: summary.intent_shares,
        observed_pragmatic_share: summary.pragmatic_share,
        observed_goal_directed_share: summary.goal_directed_share,
        allowed_intents: allowedByVoice[summary.voice_id],
        generation_target_shares: targetShares(generationSequenceByVoice[summary.voice_id]),
        intent_sequence: generationSequenceByVoice[summary.voice_id],
      },
    ])),
    official_explanation: {
      account_id: "panse_official",
      public_role: "畔色官方说明",
      observed_intent_shares: {},
      observed_pragmatic_share: null,
      observed_goal_directed_share: null,
      allowed_intents: allowedByVoice.official_explanation,
      generation_target_shares: targetShares(generationSequenceByVoice.official_explanation),
      intent_sequence: generationSequenceByVoice.official_explanation,
      note: "Official reply route is preserved for queue compatibility; the 600-sample corpus covers slots 2-5 only.",
    },
    principal_sincere_signed: {
      account_id: "panse_official",
      public_role: "真实主理人署名回复",
      observed_intent_shares: {},
      observed_pragmatic_share: null,
      observed_goal_directed_share: null,
      allowed_intents: allowedByVoice.principal_sincere_signed,
      generation_target_shares: targetShares(generationSequenceByVoice.principal_sincere_signed),
      intent_sequence: generationSequenceByVoice.principal_sincere_signed,
      note: "Principal reply route is preserved for queue compatibility; first-hand claims still require verified participation.",
    },
  },
  publish_allowed: false,
  human_review_required: true,
};

const reportLines = [
  "# 小红书四方向真实评论方向分析（600条）",
  "",
  "本次不再人为平衡‘支持/提问/观察/幽默’，而是按来源笔记轮转抽样，保留真实出现比例。",
  "",
  "| 账号方向 | 样本 | 来源笔记 | 明确目的 | 功利信号 | 主要方向 |",
  "|---|---:|---:|---:|---|",
  ...summaries.map((summary) => {
    const top = Object.entries(summary.intent_counts).sort((a, b) => b[1] - a[1]).slice(0, 4).map(([name, count]) => `${name} ${count}`).join("、");
    return `| ${summary.public_role} | ${summary.sample_count} | ${summary.source_note_count} | ${(summary.goal_directed_share * 100).toFixed(1)}% | ${(summary.pragmatic_share * 100).toFixed(1)}% | ${top} |`;
  }),
  "",
  "## 固化结论",
  "",
  "1. 写作前必须先选互动目的，不能先写一句像专家点评的话，再反推它属于哪个方向。",
  "2. 购买、价格、链接、尺寸、适配、用途和后续资料是正常主流诉求，但问题必须是正文与可见评论尚未回答的真实问题。",
  "3. 夸奖要落在原帖可见细节；禁止空洞模板夸奖，也禁止‘先夸后判卷’。",
  "4. ‘我家、我买过、我用过、我这个更好’只有在真实经历被验证后才能使用。",
  "5. 未征求意见时不主动教学；否定、纠正、老师口吻和批判式开头直接拦截。",
  "6. 国外案例可以比较具体环境与使用条件，不得把个案泛化成国家或群体优劣。",
  "",
];

writeJson(paths.corpus, corpus);
writeJson(paths.analysis, analysis);
writeJson(paths.policy, policy);
fs.writeFileSync(paths.report, `${reportLines.join("\n")}\n`, "utf8");

process.stdout.write(`${JSON.stringify({
  corpus: path.relative(REPO, paths.corpus),
  analysis: path.relative(REPO, paths.analysis),
  policy: path.relative(REPO, paths.policy),
  report: path.relative(REPO, paths.report),
  total_samples: corpus.total_samples,
  roles: summaries.map((summary) => ({
    slot: summary.slot,
    sample_count: summary.sample_count,
    source_note_count: summary.source_note_count,
    pragmatic_share: summary.pragmatic_share,
  })),
  external_posting_performed: false,
}, null, 2)}\n`);
