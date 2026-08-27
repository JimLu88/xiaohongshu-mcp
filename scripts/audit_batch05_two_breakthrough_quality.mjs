import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

const repoRoot = process.cwd();
const base = path.join(repoRoot, "research", "panse_multi_direction");
const paths = {
  stats: path.join(base, "batch05_two_breakthrough_stats.json"),
  state: path.join(base, "batch05_detail_state.json"),
  replacements: path.join(base, "batch05_replaced_failed_index_archive.json"),
  audit: path.join(base, "batch05_two_breakthrough_quality_audit.json"),
  report: path.join(base, "batch05_two_breakthrough_quality_audit.md"),
};

const directions = [
  {
    id: "transparent_validation_lab",
    label: "透明验证室",
    index: path.join(base, "batch05_transparent_validation_reference.json"),
    deep: path.join(base, "batch05_transparent_validation_deep.json"),
  },
  {
    id: "anti_consumption",
    label: "先别急着买",
    index: path.join(base, "batch05_anti_consumption_reference.json"),
    deep: path.join(base, "batch05_anti_consumption_deep.json"),
  },
];

function readJson(file, fallback = undefined) {
  if (!fs.existsSync(file)) return fallback;
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function writeJson(file, value) {
  const temp = `${file}.tmp`;
  fs.writeFileSync(temp, `${JSON.stringify(value, null, 2)}\n`, "utf8");
  fs.renameSync(temp, file);
}

function writeText(file, value) {
  const temp = `${file}.tmp`;
  fs.writeFileSync(temp, value, "utf8");
  fs.renameSync(temp, file);
}

function normalizeContent(value) {
  return String(value ?? "")
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[\p{P}\p{S}\s]/gu, "");
}

function sha256(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function duplicateGroups(notes, valueOf, minimumLength) {
  const groups = new Map();
  for (const note of notes) {
    const value = valueOf(note);
    if (value.length < minimumLength) continue;
    const key = sha256(value);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push({
      note_id: note.note_id,
      title: note.title ?? "",
    });
  }
  return [...groups.entries()]
    .filter(([, group]) => group.length > 1)
    .map(([fingerprint, notesInGroup]) => ({
      fingerprint,
      notes: notesInGroup,
    }));
}

function shingleRepresentation(note) {
  const text = normalizeContent(`${note.title ?? ""}${note.text ?? ""}`).slice(
    0,
    2500,
  );
  const shingles = new Set();
  for (let index = 0; index <= text.length - 5; index += 1) {
    shingles.add(text.slice(index, index + 5));
  }
  return { length: text.length, shingles };
}

function nearDuplicatePairs(notes) {
  const candidates = notes.filter(
    (note) => normalizeContent(note.text).length >= 40,
  );
  const representations = candidates.map(shingleRepresentation);
  const pairs = [];
  for (let left = 0; left < candidates.length; left += 1) {
    for (let right = left + 1; right < candidates.length; right += 1) {
      const a = representations[left];
      const b = representations[right];
      if (Math.min(a.length, b.length) / Math.max(a.length, b.length) < 0.75) {
        continue;
      }
      const smaller =
        a.shingles.size <= b.shingles.size ? a.shingles : b.shingles;
      const larger = smaller === a.shingles ? b.shingles : a.shingles;
      let intersection = 0;
      for (const shingle of smaller) {
        if (larger.has(shingle)) intersection += 1;
      }
      const union = a.shingles.size + b.shingles.size - intersection;
      const similarity = union ? intersection / union : 0;
      if (similarity < 0.85) continue;
      pairs.push({
        left_note_id: candidates[left].note_id,
        right_note_id: candidates[right].note_id,
        left_title: candidates[left].title ?? "",
        right_title: candidates[right].title ?? "",
        five_gram_jaccard: Number(similarity.toFixed(4)),
      });
    }
  }
  return pairs;
}

function idFromSourceUrl(sourceUrl) {
  try {
    const match = new URL(sourceUrl).pathname.match(/\/explore\/([^/?]+)/);
    return match?.[1] ?? "";
  } catch {
    return "";
  }
}

function countBy(values, keyOf) {
  const result = {};
  for (const value of values) {
    const key = keyOf(value) || "unknown";
    result[key] = (result[key] ?? 0) + 1;
  }
  return result;
}

function markdownTable(headers, rows) {
  return [
    `| ${headers.join(" | ")} |`,
    `| ${headers.map(() => "---").join(" | ")} |`,
    ...rows.map((row) => `| ${row.join(" | ")} |`),
  ].join("\n");
}

function cleanCell(value) {
  return String(value ?? "")
    .replaceAll("|", "\\|")
    .replace(/\s+/g, " ")
    .trim();
}

function main() {
  const stats = readJson(paths.stats);
  const state = readJson(paths.state, { details: {}, stop_history: [] });
  const replacementArchive = readJson(paths.replacements, {
    replacements: [],
  });
  const statsById = new Map(
    (stats?.directions ?? []).map((direction) => [
      direction.direction_id,
      direction,
    ]),
  );

  const directionAudits = [];
  const loaded = new Map();
  for (const direction of directions) {
    const index = readJson(direction.index, { notes: [] });
    const deep = readJson(direction.deep, { notes: [] });
    const indexNotes = index.notes ?? [];
    const deepNotes = deep.notes ?? [];
    const directionStats = statsById.get(direction.id);
    const classifications = new Map(
      (directionStats?.classifications ?? []).map((classification) => [
        classification.note_id,
        classification,
      ]),
    );
    const indexIds = indexNotes.map((note) => note.note_id);
    const deepIds = deepNotes.map((note) => note.note_id);
    const exactTextGroups = duplicateGroups(
      deepNotes,
      (note) => normalizeContent(note.text),
      20,
    );
    const exactTitleTextGroups = duplicateGroups(
      deepNotes,
      (note) =>
        `${normalizeContent(note.title)}${normalizeContent(note.text)}`,
      20,
    );
    const sameTitleGroups = duplicateGroups(
      deepNotes,
      (note) => normalizeContent(note.title),
      4,
    );
    const nearPairs = nearDuplicatePairs(deepNotes);
    const bucketCounts = countBy(deepNotes, (note) =>
      classifications.get(note.note_id)?.audit_bucket ?? "unclassified",
    );
    const stateRows = Object.entries(state.details ?? {})
      .filter(([key]) => key.startsWith(`${direction.id}:`))
      .map(([, value]) => value);
    directionAudits.push({
      direction_id: direction.id,
      direction_label: direction.label,
      gates: {
        minimum_nonempty_text: 200,
        reached:
          Number(directionStats?.counts?.nonempty_text ?? 0) >= 200,
      },
      counts: {
        index_rows: indexNotes.length,
        index_unique_ids: new Set(indexIds).size,
        index_duplicate_ids:
          indexIds.length - new Set(indexIds).size,
        detail_rows: deepNotes.length,
        detail_unique_ids: new Set(deepIds).size,
        detail_duplicate_ids: deepIds.length - new Set(deepIds).size,
        nonempty_text: directionStats?.counts?.nonempty_text ?? 0,
        empty_text: directionStats?.counts?.empty_text ?? 0,
        core_reference: bucketCounts.core_reference ?? 0,
        context_only: bucketCounts.context_only ?? 0,
        safety_review_required:
          directionStats?.counts?.safety_claim_flagged_nonempty ?? 0,
        unique_authors: directionStats?.counts?.unique_authors ?? 0,
      },
      source_integrity: {
        missing_source_url: deepNotes.filter((note) => !note.source_url).length,
        source_url_note_id_mismatch: deepNotes.filter((note) => {
          const sourceId = idFromSourceUrl(note.source_url);
          return sourceId && sourceId !== note.note_id;
        }).length,
      },
      duplicate_audit: {
        exact_text_groups: exactTextGroups,
        exact_title_and_text_groups: exactTitleTextGroups,
        same_normalized_title_groups: sameTitleGroups,
        near_duplicate_pairs_jaccard_gte_0_85: nearPairs,
      },
      collection_state: {
        statuses: countBy(stateRows, (row) => row.status),
        failure_classes: countBy(
          stateRows.filter((row) => row.status === "failed"),
          (row) => row.failure_class,
        ),
      },
    });
    loaded.set(direction.id, { indexNotes, deepNotes });
  }

  const transparentIds = new Set(
    loaded
      .get("transparent_validation_lab")
      .deepNotes.map((note) => note.note_id),
  );
  const antiIds = new Set(
    loaded.get("anti_consumption").deepNotes.map((note) => note.note_id),
  );
  const crossDirectionIds = [...transparentIds].filter((id) =>
    antiIds.has(id),
  );
  const stopRows = [
    ...(state.stop_history ?? []),
    ...(state.stop ? [state.stop] : []),
  ];
  const platformRiskStops = stopRows.filter((row) =>
    ["login", "security", "rate_limit"].includes(row.reason),
  );
  const audit = {
    schema_version: "0.2",
    generated_at: new Date().toISOString(),
    audit_status:
      directionAudits.every((direction) => direction.gates.reached) &&
      directionAudits.every(
        (direction) => direction.counts.detail_duplicate_ids === 0,
      )
        ? "minimum_quality_gate_reached"
        : "incomplete",
    hard_gate: {
      minimum_nonempty_text_per_direction: 200,
      reached: directionAudits.every((direction) => direction.gates.reached),
    },
    directions: directionAudits,
    cross_direction: {
      duplicate_note_ids: crossDirectionIds,
      duplicate_note_id_count: crossDirectionIds.length,
    },
    collection_risk: {
      platform_risk_stop_count: platformRiskStops.length,
      platform_risk_stops: platformRiskStops,
      ordinary_stop_count: stopRows.length - platformRiskStops.length,
      ordinary_stop_reasons: countBy(
        stopRows.filter(
          (row) =>
            !["login", "security", "rate_limit"].includes(row.reason),
        ),
        (row) => row.reason,
      ),
    },
    replacement_audit: {
      archived_replacements:
        replacementArchive.replacements?.length ?? 0,
      archive_file: paths.replacements,
    },
    interpretation: {
      core_reference:
        "正文非空，且自动规则同时命中家居/家具证据和该方向证据，可优先进入选题研究。",
      context_only:
        "正文非空，但自动规则未同时命中两类证据；只研究标题、叙事或互动机制，不直接作为畔色选题事实。",
      safety_review_required:
        "正文涉及甲醛、环保、健康、安全、国标、抽检等敏感声明，发布前必须核实证据等级。",
      dedupe:
        "以 note_id 为主键；同时审计规范化正文指纹、标题加正文指纹和 5 字符切片近重复。",
    },
  };
  writeJson(paths.audit, audit);

  const report = [
    "# 畔色小红书两个方向：质量审计",
    "",
    `生成时间：${audit.generated_at}`,
    "",
    audit.hard_gate.reached
      ? "两个方向均达到至少 200 篇正文非空的硬门槛。"
      : "至少一个方向尚未达到 200 篇正文非空的硬门槛。",
    "",
    markdownTable(
      [
        "方向",
        "索引去重",
        "详情去重",
        "非空正文",
        "核心参考",
        "语境参考",
        "空正文",
        "敏感声明",
      ],
      directionAudits.map((direction) => [
        cleanCell(direction.direction_label),
        direction.counts.index_unique_ids,
        direction.counts.detail_unique_ids,
        direction.counts.nonempty_text,
        direction.counts.core_reference,
        direction.counts.context_only,
        direction.counts.empty_text,
        direction.counts.safety_review_required,
      ]),
    ),
    "",
    "## 去重结果",
    "",
    ...directionAudits.flatMap((direction) => [
      `### ${direction.direction_label}`,
      "",
      `- 重复 note_id：${direction.counts.detail_duplicate_ids}`,
      `- 完全相同正文组：${direction.duplicate_audit.exact_text_groups.length}`,
      `- 完全相同“标题+正文”组：${direction.duplicate_audit.exact_title_and_text_groups.length}`,
      `- 近重复正文对（5 字符切片 Jaccard ≥ 0.85）：${direction.duplicate_audit.near_duplicate_pairs_jaccard_gte_0_85.length}`,
      `- 同标题组：${direction.duplicate_audit.same_normalized_title_groups.length}（同标题不自动删除）`,
      "",
    ]),
    `跨方向相同 note_id：${audit.cross_direction.duplicate_note_id_count}。`,
    "",
    "## 相关性分层",
    "",
    "- 核心参考：正文非空，并同时命中家居/家具证据和方向证据。",
    "- 语境参考：正文存在，但只用于学习叙事、标题、互动或外围语境；不能直接变成畔色事实或选题结论。",
    "- 空正文：保留详情元数据，但不计入 200 篇正文门槛。",
    "",
    "## 安全与采集风险",
    "",
    `真实登录、验证码/安全或限流停机记录：${audit.collection_risk.platform_risk_stop_count}。`,
    `普通技术停机记录：${audit.collection_risk.ordinary_stop_count}；主要原因：${Object.entries(audit.collection_risk.ordinary_stop_reasons)
      .map(([reason, count]) => `${reason}=${count}`)
      .join("，") || "无"}。`,
    "",
    "涉及甲醛、环保、健康、安全、国标、抽检等内容仅作为“需证据复核”样本；日常画面、气味、个人体验或 AI 判断不能替代第三方检测。",
    "",
    "## 可追溯性",
    "",
    `已归档被新鲜搜索结果替换的失效索引：${audit.replacement_audit.archived_replacements} 条。`,
    "逐篇审计字段在 batch05_two_breakthrough_flat.csv，包含 audit_bucket、safety_claim_flag 和 safety_terms。",
    "",
  ].join("\n");
  writeText(paths.report, `${report}\n`);
  console.log(
    JSON.stringify({
      event: "batch05_quality_audit_built",
      status: audit.audit_status,
      outputs: {
        audit: paths.audit,
        report: paths.report,
      },
    }),
  );
}

main();
