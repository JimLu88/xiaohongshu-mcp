import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.dirname(scriptDir);
const base = path.join(repoRoot, "research", "panse_multi_direction");
const corpusPath = path.join(base, "deep_corpus_v2_2026-08-11.json");
const jsonPath = path.join(base, "article_reference_pack_2026-08-11.json");
const mdPath = path.join(base, "article_reference_pack_2026-08-11.md");

const articleSpecs = [
  { id: "fw01-table-stability-four-legs", title: "四条腿的桌子，为什么还会晃", keywords: ["桌子", "餐桌", "晃", "稳定", "桌腿", "连接", "安装", "螺丝", "售后"] },
  { id: "fw02-coffee-table-wait-30-days", title: "茶几先空30天，再决定买不买", keywords: ["茶几", "先不买", "不要买", "入住", "客厅", "边几", "推车", "动线", "挡路"] },
  { id: "fw03-knots-defect-or-material-character", title: "木头有结疤，算不算质量问题", keywords: ["木结", "结疤", "实木", "木材", "纹理", "瑕疵", "开裂", "售后", "天然"] },
  { id: "fw05-3p2m-living-room-sofa-envelope", title: "3.2米客厅，先算沙发深度", keywords: ["沙发", "客厅", "开间", "进深", "茶几", "电视柜", "尺寸", "动线", "过道"] },
  { id: "sw01-veneer-is-not-a-quality-grade", title: "贴木皮，为什么不等于低配", keywords: ["木皮", "贴皮", "基材", "多层板", "胶合板", "实木", "材料", "纹理", "弯曲"] },
  { id: "sw02-finish-is-a-maintenance-choice", title: "选木蜡油还是清漆，先看怎么用", keywords: ["木蜡油", "清漆", "涂装", "油漆", "保养", "维护", "餐桌", "水渍", "划痕"] },
  { id: "sw03-modular-does-not-equal-repairable", title: "模块化家具，坏了真能单独换吗", keywords: ["模块", "组合", "零件", "维修", "备件", "拆装", "搬家", "接口", "置物架"] },
  { id: "sw04-test-report-first-read-the-scope", title: "看到检测合格，先看报告这三行", keywords: ["检测", "报告", "标准", "合格", "甲醛", "承重", "稳定", "耐久", "测试"] },
];

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function writeAtomic(file, content) {
  const temp = `${file}.tmp`;
  fs.writeFileSync(temp, content, "utf8");
  fs.renameSync(temp, file);
}

function normalize(value) {
  return String(value ?? "").normalize("NFKC").toLowerCase();
}

function shorten(value, limit = 96) {
  const text = String(value ?? "").replace(/\s+/g, " ").trim();
  return text.length <= limit ? text : `${text.slice(0, limit - 1)}…`;
}

function engagement(note) {
  const metrics = note.metrics ?? {};
  return Math.log1p(Number(metrics.likes ?? 0)) +
    1.15 * Math.log1p(Number(metrics.collects ?? 0)) +
    1.1 * Math.log1p(Number(metrics.comments ?? 0));
}

function score(note, spec) {
  const title = normalize(note.title);
  const body = normalize(note.text);
  const topics = normalize((note.topics ?? []).join(" "));
  const foundBy = normalize((note.found_by ?? []).map((item) => `${item.keyword ?? ""} ${item.query ?? ""} ${item.track_label ?? ""}`).join(" "));
  let hits = 0;
  for (const keyword of spec.keywords) {
    const key = normalize(keyword);
    if (title.includes(key)) hits += 8;
    if (topics.includes(key)) hits += 5;
    if (foundBy.includes(key)) hits += 3;
    const bodyMatches = body.split(key).length - 1;
    hits += Math.min(bodyMatches, 4) * 2;
  }
  return hits + engagement(note);
}

function structureSignals(note) {
  const text = String(note.text ?? "");
  const signals = [];
  if (/\d+(?:\.\d+)?\s*(?:米|m|cm|厘米|mm|毫米|天|年|元)/i.test(text)) signals.push("有具体数字");
  if (/(入住|用了|使用|到货|安装|维修|退货|买了)/.test(text)) signals.push("有真实使用动作");
  if (/(先|再|最后|第一|第二|第三|步骤|清单)/.test(text)) signals.push("有步骤或清单");
  if (/(但是|不过|代价|问题|缺点|不适合|别急)/.test(text)) signals.push("有反面条件");
  if (/(为什么|怎么|吗|有没有|多少|哪里)/.test(text)) signals.push("问题驱动");
  return signals.length ? signals : ["以经验叙述为主"];
}

function commentNeeds(note) {
  const comments = Array.isArray(note.first_page_comments) ? note.first_page_comments : [];
  return comments
    .map((item) => String(item.content ?? "").replace(/\s+/g, " ").trim())
    .filter(Boolean)
    .slice(0, 3)
    .map((content) => shorten(content, 52));
}

const corpus = readJson(corpusPath);
const notes = (corpus.notes ?? []).filter((note) => String(note.text ?? "").trim());
const used = new Set();
const articles = articleSpecs.map((spec) => {
  const ranked = notes
    .map((note) => ({ note, score: score(note, spec) }))
    .filter((item) => item.score >= 10)
    .sort((a, b) => b.score - a.score || String(a.note.note_id).localeCompare(String(b.note.note_id)));
  const selected = [];
  for (const item of ranked) {
    if (selected.length >= 8) break;
    if (used.has(item.note.note_id) && ranked.length >= 16) continue;
    used.add(item.note.note_id);
    selected.push({
      note_id: item.note.note_id,
      title: item.note.title,
      author: item.note.author?.nickname ?? "",
      source_url: item.note.source_url ?? "",
      metrics: item.note.metrics ?? {},
      relevance_score: Number(item.score.toFixed(3)),
      short_body_summary: shorten(item.note.text),
      opening_pattern: shorten(String(item.note.text ?? "").split(/\n|。|！|？/).find((line) => line.trim()) ?? "", 72),
      structure_signals: structureSignals(item.note),
      visible_comment_needs: commentNeeds(item.note),
      usage_boundary: "只学习问题、结构与用户需求，不复制原文或图片",
    });
  }
  return { ...spec, selected_count: selected.length, references: selected };
});

const pack = {
  schema_version: "1.0",
  generated_at: new Date().toISOString(),
  corpus_path: path.relative(repoRoot, corpusPath).replaceAll("\\", "/"),
  corpus_nonempty_count: notes.length,
  selection_rule: "每篇按标题、正文、话题、采集关键词相关度与互动量综合排序，优先不跨选题复用笔记。",
  copyright_boundary: "仅保留短摘要、短开头和可见评论需求用于内部研究；不得复制正文或第三方图片发布。",
  publish_allowed: false,
  articles,
};
writeAtomic(jsonPath, `${JSON.stringify(pack, null, 2)}\n`);

const lines = [
  "# 8 篇库存稿结构参考包（2026-08-11）",
  "",
  `- 正文级语料：${notes.length} 篇`,
  "- 每篇抽取：8 条相关样本",
  "- 用法：只学问题、结构、证据摆放和评论区真实需求，不复制原文或第三方图片",
  "- 状态：内部研究，`publish_allowed=false`",
  "",
];
for (const article of articles) {
  lines.push(`## ${article.title}`, "");
  article.references.forEach((ref, index) => {
    lines.push(
      `${index + 1}. **${ref.title || "无标题"}**｜${ref.author || "作者未记录"}`,
      `   - 短摘要：${ref.short_body_summary}`,
      `   - 结构信号：${ref.structure_signals.join("、")}`,
      `   - 评论需求：${ref.visible_comment_needs.length ? ref.visible_comment_needs.join("；") : "当前样本未记录可见评论"}`,
      `   - 来源：${ref.source_url || `note_id:${ref.note_id}`}`,
      "",
    );
  });
}
writeAtomic(mdPath, `${lines.join("\n")}\n`);

console.log(JSON.stringify({ corpus_nonempty_count: notes.length, articles: articles.map((item) => ({ id: item.id, selected: item.selected_count })) }, null, 2));
