import fs from "node:fs";
import path from "node:path";

const apiBase = process.env.PANSE_XHS_API ?? "http://127.0.0.1:18060";
const base = path.resolve("research", "panse_multi_direction");
const rawSearchDir = path.join(base, "raw", "search");
const state = JSON.parse(fs.readFileSync(path.join(base, "state.json"), "utf8"));
const candidates = JSON.parse(
  fs.readFileSync(path.join(base, "candidates.json"), "utf8"),
).candidates;
const refreshAllMissing = process.argv.includes("--all-missing");
const selected = JSON.parse(
  fs.readFileSync(path.join(base, "selected.json"), "utf8"),
).selected;
const rawDetailDir = path.join(base, "raw", "detail");
const existingDetailIds = new Set(
  fs
    .readdirSync(rawDetailDir)
    .filter((filename) => filename.endsWith(".json"))
    .map((filename) => path.basename(filename, ".json")),
);
const targetIds = refreshAllMissing
  ? new Set(
      selected
        .filter((candidate) => !existingDetailIds.has(candidate.note_id))
        .map((candidate) => candidate.note_id),
    )
  : new Set(
      Object.entries(state.details)
        .filter(([, value]) => value.status === "failed")
        .map(([noteId]) => noteId),
    );

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function safeSegment(value) {
  return String(value)
    .normalize("NFKC")
    .replace(/[<>:"/\\|?*\u0000-\u001f]/g, "_")
    .replace(/\s+/g, "_")
    .slice(0, 60);
}

function writeJson(file, value) {
  const temp = `${file}.tmp`;
  fs.writeFileSync(temp, `${JSON.stringify(value, null, 2)}\n`, "utf8");
  fs.renameSync(temp, file);
}

async function requestSearch(query) {
  let lastError;
  for (let attempt = 1; attempt <= 2; attempt += 1) {
    try {
      const response = await fetch(`${apiBase}/api/v1/feeds/search`, {
        method: "POST",
        headers: { "content-type": "application/json; charset=utf-8" },
        body: JSON.stringify({
          keyword: query.keyword,
          filters: { sort_by: query.sort_by },
        }),
        signal: AbortSignal.timeout(90_000),
      });
      const payload = await response.json();
      if (!response.ok || payload?.success === false) {
        throw new Error(`${response.status}: ${JSON.stringify(payload)}`);
      }
      return payload;
    } catch (error) {
      lastError = error;
      if (attempt < 2) await sleep(10000);
    }
  }
  throw lastError;
}

const candidatesById = new Map(
  candidates.map((candidate) => [candidate.note_id, candidate]),
);
const queryGroups = new Map();
for (const noteId of targetIds) {
  const candidate = candidatesById.get(noteId);
  if (!candidate) continue;
  for (const source of candidate.found_by) {
    const key = `${source.track_id}::${source.keyword}::${source.sort_by}`;
    if (!queryGroups.has(key)) {
      queryGroups.set(key, {
        track_id: source.track_id,
        track_group: source.track_group,
        track_label: source.track_label,
        keyword: source.keyword,
        sort_by: source.sort_by,
        target_note_ids: new Set(),
      });
    }
    queryGroups.get(key).target_note_ids.add(noteId);
  }
}

const summary = [];
for (const [index, group] of [...queryGroups.values()].entries()) {
  const collectedAt = new Date().toISOString();
  try {
    const response = await requestSearch(group);
    const returnedIds = new Set(
      (response?.data?.feeds ?? []).map((feed) => feed.id),
    );
    const recovered = [...group.target_note_ids].filter((noteId) =>
      returnedIds.has(noteId),
    );
    const filename = [
      "refresh",
      collectedAt.replace(/[:.]/g, "-"),
      safeSegment(group.track_id),
      safeSegment(group.keyword),
      safeSegment(group.sort_by),
    ].join("__");
    writeJson(path.join(rawSearchDir, `${filename}.json`), {
      collected_at: collectedAt,
      track_id: group.track_id,
      track_group: group.track_group,
      track_label: group.track_label,
      query: {
        keyword: group.keyword,
        sort_by: group.sort_by,
      },
      refresh_for_failed_note_ids: [...group.target_note_ids],
      recovered_note_ids: recovered,
      response,
    });
    summary.push({
      status: "completed",
      track_id: group.track_id,
      keyword: group.keyword,
      sort_by: group.sort_by,
      targets: group.target_note_ids.size,
      recovered: recovered.length,
    });
    console.log(
      JSON.stringify({
        event: "refresh_completed",
        completed: index + 1,
        total: queryGroups.size,
        track_id: group.track_id,
        keyword: group.keyword,
        targets: group.target_note_ids.size,
        recovered: recovered.length,
      }),
    );
  } catch (error) {
    summary.push({
      status: "failed",
      track_id: group.track_id,
      keyword: group.keyword,
      sort_by: group.sort_by,
      targets: group.target_note_ids.size,
      recovered: 0,
      message: String(error?.message ?? error),
    });
    console.log(
      JSON.stringify({
        event: "refresh_failed",
        completed: index + 1,
        total: queryGroups.size,
        track_id: group.track_id,
        keyword: group.keyword,
        message: String(error?.message ?? error),
      }),
    );
  }
  if (index < queryGroups.size - 1) await sleep(10000);
}

writeJson(
  path.join(
    base,
    refreshAllMissing
      ? "missing_token_refresh.json"
      : "failed_token_refresh.json",
  ),
  {
  generated_at: new Date().toISOString(),
  mode: refreshAllMissing ? "all_missing_selected" : "failed_state",
  target_note_count: targetIds.size,
  query_count: queryGroups.size,
  recovered_note_occurrences: summary.reduce(
    (total, item) => total + item.recovered,
    0,
  ),
  summary,
  },
);
console.log(
  JSON.stringify({
    event: "refresh_summary",
    mode: refreshAllMissing ? "all_missing_selected" : "failed_state",
    target_notes: targetIds.size,
    queries: queryGroups.size,
    recovered_occurrences: summary.reduce(
      (total, item) => total + item.recovered,
      0,
    ),
  }),
);
