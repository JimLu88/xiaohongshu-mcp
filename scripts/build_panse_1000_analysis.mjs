import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.dirname(scriptDir);
const researchDir = path.join(
  repoRoot,
  "research",
  "panse_multi_direction",
);

const paths = {
  campaign: path.join(researchDir, "campaign.json"),
  batch03: path.join(researchDir, "batch03_collection_queue.json"),
  batch04: path.join(researchDir, "batch04_competitor_ugc_queue.json"),
  deep: path.join(researchDir, "dataset.json"),
  reference: path.join(researchDir, "reference_index.json"),
  corpus: path.join(researchDir, "corpus_master.json"),
  output: path.join(researchDir, "corpus_1000_stats.json"),
  csv: path.join(researchDir, "corpus_1000_flat.csv"),
};

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function normalizeName(value) {
  return String(value ?? "")
    .normalize("NFKC")
    .replace(/\s+/g, "")
    .toLowerCase();
}

function noteAuthorKey(note) {
  const userId = note.author?.user_id?.trim();
  if (userId) return `id:${userId}`;
  const nickname = normalizeName(note.author?.nickname);
  return nickname ? `name:${nickname}` : "";
}

function unique(values) {
  return [...new Set(values.filter(Boolean))];
}

function safeMetric(note, key) {
  const value = Number(note.metrics?.[key] ?? 0);
  return Number.isFinite(value) ? value : 0;
}

function engagement(note) {
  return (
    safeMetric(note, "likes") +
    safeMetric(note, "collects") +
    safeMetric(note, "comments")
  );
}

function sortTopNotes(notes, limit = 10) {
  return [...notes]
    .sort(
      (a, b) =>
        engagement(b) - engagement(a) ||
        safeMetric(b, "likes") - safeMetric(a, "likes"),
    )
    .slice(0, limit)
    .map((note) => ({
      note_id: note.note_id,
      title: note.title,
      author: note.author?.nickname ?? "",
      likes: safeMetric(note, "likes"),
      collects:
        note.metrics?.collects == null ? null : safeMetric(note, "collects"),
      comments:
        note.metrics?.comments == null ? null : safeMetric(note, "comments"),
      source_url: note.source_url,
      detail_level: note.detail_level ?? "deep",
    }));
}

function countDuplicates(notes) {
  const counts = new Map();
  for (const note of notes) {
    counts.set(note.note_id, (counts.get(note.note_id) ?? 0) + 1);
  }
  return [...counts.values()].filter((count) => count > 1).length;
}

function writeJsonAtomic(filePath, data) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  const tempPath = `${filePath}.tmp`;
  fs.writeFileSync(tempPath, `${JSON.stringify(data, null, 2)}\n`, "utf8");
  fs.renameSync(tempPath, filePath);
}

function csvCell(value) {
  const text = String(value ?? "").replace(/\r?\n/g, " ");
  return `"${text.replaceAll('"', '""')}"`;
}

function writeCsvAtomic(filePath, rows) {
  const columns = [
    "note_id",
    "detail_level",
    "title",
    "author",
    "author_user_id",
    "published_at_or_label",
    "likes",
    "comments",
    "collects",
    "topics",
    "track_ids",
    "queries",
    "source_url",
    "quality_flags",
  ];
  const lines = [
    columns.map(csvCell).join(","),
    ...rows.map((row) => columns.map((column) => csvCell(row[column])).join(",")),
  ];
  const tempPath = `${filePath}.tmp`;
  fs.writeFileSync(tempPath, `\uFEFF${lines.join("\r\n")}\r\n`, "utf8");
  fs.renameSync(tempPath, filePath);
}

const campaign = readJson(paths.campaign);
const batch03 = readJson(paths.batch03);
const batch04 = readJson(paths.batch04);
const deep = readJson(paths.deep);
const reference = readJson(paths.reference);
const corpus = readJson(paths.corpus);

const deepIds = new Set(deep.notes.map((note) => note.note_id));
const referenceOnly = reference.notes.filter(
  (note) => !deepIds.has(note.note_id),
);
const referenceById = new Map(
  reference.notes.map((note) => [note.note_id, note]),
);
const allNotes = [
  ...deep.notes.map((note) => ({ ...note, detail_level: "deep" })),
  ...referenceOnly,
];
const allById = new Map(allNotes.map((note) => [note.note_id, note]));

const trackMeta = new Map();
for (const track of campaign.tracks) {
  trackMeta.set(track.id, {
    id: track.id,
    label: track.label,
    group: track.group,
    parent: "",
    priority: "",
    brand: track.brand ?? "",
    account: track.account ?? "",
    source_batch: "campaign",
  });
}
for (const track of batch03.tracks) {
  trackMeta.set(track.id, {
    id: track.id,
    label: track.label,
    group: "direction_deepening",
    parent: track.parent,
    priority: track.priority,
    brand: "",
    account: "",
    source_batch: batch03.batch_id,
  });
}
for (const query of batch04.queries) {
  if (!trackMeta.has(query.track)) {
    trackMeta.set(query.track, {
      id: query.track,
      label: query.brand,
      group: query.track.startsWith("competitor_")
        ? "competitor_ugc"
        : "collaborator",
      parent: "",
      priority: "P0",
      brand: query.brand,
      account: query.track.startsWith("collaborator_") ? query.brand : "",
      source_batch: batch04.batch,
    });
  }
}

const trackNoteIds = new Map();
const trackQueries = new Map();
function addTrackNote(trackId, noteId, query = "") {
  if (!trackId || !noteId) return;
  if (!trackNoteIds.has(trackId)) trackNoteIds.set(trackId, new Set());
  trackNoteIds.get(trackId).add(noteId);
  if (query) {
    if (!trackQueries.has(trackId)) trackQueries.set(trackId, new Set());
    trackQueries.get(trackId).add(query);
  }
}

for (const note of deep.notes) {
  for (const selection of note.selected_for ?? []) {
    addTrackNote(selection.track_id, note.note_id);
  }
  for (const found of note.found_by ?? []) {
    addTrackNote(
      found.track_id,
      note.note_id,
      found.keyword ?? found.query ?? "",
    );
  }
}
for (const note of reference.notes) {
  for (const found of note.found_by ?? []) {
    addTrackNote(
      found.track_id,
      note.note_id,
      found.query ?? found.keyword ?? "",
    );
  }
}

const trackCoverage = [...trackMeta.values()]
  .map((meta) => {
    const ids = trackNoteIds.get(meta.id) ?? new Set();
    const notes = [...ids]
      .map((id) => allById.get(id))
      .filter(Boolean);
    const deepCount = notes.filter((note) => note.detail_level === "deep").length;
    const referenceOnlyCount = notes.length - deepCount;
    return {
      ...meta,
      unique_notes: notes.length,
      deep_notes: deepCount,
      reference_only_notes: referenceOnlyCount,
      unique_authors: new Set(notes.map(noteAuthorKey).filter(Boolean)).size,
      queries_seen: [...(trackQueries.get(meta.id) ?? new Set())].sort(),
      top_notes: sortTopNotes(notes, 5),
    };
  })
  .sort(
    (a, b) =>
      b.unique_notes - a.unique_notes || a.id.localeCompare(b.id),
  );

const parentRollupMap = new Map();
for (const coverage of trackCoverage) {
  const parentId = coverage.parent || coverage.id;
  if (!parentRollupMap.has(parentId)) {
    parentRollupMap.set(parentId, {
      parent_id: parentId,
      child_tracks: [],
      note_ids: new Set(),
    });
  }
  const item = parentRollupMap.get(parentId);
  item.child_tracks.push(coverage.id);
  for (const id of trackNoteIds.get(coverage.id) ?? []) item.note_ids.add(id);
}
const parentRollup = [...parentRollupMap.values()]
  .map((item) => {
    const notes = [...item.note_ids].map((id) => allById.get(id)).filter(Boolean);
    return {
      parent_id: item.parent_id,
      child_tracks: item.child_tracks,
      unique_notes: notes.length,
      deep_notes: notes.filter((note) => note.detail_level === "deep").length,
      reference_only_notes: notes.filter(
        (note) => note.detail_level !== "deep",
      ).length,
      unique_authors: new Set(notes.map(noteAuthorKey).filter(Boolean)).size,
    };
  })
  .sort(
    (a, b) =>
      b.unique_notes - a.unique_notes ||
      a.parent_id.localeCompare(b.parent_id),
  );

const topicCounts = new Map();
for (const note of deep.notes) {
  for (const topic of unique(note.topics ?? [])) {
    topicCounts.set(topic, (topicCounts.get(topic) ?? 0) + 1);
  }
}
const topTopics = [...topicCounts]
  .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
  .slice(0, 80)
  .map(([topic, count]) => ({ topic, count }));

const titlePatterns = [
  {
    id: "question_or_decision",
    label: "问题与选择",
    regex: /怎么|如何|为什么|到底|能不能|值不值|哪种|该不该|要不要|吗[？?]?$/,
  },
  {
    id: "failure_or_warning",
    label: "失败、踩坑与反常识",
    regex: /翻车|踩坑|返工|失败|后悔|避坑|误区|劝退|不要|别再|不建议|血泪/,
  },
  {
    id: "process_evidence",
    label: "过程与证据",
    regex: /建模|渲染|打样|草图|过程|工作流|从.+到|改了|实物对比|落地|成品/,
  },
  {
    id: "real_home",
    label: "真实家庭与使用",
    regex: /我家|家里|用户家|入住|实拍|使用|开箱|到货|安装|住了|家属/,
  },
  {
    id: "founder_growth",
    label: "主理人与成长节点",
    regex: /创业|主理人|创立|品牌|第一件|第一笔|第.*年|周年|复盘|成长|辞职/,
  },
  {
    id: "list_or_number",
    label: "数字、清单与系列",
    regex: /\d+|[一二三四五六七八九十]+个|清单|合集|第.+期|no\.\s*\d+/i,
  },
  {
    id: "result_or_transformation",
    label: "结果、前后与变化",
    regex: /终于|完成|变成|改造|显大|好看|值了|前后|焕新|变身|拯救/,
  },
];
const titlePatternStats = titlePatterns
  .map((pattern) => {
    const matches = allNotes.filter((note) => pattern.regex.test(note.title ?? ""));
    return {
      id: pattern.id,
      label: pattern.label,
      unique_notes: matches.length,
      share_of_corpus: Number(
        ((matches.length / allNotes.length) * 100).toFixed(2),
      ),
      top_notes: sortTopNotes(matches, 8),
    };
  })
  .sort((a, b) => b.unique_notes - a.unique_notes);

const competitorTracks = campaign.tracks.filter(
  (track) => track.group === "competitor",
);
const competitorStats = competitorTracks.map((track) => {
  const relatedTrackIds = [
    track.id,
    `${track.id}_ugc`,
  ];
  const ids = new Set();
  for (const trackId of relatedTrackIds) {
    for (const id of trackNoteIds.get(trackId) ?? []) ids.add(id);
  }
  const notes = [...ids].map((id) => allById.get(id)).filter(Boolean);
  const officialNames = new Set(
    (track.official_account_names ?? []).map(normalizeName),
  );
  const official = notes.filter((note) =>
    officialNames.has(normalizeName(note.author?.nickname)),
  );
  const nonOfficial = notes.filter(
    (note) => !officialNames.has(normalizeName(note.author?.nickname)),
  );
  const deepNotes = notes.filter((note) => note.detail_level === "deep");
  const deepValidatedOfficial = deepNotes.filter((note) =>
    (note.track_validation ?? []).some(
      (validation) =>
        validation.track_id === track.id &&
        validation.status === "confirmed_official_account",
    ),
  );
  const deepValidatedMention = deepNotes.filter((note) =>
    (note.track_validation ?? []).some(
      (validation) =>
        validation.track_id === track.id &&
        validation.status === "confirmed_brand_mention",
    ),
  );
  return {
    brand: track.brand,
    official_account_names: track.official_account_names,
    unique_notes: notes.length,
    deep_notes: deepNotes.length,
    reference_only_notes: notes.length - deepNotes.length,
    official_account_notes: official.length,
    nonofficial_candidate_notes: nonOfficial.length,
    nonofficial_candidate_authors: new Set(
      nonOfficial.map(noteAuthorKey).filter(Boolean),
    ).size,
    deep_validated_official_notes: deepValidatedOfficial.length,
    deep_validated_brand_mention_notes: deepValidatedMention.length,
    top_official_notes: sortTopNotes(official, 5),
    top_nonofficial_notes: sortTopNotes(nonOfficial, 8),
  };
});

const collaboratorSpecs = [
  {
    account: "苏安生home",
    track_ids: [
      "collaborator_suansheng",
      "collaborator_suansheng_content",
    ],
  },
  {
    account: "蓝山Orz",
    track_ids: [
      "collaborator_lanshan",
      "collaborator_lanshan_content",
    ],
  },
];
const collaboratorStats = collaboratorSpecs.map((spec) => {
  const ids = new Set();
  for (const trackId of spec.track_ids) {
    for (const id of trackNoteIds.get(trackId) ?? []) ids.add(id);
  }
  const notes = [...ids].map((id) => allById.get(id)).filter(Boolean);
  const ownNotes = notes.filter(
    (note) =>
      normalizeName(note.author?.nickname) === normalizeName(spec.account),
  );
  return {
    account: spec.account,
    unique_search_results: notes.length,
    deep_notes: notes.filter((note) => note.detail_level === "deep").length,
    exact_account_notes: ownNotes.length,
    unique_authors_in_results: new Set(
      notes.map(noteAuthorKey).filter(Boolean),
    ).size,
    top_exact_account_notes: sortTopNotes(ownNotes, 10),
    top_search_results: sortTopNotes(notes, 10),
  };
});

const queryStatsMap = new Map();
for (const note of reference.notes) {
  for (const found of note.found_by ?? []) {
    const key = `${found.track_id}\u0000${found.query ?? ""}`;
    if (!queryStatsMap.has(key)) {
      queryStatsMap.set(key, {
        track_id: found.track_id,
        query: found.query ?? "",
        note_ids: new Set(),
      });
    }
    queryStatsMap.get(key).note_ids.add(note.note_id);
  }
}
const queryStats = [...queryStatsMap.values()]
  .map((item) => {
    const notes = [...item.note_ids]
      .map((id) => allById.get(id))
      .filter(Boolean);
    return {
      track_id: item.track_id,
      query: item.query,
      unique_notes: notes.length,
      unique_authors: new Set(notes.map(noteAuthorKey).filter(Boolean)).size,
      top_notes: sortTopNotes(notes, 5),
    };
  })
  .sort(
    (a, b) =>
      a.track_id.localeCompare(b.track_id) ||
      b.unique_notes - a.unique_notes ||
      a.query.localeCompare(b.query),
  );

const authorCounts = new Map();
for (const note of allNotes) {
  const key = noteAuthorKey(note);
  if (!key) continue;
  if (!authorCounts.has(key)) {
    authorCounts.set(key, {
      author_key: key,
      nickname: note.author?.nickname ?? "",
      note_ids: new Set(),
      deep_note_ids: new Set(),
    });
  }
  const item = authorCounts.get(key);
  item.note_ids.add(note.note_id);
  if (note.detail_level === "deep") item.deep_note_ids.add(note.note_id);
}
const topAuthors = [...authorCounts.values()]
  .sort(
    (a, b) =>
      b.note_ids.size - a.note_ids.size ||
      b.deep_note_ids.size - a.deep_note_ids.size ||
      a.nickname.localeCompare(b.nickname),
  )
  .slice(0, 80)
  .map((item) => ({
    author_key: item.author_key,
    nickname: item.nickname,
    unique_notes: item.note_ids.size,
    deep_notes: item.deep_note_ids.size,
  }));

const output = {
  schema_version: "0.1",
  generated_at: new Date().toISOString(),
  project: campaign.project,
  methodology: {
    deep_definition:
      "正文级样本：包含标题、正文、话题、作者、互动量和来源链接。",
    reference_definition:
      "参考卡片级样本：来自小红书搜索结果卡，包含标题、作者、发布日期标签、点赞标签和链接；不假装拥有正文、话题、收藏或评论。",
    competitor_caution:
      "非官方候选仅表示由品牌词检索召回且作者名不等于已知官方账号；不能自动等同于付费投放、商业合作或真实买家。",
  },
  counts: {
    unique_total: allNotes.length,
    deep_notes: deep.notes.length,
    reference_index_notes: reference.notes.length,
    reference_only_notes: referenceOnly.length,
    deep_reference_overlap: reference.notes.length - referenceOnly.length,
    unique_authors: authorCounts.size,
    unique_topics_deep_only: topicCounts.size,
    deep_note_id_duplicates: countDuplicates(deep.notes),
    reference_note_id_duplicates: countDuplicates(reference.notes),
  },
  quality_audit: {
    deep_missing_title: deep.notes.filter((note) => !note.title?.trim()).length,
    deep_missing_body: deep.notes.filter((note) => !note.text?.trim()).length,
    deep_missing_topics: deep.notes.filter(
      (note) => !(note.topics?.length > 0),
    ).length,
    deep_missing_author: deep.notes.filter(
      (note) => !note.author?.nickname?.trim(),
    ).length,
    deep_missing_source_url: deep.notes.filter(
      (note) => !note.source_url?.trim(),
    ).length,
    reference_missing_title: reference.notes.filter(
      (note) => !note.title?.trim(),
    ).length,
    reference_missing_author: reference.notes.filter(
      (note) => !note.author?.nickname?.trim(),
    ).length,
    reference_missing_source_url: reference.notes.filter(
      (note) => !note.source_url?.trim(),
    ).length,
  },
  target_check: {
    requested_target: campaign.target_total,
    target_reached: allNotes.length >= campaign.target_total,
    surplus: allNotes.length - campaign.target_total,
  },
  track_coverage: trackCoverage,
  parent_rollup: parentRollup,
  competitor_stats: competitorStats,
  collaborator_stats: collaboratorStats,
  title_pattern_stats: titlePatternStats,
  top_topics_deep_only: topTopics,
  top_authors: topAuthors,
  query_stats: queryStats,
  top_notes_overall: sortTopNotes(allNotes, 50),
  source_files: Object.fromEntries(
    Object.entries(paths)
      .filter(([key]) => !["output", "csv"].includes(key))
      .map(([key, value]) => [key, path.relative(researchDir, value)]),
  ),
  corpus_counts_snapshot: corpus.counts,
};

writeJsonAtomic(paths.output, output);
const flatRows = allNotes.map((note) => {
  const referenceMatch = referenceById.get(note.note_id);
  const foundBy = [
    ...(note.found_by ?? []),
    ...(referenceMatch?.found_by ?? []),
  ];
  const selectedTrackIds = (note.selected_for ?? []).map(
    (selection) => selection.track_id,
  );
  return {
    note_id: note.note_id,
    detail_level: note.detail_level,
    title: note.title,
    author: note.author?.nickname ?? "",
    author_user_id: note.author?.user_id ?? "",
    published_at_or_label: note.published_at ?? note.published_label ?? "",
    likes: note.metrics?.likes ?? "",
    comments: note.metrics?.comments ?? "",
    collects: note.metrics?.collects ?? "",
    topics: unique(note.topics ?? []).join(" | "),
    track_ids: unique([
      ...selectedTrackIds,
      ...foundBy.map((item) => item.track_id),
    ]).join(" | "),
    queries: unique(
      foundBy.map((item) => item.query ?? item.keyword ?? ""),
    ).join(" | "),
    source_url: note.source_url,
    quality_flags: unique(note.quality_flags ?? []).join(" | "),
  };
});
writeCsvAtomic(paths.csv, flatRows);
console.log(
  JSON.stringify(
    {
      output: paths.output,
      csv: paths.csv,
      counts: output.counts,
      quality_audit: output.quality_audit,
      target_check: output.target_check,
    },
    null,
    2,
  ),
);
