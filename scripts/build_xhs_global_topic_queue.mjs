import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

export const GLOBAL_DEBATE_BASES = new Set([
  "craft_process_difference",
  "material_aesthetic_difference",
  "market_preference_difference",
  "context_difference",
  "local_adaptation_tradeoff",
  "real_tradeoff",
  "preference_split",
]);

const BROAD_GENERALIZATION_PATTERNS = [
  /国外(人)?(都|普遍|就是|一定|更高级|更文明|更懂)/u,
  /外国人(都|普遍|就是|一定|更高级|更文明|更懂)/u,
  /中国人(都|普遍|就是|一定|不懂|不如|只认)/u,
  /西方人(都|普遍|就是|一定)/u,
  /国外工艺(一定|就是|普遍).{0,8}(更好|更先进)/u,
  /国外.{0,10}(接受度|偏好).{0,8}(更高|更低|更强)/u,
  /中国.{0,10}(接受度|偏好).{0,8}(更高|更低|更强)/u,
];

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function normalizeText(value = "") {
  return String(value)
    .normalize("NFKC")
    .replace(/\s+/gu, " ")
    .trim();
}

function validateFramework(registry) {
  const errors = [];
  const macroThemes = Array.isArray(registry?.macro_themes)
    ? registry.macro_themes
    : [];
  const articleSeeds = Array.isArray(registry?.article_seed_bank)
    ? registry.article_seed_bank
    : [];
  const contentDomains = Array.isArray(registry?.pillars)
    ? registry.pillars
    : [];
  const mappings = registry?.article_seed_mappings ?? {};
  if (registry?.framework_id !== "global_furniture_craft_culture_v1") {
    errors.push("framework_id 不正确");
  }
  if (registry?.account_id !== "global_furniture_editor") {
    errors.push("必须由 global_furniture_editor 承载");
  }
  if (macroThemes.length < 15 || macroThemes.length > 20) {
    errors.push("一级开放主题数量必须在 15—20 个之间");
  }
  const macroThemeIds = macroThemes.map((theme) =>
    normalizeText(theme?.theme_id),
  );
  if (new Set(macroThemeIds).size !== macroThemeIds.length) {
    errors.push("一级主题 theme_id 存在重复");
  }
  const contentDomainIds = new Set(
    contentDomains.map((domain) => normalizeText(domain?.pillar_id)),
  );
  if (contentDomainIds.size < 4) {
    errors.push("框架至少需要四个内容领域");
  }

  for (const theme of macroThemes) {
    const prefix = normalizeText(theme?.theme_id) || "unknown_macro_theme";
    const searchable = normalizeText(
      [
        theme?.name,
        theme?.open_question,
        ...(theme?.example_questions ?? []),
      ]
        .filter(Boolean)
        .join(" "),
    );
    if (
      !prefix ||
      !normalizeText(theme?.name) ||
      !normalizeText(theme?.open_question)
    ) {
      errors.push(`${prefix}: 缺少一级主题 ID、名称或开放问题`);
    }
    if (
      !Array.isArray(theme?.subtopic_families) ||
      theme.subtopic_families.length < 4
    ) {
      errors.push(`${prefix}: 每个一级主题至少需要四个子话题族`);
    }
    if (
      !Array.isArray(theme?.example_questions) ||
      theme.example_questions.length < 2
    ) {
      errors.push(`${prefix}: 每个一级主题至少需要两个示例问题`);
    }
    if (
      BROAD_GENERALIZATION_PATTERNS.some((pattern) =>
        pattern.test(searchable),
      )
    ) {
      errors.push(`${prefix}: 一级主题出现笼统群体或工艺优越判断`);
    }
  }

  const topicIds = articleSeeds.map((seed) =>
    normalizeText(seed?.topic_id),
  );
  if (new Set(topicIds).size !== topicIds.length) {
    errors.push("文章种子 topic_id 存在重复");
  }
  for (const seed of articleSeeds) {
    const prefix = normalizeText(seed?.topic_id) || "unknown_article_seed";
    const searchable = normalizeText(
      [
        seed?.working_title,
        seed?.core_question,
        seed?.neutral_prompt,
      ]
        .filter(Boolean)
        .join(" "),
    );
    if (!prefix || !normalizeText(seed?.working_title)) {
      errors.push(`${prefix}: 缺少 topic_id 或标题`);
    }
    if (!contentDomainIds.has(normalizeText(seed?.pillar_id))) {
      errors.push(`${prefix}: 内容领域 pillar_id 不在框架中`);
    }
    if (seed?.account_id !== "global_furniture_editor") {
      errors.push(`${prefix}: 承载账号错误`);
    }
    if (seed?.claim_scope !== "named_market_brand_standard_or_case") {
      errors.push(`${prefix}: 必须限定到具体市场、品牌、标准或案例`);
    }
    if (
      !Array.isArray(seed?.evidence_requirements) ||
      seed.evidence_requirements.length < 3
    ) {
      errors.push(`${prefix}: 至少需要三类证据`);
    }
    if (
      BROAD_GENERALIZATION_PATTERNS.some((pattern) =>
        pattern.test(searchable),
      )
    ) {
      errors.push(`${prefix}: 出现笼统群体或工艺优越判断`);
    }
    if (
      seed?.content_mode === "constructive_debate_candidate" &&
      !GLOBAL_DEBATE_BASES.has(normalizeText(seed?.debate_basis))
    ) {
      errors.push(`${prefix}: 争点依据不在允许范围`);
    }
    if (
      seed?.content_mode === "constructive_debate_candidate" &&
      !normalizeText(seed?.neutral_prompt)
    ) {
      errors.push(`${prefix}: 争点候选缺少中性提问`);
    }
    if (!normalizeText(seed?.china_localization)) {
      errors.push(`${prefix}: 缺少中国家庭适配任务`);
    }
    if (!Array.isArray(seed?.red_lines) || seed.red_lines.length === 0) {
      errors.push(`${prefix}: 缺少选题红线`);
    }
    const mappedThemes = Array.isArray(mappings[prefix])
      ? mappings[prefix]
      : [];
    if (mappedThemes.length < 2) {
      errors.push(`${prefix}: 至少映射到两个一级开放主题`);
    }
    for (const themeId of mappedThemes) {
      if (!macroThemeIds.includes(normalizeText(themeId))) {
        errors.push(`${prefix}: 映射到不存在的一级主题 ${themeId}`);
      }
    }
  }
  return errors;
}

export function buildGlobalTopicQueue(
  registry,
  generatedAt = new Date().toISOString(),
) {
  const errors = validateFramework(registry);
  if (errors.length > 0) {
    throw new Error(`Global topic framework validation failed:\n${errors.join("\n")}`);
  }
  const macroThemeRecords = registry.macro_themes.map((theme, index) => ({
    theme_id: normalizeText(theme.theme_id),
    priority_order: index + 1,
    name: normalizeText(theme.name),
    open_question: normalizeText(theme.open_question),
    subtopic_families: theme.subtopic_families.map(normalizeText),
    example_questions: theme.example_questions.map(normalizeText),
    debate_eligible: theme.debate_eligible === true,
    hierarchy_level: "macro_theme",
    queue_status: "active_theme_direction",
    human_review_required: true,
    write_allowed: false,
    publish_allowed: false,
  }));
  const articleSeeds = [...registry.article_seed_bank].sort(
    (left, right) =>
      Number(left?.priority_order ?? 999) -
      Number(right?.priority_order ?? 999),
  );
  const articleSeedRecords = articleSeeds.map((seed) => ({
    topic_id: normalizeText(seed.topic_id),
    priority_order: Number(seed.priority_order),
    pillar_id: normalizeText(seed.pillar_id),
    account_id: "global_furniture_editor",
    working_title: normalizeText(seed.working_title),
    core_question: normalizeText(seed.core_question),
    content_mode: normalizeText(seed.content_mode),
    debate_basis: normalizeText(seed.debate_basis),
    neutral_prompt: normalizeText(seed.neutral_prompt),
    china_localization: normalizeText(seed.china_localization),
    evidence_requirements: seed.evidence_requirements,
    visual_plan: seed.visual_plan,
    red_lines: seed.red_lines,
    macro_theme_ids: registry.article_seed_mappings[seed.topic_id],
    hierarchy_level: "article_seed",
    queue_status: "awaiting_source_pack",
    source_pack_complete: false,
    human_review_required: true,
    write_allowed: false,
    publish_allowed: false,
  }));
  const debateCandidates = articleSeedRecords.filter(
    (record) => record.content_mode === "constructive_debate_candidate",
  );
  const subtopicFamilyCount = macroThemeRecords.reduce(
    (sum, record) => sum + record.subtopic_families.length,
    0,
  );
  return {
    schema_version: 2,
    generated_at: generatedAt,
    system: "panse_global_furniture_topic_queue",
    execution_scope: "local_planning_only",
    network_access_performed: false,
    external_platform_write_performed: false,
    framework: {
      framework_id: registry.framework_id,
      display_name: registry.display_name,
      account_id: registry.account_id,
      direction: registry.direction,
      scope_rule: registry.scope_rule,
      evidence_policy: registry.evidence_policy,
    },
    summary: {
      content_domain_count: registry.pillars.length,
      macro_theme_count: macroThemeRecords.length,
      subtopic_family_count: subtopicFamilyCount,
      article_seed_count: articleSeedRecords.length,
      debate_eligible_macro_themes: macroThemeRecords.filter(
        (record) => record.debate_eligible,
      ).length,
      constructive_debate_article_seeds: debateCandidates.length,
      evergreen_article_seeds:
        articleSeedRecords.length - debateCandidates.length,
      first_wave_macro_theme_ids: macroThemeRecords
        .slice(0, 6)
        .map((record) => record.theme_id),
      first_wave_article_seed_ids: articleSeedRecords
        .slice(0, 6)
        .map((record) => record.topic_id),
    },
    hierarchy: [
      "macro_theme",
      "subtopic_family",
      "article_seed",
      "sourced_article_brief",
    ],
    scheduling_policy: {
      constructive_debate_maximum_per_ten_posts: 1,
      constructive_debate_cooldown_days: 7,
      debate_candidates_are_not_automatic_slots: true,
      source_pack_required_before_writing: true,
      human_approval_required: true,
      publish_allowed: false,
    },
    content_domains: registry.pillars,
    macro_theme_records: macroThemeRecords,
    article_seed_records: articleSeedRecords,
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
      "Usage: node scripts/build_xhs_global_topic_queue.mjs --input <framework.json> [--output <queue.json>] [--compact]",
    );
  }
  const queue = buildGlobalTopicQueue(readJson(path.resolve(args.input)));
  const serialized = `${JSON.stringify(queue, null, args.compact ? 0 : 2)}\n`;
  if (args.output) {
    const outputPath = path.resolve(args.output);
    fs.mkdirSync(path.dirname(outputPath), { recursive: true });
    fs.writeFileSync(outputPath, serialized, "utf8");
    process.stdout.write(
      `${JSON.stringify({ output: outputPath, ...queue.summary }, null, 2)}\n`,
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
