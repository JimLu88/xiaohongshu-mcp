import fs from "node:fs";
import path from "node:path";

const apiBase = process.env.PANSE_XHS_API ?? "http://127.0.0.1:18060";
const repoRoot = process.cwd();
const base = path.join(repoRoot, "research", "panse_multi_direction");
const rawRoot = path.join(base, "raw", "batch05_token_refresh");
const statePath = path.join(base, "batch05_detail_state.json");
const summaryPath = path.join(base, "batch05_token_refresh_summary.json");
const replacementArchivePath = path.join(
  base,
  "batch05_replaced_failed_index_archive.json",
);
const delayMs = Math.max(
  0,
  Number(process.env.PANSE_BATCH05_REFRESH_DELAY_MS ?? 2500),
);
const refreshTimeoutMs = Math.max(
  5_000,
  Number(process.env.PANSE_BATCH05_REFRESH_TIMEOUT_MS ?? 90_000),
);
const sorts = (
  process.env.PANSE_BATCH05_REFRESH_SORTS ?? "综合,最新,最多收藏"
)
  .split(",")
  .map((value) => value.trim())
  .filter(Boolean);
const directionId =
  process.argv[process.argv.indexOf("--direction") + 1] ??
  "anti_consumption";
const replaceFailed =
  process.env.PANSE_BATCH05_REPLACE_FAILED_INDEX === "1";

const directions = {
  transparent_validation_lab: {
    label: "透明验证室",
    indexPath: path.join(
      base,
      "batch05_transparent_validation_reference.json",
    ),
  },
  anti_consumption: {
    label: "先别急着买",
    indexPath: path.join(base, "batch05_anti_consumption_reference.json"),
  },
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

function numberish(value) {
  const text = String(value ?? "")
    .trim()
    .replaceAll(",", "")
    .toLowerCase();
  if (!text) return 0;
  const match = text.match(/^([\d.]+)\s*(万|w|k)?$/i);
  if (!match) return 0;
  const number = Number.parseFloat(match[1]);
  if (!Number.isFinite(number)) return 0;
  if (match[2] === "万" || match[2]?.toLowerCase() === "w") {
    return Math.round(number * 10_000);
  }
  if (match[2]?.toLowerCase() === "k") return Math.round(number * 1_000);
  return Math.round(number);
}

function sourceUrl(noteId, token) {
  return `https://www.xiaohongshu.com/explore/${encodeURIComponent(noteId)}?xsec_token=${encodeURIComponent(token)}&xsec_source=pc_search`;
}

function classifyFailure(message) {
  const text = String(message ?? "");
  if (/登录|login|cookie/i.test(text)) return "login";
  if (/验证码|安全验证|风控|账号异常|risk|security/i.test(text)) {
    return "security";
  }
  if (/频繁|限流|rate.?limit|too many/i.test(text)) return "rate_limit";
  return "other";
}

async function search(keyword, sortBy) {
  const response = await fetch(`${apiBase}/api/v1/feeds/search`, {
    method: "POST",
    headers: { "content-type": "application/json; charset=utf-8" },
    body: JSON.stringify({
      keyword,
      filters: { sort_by: sortBy },
    }),
    signal: AbortSignal.timeout(refreshTimeoutMs),
  });
  const text = await response.text();
  let payload = JSON.parse(text);
  if (typeof payload === "string") payload = JSON.parse(payload);
  if (!response.ok || payload?.success === false) {
    throw new Error(`${response.status}: ${text.slice(0, 1600)}`);
  }
  return payload;
}

function mergeFoundBy(existing = [], incoming = []) {
  const map = new Map();
  for (const item of [...existing, ...incoming]) {
    const key = [
      item.track_id ?? "",
      item.query ?? item.keyword ?? "",
      item.sort_by ?? "",
      item.source_url ?? "",
    ].join("\u0000");
    if (!map.has(key)) map.set(key, item);
  }
  return [...map.values()];
}

async function main() {
  const direction = directions[directionId];
  if (!direction) throw new Error(`unknown_direction:${directionId}`);
  const index = readJson(direction.indexPath, {
    notes_count: 0,
    notes: [],
  });
  const state = readJson(statePath, {
    schema_version: "0.2",
    details: {},
    stop: null,
    stop_history: [],
  });
  const queries = [
    ...new Set(
      (index.notes ?? []).flatMap((note) =>
        (note.found_by ?? [])
          .filter((source) => source.track_id === directionId)
          .map((source) => source.query ?? source.keyword)
          .filter(Boolean),
      ),
    ),
  ];
  const jobs = queries.flatMap((keyword) =>
    sorts.map((sortBy) => ({ keyword, sortBy })),
  );
  const latestById = new Map();
  const jobResults = [];
  let consecutiveFailures = 0;
  let stop = null;

  fs.mkdirSync(path.join(rawRoot, directionId), { recursive: true });
  for (const [jobIndex, job] of jobs.entries()) {
    const collectedAt = new Date().toISOString();
    try {
      const payload = await search(job.keyword, job.sortBy);
      const feeds = payload?.data?.feeds ?? [];
      const rawPath = path.join(
        rawRoot,
        directionId,
        [
          collectedAt.replace(/[:.]/g, "-"),
          safeSegment(job.keyword),
          safeSegment(job.sortBy),
        ].join("__") + ".json",
      );
      writeJson(rawPath, {
        collected_at: collectedAt,
        direction_id: directionId,
        keyword: job.keyword,
        sort_by: job.sortBy,
        response: payload,
      });
      for (const [position, feed] of feeds.entries()) {
        if (!feed?.id || !feed?.xsecToken) continue;
        latestById.set(feed.id, {
          feed,
          collected_at: collectedAt,
          keyword: job.keyword,
          sort_by: job.sortBy,
          position,
        });
      }
      consecutiveFailures = 0;
      jobResults.push({
        status: "completed",
        keyword: job.keyword,
        sort_by: job.sortBy,
        returned: feeds.length,
      });
      console.log(
        JSON.stringify({
          event: "refresh_search_completed",
          completed: jobIndex + 1,
          total: jobs.length,
          keyword: job.keyword,
          sort_by: job.sortBy,
          returned: feeds.length,
          token_ids: latestById.size,
        }),
      );
    } catch (error) {
      const message = String(error?.message ?? error);
      const failureClass = classifyFailure(message);
      consecutiveFailures += 1;
      jobResults.push({
        status: "failed",
        keyword: job.keyword,
        sort_by: job.sortBy,
        failure_class: failureClass,
        message,
      });
      console.log(
        JSON.stringify({
          event: "refresh_search_failed",
          completed: jobIndex + 1,
          total: jobs.length,
          keyword: job.keyword,
          sort_by: job.sortBy,
          failure_class: failureClass,
          message,
        }),
      );
      if (
        ["login", "security", "rate_limit"].includes(failureClass) ||
        consecutiveFailures >= 3
      ) {
        stop = {
          at: new Date().toISOString(),
          reason:
            failureClass === "other"
              ? "consecutive_failures"
              : failureClass,
          keyword: job.keyword,
          sort_by: job.sortBy,
          message,
        };
        break;
      }
    }
    if (jobIndex < jobs.length - 1) await sleep(delayMs);
  }

  const byId = new Map(
    (index.notes ?? []).map((note) => [note.note_id, note]),
  );
  const replaceableFailedIds = replaceFailed
    ? (index.notes ?? [])
        .filter(
          (note) =>
            state.details[`${directionId}:${note.note_id}`]?.status ===
              "failed" && !latestById.has(note.note_id),
        )
        .map((note) => note.note_id)
    : [];
  const replacements = [];
  let existingRefreshed = 0;
  let appended = 0;
  for (const [noteId, fresh] of latestById) {
    const card = fresh.feed.noteCard ?? {};
    const user = card.user ?? {};
    const interact = card.interactInfo ?? {};
    const foundBy = {
      track_id: directionId,
      track_label: direction.label,
      query: fresh.keyword,
      sort_by: fresh.sort_by,
      position: fresh.position,
      source_url: sourceUrl(noteId, fresh.feed.xsecToken),
      refreshed_at: fresh.collected_at,
    };
    const existing = byId.get(noteId);
    if (existing) {
      existing.source_url = sourceUrl(noteId, fresh.feed.xsecToken);
      existing.found_by = mergeFoundBy(existing.found_by, [foundBy]);
      existing.token_refreshed_at = fresh.collected_at;
      if (!existing.title && card.displayTitle) {
        existing.title = card.displayTitle;
      }
      if (!existing.author?.nickname && (user.nickname || user.nickName)) {
        existing.author = {
          user_id: user.userId ?? "",
          nickname: user.nickname ?? user.nickName ?? "",
        };
      }
      existing.metrics = existing.metrics ?? {};
      existing.metrics.likes = Math.max(
        Number(existing.metrics.likes ?? 0),
        numberish(interact.likedCount),
      );
      existingRefreshed += 1;
    } else {
      let replacedNote = null;
      while (byId.size >= 500 && replaceableFailedIds.length) {
        const replaceId = replaceableFailedIds.shift();
        const candidate = byId.get(replaceId);
        if (!candidate) continue;
        byId.delete(replaceId);
        replacedNote = candidate;
        break;
      }
      if (byId.size >= 500) continue;
      byId.set(noteId, {
        note_id: noteId,
        detail_level: "search_card",
        title: card.displayTitle ?? "",
        text: "",
        topics: [],
        note_type: card.type ?? "",
        author: {
          user_id: user.userId ?? "",
          nickname: user.nickname ?? user.nickName ?? "",
        },
        published_label: "",
        metrics: {
          likes: numberish(interact.likedCount),
          likes_label: interact.likedCount ?? "",
          comments: numberish(interact.commentCount),
          collects: numberish(interact.collectedCount),
        },
        source_url: sourceUrl(noteId, fresh.feed.xsecToken),
        found_by: [foundBy],
        collected_at: fresh.collected_at,
        token_refreshed_at: fresh.collected_at,
        quality_flags: [
          "search_card_only",
          "body_not_collected",
          "topics_not_collected",
          "appended_during_token_refresh",
        ],
      });
      appended += 1;
      if (replacedNote) {
        replacements.push({
          replaced_note: replacedNote,
          replacement_note_id: noteId,
          replaced_at: fresh.collected_at,
          reason: "confirmed_detail_failure_replaced_by_fresh_search_result",
        });
      }
    }
    const stateKey = `${directionId}:${noteId}`;
    if (state.details[stateKey]?.status === "failed") {
      state.details[stateKey] = {
        status: "refreshed_pending",
        refreshed_at: fresh.collected_at,
      };
    }
  }

  index.generated_at = new Date().toISOString();
  index.notes = [...byId.values()].sort((a, b) =>
    a.note_id.localeCompare(b.note_id),
  );
  index.notes_count = index.notes.length;
  index.metadata = {
    ...(index.metadata ?? {}),
    last_token_refresh_at: index.generated_at,
    token_refresh_sorts: sorts,
    token_refresh_query_count: queries.length,
  };
  writeJson(direction.indexPath, index);
  if (state.stop) {
    state.stop_history = [...(state.stop_history ?? []), state.stop];
    state.stop = null;
  }
  writeJson(statePath, state);
  if (replacements.length) {
    const archive = readJson(replacementArchivePath, {
      schema_version: "0.1",
      replacements: [],
    });
    writeJson(replacementArchivePath, {
      schema_version: "0.1",
      generated_at: new Date().toISOString(),
      replacements: [...(archive.replacements ?? []), ...replacements],
    });
  }

  const summary = {
    schema_version: "0.2",
    generated_at: new Date().toISOString(),
    direction_id: directionId,
    queries,
    sorts,
    jobs_total: jobs.length,
    jobs_completed: jobResults.filter((result) => result.status === "completed")
      .length,
    jobs_failed: jobResults.filter((result) => result.status === "failed")
      .length,
    unique_fresh_token_ids: latestById.size,
    existing_refreshed: existingRefreshed,
    appended_new_notes: appended,
    replaced_failed_notes: replacements.length,
    index_unique_after: index.notes_count,
    stop,
    job_results: jobResults,
  };
  const previous = readJson(summaryPath, { runs: [] });
  writeJson(summaryPath, {
    schema_version: "0.2",
    generated_at: summary.generated_at,
    runs: [...(previous.runs ?? []), summary],
  });
  console.log(JSON.stringify({ event: "refresh_completed", ...summary }));
}

main().catch((error) => {
  console.error(
    JSON.stringify({
      event: "fatal",
      message: String(error?.stack ?? error),
    }),
  );
  process.exit(1);
});
