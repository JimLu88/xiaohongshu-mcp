import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

export const DM_INTENTS = [
  "product_spec",
  "price_version_purchase",
  "layout_dimension",
  "styling_mix",
  "global_source",
  "after_sales_order",
  "collaboration",
];

const INTENT_RULES = [
  ["after_sales_order", /售后|退货|换货|破损|投诉|订单|物流|补发/u],
  ["price_version_purchase", /价格|多少钱|链接|哪里买|购买|版本|库存/u],
  ["layout_dimension", /户型|尺寸|墙宽|动线|放得下|开间|进深/u],
  ["styling_mix", /搭配|配色|图片|效果图|合成|软装|风格/u],
  ["global_source", /国外|海外|来源|设计师|原版|展会|经典家具/u],
  ["collaboration", /合作|商务|博主|媒体|报价|档期/u],
  ["product_spec", /材料|材质|结构|检测|报告|参数|承重/u],
];

const ROUTES = {
  product_spec: "furniture_decision_editor",
  price_version_purchase: "panse_official",
  layout_dimension: "space_clinic",
  styling_mix: "mix_home_editor",
  global_source: "global_furniture_editor",
  after_sales_order: "panse_official",
  collaboration: "panse_official",
};

const RESPONSE_OUTLINES = {
  product_spec: "先回答已确认的结构或材料事实；缺少批次时转畔色官方核对。",
  price_version_purchase: "核对产品名、版本和站内商品信息后回答，不承诺未确认的库存或价格。",
  layout_dimension: "先收集最少必要尺寸，再给条件化判断，不凭无比例图片下结论。",
  styling_mix: "确认房间用途、已有家具和风格目标；合成图必须标注空间提案或场景合成。",
  global_source: "给出可追溯来源，并说明原始语境和中国户型适配边界。",
  after_sales_order: "先确认问题与处理优先级；订单信息只在站内私信核对并转人工。",
  collaboration: "确认对方身份、合作范围、时间、授权和交付要求后转人工。",
};

const RESPONSE_DRAFTS = {
  product_spec:
    "可以先核对。请补充具体产品名和版本；结构、材料和报告要按同一版本看，我们不会把单项检测直接外推成整件家具的长期表现。",
  price_version_purchase:
    "可以，先确认一下具体产品名和版本。价格、库存和购买入口以小红书站内当前商品信息为准，核对后给你准确答复。",
  layout_dimension:
    "可以先看。请补充墙面净宽、相邻门洞位置和需要保留的通道宽度；尺寸齐了以后，我们再给条件化判断。",
  styling_mix:
    "可以，先说一下房间用途、已有家具和希望保留的颜色。涉及效果图时会明确标注“空间提案”或“场景合成”。",
  global_source:
    "可以，我会先核对原始来源、设计者和案例语境，再说明哪些做法适合中国户型、哪些条件不能直接照搬。",
  after_sales_order:
    "收到，我们先核对订单批次和具体问题。订单信息不适合公开，请只在小红书站内私信提供必要信息，核对后由畔色官方给出处理节点。",
  collaboration:
    "收到，麻烦补充账号主页、合作内容范围、计划时间和授权需求；我们整理后由畔色官方人工回复。",
};

const PHONE_PATTERN = /(?<!\d)1[3-9]\d{9}(?!\d)/gu;
const ORDER_PATTERN = /(?<!\d)\d{10,24}(?!\d)/gu;
const ADDRESS_PATTERN =
  /(?:省|市|区|县|镇|街道|路|号楼|单元|室).{0,30}/gu;

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function normalizeText(value = "") {
  return String(value)
    .normalize("NFKC")
    .replace(/\s+/gu, " ")
    .trim();
}

function classifyIntent(message, declaredIntent) {
  if (DM_INTENTS.includes(declaredIntent)) return declaredIntent;
  return (
    INTENT_RULES.find(([, pattern]) => pattern.test(message))?.[0] ??
    "product_spec"
  );
}

function redactSensitive(message) {
  return message
    .replace(PHONE_PATTERN, "[手机号已遮蔽]")
    .replace(ORDER_PATTERN, "[订单号已遮蔽]")
    .replace(ADDRESS_PATTERN, "[地址已遮蔽]");
}

function evaluateThread(thread) {
  const threadId = normalizeText(thread?.thread_id);
  const message = normalizeText(thread?.incoming_message);
  const userInitiated = thread?.user_initiated === true;
  const outboundCold = thread?.outbound_cold === true || !userInitiated;
  const competitorProspect =
    thread?.origin?.competitor_commercial_thread === true;
  const intent = classifyIntent(
    message,
    normalizeText(thread?.declared_intent),
  );
  const redacted = redactSensitive(message).slice(0, 240);
  const containsSensitiveData = redacted !== message;
  const urgent =
    intent === "after_sales_order" &&
    /破损|投诉|安全|受伤|退货|补发/u.test(message);
  const accepted =
    Boolean(threadId) &&
    Boolean(message) &&
    userInitiated &&
    !outboundCold &&
    !competitorProspect;
  const humanReviewReasons = [
    "所有私信回复都需人工复核",
    ...(containsSensitiveData ? ["包含已遮蔽的敏感信息"] : []),
    ...(["after_sales_order", "collaboration"].includes(intent)
      ? ["售后或合作必须转人工"]
      : []),
  ];

  return {
    thread_id: threadId,
    idempotency_key: `${threadId}::${normalizeText(thread?.message_id) || redacted}`,
    user_initiated: userInitiated,
    intent,
    route_account_id: ROUTES[intent],
    priority: urgent ? "urgent" : "normal",
    incoming_excerpt_redacted: redacted,
    raw_message_retained: false,
    contains_sensitive_data: containsSensitiveData,
    response_outline: RESPONSE_OUTLINES[intent],
    reply_draft: accepted ? RESPONSE_DRAFTS[intent] : "",
    queue_status: accepted
      ? "awaiting_human_review"
      : "rejected_by_policy",
    rejection_reasons: [
      ...(!threadId || !message ? ["缺少会话或消息"] : []),
      ...(!userInitiated || outboundCold ? ["不是用户主动发起的入站私信"] : []),
      ...(competitorProspect ? ["来自竞品商业帖的潜客截流"] : []),
    ],
    human_review_required: accepted,
    human_review_reasons: accepted ? humanReviewReasons : [],
    send_allowed: false,
  };
}

export function buildDmReviewQueue(
  payload,
  generatedAt = new Date().toISOString(),
) {
  const threads = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.threads)
      ? payload.threads
      : [];
  const dailyReviewLimit = Math.max(
    1,
    Math.min(30, Number(payload?.config?.daily_review_limit) || 15),
  );
  const seen = new Set();
  const duplicates = [];
  const records = [];
  for (const thread of threads) {
    const record = evaluateThread(thread);
    if (seen.has(record.idempotency_key)) {
      duplicates.push({
        thread_id: record.thread_id,
        idempotency_key: record.idempotency_key,
      });
      continue;
    }
    seen.add(record.idempotency_key);
    records.push(record);
  }
  const reviewCandidates = records
    .filter((record) => record.queue_status === "awaiting_human_review")
    .sort((left, right) => {
      if (left.priority === right.priority) return 0;
      return left.priority === "urgent" ? -1 : 1;
    });
  const activeKeys = new Set(
    reviewCandidates
      .slice(0, dailyReviewLimit)
      .map((record) => record.idempotency_key),
  );
  for (const record of records) {
    if (
      record.queue_status === "awaiting_human_review" &&
      !activeKeys.has(record.idempotency_key)
    ) {
      record.queue_status = "deferred_to_next_batch";
      record.human_review_required = false;
      record.human_review_reasons = ["超过当日审核上限，顺延到下一批"];
    }
  }
  return {
    schema_version: 1,
    generated_at: generatedAt,
    system: "panse_xiaohongshu_dm_review_queue",
    execution_scope: "local_analysis_only",
    network_access_performed: false,
    external_sending_enabled: false,
    send_allowed: false,
    summary: {
      input_threads: threads.length,
      unique_threads: records.length,
      duplicates_removed: duplicates.length,
      awaiting_human_review: records.filter(
        (record) => record.queue_status === "awaiting_human_review",
      ).length,
      rejected_by_policy: records.filter(
        (record) => record.queue_status === "rejected_by_policy",
      ).length,
      deferred_to_next_batch: records.filter(
        (record) => record.queue_status === "deferred_to_next_batch",
      ).length,
      urgent: records.filter((record) => record.priority === "urgent").length,
      intents_present: [...new Set(records.map((record) => record.intent))],
      daily_review_limit: dailyReviewLimit,
    },
    duplicates,
    records,
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
      "Usage: node scripts/build_xhs_dm_review_queue.mjs --input <threads.json> [--output <queue.json>] [--compact]",
    );
  }
  const queue = buildDmReviewQueue(readJson(path.resolve(args.input)));
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
