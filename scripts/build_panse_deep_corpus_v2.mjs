import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.dirname(scriptDir);
const base = path.join(repoRoot, "research", "panse_multi_direction");
const generatedDate = "2026-08-11";

const paths = {
  originalDeep: path.join(base, "dataset.json"),
  transparentDeep: path.join(base, "batch05_transparent_validation_deep.json"),
  antiDeep: path.join(base, "batch05_anti_consumption_deep.json"),
  manualEnrichment: path.join(base, "manual_enrichment_2026-08-11.json"),
  originalReference: path.join(base, "reference_index.json"),
  transparentReference: path.join(base, "batch05_transparent_validation_reference.json"),
  antiReference: path.join(base, "batch05_anti_consumption_reference.json"),
  corpus: path.join(base, `deep_corpus_v2_${generatedDate}.json`),
  flat: path.join(base, `deep_corpus_v2_${generatedDate}.csv`),
  stats: path.join(base, `deep_corpus_v2_stats_${generatedDate}.json`),
  queue: path.join(base, `deep_enrichment_queue_${generatedDate}.json`),
};

function readJson(file, fallback = undefined) {
  if (!fs.existsSync(file)) return fallback;
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function writeJsonAtomic(file, value) {
  const temp = `${file}.tmp`;
  fs.writeFileSync(temp, `${JSON.stringify(value, null, 2)}\n`, "utf8");
  fs.renameSync(temp, file);
}

function writeTextAtomic(file, value) {
  const temp = `${file}.tmp`;
  fs.writeFileSync(temp, value, "utf8");
  fs.renameSync(temp, file);
}

function textOf(note) {
  for (const value of [note?.text, note?.body, note?.desc]) {
    const text = String(value ?? "").trim();
    if (text) return text;
  }
  return "";
}

function noteIdOf(note) {
  return String(note?.note_id ?? note?.noteId ?? note?.id ?? "").trim();
}

function titleOf(note) {
  return String(note?.title ?? note?.display_title ?? note?.displayTitle ?? "").trim();
}

function numberish(value) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  const text = String(value ?? "").trim().toLowerCase().replaceAll(",", "");
  if (!text) return 0;
  const parsed = Number.parseFloat(text);
  if (!Number.isFinite(parsed)) return 0;
  return Math.round(parsed * (text.includes("万") || text.includes("w") ? 10_000 : 1));
}

function metricsOf(note) {
  const metrics = note?.metrics ?? note?.search_metrics ?? {};
  return {
    likes: numberish(metrics.likes ?? metrics.liked_count ?? metrics.likedCount),
    comments: numberish(metrics.comments ?? metrics.comment_count ?? metrics.commentCount),
    collects: numberish(metrics.collects ?? metrics.collected_count ?? metrics.collectedCount),
    shares: numberish(metrics.shares ?? metrics.shared_count ?? metrics.sharedCount),
  };
}

function authorOf(note) {
  const author = note?.author ?? note?.user ?? {};
  return {
    user_id: String(author.user_id ?? author.userId ?? ""),
    nickname: String(author.nickname ?? author.nickName ?? ""),
  };
}

function topicsOf(note) {
  return [...new Set((note?.topics ?? []).map((value) => String(value).trim()).filter(Boolean))];
}

function commentsOf(note) {
  return Array.isArray(note?.first_page_comments) ? note.first_page_comments : [];
}

function richer(a, b) {
  const aText = textOf(a);
  const bText = textOf(b);
  if (aText && !bText) return a;
  if (bText && !aText) return b;
  const score = (note) =>
    textOf(note).length * 10 +
    topicsOf(note).length * 40 +
    commentsOf(note).length * 25 +
    (titleOf(note) ? 20 : 0);
  return score(b) > score(a) ? b : a;
}

function mergeDeepSources(sources) {
  const byId = new Map();
  for (const source of sources) {
    for (const note of source.notes) {
      const noteId = noteIdOf(note);
      if (!noteId) continue;
      const existing = byId.get(noteId);
      if (!existing) {
        byId.set(noteId, { note, provenance: [source.id] });
        continue;
      }
      existing.note = richer(existing.note, note);
      if (!existing.provenance.includes(source.id)) existing.provenance.push(source.id);
    }
  }
  return [...byId.entries()]
    .map(([noteId, entry]) => ({
      ...entry.note,
      note_id: noteId,
      text: textOf(entry.note),
      title: titleOf(entry.note),
      topics: topicsOf(entry.note),
      author: authorOf(entry.note),
      metrics: metricsOf(entry.note),
      first_page_comments: commentsOf(entry.note),
      deep_corpus_provenance: entry.provenance,
    }))
    .sort((a, b) => a.note_id.localeCompare(b.note_id));
}

function readNotes(file) {
  const value = readJson(file, { notes: [] });
  return Array.isArray(value?.notes) ? value.notes : [];
}

function mergeReferenceSources(sources) {
  const byId = new Map();
  for (const source of sources) {
    for (const note of source.notes) {
      const noteId = noteIdOf(note);
      if (!noteId) continue;
      const normalized = {
        note_id: noteId,
        title: titleOf(note),
        author: authorOf(note),
        metrics: metricsOf(note),
        source_url: String(note?.source_url ?? note?.url ?? ""),
        found_by: Array.isArray(note?.found_by) ? note.found_by : [],
        reference_provenance: [source.id],
      };
      if (!byId.has(noteId)) {
        byId.set(noteId, normalized);
        continue;
      }
      const existing = byId.get(noteId);
      if (!existing.title && normalized.title) existing.title = normalized.title;
      if (!existing.source_url && normalized.source_url) existing.source_url = normalized.source_url;
      if (!existing.author.nickname && normalized.author.nickname) existing.author = normalized.author;
      for (const key of Object.keys(existing.metrics)) {
        existing.metrics[key] = Math.max(existing.metrics[key], normalized.metrics[key]);
      }
      existing.found_by.push(...normalized.found_by);
      existing.reference_provenance.push(...normalized.reference_provenance);
      existing.reference_provenance = [...new Set(existing.reference_provenance)];
    }
  }
  return [...byId.values()];
}

const directionRules = [
  {
    id: "panse_official",
    label: "畔色品牌主号",
    keywords: ["ai", "建模", "渲染", "效果图", "打样", "工坊", "制作", "设计", "主理人", "创业", "家具品牌"],
  },
  {
    id: "furniture_decision_editor",
    label: "家具配置表",
    keywords: ["测评", "别买", "避坑", "材质", "维修", "退货", "检测", "报告", "承重", "稳定", "耐用", "售后", "尺寸"],
  },
  {
    id: "global_furniture_editor",
    label: "家具在别处",
    keywords: ["国外", "海外", "米兰", "设计周", "经典家具", "木皮", "涂装", "模块", "结构", "连接", "设计史"],
  },
  {
    id: "space_clinic",
    label: "放得下研究所",
    keywords: ["小户型", "动线", "客厅", "餐厅", "开间", "过道", "柜门", "收纳", "玄关", "沙发", "餐桌", "衣柜"],
  },
  {
    id: "mix_home_editor",
    label: "空间搭配号",
    keywords: ["配色", "木色", "软装", "roomtour", "小家", "我家", "光线", "机位", "氛围", "布置", "改造", "灵感"],
  },
];

function haystack(note) {
  const foundBy = (note.found_by ?? [])
    .map((item) => [item.keyword, item.track_label, item.track_id].filter(Boolean).join(" "))
    .join(" ");
  return `${note.title} ${note.author.nickname} ${foundBy}`.normalize("NFKC").toLowerCase();
}

function engagementScore(note) {
  const m = note.metrics;
  return (
    Math.log1p(m.likes) +
    1.2 * Math.log1p(m.collects) +
    1.1 * Math.log1p(m.comments) +
    0.4 * Math.log1p(m.shares)
  );
}

function directionScore(note, direction) {
  const text = haystack(note);
  const keywordHits = direction.keywords.reduce(
    (sum, keyword) => sum + (text.includes(keyword.toLowerCase()) ? 1 : 0),
    0,
  );
  return keywordHits * 4 + engagementScore(note);
}

function buildBalancedQueue(referenceOnly, perDirection = 52) {
  const chosenIds = new Set();
  const queue = [];
  for (const direction of directionRules) {
    const ranked = referenceOnly
      .map((note) => ({ note, score: directionScore(note, direction) }))
      .sort((a, b) => b.score - a.score || a.note.note_id.localeCompare(b.note.note_id));
    let picked = 0;
    for (const item of ranked) {
      if (picked >= perDirection) break;
      if (chosenIds.has(item.note.note_id)) continue;
      chosenIds.add(item.note.note_id);
      queue.push({
        queue_index: queue.length + 1,
        target_account_id: direction.id,
        target_account_label: direction.label,
        priority_score: Number(item.score.toFixed(4)),
        status: "pending_detail_enrichment",
        ...item.note,
      });
      picked += 1;
    }
  }
  return queue;
}

function csvCell(value) {
  const text = String(value ?? "");
  return `"${text.replaceAll('"', '""')}"`;
}

const deepSources = [
  { id: "campaign_dataset", notes: readNotes(paths.originalDeep) },
  { id: "batch05_transparent_validation", notes: readNotes(paths.transparentDeep) },
  { id: "batch05_anti_consumption", notes: readNotes(paths.antiDeep) },
  { id: "manual_enrichment_2026-08-11", notes: readNotes(paths.manualEnrichment) },
];
const notes = mergeDeepSources(deepSources);
const nonemptyNotes = notes.filter((note) => note.text.length > 0);
const reference = mergeReferenceSources([
  { id: "reference_index", notes: readNotes(paths.originalReference) },
  { id: "batch05_transparent_validation_reference", notes: readNotes(paths.transparentReference) },
  { id: "batch05_anti_consumption_reference", notes: readNotes(paths.antiReference) },
]);
const deepIds = new Set(notes.map((note) => note.note_id));
const referenceOnly = reference.filter((note) => !deepIds.has(note.note_id));
const queue = buildBalancedQueue(referenceOnly);
const target = 1000;
const shortfall = Math.max(0, target - nonemptyNotes.length);

const stats = {
  schema_version: "0.3",
  generated_at: new Date().toISOString(),
  generated_date: generatedDate,
  target_definition: "Unique Xiaohongshu notes with non-empty body text.",
  counts: {
    deep_unique: notes.length,
    deep_nonempty_unique: nonemptyNotes.length,
    deep_empty_text_unique: notes.length - nonemptyNotes.length,
    reference_unique_across_sources: reference.length,
    reference_only_unique: referenceOnly.length,
    target_nonempty: target,
    remaining_to_target: shortfall,
    enrichment_queue_size: queue.length,
    enrichment_failure_buffer: Math.max(0, queue.length - shortfall),
  },
  source_counts: deepSources.map((source) => ({ id: source.id, notes: source.notes.length })),
  queue_distribution: directionRules.map((direction) => ({
    account_id: direction.id,
    label: direction.label,
    notes: queue.filter((item) => item.target_account_id === direction.id).length,
  })),
  publication_boundary: {
    publish_allowed: false,
    note: "The corpus and queue are research artifacts. They do not authorize copying or publishing source text or images.",
  },
};

writeJsonAtomic(paths.corpus, {
  schema_version: "0.3",
  generated_at: stats.generated_at,
  counts: stats.counts,
  notes,
});
writeJsonAtomic(paths.stats, stats);
writeJsonAtomic(paths.queue, {
  schema_version: "0.1",
  generated_at: stats.generated_at,
  target_nonempty: target,
  deep_nonempty_before_enrichment: nonemptyNotes.length,
  required_successes: shortfall,
  queued_candidates: queue.length,
  deduplicated_against_deep_corpus: true,
  notes: queue,
});

const csvRows = [
  ["note_id", "title", "author", "text", "topics", "likes", "comments", "collects", "source_url", "provenance"],
  ...notes.map((note) => [
    note.note_id,
    note.title,
    note.author.nickname,
    note.text,
    note.topics.join("|"),
    note.metrics.likes,
    note.metrics.comments,
    note.metrics.collects,
    note.source_url ?? "",
    note.deep_corpus_provenance.join("|"),
  ]),
];
writeTextAtomic(
  paths.flat,
  `\uFEFF${csvRows.map((row) => row.map(csvCell).join(",")).join("\r\n")}\r\n`,
);

console.log(JSON.stringify(stats, null, 2));
