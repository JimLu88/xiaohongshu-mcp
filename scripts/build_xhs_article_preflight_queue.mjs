import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";


const MODULE_DIR = path.dirname(fileURLToPath(import.meta.url));
export const ARTICLE_STYLE_CONTRACT_PATH = path.resolve(
  MODULE_DIR,
  "..",
  "research",
  "panse_multi_direction",
  "xhs_article_style_contract_v2.json",
);
export const LAUNCH_CONFIG_PATH = path.resolve(
  MODULE_DIR,
  "..",
  "research",
  "panse_multi_direction",
  "five_direction_launch_config.json",
);
export const ARTICLE_STYLE_CONTRACT = readJson(ARTICLE_STYLE_CONTRACT_PATH);
export const LAUNCH_CONFIG = readJson(LAUNCH_CONFIG_PATH);


function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}


function normalizeText(value) {
  return String(value ?? "")
    .replace(/\s+/gu, " ")
    .trim();
}


function canonicalJson(value) {
  if (Array.isArray(value)) {
    return `[${value.map((item) => canonicalJson(item)).join(",")}]`;
  }
  if (value && typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}


function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}


function articleInputFingerprint(candidate) {
  const { style_lab_receipt: ignoredReceipt, ...withoutReceipt } = candidate ?? {};
  void ignoredReceipt;
  return sha256(canonicalJson(withoutReceipt));
}


function gate(name, passed, reason) {
  return { name, passed: Boolean(passed), reason };
}


function isSha256(value) {
  return /^[0-9a-f]{64}$/u.test(normalizeText(value));
}


function isIsoDate(value) {
  return !Number.isNaN(Date.parse(normalizeText(value)));
}


function profileForDirection(direction) {
  return ARTICLE_STYLE_CONTRACT.direction_profiles.find(
    (profile) => profile.direction === direction,
  );
}


function factContractComplete(factContract) {
  return (
    Array.isArray(factContract?.protected_facts) &&
    factContract?.allowed_paraphrases &&
    typeof factContract.allowed_paraphrases === "object" &&
    !Array.isArray(factContract.allowed_paraphrases) &&
    Array.isArray(factContract?.forbidden_inferences) &&
    factContract?.citation_anchors &&
    typeof factContract.citation_anchors === "object" &&
    !Array.isArray(factContract.citation_anchors) &&
    Array.isArray(factContract?.must_cover_fact_ids)
  );
}


function evaluateDirectionGate(candidate, direction) {
  if (direction === "furniture_configuration_observation") {
    const context = candidate?.decision_context ?? {};
    const passed = [context.room, context.budget, context.use_condition].some(
      (value) => Boolean(normalizeText(value)),
    );
    return gate(
      "家具配置条件门",
      passed,
      passed
        ? "已登记房间、预算或使用条件"
        : "至少需要一个真实房间、预算或使用条件",
    );
  }
  if (direction === "wait_before_buy") {
    const alternatives = new Set(
      (candidate?.decision_alternatives ?? []).map(normalizeText),
    );
    const passed = ["lower_cost", "delay_purchase", "no_purchase"].some(
      (value) => alternatives.has(value),
    );
    return gate(
      "先别买替代方案门",
      passed,
      passed
        ? "包含低成本、延迟购买或不购买方案"
        : "必须给出低成本、延迟购买或不购买中的至少一种方案",
    );
  }
  if (direction === "global_furniture_observation") {
    const refs = Array.isArray(candidate?.claim_scope_refs)
      ? candidate.claim_scope_refs
      : [];
    const allowedKeys = ["market", "brand", "standard", "year", "case"];
    const passed =
      refs.length > 0 &&
      refs.every((item) =>
        allowedKeys.some((key) => Boolean(normalizeText(item?.[key]))),
      );
    return gate(
      "海外主张范围门",
      passed,
      passed
        ? "具体主张已绑定市场、品牌、标准、年份或案例"
        : "每条海外主张都必须绑定市场、品牌、标准、年份或案例",
    );
  }
  if (direction === "image_mix_home") {
    const visuals = Array.isArray(candidate?.visuals) ? candidate.visuals : [];
    const passed =
      visuals.length > 0 &&
      visuals.every(
        (item) =>
          ["owned", "authorized"].includes(normalizeText(item?.rights_status)) &&
          item?.product_fidelity_reviewed === true &&
          (item?.synthetic !== true ||
            /空间提案|场景合成/u.test(normalizeText(item?.disclosure))),
      );
    return gate(
      "场景合成专属门",
      passed,
      passed
        ? "视觉授权、产品保真复核和合成披露完整"
        : "每张图都需要授权、产品保真复核；合成图还要标注空间提案或场景合成",
    );
  }
  if (direction === "space_diagnosis") {
    const diagnosis = candidate?.space_diagnosis ?? {};
    const passed =
      Boolean(normalizeText(diagnosis?.dimensions)) &&
      Boolean(normalizeText(diagnosis?.circulation_constraints)) &&
      Boolean(normalizeText(diagnosis?.household_needs));
    return gate(
      "空间问诊输入门",
      passed,
      passed
        ? "尺寸、动线限制和家庭需求完整"
        : "尺寸、动线限制和家庭需求缺一不可",
    );
  }
  return gate("方向专属门", false, "没有匹配的正文方向配置");
}


export function evaluateArticleCandidate(candidate) {
  const candidateId = normalizeText(candidate?.candidate_id);
  const direction = normalizeText(candidate?.direction);
  const profile = profileForDirection(direction);
  const accountId = normalizeText(candidate?.account_id);
  const hierarchy = candidate?.topic_hierarchy ?? {};
  const briefRaw = String(candidate?.sourced_article_brief ?? "");
  const brief = normalizeText(briefRaw);
  const computedBriefSha256 = sha256(briefRaw);
  const source = candidate?.source_contract ?? {};
  const evidencePack = Array.isArray(candidate?.evidence_pack)
    ? candidate.evidence_pack
    : [];
  const factContract = candidate?.fact_contract ?? {};
  const identity = candidate?.identity ?? {};
  const visuals = Array.isArray(candidate?.visuals) ? candidate.visuals : [];
  const platformRisk = candidate?.platform_risk ?? {};
  const minimumEvidenceTypes =
    ARTICLE_STYLE_CONTRACT.topic_hierarchy_contract.minimum_evidence_types;

  const directionPassed = Boolean(profile) && accountId === profile?.account_id;
  const hierarchyPassed = [
    hierarchy?.macro_theme,
    hierarchy?.subtopic_family,
    hierarchy?.article_seed,
    brief,
  ].every((value) => Boolean(normalizeText(value)));
  const briefPassed = brief.length >= 80;
  const evidenceTypes = new Set(
    evidencePack.map((item) => normalizeText(item?.evidence_type)).filter(Boolean),
  );
  const evidencePassed =
    evidenceTypes.size >= minimumEvidenceTypes &&
    evidencePack.every(
      (item) =>
        Boolean(normalizeText(item?.source_locator)) &&
        isSha256(item?.content_sha256) &&
        Boolean(normalizeText(item?.rights_basis)) &&
        item?.body_nonempty === true &&
        Boolean(normalizeText(item?.claim_usage)) &&
        isIsoDate(item?.captured_at),
    );
  const sourcePassed =
    Boolean(normalizeText(source?.source_locator)) &&
    isSha256(source?.brief_sha256) &&
    normalizeText(source?.brief_sha256) === computedBriefSha256 &&
    Boolean(normalizeText(source?.owner_or_rights_holder)) &&
    Boolean(normalizeText(source?.rights_basis)) &&
    Array.isArray(source?.allowed_operations) &&
    source.allowed_operations.includes("generate") &&
    Boolean(normalizeText(source?.language)) &&
    ["public", "internal", "private", "restricted"].includes(
      normalizeText(source?.sensitivity),
    ) &&
    isIsoDate(source?.review_due_at);
  const factsPassed = factContractComplete(factContract);
  const identityPassed =
    identity?.fake_consumer_identity !== true &&
    identity?.firsthand_claims_unverified !== true &&
    (identity?.brand_involvement !== true ||
      Boolean(normalizeText(identity?.affiliation_disclosure)));
  const visualsPassed = visuals.every(
    (item) =>
      ["owned", "authorized"].includes(normalizeText(item?.rights_status)) &&
      (item?.synthetic !== true ||
        /空间提案|场景合成|AI|渲染/u.test(normalizeText(item?.disclosure))),
  );
  const platformPassed =
    platformRisk?.captcha !== true &&
    platformRisk?.safety_warning !== true &&
    platformRisk?.frequency_warning !== true &&
    platformRisk?.account_risk_notice !== true &&
    platformRisk?.takedown_pattern !== true &&
    platformRisk?.rights_holder_objection !== true;
  const directionSpecificGate = evaluateDirectionGate(candidate, direction);

  const gates = [
    gate(
      "方向与账号门",
      directionPassed,
      directionPassed
        ? "方向与已配置账号一致"
        : "正文方向不存在或承接账号不匹配",
    ),
    gate(
      "选题层级门",
      hierarchyPassed,
      hierarchyPassed
        ? "宏观主题、子话题、文章种子和来源简报完整"
        : "缺少宏观主题、子话题、文章种子或来源简报",
    ),
    gate(
      "完整简报门",
      briefPassed,
      briefPassed ? "简报达到最低完整度" : "来源文章简报少于 80 字",
    ),
    gate(
      "多类型来源包门",
      evidencePassed,
      evidencePassed
        ? `来源包包含 ${evidenceTypes.size} 类非空证据`
        : `至少需要 ${minimumEvidenceTypes} 类证据，且每条都要有正文、定位、哈希、授权、用途和采集时间`,
    ),
    gate(
      "来源授权门",
      sourcePassed,
      sourcePassed
        ? "来源描述、授权、操作范围和复核日期完整"
        : "来源描述、brief SHA-256、授权或 generate 权限不完整",
    ),
    gate(
      "事实合同门",
      factsPassed,
      factsPassed ? "事实合同结构完整" : "事实合同必须显式包含五类字段",
    ),
    gate(
      "身份与利益关系门",
      identityPassed,
      identityPassed
        ? "没有虚构消费者身份，品牌介入已披露"
        : "存在虚构身份、未核实亲历或未披露品牌介入",
    ),
    gate(
      "视觉授权与披露门",
      visualsPassed,
      visualsPassed
        ? "视觉授权与 AI、渲染、合成披露完整"
        : "视觉缺少授权或合成性质披露",
    ),
    gate(
      "平台风险门",
      platformPassed,
      platformPassed ? "未发现平台或权利人停止信号" : "存在平台或权利人停止信号",
    ),
    directionSpecificGate,
  ];
  const failedGates = gates.filter((item) => !item.passed);
  const preconditionsReady = failedGates.length === 0;
  const generationEnabled =
    ARTICLE_STYLE_CONTRACT.launch_policy.article_generation_enabled === true &&
    ARTICLE_STYLE_CONTRACT.launch_policy.write_allowed === true &&
    LAUNCH_CONFIG.writing_runtime.article_generation_enabled === true;
  const inputSha256 = articleInputFingerprint(candidate);

  return {
    candidate_id: candidateId,
    direction,
    account_id: accountId,
    article_input_sha256: inputSha256,
    brief_sha256: computedBriefSha256,
    topic_hierarchy: {
      macro_theme: normalizeText(hierarchy?.macro_theme),
      subtopic_family: normalizeText(hierarchy?.subtopic_family),
      article_seed: normalizeText(hierarchy?.article_seed),
      sourced_article_brief_present: Boolean(brief),
    },
    evidence_type_count: evidenceTypes.size,
    style_generation: {
      contract_schema_version: ARTICLE_STYLE_CONTRACT.schema_version,
      contract_path: ARTICLE_STYLE_CONTRACT_PATH,
      direction_profile_sha256: profile?.direction_profile_sha256 ?? "",
      catalog_version: ARTICLE_STYLE_CONTRACT.style_lab.catalog_version,
      catalog_sha256: ARTICLE_STYLE_CONTRACT.style_lab.catalog_sha256,
      taxonomy_ids: profile?.taxonomy_ids ?? [],
      requested_strength: profile?.requested_strength ?? null,
      approved_card_refs: profile?.approved_card_refs ?? [],
      output: profile?.output ?? {},
      required_model_id:
        ARTICLE_STYLE_CONTRACT.provider_contract.required_model_id,
      fallback_model_allowed:
        ARTICLE_STYLE_CONTRACT.provider_contract.fallback_model_allowed,
      generation_enabled: generationEnabled,
      publish_allowed: false,
    },
    gates,
    failed_gates: failedGates.map((item) => item.name),
    preconditions_ready: preconditionsReady,
    eligible_for_style_generation: preconditionsReady && generationEnabled,
    queue_status: !preconditionsReady
      ? "rejected_by_precondition"
      : generationEnabled
        ? "awaiting_style_lab_generation"
        : "ready_but_generation_disabled_during_warmup",
    human_review_required: true,
    publish_allowed: false,
  };
}


export function buildArticlePreflightQueue(
  payload,
  generatedAt = new Date().toISOString(),
) {
  const candidates = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.candidates)
      ? payload.candidates
      : [];
  const records = candidates.map(evaluateArticleCandidate);
  return {
    schema_version: 1,
    generated_at: generatedAt,
    system: "panse_xiaohongshu_article_preflight_queue",
    execution_scope: "local_preflight_only",
    network_access_performed: false,
    text_generated: false,
    external_posting_enabled: false,
    publish_allowed: false,
    summary: {
      input_candidates: candidates.length,
      preconditions_ready: records.filter((item) => item.preconditions_ready).length,
      awaiting_style_lab_generation: records.filter(
        (item) => item.queue_status === "awaiting_style_lab_generation",
      ).length,
      ready_but_generation_disabled_during_warmup: records.filter(
        (item) =>
          item.queue_status ===
          "ready_but_generation_disabled_during_warmup",
      ).length,
      rejected_by_precondition: records.filter(
        (item) => item.queue_status === "rejected_by_precondition",
      ).length,
    },
    records,
  };
}


function parseArgs(argv) {
  const args = { input: "", output: "" };
  for (let index = 0; index < argv.length; index += 1) {
    if (argv[index] === "--input") args.input = argv[index + 1] ?? "";
    if (argv[index] === "--output") args.output = argv[index + 1] ?? "";
  }
  return args;
}


async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.input) {
    throw new Error("Usage: node build_xhs_article_preflight_queue.mjs --input <json> [--output <json>]");
  }
  const result = buildArticlePreflightQueue(readJson(path.resolve(args.input)));
  const output = `${JSON.stringify(result, null, 2)}\n`;
  if (args.output) {
    fs.writeFileSync(path.resolve(args.output), output, "utf8");
    return;
  }
  process.stdout.write(output);
}


if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    process.stderr.write(`${error.stack ?? error.message}\n`);
    process.exitCode = 1;
  });
}
