#!/usr/bin/env node

/**
 * Build a balanced 100-comment human corpus and 100 matched Style Lab requests.
 *
 * This script is local-only. It neither opens Xiaohongshu nor publishes anything.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(SCRIPT_DIR, "..");
const RESEARCH = path.join(REPO, "research", "panse_multi_direction");
const DEEP_READS_PATH = path.join(RESEARCH, "day05_deep_reads_2026-08-06.json");
const CORRECTIONS_PATH = path.join(RESEARCH, "day05_comment_human_corrections_2026-08-06.json");
const CORPUS_PATH = path.join(RESEARCH, "style_experiment_real_comments_100_2026-08-06.json");
const REQUESTS_PATH = path.join(RESEARCH, "style_experiment_four_mode_generation_requests_100_2026-08-07.json");

const deepReads = JSON.parse(fs.readFileSync(DEEP_READS_PATH, "utf8"));
const corrections = JSON.parse(fs.readFileSync(CORRECTIONS_PATH, "utf8"));

const normalize = (value) => String(value ?? "").replace(/\s+/gu, " ").trim();

const SIGNALS = {
  praise: /好看|漂亮|喜欢|温馨|舒服|氛围|治愈|厉害|绝了|太美|高级|可爱|羡慕|心动|爱了|梦中情|有生活|抄作业|参考|赞|真棒|真好/iu,
  question: /[?？]|请问|想问|怎么|哪里|哪儿|多大|多少|是不是|可以问|求问|什么|为啥|为什么|有链接|求链接|尺寸|朝向/iu,
  experience: /我家|我也|我们家|我在|我用|我买|我装|我住|同款|正在装修|准备装修|打算|我觉得|我感觉|我会|我想|我正/iu,
  humor: /哈哈|笑死|搬出去|离开我的家|让我住|给我住|排队|偷走|打劫|梦里|请出去|夺舍|地址给我|不许住/iu,
  suggestion: /建议|最好|可以试|可以把|要考虑|注意|别|不要|得看|需要|不如|换成|记得|尽量|实在不行/iu,
  answer: /^(朝南|不是|是的|是|没有|有|对|嗯|可以|不可以|不会|会|\d+(?:[.*×xX]\d+)?(?:米|m|cm|厘米|平|个)?|[A-Za-z0-9 ._-]+)$/iu,
  teacher_posture: /真正|关键|本质|更值得参考|主要还得看|别硬|必须|一定要|照着做|听我的|比.*更有参考|正确做法|应该先|才是/iu,
  uncertainty: /好像|感觉|可能|是不是|会不会|有点|看起来|我猜|也许|吧|呢|呀|啊|嘛/iu,
  emoji: /\p{Extended_Pictographic}|[👍🙏✨❤️❤💡‼️❗️❓☀️🟤⚫️⚪️]/u,
};

function labelsFor(text) {
  const labels = [];
  for (const [name, pattern] of Object.entries(SIGNALS)) {
    if (pattern.test(text)) labels.push(name);
  }
  if (!labels.some((label) => ["praise", "question", "experience", "humor", "suggestion", "answer"].includes(label))) {
    labels.push("other");
  }
  return labels;
}

function primaryLabel(labels) {
  for (const label of ["humor", "praise", "question", "experience", "suggestion", "answer", "other"]) {
    if (labels.includes(label)) return label;
  }
  return "other";
}

const candidatesByNote = deepReads.records.map((record) => {
  const seen = new Set();
  const comments = [];
  for (const raw of record.visible_comments ?? []) {
    const text = normalize(raw);
    if (text.length < 2 || text.length > 180 || seen.has(text)) continue;
    seen.add(text);
    const labels = labelsFor(text);
    comments.push({ text, labels, primary_label: primaryLabel(labels) });
  }
  return { record, comments };
});

const selected = [];
const selectedText = new Set();
const selectedPerNote = new Map();
const categoryCounts = new Map();

function addCandidate(note, comment) {
  if (!comment || selectedText.has(comment.text)) return false;
  selected.push({ note, comment });
  selectedText.add(comment.text);
  const used = selectedPerNote.get(note.note_id) ?? [];
  used.push(comment);
  selectedPerNote.set(note.note_id, used);
  categoryCounts.set(comment.primary_label, (categoryCounts.get(comment.primary_label) ?? 0) + 1);
  return true;
}

// Two passes guarantee broad source coverage before adding a third item from any note.
for (let pass = 0; pass < 2; pass += 1) {
  for (const { record, comments } of candidatesByNote) {
    const already = selectedPerNote.get(record.note_id) ?? [];
    const usedCategories = new Set(already.map((item) => item.primary_label));
    const ranked = [...comments].sort((a, b) => {
      const categoryNoveltyA = usedCategories.has(a.primary_label) ? 1 : 0;
      const categoryNoveltyB = usedCategories.has(b.primary_label) ? 1 : 0;
      if (categoryNoveltyA !== categoryNoveltyB) return categoryNoveltyA - categoryNoveltyB;
      const countA = categoryCounts.get(a.primary_label) ?? 0;
      const countB = categoryCounts.get(b.primary_label) ?? 0;
      if (countA !== countB) return countA - countB;
      return Math.abs(a.text.length - 24) - Math.abs(b.text.length - 24);
    });
    addCandidate(record, ranked.find((item) => !selectedText.has(item.text)));
  }
}

while (selected.length < 100) {
  let best = null;
  for (const { record, comments } of candidatesByNote) {
    const perNoteCount = (selectedPerNote.get(record.note_id) ?? []).length;
    for (const comment of comments) {
      if (selectedText.has(comment.text)) continue;
      const score =
        perNoteCount * 1000 +
        (categoryCounts.get(comment.primary_label) ?? 0) * 20 +
        Math.abs(comment.text.length - 28);
      if (!best || score < best.score) best = { record, comment, score };
    }
  }
  if (!best) throw new Error(`Only found ${selected.length} unique eligible comments`);
  addCandidate(best.record, best.comment);
}

const interactionModeByIndex = [
  ...Array(40).fill("support_only"),
  ...Array(35).fill("curiosity_question"),
  ...Array(15).fill("soft_observation"),
  ...Array(10).fill("light_humor_or_neutral"),
];
const noteOccurrences = new Map();

const samples = selected.map(({ note, comment }, index) => {
  const occurrence = noteOccurrences.get(note.note_id) ?? 0;
  noteOccurrences.set(note.note_id, occurrence + 1);
  return {
    sample_id: `real-xhs-${String(index + 1).padStart(3, "0")}`,
    note_id: note.note_id,
    source_locator: note.url,
    note_title: note.title,
    note_author: note.author,
    comment_text: comment.text,
    signal_labels: comment.labels,
    primary_label: comment.primary_label,
    matched_generation_intent: interactionModeByIndex[index],
    provenance: "visible public comment stored in day05 deep-read artifact",
  };
});

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function summarize(items, textKey) {
  const texts = items.map((item) => normalize(item[textKey]));
  const lengths = texts.map((text) => [...text].length);
  const signalCounts = {};
  for (const [name, pattern] of Object.entries(SIGNALS)) {
    signalCounts[name] = texts.filter((text) => pattern.test(text)).length;
  }
  return {
    count: texts.length,
    source_note_count: new Set(items.map((item) => item.note_id)).size,
    character_length: {
      min: Math.min(...lengths),
      max: Math.max(...lengths),
      mean: Number((lengths.reduce((sum, value) => sum + value, 0) / lengths.length).toFixed(2)),
      median: median(lengths),
    },
    signal_counts: signalCounts,
    signal_rates: Object.fromEntries(
      Object.entries(signalCounts).map(([name, count]) => [name, Number((count / texts.length).toFixed(3))]),
    ),
  };
}

const corpusPayload = {
  schema_version: 1,
  project: "panse_xiaohongshu",
  created_at: "2026-08-06",
  purpose: "Balanced real-comment reference corpus for a 100-vs-100 Style Lab experiment.",
  source_artifact: path.relative(REPO, DEEP_READS_PATH).replaceAll("\\", "/"),
  source_visible_comment_total: deepReads.records.reduce((sum, record) => sum + (record.visible_comments?.length ?? 0), 0),
  source_unique_comment_total: new Set(
    deepReads.records.flatMap((record) => (record.visible_comments ?? []).map(normalize).filter(Boolean)),
  ).size,
  selection_method: {
    target_count: 100,
    broad_source_coverage_first: true,
    duplicate_text_removed: true,
    source_note_cap_soft: 3,
    category_diversity_labels: ["praise", "question", "experience", "humor", "suggestion", "answer", "other"],
    caveat: "Keyword labels are descriptive heuristics, not ground-truth sentiment or intent labels.",
  },
  summary: summarize(samples, "comment_text"),
  samples,
  network_access_performed: false,
  external_posting_performed: false,
};

const intentRules = {
  support_only: "只回应一个能够从正文或可见评论定位的具体优点；不提建议、不提问、不补家庭日常落点。",
  curiosity_question: "先承接一个可定位的具体细节，再问一个正文和全部可见评论尚未回答的问题；不把建议伪装成问题。",
  soft_observation: "先承接一个可定位的具体细节，再用不确定语气补一个普通家庭条件和一个可能的日常影响。",
  light_humor_or_neutral: "顺着正文和评论区语气做一条轻松或中性回应；不嘲讽、不硬夸、不提建议。",
};

const modeLengthRanges = {
  support_only: [12, 38],
  curiosity_question: [18, 55],
  soft_observation: [25, 70],
  light_humor_or_neutral: [8, 32],
};

const requestItems = samples.map((sample, index) => {
  const note = deepReads.records.find((record) => record.note_id === sample.note_id);
  const intent = interactionModeByIndex[index];
  const [bodyMinChars, bodyMaxChars] = modeLengthRanges[intent];
  const requestId = `panse.style-experiment.comment.${String(index + 1).padStart(3, "0")}`;
  const briefText = [
    `目标原帖由${note.author}发布，标题为《${note.title || "未显示标题"}》。`,
    `已完整读取正文和当前保存的${note.visible_comments.length}条可见评论；不得只根据标题推断。`,
    `本条实验意图：${intentRules[intent]}`,
    "说话位置是来支持创作者的普通同好，不是老师、评委、验收人员或设计大师。",
    "具体承接必须带正文或可见评论的短证据定位；避免‘真正、关键、本质、必须、别硬、才是、比……更有参考性’等判卷式表达。",
    "只使用原帖正文和可见评论中能够观察到的信息，不虚构购买、入住、装修、施工、测评或长期使用经历。",
    `输出${bodyMinChars}—${bodyMaxChars}个中文字符，1—2句，不提畔色，不引导主页、私信、搜索、关注、点赞或购买。`,
  ].join("");
  return {
    experiment_id: `generated-xhs-${String(index + 1).padStart(3, "0")}`,
    comparison_sample_id: sample.sample_id,
    target_note: {
      note_id: note.note_id,
      title: note.title,
      author: note.author,
      source_locator: note.url,
    },
    generation_intent: intent,
    interaction_mode: intent,
    intent_rule: intentRules[intent],
    source_context: {
      body: note.body,
      visible_comments: note.visible_comments,
      body_nonempty: note.body_nonempty,
      image_count: note.image_count,
      warning: note.warning,
    },
    style_request: {
      request_id: requestId,
      idempotency_key: `panse:style-experiment:four-mode:2026-08-07:${sample.sample_id}`,
      brief_text: briefText,
      source_locator: note.url,
      rights_basis: "public note and visible public comments used only as context for a new non-quoting research draft",
      sensitivity: "internal",
      language: "zh-CN",
      channel: "小红书",
      scenario: "家居内容评论语气实验",
      audience: "关注家装、家具与空间生活的普通用户",
      use_case: "生成一条支持创作者、便于自然互动的研究评论草稿",
      artifact_type: "comment",
      interaction_mode: intent,
      source_context: {
        body: note.body,
        visible_comments: note.visible_comments,
        body_complete: true,
        visible_comments_complete: true,
        expected_visible_comment_count: note.visible_comments.length,
      },
      taxonomy_ids: [
        "platform.xiaohongshu-comment",
        "persona.lifestyle-curator",
        "role.editor",
        "scene.social-comment",
      ],
      style_card_refs: [
        { card_id: "preset.platform.xiaohongshu-comment", card_version: 12 },
        { card_id: "preset.persona.lifestyle-curator", card_version: 12 },
        { card_id: "preset.role.editor", card_version: 12 },
        { card_id: "preset.scene.social-comment", card_version: 12 },
      ],
      requested_strength: 0.5,
      style_requirement: "approved_required",
      pin_card_versions: true,
      required_model_id: "gpt-5.6-sol",
      fallback_model_allowed: false,
      content_contract: {
        protected_facts: note.title
          ? [
              {
                fact_id: "target_note_title",
                kind: "quote",
                required: false,
                value: note.title,
                aliases: [],
                subject: "",
                predicate: "",
                object: "",
                qualifiers: ["原帖标题，仅作上下文，不要求复述"],
                citation_anchor: "target_note",
              },
            ]
          : [],
        allowed_paraphrases: {},
        forbidden_inferences: [
          "不得虚构购买、入住、设计、装修、施工、检测或长期使用经历",
          "不得把品牌运营账号伪装成独立消费者、屋主、设计师或测评者",
          "不得只凭标题推断正文、图片或作者动机",
          "不得推断原帖和可见评论未确认的结构、材质、尺寸、朝向、照度、承重或健康效果",
          "不得为了显得友好而使用空洞模板夸奖",
          "不得以老师、评委或验收人员口吻纠正创作者",
          "不得提及畔色、引导私信、搜索品牌或站外联系",
        ],
        citation_anchors: note.title ? { target_note_title: "target_note" } : {},
        must_cover_fact_ids: [],
      },
      output: {
        title_candidates: 0,
        title_max_chars: 0,
        body_min_chars: bodyMinChars,
        body_max_chars: bodyMaxChars,
        tag_min: 0,
        tag_max: 0,
      },
      max_authorized_excerpt_chars: 0,
    },
  };
});

const requestsPayload = {
  schema_version: 1,
  project: "panse_xiaohongshu",
  created_at: "2026-08-07",
  phase: "style_research_only",
  account_slot: 2,
  account_id: "mix_home_editor",
  public_role: "空间生活提案编辑",
  source_real_corpus: path.relative(REPO, CORPUS_PATH).replaceAll("\\", "/"),
  human_gold_corrections: path.relative(REPO, CORRECTIONS_PATH).replaceAll("\\", "/"),
  provider_contract: {
    required_model_id: "gpt-5.6-sol",
    required_model_match: "exact",
    stages: ["plan", "draft", "semantic_review"],
    fallback_model_allowed: false,
    fail_closed_on_mismatch: true,
  },
  front_constraints: {
    full_note_body_required: true,
    visible_comment_context_required: true,
    supportive_peer_position_required: true,
    specific_honest_acknowledgement_preferred: true,
    critique_first_forbidden: true,
    teacher_or_judge_posture_forbidden: true,
    fabricated_firsthand_forbidden: true,
    canned_praise_forbidden: true,
    interaction_mode_required: true,
    question_answer_check_required: true,
    source_evidence_locator_required: true,
    daily_life_landing_required_only_for: "soft_observation",
    human_review_required: true,
    publish_allowed: false,
  },
  interaction_mode_counts: Object.fromEntries(
    Object.keys(intentRules).map((mode) => [
      mode,
      requestItems.filter((item) => item.interaction_mode === mode).length,
    ]),
  ),
  request_count: requestItems.length,
  requests: requestItems,
  network_access_performed: false,
  external_posting_performed: false,
};

if (!fs.existsSync(CORPUS_PATH)) {
  fs.writeFileSync(CORPUS_PATH, `${JSON.stringify(corpusPayload, null, 2)}\n`, "utf8");
}
fs.writeFileSync(REQUESTS_PATH, `${JSON.stringify(requestsPayload, null, 2)}\n`, "utf8");

console.log(JSON.stringify({
  corpus_path: path.relative(REPO, CORPUS_PATH),
  requests_path: path.relative(REPO, REQUESTS_PATH),
  real_comment_count: samples.length,
  source_note_count: corpusPayload.summary.source_note_count,
  category_counts: samples.reduce((acc, item) => {
    acc[item.primary_label] = (acc[item.primary_label] ?? 0) + 1;
    return acc;
  }, {}),
  external_posting_performed: false,
}, null, 2));
