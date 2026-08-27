import fs from "node:fs";
import path from "node:path";

const repoRoot = process.cwd();
const base = path.join(repoRoot, "research", "panse_multi_direction");
const paths = {
  transparentIndex: path.join(
    base,
    "batch05_transparent_validation_reference.json",
  ),
  transparentDeep: path.join(
    base,
    "batch05_transparent_validation_deep.json",
  ),
  antiIndex: path.join(base, "batch05_anti_consumption_reference.json"),
  antiDeep: path.join(base, "batch05_anti_consumption_deep.json"),
  stats: path.join(base, "batch05_two_breakthrough_stats.json"),
  report: path.join(base, "batch05_two_breakthrough_analysis.md"),
  flat: path.join(base, "batch05_two_breakthrough_flat.csv"),
};

function readJson(file, fallback = undefined) {
  if (!fs.existsSync(file)) return fallback;
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function writeJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const temp = `${file}.tmp`;
  fs.writeFileSync(temp, `${JSON.stringify(value, null, 2)}\n`, "utf8");
  fs.renameSync(temp, file);
}

function writeText(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const temp = `${file}.tmp`;
  fs.writeFileSync(temp, value, "utf8");
  fs.renameSync(temp, file);
}

function unique(values) {
  return [...new Set(values.filter(Boolean))];
}

function median(values) {
  const sorted = values
    .map(Number)
    .filter(Number.isFinite)
    .sort((a, b) => a - b);
  if (!sorted.length) return 0;
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2
    ? sorted[middle]
    : Math.round((sorted[middle - 1] + sorted[middle]) / 2);
}

function percentile(values, p) {
  const sorted = values
    .map(Number)
    .filter(Number.isFinite)
    .sort((a, b) => a - b);
  if (!sorted.length) return 0;
  const index = Math.min(
    sorted.length - 1,
    Math.max(0, Math.ceil(sorted.length * p) - 1),
  );
  return sorted[index];
}

function matchesAny(text, patterns) {
  return patterns.some((pattern) => text.includes(pattern));
}

function matchedTerms(text, patterns) {
  return unique(patterns.filter((pattern) => text.includes(pattern)));
}

const TITLE_PATTERN_LABELS = {
  plain: "直接陈述",
  question: "提问/求判断",
  negation: "否定与劝退",
  time_validation: "时间验证",
  test_or_teardown: "测试/拆解",
  avoid_mistake: "避坑/后悔",
  number: "数字清单",
};

const HOME_TERMS = [
  "家具",
  "家居",
  "装修",
  "新家",
  "客厅",
  "卧室",
  "餐厅",
  "茶几",
  "电视",
  "沙发",
  "餐桌",
  "桌子",
  "椅子",
  "凳子",
  "柜子",
  "鞋柜",
  "置物柜",
  "收纳",
  "床垫",
  "床架",
  "空间",
  "入住",
  "房子",
  "户型",
];
const MATERIAL_TERMS = [
  "实木",
  "木头",
  "木材",
  "板材",
  "橡木",
  "胡桃木",
  "榫卯",
  "结构",
  "材质",
  "材料",
  "五金",
  "漆面",
];
const VALIDATION_TERMS = [
  "测试",
  "测评",
  "检测",
  "验证",
  "承重",
  "稳定",
  "耐久",
  "暴力",
  "耐磨",
  "耐污",
  "污渍",
  "拆解",
  "内部",
  "真假",
  "真伪",
  "开合",
  "抽屉",
  "安装",
  "质检",
  "抽检",
  "标准",
  "用了",
  "使用一年",
  "使用三年",
  "多年",
  "长期使用",
  "入住一年",
  "入住三年",
];
const ANTI_TERMS = [
  "不买",
  "别买",
  "先别",
  "没必要买",
  "不要买",
  "慢慢买",
  "慢慢添置",
  "一次买齐",
  "冷静期",
  "低物欲",
  "少物",
  "反消费",
  "不消费",
  "去客厅",
  "去电视",
  "不要茶几",
  "智商税",
  "一物多用",
  "不需要",
];
const SAFETY_TERMS = [
  "甲醛",
  "环保",
  "有毒",
  "毒性",
  "致癌",
  "过敏",
  "鼻炎",
  "健康",
  "安全",
  "检测报告",
  "抽检",
  "国标",
  "标准",
  "霉菌",
];

const TRANSPARENT_CLUSTERS = [
  {
    id: "engineering_test",
    label: "工程与日常测试",
    terms: [
      "承重",
      "稳定",
      "耐久",
      "暴力",
      "耐磨",
      "耐污",
      "污渍",
      "开合",
      "抽屉",
      "安装",
      "功能测试",
      "测试",
      "验证",
    ],
  },
  {
    id: "material_truth",
    label: "拆解与材质真相",
    terms: [
      "拆解",
      "内部",
      "真假",
      "真伪",
      "实木",
      "板材",
      "材质",
      "木头",
      "木材",
      "结构",
      "榫卯",
    ],
  },
  {
    id: "long_term_use",
    label: "长期使用验证",
    terms: [
      "使用一年",
      "使用三年",
      "用了",
      "多年",
      "长期使用",
      "入住一年",
      "入住三年",
      "几年后",
      "质保",
    ],
  },
  {
    id: "compliance_health",
    label: "检测、合规与健康",
    terms: [
      "甲醛",
      "环保",
      "检测",
      "抽检",
      "质检",
      "国标",
      "标准",
      "健康",
      "安全",
    ],
  },
];

const ANTI_CLUSTERS = [
  {
    id: "no_buy_challenge",
    label: "不买挑战与低物欲",
    terms: [
      "不买",
      "别买任何",
      "先别买",
      "低物欲",
      "反消费",
      "不消费",
      "少物",
    ],
  },
  {
    id: "remove_defaults",
    label: "删掉默认家具清单",
    terms: [
      "不要茶几",
      "去客厅",
      "去电视",
      "没必要买",
      "智商税",
      "不需要",
    ],
  },
  {
    id: "slow_purchase",
    label: "慢买与入住后添置",
    terms: [
      "慢慢买",
      "慢慢添置",
      "一次买齐",
      "入住后",
      "买前",
      "冷静期",
    ],
  },
  {
    id: "fewer_better_longer",
    label: "少而好、一物多用与长期主义",
    terms: [
      "一物多用",
      "长期主义",
      "使用五年",
      "用了五年",
      "家越住越空",
      "少而精",
      "买得少",
    ],
  },
];

function searchable(note) {
  return `${note.title ?? ""}\n${note.text ?? ""}`.normalize("NFKC");
}

function classifyNote(note, directionId) {
  const text = searchable(note);
  const foundQueries = unique(
    (note.found_by ?? []).map((source) => source.query),
  );
  const queryText = foundQueries.join("\n");
  const homeEvidence = matchesAny(text, [...HOME_TERMS, ...MATERIAL_TERMS]);
  const validationEvidence = matchesAny(text, VALIDATION_TERMS);
  const antiEvidence = matchesAny(text, ANTI_TERMS);
  const relevant =
    directionId === "transparent_validation_lab"
      ? homeEvidence && validationEvidence
      : homeEvidence && antiEvidence;
  const clusters =
    directionId === "transparent_validation_lab"
      ? TRANSPARENT_CLUSTERS
      : ANTI_CLUSTERS;
  const matchedClusters = clusters
    .filter((cluster) => matchesAny(`${text}\n${queryText}`, cluster.terms))
    .map((cluster) => cluster.id);
  const title = String(note.title ?? "");
  const hasBody = Boolean(String(note.text ?? "").trim());
  const safetyTerms = matchedTerms(text, SAFETY_TERMS);
  const titlePatterns = unique([
    ...(title.includes("?") || title.includes("？") ? ["question"] : []),
    ...(matchesAny(title, ["不买", "别买", "不要", "没必要", "不需要"])
      ? ["negation"]
      : []),
    ...(matchesAny(title, ["一年", "三年", "五年", "几年", "长期", "入住后"])
      ? ["time_validation"]
      : []),
    ...(matchesAny(title, ["测试", "测评", "暴力", "拆解", "检测", "承重"])
      ? ["test_or_teardown"]
      : []),
    ...(matchesAny(title, ["避坑", "踩雷", "后悔", "智商税", "红黑榜"])
      ? ["avoid_mistake"]
      : []),
    ...(/\d/.test(title) ? ["number"] : []),
  ]);
  return {
    relevant,
    audit_bucket: !hasBody
      ? "empty_body"
      : relevant
        ? "core_reference"
        : "context_only",
    home_evidence: homeEvidence,
    direction_evidence:
      directionId === "transparent_validation_lab"
        ? validationEvidence
        : antiEvidence,
    clusters: matchedClusters.length ? matchedClusters : ["other"],
    title_patterns: titlePatterns.length ? titlePatterns : ["plain"],
    safety_claim_flag: safetyTerms.length > 0,
    safety_terms: safetyTerms,
    found_queries: foundQueries,
  };
}

function queryStats(index, deepById, classifiedById) {
  const rows = new Map();
  for (const note of index.notes ?? []) {
    for (const source of note.found_by ?? []) {
      const key = `${source.track_id ?? ""}\u0000${source.query ?? ""}`;
      if (!rows.has(key)) {
        rows.set(key, {
          track_id: source.track_id ?? "",
          query: source.query ?? "",
          index_note_ids: new Set(),
          deep_note_ids: new Set(),
          nonempty_deep_note_ids: new Set(),
          relevant_deep_note_ids: new Set(),
        });
      }
      const row = rows.get(key);
      row.index_note_ids.add(note.note_id);
      if (deepById.has(note.note_id)) {
        row.deep_note_ids.add(note.note_id);
        const deepNote = deepById.get(note.note_id);
        const hasBody = Boolean(String(deepNote?.text ?? "").trim());
        if (hasBody) row.nonempty_deep_note_ids.add(note.note_id);
        if (hasBody && classifiedById.get(note.note_id)?.relevant) {
          row.relevant_deep_note_ids.add(note.note_id);
        }
      }
    }
  }
  return [...rows.values()]
    .map((row) => ({
      track_id: row.track_id,
      query: row.query,
      index_unique: row.index_note_ids.size,
      deep_unique: row.deep_note_ids.size,
      nonempty_deep_unique: row.nonempty_deep_note_ids.size,
      relevant_deep_unique: row.relevant_deep_note_ids.size,
      deep_relevance_rate: row.nonempty_deep_note_ids.size
        ? Number(
            (
              row.relevant_deep_note_ids.size /
              row.nonempty_deep_note_ids.size
            ).toFixed(4),
          )
        : null,
    }))
    .sort(
      (a, b) =>
        (b.relevant_deep_unique ?? 0) - (a.relevant_deep_unique ?? 0) ||
        b.index_unique - a.index_unique,
    );
}

function engagementSummary(notes, highLikeCutoff) {
  const likes = notes.map((note) => Number(note.metrics?.likes ?? 0));
  return {
    samples: notes.length,
    median_likes: median(likes),
    p90_likes: percentile(likes, 0.9),
    high_like_count: notes.filter(
      (note) => Number(note.metrics?.likes ?? 0) >= highLikeCutoff,
    ).length,
  };
}

function analyzeDirection(directionId, label, index, deep) {
  const notes = deep.notes ?? [];
  const deepById = new Map(notes.map((note) => [note.note_id, note]));
  const classifications = notes.map((note) => ({
    note_id: note.note_id,
    ...classifyNote(note, directionId),
  }));
  const classifiedById = new Map(
    classifications.map((item) => [item.note_id, item]),
  );
  const nonemptyNotes = notes.filter((note) =>
    Boolean(String(note.text ?? "").trim()),
  );
  const relevantNotes = notes.filter(
    (note) =>
      Boolean(String(note.text ?? "").trim()) &&
      classifiedById.get(note.note_id)?.relevant,
  );
  const clusterDefs =
    directionId === "transparent_validation_lab"
      ? TRANSPARENT_CLUSTERS
      : ANTI_CLUSTERS;
  const clusterIds = [...clusterDefs.map((cluster) => cluster.id), "other"];
  const clusters = clusterIds.map((clusterId) => {
    const clusterNotes = notes.filter((note) =>
      classifiedById.get(note.note_id)?.clusters.includes(clusterId),
    );
    const relevantClusterNotes = clusterNotes.filter(
      (note) =>
        Boolean(String(note.text ?? "").trim()) &&
        classifiedById.get(note.note_id)?.relevant,
    );
    return {
      cluster_id: clusterId,
      cluster_label:
        clusterDefs.find((cluster) => cluster.id === clusterId)?.label ??
        "其他/待归类",
      notes: clusterNotes.length,
      nonempty_notes: clusterNotes.filter((note) =>
        Boolean(String(note.text ?? "").trim()),
      ).length,
      relevant_notes: relevantClusterNotes.length,
      median_likes: median(
        relevantClusterNotes.map((note) => note.metrics?.likes ?? 0),
      ),
      p90_likes: percentile(
        relevantClusterNotes.map((note) => note.metrics?.likes ?? 0),
        0.9,
      ),
      top_notes: [...relevantClusterNotes]
        .sort(
          (a, b) =>
            Number(b.metrics?.likes ?? 0) - Number(a.metrics?.likes ?? 0),
        )
        .slice(0, 10)
        .map((note) => ({
          note_id: note.note_id,
          title: note.title,
          author: note.author?.nickname ?? "",
          likes: note.metrics?.likes ?? 0,
          source_url: note.source_url,
          relevant: true,
        })),
    };
  });
  const titlePatternCounts = new Map();
  for (const classification of classifications) {
    for (const pattern of classification.title_patterns) {
      titlePatternCounts.set(
        pattern,
        (titlePatternCounts.get(pattern) ?? 0) + 1,
      );
    }
  }
  const ids = notes.map((note) => note.note_id);
  const emptyText = notes.filter(
    (note) => !String(note.text ?? "").trim(),
  ).length;
  const highLikeCutoff = Math.max(
    1,
    percentile(
      relevantNotes.map((note) => note.metrics?.likes ?? 0),
      0.9,
    ),
  );
  const relevantPatternIds = unique(
    relevantNotes.flatMap(
      (note) => classifiedById.get(note.note_id)?.title_patterns ?? [],
    ),
  );
  const relevantClusterIds = unique(
    relevantNotes.flatMap(
      (note) => classifiedById.get(note.note_id)?.clusters ?? [],
    ),
  );
  const safetyTermCounts = new Map();
  for (const classification of classifications) {
    if (classification.audit_bucket === "empty_body") continue;
    for (const term of classification.safety_terms ?? []) {
      safetyTermCounts.set(term, (safetyTermCounts.get(term) ?? 0) + 1);
    }
  }
  const engagementMechanisms = {
    population: "core_reference_nonempty",
    samples: relevantNotes.length,
    high_like_cutoff: highLikeCutoff,
    by_title_pattern: relevantPatternIds
      .map((pattern) => ({
        pattern,
        label: TITLE_PATTERN_LABELS[pattern] ?? pattern,
        ...engagementSummary(
          relevantNotes.filter((note) =>
            classifiedById
              .get(note.note_id)
              ?.title_patterns.includes(pattern),
          ),
          highLikeCutoff,
        ),
      }))
      .sort(
        (a, b) =>
          b.median_likes - a.median_likes || b.samples - a.samples,
      ),
    by_cluster: relevantClusterIds
      .map((clusterId) => ({
        cluster_id: clusterId,
        cluster_label:
          clusterDefs.find((cluster) => cluster.id === clusterId)?.label ??
          "其他/待归类",
        ...engagementSummary(
          relevantNotes.filter((note) =>
            classifiedById.get(note.note_id)?.clusters.includes(clusterId),
          ),
          highLikeCutoff,
        ),
      }))
      .sort(
        (a, b) =>
          b.median_likes - a.median_likes || b.samples - a.samples,
      ),
    by_text_length: [
      { id: "short", label: "短正文（<150字）", min: 0, max: 150 },
      { id: "medium", label: "中正文（150–499字）", min: 150, max: 500 },
      {
        id: "long",
        label: "长正文（≥500字）",
        min: 500,
        max: Number.POSITIVE_INFINITY,
      },
    ].map((band) => ({
      id: band.id,
      label: band.label,
      ...engagementSummary(
        relevantNotes.filter((note) => {
          const length = String(note.text ?? "").length;
          return length >= band.min && length < band.max;
        }),
        highLikeCutoff,
      ),
    })),
    by_note_type: unique(
      relevantNotes.map((note) => note.note_type || "unknown"),
    ).map((noteType) => ({
      note_type: noteType,
      ...engagementSummary(
        relevantNotes.filter(
          (note) => (note.note_type || "unknown") === noteType,
        ),
        highLikeCutoff,
      ),
    })),
    top_relevant_notes: [...relevantNotes]
      .sort(
        (a, b) =>
          Number(b.metrics?.likes ?? 0) - Number(a.metrics?.likes ?? 0),
      )
      .slice(0, 15)
      .map((note) => ({
        note_id: note.note_id,
        title: note.title,
        author: note.author?.nickname ?? "",
        likes: Number(note.metrics?.likes ?? 0),
        clusters: classifiedById.get(note.note_id)?.clusters ?? [],
        title_patterns:
          classifiedById.get(note.note_id)?.title_patterns ?? [],
        source_url: note.source_url,
      })),
  };
  const stats = {
    direction_id: directionId,
    direction_label: label,
    status:
      notes.length - emptyText >= 200 ? "minimum_reached" : "collecting",
    counts: {
      index_unique: index.notes_count ?? index.notes?.length ?? 0,
      deep_unique: notes.length,
      deep_duplicate_ids: ids.length - new Set(ids).size,
      nonempty_text: notes.length - emptyText,
      empty_text: emptyText,
      video_notes: notes.filter((note) => note.note_type === "video").length,
      with_topics: notes.filter((note) => (note.topics ?? []).length > 0)
        .length,
      unique_topics: unique(notes.flatMap((note) => note.topics ?? [])).length,
      unique_authors: unique(
        notes.map((note) => note.author?.user_id || note.author?.nickname),
      ).length,
      relevant_deep: relevantNotes.length,
      relevant_nonempty: relevantNotes.length,
      context_only_nonempty: nonemptyNotes.length - relevantNotes.length,
      noise_or_uncertain_deep: notes.length - relevantNotes.length,
      safety_claim_flagged: classifications.filter(
        (classification) => classification.safety_claim_flag,
      ).length,
      safety_claim_flagged_nonempty: classifications.filter(
        (classification) =>
          classification.safety_claim_flag &&
          classification.audit_bucket !== "empty_body",
      ).length,
    },
    rates: {
      text_availability: notes.length
        ? Number(((notes.length - emptyText) / notes.length).toFixed(4))
        : 0,
      relevance: notes.length
        ? Number((relevantNotes.length / notes.length).toFixed(4))
        : 0,
      relevance_among_nonempty: nonemptyNotes.length
        ? Number((relevantNotes.length / nonemptyNotes.length).toFixed(4))
        : 0,
    },
    engagement: {
      median_likes: median(notes.map((note) => note.metrics?.likes ?? 0)),
      p90_likes: percentile(
        notes.map((note) => note.metrics?.likes ?? 0),
        0.9,
      ),
      max_likes: Math.max(
        0,
        ...notes.map((note) => Number(note.metrics?.likes ?? 0)),
      ),
    },
    title_patterns: [...titlePatternCounts.entries()]
      .map(([pattern, count]) => ({ pattern, count }))
      .sort((a, b) => b.count - a.count),
    safety_terms: [...safetyTermCounts.entries()]
      .map(([term, count]) => ({ term, count }))
      .sort((a, b) => b.count - a.count || a.term.localeCompare(b.term)),
    engagement_mechanisms: engagementMechanisms,
    query_stats: queryStats(index, deepById, classifiedById),
    clusters,
    classifications,
  };
  return { stats, classifiedById };
}

function csvCell(value) {
  const text =
    value == null
      ? ""
      : Array.isArray(value)
        ? value.join(" | ")
        : String(value);
  return `"${text.replaceAll('"', '""')}"`;
}

function markdownTable(headers, rows) {
  return [
    `| ${headers.join(" | ")} |`,
    `| ${headers.map(() => "---").join(" | ")} |`,
    ...rows.map((row) => `| ${row.join(" | ")} |`),
  ].join("\n");
}

function safeText(value) {
  return String(value ?? "")
    .replaceAll("|", "\\|")
    .replace(/\s+/g, " ")
    .trim();
}

function reportForDirection(analysis) {
  const { stats } = analysis;
  const c = stats.counts;
  const lines = [
    `## ${stats.direction_label}`,
    "",
    `当前状态：${stats.status === "minimum_reached" ? "已达到 200 篇最低正文线" : "仍在采集中，以下结论为阶段性"}。`,
    "",
    markdownTable(
      [
        "索引",
        "详情",
        "非空正文",
        "核心相关",
        "语境样本",
        "空正文",
        "作者",
        "敏感声明",
      ],
      [
        [
          c.index_unique,
          c.deep_unique,
          c.nonempty_text,
          c.relevant_nonempty,
          c.context_only_nonempty,
          c.empty_text,
          c.unique_authors,
          c.safety_claim_flagged_nonempty,
        ],
      ],
    ),
    "",
    `正文可用率 ${(stats.rates.text_availability * 100).toFixed(1)}%，非空正文中的自动核心相关率 ${(stats.rates.relevance_among_nonempty * 100).toFixed(1)}%。核心相关可直接进入选题研究；语境样本只研究叙事或互动机制。自动分类只作为审计入口，不替代人工看样本。`,
    "",
    "### 子方向",
    "",
    "子方向为多标签，一篇可能同时属于多个子方向，不能把各行样本数相加当作总量。",
    "",
    markdownTable(
      ["子方向", "非空正文", "核心相关", "核心赞中位数", "核心赞 P90"],
      stats.clusters.map((cluster) => [
        safeText(cluster.cluster_label),
        cluster.nonempty_notes,
        cluster.relevant_notes,
        cluster.median_likes,
        cluster.p90_likes,
      ]),
    ),
    "",
    "### 高赞内容机制",
    "",
    `以下只统计“正文非空且核心相关”的 ${stats.engagement_mechanisms.samples} 篇；本方向高赞阈值按该样本赞数 P90 定为 ${stats.engagement_mechanisms.high_like_cutoff}。搜索结果混有综合、最新和最多收藏排序，数据用于发现模式，不用于证明因果。`,
    "",
    markdownTable(
      ["标题结构", "样本", "赞中位数", "赞 P90", "达到高赞阈值"],
      stats.engagement_mechanisms.by_title_pattern.map((row) => [
        safeText(row.label),
        row.samples,
        row.median_likes,
        row.p90_likes,
        row.high_like_count,
      ]),
    ),
    "",
    markdownTable(
      ["正文长度", "样本", "赞中位数", "赞 P90", "达到高赞阈值"],
      stats.engagement_mechanisms.by_text_length.map((row) => [
        safeText(row.label),
        row.samples,
        row.median_likes,
        row.p90_likes,
        row.high_like_count,
      ]),
    ),
    "",
    "### 当前核心相关高赞样本",
    "",
  ];
  const top = stats.clusters
    .flatMap((cluster) =>
      cluster.top_notes.map((note) => ({
        cluster: cluster.cluster_label,
        ...note,
      })),
    )
    .sort((a, b) => b.likes - a.likes)
    .filter(
      (note, index, all) =>
        all.findIndex((other) => other.note_id === note.note_id) === index,
    )
    .slice(0, 15);
  lines.push(
    markdownTable(
      ["子方向", "标题", "作者", "赞"],
      top.map((note) => [
        safeText(note.cluster),
        safeText(note.title),
        safeText(note.author),
        note.likes,
      ]),
    ),
    "",
    "### 敏感声明审计",
    "",
    stats.safety_terms.length
      ? markdownTable(
          ["触发词", "非空正文命中"],
          stats.safety_terms.map((row) => [safeText(row.term), row.count]),
        )
      : "未命中预设敏感声明词。",
    "",
    "### 搜索词质量",
    "",
    markdownTable(
      ["搜索词", "索引", "详情", "非空正文", "核心相关", "正文相关率"],
      stats.query_stats.map((row) => [
        safeText(row.query),
        row.index_unique,
        row.deep_unique,
        row.nonempty_deep_unique,
        row.relevant_deep_unique,
        row.deep_relevance_rate == null
          ? "-"
          : `${(row.deep_relevance_rate * 100).toFixed(1)}%`,
      ]),
    ),
    "",
  );
  return lines.join("\n");
}

function main() {
  const transparentIndex = readJson(paths.transparentIndex, {
    notes_count: 0,
    notes: [],
  });
  const transparentDeep = readJson(paths.transparentDeep, {
    notes: [],
  });
  const antiIndex = readJson(paths.antiIndex, { notes_count: 0, notes: [] });
  const antiDeep = readJson(paths.antiDeep, { notes: [] });

  const transparent = analyzeDirection(
    "transparent_validation_lab",
    "透明验证室",
    transparentIndex,
    transparentDeep,
  );
  const anti = analyzeDirection(
    "anti_consumption",
    "先别急着买",
    antiIndex,
    antiDeep,
  );
  const transparentIds = new Set(
    (transparentDeep.notes ?? []).map((note) => note.note_id),
  );
  const antiIds = new Set(
    (antiDeep.notes ?? []).map((note) => note.note_id),
  );
  const crossOverlap = [...transparentIds].filter((id) => antiIds.has(id));
  const complete =
    transparent.stats.counts.nonempty_text >= 200 &&
    anti.stats.counts.nonempty_text >= 200;
  const output = {
    schema_version: "0.2",
    generated_at: new Date().toISOString(),
    batch_id: "batch_05_two_breakthrough_directions",
    analysis_status: complete ? "minimum_complete" : "preliminary_collecting",
    completion_gate: {
      minimum_nonempty_text_per_direction: 200,
      transparent_reached:
        transparent.stats.counts.nonempty_text >= 200,
      anti_consumption_reached:
        anti.stats.counts.nonempty_text >= 200,
    },
    cross_direction_overlap: {
      count: crossOverlap.length,
      note_ids: crossOverlap,
    },
    directions: [transparent.stats, anti.stats],
    safety_policy: {
      everyday_engineering:
        "承重、稳定、开合、耐污等日常演示只能说明该次样品和该次条件。",
      compliance_health:
        "甲醛、环保、健康、安全、国标或抽检结论必须有合格第三方检测或明确证据，不从画面和个案外推。",
      high_likes:
        "高赞只代表传播表现，不自动证明相关性、真实性、测试方法或适合畔色。",
    },
  };
  writeJson(paths.stats, output);

  const allRows = [
    ...((transparentDeep.notes ?? []).map((note) => ({
      direction_id: "transparent_validation_lab",
      direction_label: "透明验证室",
      note,
      classification: transparent.classifiedById.get(note.note_id),
    }))),
    ...((antiDeep.notes ?? []).map((note) => ({
      direction_id: "anti_consumption",
      direction_label: "先别急着买",
      note,
      classification: anti.classifiedById.get(note.note_id),
    }))),
  ];
  const csvHeaders = [
    "direction_id",
    "direction_label",
    "note_id",
    "title",
    "text",
    "text_length",
    "topics",
    "author",
    "likes",
    "comments",
    "collects",
    "note_type",
    "clusters",
    "relevant",
    "audit_bucket",
    "safety_claim_flag",
    "safety_terms",
    "title_patterns",
    "found_queries",
    "source_url",
  ];
  const csv = [
    csvHeaders.map(csvCell).join(","),
    ...allRows.map(({ direction_id, direction_label, note, classification }) =>
      [
        direction_id,
        direction_label,
        note.note_id,
        note.title,
        note.text,
        note.text_length,
        note.topics ?? [],
        note.author?.nickname ?? "",
        note.metrics?.likes ?? 0,
        note.metrics?.comments ?? 0,
        note.metrics?.collects ?? 0,
        note.note_type,
        classification?.clusters ?? [],
        classification?.relevant ?? false,
        classification?.audit_bucket ?? "",
        classification?.safety_claim_flag ?? false,
        classification?.safety_terms ?? [],
        classification?.title_patterns ?? [],
        classification?.found_queries ?? [],
        note.source_url,
      ]
        .map(csvCell)
        .join(","),
    ),
  ].join("\n");
  writeText(paths.flat, `\uFEFF${csv}\n`);

  const report = [
    "# 畔色小红书两个突破方向：正文语料分析",
    "",
    `生成时间：${output.generated_at}`,
    "",
    complete
      ? "两个方向均已达到至少 200 篇正文级样本，以下为最低线完成后的正式分析。"
      : "当前仍在正文采集中。本文件为可重复生成的阶段性分析；未达到 200 篇的方向不做最终优先级裁决。",
    "",
    "## 先说结论",
    "",
    "- 第二个方向正式使用中性栏目名《先别急着买》；不在账号名、栏目名或固定口号中出现品牌词。",
    "- 透明验证室要分成“日常工程演示”“拆解与材料”“时间验证”“第三方检测”四种证据等级，不能混写。",
    "- 《先别急着买》不等于永远不买，而是删除默认购物清单、延迟错误购买、先用生活验证需求，再购买少而合适的家具。",
    "- 高赞只用于研究传播机制；相关性、正文完整度、证据质量和品牌可执行性必须另行过关。",
    "",
    reportForDirection(transparent),
    reportForDirection(anti),
    "## 跨方向关系",
    "",
    `当前正文 ID 交叉 ${crossOverlap.length} 篇。交叉样本适合作为“先别买—先验证需求—再做长期验证”的桥接内容，但发布时不能在同一篇里先反消费、后立即硬卖产品。`,
    "",
    "## 品牌落地边界",
    "",
    "1. 日常承重、稳定、开合、耐污可以做内部可复现实验，但必须公布样品、条件、次数和限制。",
    "2. 甲醛、环保、健康、安全、国标等结论必须由合格第三方检测支撑；画面、气味、个案和 AI 判断都不能代替检测。",
    "3. 《先别急着买》先给用户一个“不买也成立”的答案；只有在需求被验证后，才讨论什么家具值得买。",
    "4. 不把竞品或用户个案中的负面体验外推为整个品牌或材料结论。",
    "5. 图片与视频后续用于视觉分析时，固定产品来源、场景来源、镜头类型、产品状态和几何约束，最终以人工复核为准。",
    "",
  ].join("\n");
  writeText(paths.report, `${report}\n`);
  console.log(
    JSON.stringify({
      event: "batch05_analysis_built",
      status: output.analysis_status,
      transparent_deep: transparent.stats.counts.deep_unique,
      anti_deep: anti.stats.counts.deep_unique,
      cross_overlap: crossOverlap.length,
      outputs: paths,
    }),
  );
}

main();
