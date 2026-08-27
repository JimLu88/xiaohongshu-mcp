import fs from "node:fs";
import path from "node:path";

const base = path.resolve("research", "panse_multi_direction");
const campaign = JSON.parse(fs.readFileSync(path.join(base, "campaign.json"), "utf8"));
const candidates = JSON.parse(fs.readFileSync(path.join(base, "candidates.json"), "utf8"));
const selected = JSON.parse(fs.readFileSync(path.join(base, "selected.json"), "utf8"));
const dataset = JSON.parse(fs.readFileSync(path.join(base, "dataset.json"), "utf8"));
const strategicProfiles = fs.existsSync(path.join(base, "strategic_profiles.json"))
  ? JSON.parse(
      fs.readFileSync(path.join(base, "strategic_profiles.json"), "utf8"),
    )
  : { profiles: [] };

function esc(value) {
  return String(value ?? "").replace(/\|/g, "\\|").replace(/\r?\n/g, " ");
}

function sum(values) {
  return values.reduce((total, value) => total + value, 0);
}

function median(values) {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2
    ? sorted[middle]
    : Math.round((sorted[middle - 1] + sorted[middle]) / 2);
}

const trackById = new Map(campaign.tracks.map((track) => [track.id, track]));
const trackRows = dataset.track_coverage.map((coverage) => {
  const notes = dataset.notes.filter((note) =>
    note.selected_for.some((source) => source.track_id === coverage.track_id),
  );
  return {
    ...coverage,
    median_likes: median(notes.map((note) => note.metrics.likes)),
    median_comments: median(notes.map((note) => note.metrics.comments)),
    median_collects: median(notes.map((note) => note.metrics.collects)),
    unique_authors: new Set(notes.map((note) => note.author.user_id)).size,
  };
});

const topicCounts = new Map();
for (const note of dataset.notes) {
  for (const topic of note.topics) {
    topicCounts.set(topic, (topicCounts.get(topic) ?? 0) + 1);
  }
}
const topTopics = [...topicCounts.entries()]
  .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
  .slice(0, 40);

const authorMap = new Map();
for (const note of dataset.notes) {
  const id = note.author.user_id || note.author.nickname;
  if (!authorMap.has(id)) {
    authorMap.set(id, {
      user_id: note.author.user_id,
      nickname: note.author.nickname,
      notes: [],
      track_groups: new Set(),
      competitor_tracks: new Set(),
    });
  }
  const author = authorMap.get(id);
  author.notes.push(note);
  for (const selectedFor of note.selected_for) {
    author.track_groups.add(selectedFor.track_group);
    if (selectedFor.track_group === "competitor") {
      author.competitor_tracks.add(selectedFor.track_id);
    }
  }
}

const authors = [...authorMap.values()]
  .map((author) => ({
    ...author,
    track_groups: [...author.track_groups],
    competitor_tracks: [...author.competitor_tracks],
    notes_count: author.notes.length,
    total_interactions: sum(
      author.notes.map(
        (note) =>
          note.metrics.likes + note.metrics.comments + note.metrics.collects,
      ),
    ),
  }))
  .sort(
    (a, b) =>
      b.notes_count - a.notes_count ||
      b.total_interactions - a.total_interactions,
  );

const competitorRows = campaign.tracks
  .filter((track) => track.group === "competitor")
  .map((track) => {
    const notes = dataset.notes.filter((note) =>
      note.selected_for.some((item) => item.track_id === track.id),
    );
    const confirmedNotes = notes.filter((note) =>
      note.track_validation?.some(
        (validation) =>
          validation.track_id === track.id && validation.confirmed,
      ),
    );
    const officialNames = new Set(track.official_account_names ?? []);
    const officialNotes = confirmedNotes.filter((note) =>
      officialNames.has(note.author.nickname),
    );
    const otherNotes = confirmedNotes.filter(
      (note) => !officialNames.has(note.author.nickname),
    );
    return {
      brand: track.brand,
      collected: notes.length,
      confirmed: confirmedNotes.length,
      search_only: notes.length - confirmedNotes.length,
      official_account_notes: officialNotes.length,
      other_author_notes: otherNotes.length,
      other_authors: new Set(otherNotes.map((note) => note.author.user_id)).size,
      explicit_commercial_markers: notes.filter(
        (note) => note.commercial_marker_detected,
      ).length,
    };
  });

const profileByName = new Map(
  strategicProfiles.profiles
    .filter((profile) => profile.status === "completed")
    .map((profile) => [profile.requested_name, profile]),
);

const collaboratorRows = campaign.tracks
  .filter((track) => track.group === "collaborator")
  .map((track) => {
    const notes = dataset.notes.filter(
      (note) => note.author.nickname === track.account,
    );
    const profile = profileByName.get(track.account);
    return {
      account: track.account,
      followers: profile?.followers ?? 0,
      notes: notes.length,
      videos: notes.filter((note) => note.note_type === "video").length,
      average_text_length: notes.length
        ? Math.round(sum(notes.map((note) => note.text.length)) / notes.length)
        : 0,
      median_likes: median(notes.map((note) => note.metrics.likes)),
      median_comments: median(notes.map((note) => note.metrics.comments)),
      median_collects: median(notes.map((note) => note.metrics.collects)),
    };
  });

const errors = fs.existsSync(path.join(base, "errors.ndjson"))
  ? fs
      .readFileSync(path.join(base, "errors.ndjson"), "utf8")
      .split(/\r?\n/)
      .filter(Boolean).length
  : 0;

const missingTitles = dataset.notes.filter((note) => !note.title.trim()).length;
const missingTopics = dataset.notes.filter((note) => note.topics.length === 0).length;
const validTrackNotes = dataset.notes.filter((note) =>
  note.track_validation?.some((validation) => validation.confirmed),
).length;
const rawDetailDir = path.join(base, "raw", "detail");
const rawDetailIds = new Set(
  fs
    .readdirSync(rawDetailDir)
    .filter((filename) => filename.endsWith(".json"))
    .map((filename) => path.basename(filename, ".json")),
);
const pendingSelectedDetails = selected.selected.filter(
  (candidate) => !rawDetailIds.has(candidate.note_id),
).length;
const selectionExclusions = fs.existsSync(
  path.join(base, "selection_exclusions.json"),
)
  ? JSON.parse(
      fs.readFileSync(path.join(base, "selection_exclusions.json"), "utf8"),
    )
  : { note_ids: [] };
const totalCommentsLoaded = sum(
  dataset.notes.map((note) => note.first_page_comments.length),
);
const explicitCommercialMarkers = dataset.notes.filter(
  (note) => note.commercial_marker_detected,
).length;

const lines = [
  "# 畔色小红书多方向采集：阶段进度报告",
  "",
  `生成时间：${new Date().toISOString()}`,
  "",
  "## 当前结果",
  "",
  `- 搜索候选去重后：${candidates.unique_count} 篇。`,
  `- 按轨道配额选择：${selected.selected_unique_count} 篇。`,
  `- 成功取得正文详情：${dataset.notes_count} 篇。`,
  `- 至少有一条轨道经账号或正文确认：${validTrackNotes} 篇；其余为搜索命中但待排除的噪声。`,
  `- 当前详情队列仍待补：${pendingSelectedDetails} 篇。`,
  `- 距约 ${campaign.target_total} 篇目标：原始正文完成 ${((dataset.notes_count / campaign.target_total) * 100).toFixed(1)}%，轨道确认样本完成 ${((validTrackNotes / campaign.target_total) * 100).toFixed(1)}%。`,
  `- 覆盖账号：${authors.length} 个。`,
  `- 话题出现次数：${sum(dataset.notes.map((note) => note.topics.length))} 次；去重话题：${topicCounts.size} 个。`,
  `- 首屏评论记录：${totalCommentsLoaded} 条。`,
  `- 采集期间记录的重试/失败事件：${errors} 次；以 state.json 和 raw 目录为准，可断点续跑。`,
  "",
  `数据质量提示：${missingTitles} 篇没有标题，${missingTopics} 篇没有解析到标准话题标签；${selectionExclusions.note_ids.length} 篇因多轮无法取得详情被排除出当前抽样队列。它们仍保留搜索候选记录，不计入正文样本。`,
  "",
  `这里的“其他作者”只能说明笔记作者不在已识别的品牌主账号名单，不能自动认定为付费素人或品牌协同。本批正文检测到 ${explicitCommercialMarkers} 篇带“商业合作、品牌合作、广告合作、报备、赞助”等明确字样；检测不到也不等于没有合作。`,
  "",
  "## 当前方向判断",
  "",
  "这 15 个方向应该同步研究，但不建议立刻拆成 15 个账号。先把它们组织成六条可长期生产的内容线：",
  "",
  "1. **官方产品线**：上新、评审、颜色投票、功能取舍和命名共创。",
  "2. **主理人/设计过程线**：真实决策、打样迭代、设计来源和失败修正；不强行编造创业戏剧。",
  "3. **真实家庭解题线**：小户型、收纳、宠物、有娃、租房和一件家具解决一个问题。",
  "4. **购买后证据线**：到货、安装、售后、一个月/半年/两年后的长期使用。",
  "5. **设计知识线**：经典家具、人体尺度、材料、配色和空间关系，承担收藏价值。",
  "6. **生活氛围线**：固定室内机位下的花、咖啡、光影和日常，让家具反复出现但不篇篇硬卖。",
  "",
  "当前每个方向最多 10 篇定向样本，互动中位数仍受搜索排序、发布时间和账号体量影响，只用于发现内容结构，不用于给方向做最终胜负排名。",
  "",
  "## 方向覆盖",
  "",
  "| 分组 | 方向 | 配额 | 已取得详情 | 作者数 | 赞中位数 | 评中位数 | 藏中位数 |",
  "|---|---|---:|---:|---:|---:|---:|---:|",
  ...trackRows.map(
    (row) =>
      `| ${esc(row.track_group)} | ${esc(row.track_label)} | ${row.quota} | ${row.completed_count} | ${row.unique_authors} | ${row.median_likes} | ${row.median_comments} | ${row.median_collects} |`,
  ),
  "",
  "## 竞品主账号与其他作者",
  "",
  "| 竞品 | 搜索轨道详情 | 正文/账号确认 | 搜索词误召回待排除 | 已识别主账号笔记 | 其他作者笔记 | 其他作者数 | 明确商业标识 |",
  "|---|---:|---:|---:|---:|---:|---:|---:|",
  ...competitorRows.map(
    (row) =>
      `| ${esc(row.brand)} | ${row.collected} | ${row.confirmed} | ${row.search_only} | ${row.official_account_notes} | ${row.other_author_notes} | ${row.other_authors} | ${row.explicit_commercial_markers} |`,
  ),
  "",
  "竞品初步结构：乙舟主账号擅长新品剧透、评审和组件共创；小写的其他作者更常把产品放入开放式餐厨、长桌和原木居住场景；多匣的其他作者集中呈现墙面系统落地、总价、安装和混搭；凡屋出现一个月到三年的长期使用及问题反馈；二黑木作同时覆盖品牌上新、全屋购买、海外运输和长期体验。以上只描述当前样本结构，不推断付费关系。",
  "",
  "## 战略账号主页快照",
  "",
  "| 账号 | 粉丝快照 | 获赞与收藏 | 主页笔记载入 | 简介摘要 |",
  "|---|---:|---:|---:|---|",
  ...strategicProfiles.profiles
    .filter((profile) => profile.status === "completed")
    .sort((a, b) => b.followers - a.followers)
    .map(
      (profile) =>
        `| ${esc(profile.requested_name)} | ${profile.followers} | ${profile.total_likes_and_collects} | ${profile.profile_feeds_loaded} | ${esc(profile.bio).slice(0, 80)} |`,
    ),
  "",
  "## 两位合作博主",
  "",
  "| 账号 | 粉丝快照 | 本批本人笔记 | 视频 | 正文平均字数 | 赞中位数 | 评中位数 | 藏中位数 |",
  "|---|---:|---:|---:|---:|---:|---:|---:|",
  ...collaboratorRows.map(
    (row) =>
      `| ${esc(row.account)} | ${row.followers} | ${row.notes} | ${row.videos} | ${row.average_text_length} | ${row.median_likes} | ${row.median_comments} | ${row.median_collects} |`,
  ),
  "",
  "- **苏安生home**：10 篇中 8 篇视频，文字更短；题材从装修收纳延伸到花材、咖啡角和季节日常。适合固定家中局部机位，让畔色家具作为长期背景进入生活。",
  "- **蓝山Orz**：正文更长，偏光影、空间关系、小户型方案和长期主义；适合“同一房间多机位 + 功能证据 + 生活叙事”的图文/视频组合。",
  "",
  "## 高频话题",
  "",
  "| 话题 | 次数 |",
  "|---|---:|",
  ...topTopics.map(([topic, count]) => `| ${esc(topic)} | ${count} |`),
  "",
  "## 多次入选的账号",
  "",
  "| 账号 | 入选笔记数 | 轨道类型 | 累计赞评藏 |",
  "|---|---:|---|---:|",
  ...authors
    .filter((author) => author.notes_count >= 2)
    .slice(0, 40)
    .map(
      (author) =>
        `| ${esc(author.nickname)} | ${author.notes_count} | ${esc(author.track_groups.join("、"))} | ${author.total_interactions} |`,
    ),
  "",
  "## 文件",
  "",
  "- `campaign.json`：方向、关键词、配额与只读边界。",
  "- `candidates.json`：搜索候选池，按 note_id 去重。",
  "- `selected.json`：每条轨道平衡抽样后的详情队列。",
  "- `dataset.json`：正文、话题、互动、评论首屏、媒体链接和来源轨道。",
  "- `strategic_profiles.json`：竞品已识别主账号和两位合作博主的主页快照。",
  "- `state.json`：断点续跑状态。",
  "- `selection_exclusions.json`：多轮无法取得详情、暂不再重复的候选。",
  "- `missing_token_refresh.json`：当前缺失队列的搜索令牌刷新证据。",
  "- `raw/`：原始搜索与详情响应。",
  "",
  "## 下一批执行口径",
  "",
  "1. 保留全部成功正文，不重抓。",
  "2. 在冷却窗口后先刷新缺失队列的搜索令牌，再补详情。",
  "3. 小写保持当前可用样本，不用打不开的搜索卡片凑配额。",
  "4. 补充更细的产品词、购买阶段词和普通低互动对照词，把有效正文推进到约 500 篇后再做第二轮方向取舍。",
  "",
];

fs.writeFileSync(path.join(base, "README.md"), `${lines.join("\n")}\n`, "utf8");
console.log(
  JSON.stringify({
    output: path.join(base, "README.md"),
    notes: dataset.notes_count,
    authors: authors.length,
    topics: topicCounts.size,
  }),
);
