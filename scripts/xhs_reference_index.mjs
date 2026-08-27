import fs from "node:fs";
import path from "node:path";

const XHS_ORIGIN = "https://www.xiaohongshu.com";

function numberish(value) {
  const text = String(value ?? "")
    .trim()
    .replaceAll(",", "")
    .toLowerCase();
  if (!text || text === "赞") return 0;
  const match = text.match(/^([\d.]+)\s*([万wk]?)$/i);
  if (!match) return 0;
  const number = Number.parseFloat(match[1]);
  if (!Number.isFinite(number)) return 0;
  if (match[2] === "万" || match[2].toLowerCase() === "w") {
    return Math.round(number * 10_000);
  }
  if (match[2].toLowerCase() === "k") return Math.round(number * 1_000);
  return Math.round(number);
}

function unquoteSnapshotText(value) {
  return String(value ?? "")
    .replaceAll('\\"', '"')
    .replaceAll("\\\\", "\\")
    .trim();
}

function absoluteXhsUrl(href) {
  try {
    return new URL(href, XHS_ORIGIN).href;
  } catch {
    return "";
  }
}

function mergeFoundBy(existing = [], incoming = []) {
  const byKey = new Map();
  for (const item of [...existing, ...incoming]) {
    const key = [
      item.track_id ?? "",
      item.query ?? "",
      item.source_url ?? "",
    ].join("\u0000");
    if (!byKey.has(key)) byKey.set(key, item);
  }
  return [...byKey.values()];
}

export function parseSearchSnapshot(
  snapshot,
  {
    query,
    trackId,
    trackLabel,
    sourceUrl,
    collectedAt = new Date().toISOString(),
  },
) {
  const lines = String(snapshot ?? "").split(/\r?\n/);
  const notes = [];
  const seen = new Set();

  for (let index = 0; index < lines.length - 1; index += 1) {
    const titleMatch = lines[index].match(/^\s*-\s+link "(.*)":\s*$/);
    if (!titleMatch) continue;
    const hrefMatch = lines[index + 1].match(
      /^\s*-\s+\/url:\s+(\/search_result\/([0-9a-f]{24})\?[^\s]*)\s*$/,
    );
    if (!hrefMatch) continue;

    const noteId = hrefMatch[2];
    if (seen.has(noteId)) continue;

    let author = "";
    let authorUserId = "";
    let publishedLabel = "";
    let metricText = "";

    const scanEnd = Math.min(lines.length, index + 14);
    for (let scan = index + 2; scan < scanEnd; scan += 1) {
      const profileMatch = lines[scan].match(
        /^\s*-\s+\/url:\s+\/user\/profile\/([0-9a-f]+)[^\s]*\s*$/,
      );
      if (!profileMatch) continue;
      authorUserId = profileMatch[1];

      const nearby = lines.slice(scan + 1, Math.min(scan + 7, lines.length));
      const genericValues = nearby
        .map((line) => line.match(/^\s*-\s+generic:\s+"?(.*?)"?\s*$/)?.[1])
        .filter(Boolean)
        .map(unquoteSnapshotText);
      author = genericValues[0] ?? "";
      publishedLabel = genericValues[1] ?? "";

      for (let metricIndex = scan + 1; metricIndex < scanEnd; metricIndex += 1) {
        const topLevelMetric = lines[metricIndex].match(
          /^-\s+generic:\s+"?(.*?)"?\s*$/,
        );
        if (topLevelMetric) {
          metricText = unquoteSnapshotText(topLevelMetric[1]);
          break;
        }
      }
      break;
    }

    seen.add(noteId);
    notes.push({
      note_id: noteId,
      detail_level: "search_card",
      title: unquoteSnapshotText(titleMatch[1]),
      text: "",
      topics: [],
      author: {
        user_id: authorUserId,
        nickname: author,
      },
      published_label: publishedLabel,
      metrics: {
        likes: numberish(metricText),
        likes_label: metricText,
        comments: null,
        collects: null,
      },
      source_url: absoluteXhsUrl(hrefMatch[1]),
      found_by: [
        {
          track_id: trackId,
          track_label: trackLabel,
          query,
          source_url: sourceUrl,
        },
      ],
      collected_at: collectedAt,
      quality_flags: ["search_card_only", "body_not_collected", "topics_not_collected"],
    });
  }

  return notes;
}

export function mergeReferenceIndex(indexPath, incomingNotes, metadata = {}) {
  const current = fs.existsSync(indexPath)
    ? JSON.parse(fs.readFileSync(indexPath, "utf8"))
    : {
        schema_version: "0.1",
        description:
          "小红书搜索卡片级参考索引；与正文/话题完整的深度样本分层保存。",
        notes_count: 0,
        notes: [],
      };
  const byId = new Map(current.notes.map((note) => [note.note_id, note]));

  for (const incoming of incomingNotes) {
    const existing = byId.get(incoming.note_id);
    if (!existing) {
      byId.set(incoming.note_id, incoming);
      continue;
    }
    existing.found_by = mergeFoundBy(existing.found_by, incoming.found_by);
    if (!existing.title && incoming.title) existing.title = incoming.title;
    if (!existing.author?.nickname && incoming.author?.nickname) {
      existing.author = incoming.author;
    }
    if (
      Number(incoming.metrics?.likes ?? 0) >
      Number(existing.metrics?.likes ?? 0)
    ) {
      existing.metrics.likes = incoming.metrics.likes;
      existing.metrics.likes_label = incoming.metrics.likes_label;
    }
  }

  current.generated_at = new Date().toISOString();
  current.metadata = { ...(current.metadata ?? {}), ...metadata };
  current.notes = [...byId.values()].sort((a, b) =>
    a.note_id.localeCompare(b.note_id),
  );
  current.notes_count = current.notes.length;

  fs.mkdirSync(path.dirname(indexPath), { recursive: true });
  const tempPath = `${indexPath}.tmp`;
  fs.writeFileSync(tempPath, `${JSON.stringify(current, null, 2)}\n`, "utf8");
  fs.renameSync(tempPath, indexPath);
  return current;
}

export function buildMasterCorpus({
  deepDatasetPath,
  referenceIndexPath,
  outputPath,
}) {
  const deep = JSON.parse(fs.readFileSync(deepDatasetPath, "utf8"));
  const reference = fs.existsSync(referenceIndexPath)
    ? JSON.parse(fs.readFileSync(referenceIndexPath, "utf8"))
    : { notes: [] };
  const deepIds = new Set(deep.notes.map((note) => note.note_id));
  const referenceOnly = reference.notes.filter(
    (note) => !deepIds.has(note.note_id),
  );
  const corpus = {
    schema_version: "0.1",
    generated_at: new Date().toISOString(),
    description:
      "畔色小红书分层研究语料：deep notes含正文/话题，reference-only notes为搜索卡片索引。",
    counts: {
      unique_total: deep.notes.length + referenceOnly.length,
      deep_notes: deep.notes.length,
      reference_only_notes: referenceOnly.length,
      overlap_removed: reference.notes.length - referenceOnly.length,
    },
    deep_dataset_path: path.relative(path.dirname(outputPath), deepDatasetPath),
    reference_index_path: path.relative(
      path.dirname(outputPath),
      referenceIndexPath,
    ),
    reference_only_notes: referenceOnly,
  };

  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  const tempPath = `${outputPath}.tmp`;
  fs.writeFileSync(tempPath, `${JSON.stringify(corpus, null, 2)}\n`, "utf8");
  fs.renameSync(tempPath, outputPath);
  return corpus;
}
