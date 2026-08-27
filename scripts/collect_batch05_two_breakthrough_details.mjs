import fs from "node:fs";
import path from "node:path";

const apiBase = process.env.PANSE_XHS_API ?? "http://127.0.0.1:18060";
const repoRoot = process.cwd();
const researchDir = path.join(
  repoRoot,
  "research",
  "panse_multi_direction",
);
const rawRoot = path.join(researchDir, "raw", "batch05_details");
const legacyRawRoot = path.join(researchDir, "raw", "detail");
const statePath = path.join(researchDir, "batch05_detail_state.json");
const combinedPath = path.join(
  researchDir,
  "batch05_two_breakthrough_deep_dataset.json",
);

const directions = [
  {
    id: "transparent_validation_lab",
    label: "透明验证室",
    indexPath: path.join(
      researchDir,
      "batch05_transparent_validation_reference.json",
    ),
    outputPath: path.join(
      researchDir,
      "batch05_transparent_validation_deep.json",
    ),
  },
  {
    id: "anti_consumption",
    label: "先别急着买",
    indexPath: path.join(
      researchDir,
      "batch05_anti_consumption_reference.json",
    ),
    outputPath: path.join(
      researchDir,
      "batch05_anti_consumption_deep.json",
    ),
  },
];

const args = process.argv.slice(2);
const argValue = (name, fallback = "") => {
  const index = args.indexOf(name);
  return index >= 0 && index + 1 < args.length ? args[index + 1] : fallback;
};
const normalizeOnly = args.includes("--normalize-only");
const requestedDirection = argValue("--direction");
const limit = Math.max(1, Number(argValue("--limit", "10")));
const delayMs = Math.max(
  0,
  Number(process.env.PANSE_BATCH05_DETAIL_DELAY_MS ?? 1800),
);
const detailTimeoutMs = Math.max(
  5_000,
  Number(process.env.PANSE_BATCH05_DETAIL_TIMEOUT_MS ?? 90_000),
);
const maxAttempts = Math.max(
  1,
  Number(process.env.PANSE_BATCH05_MAX_ATTEMPTS ?? 2),
);
const maxConsecutiveFailures = Math.max(
  1,
  Number(process.env.PANSE_BATCH05_MAX_CONSECUTIVE_FAILURES ?? 3),
);
const detailConcurrency = Math.max(
  1,
  Number(process.env.PANSE_BATCH05_DETAIL_CONCURRENCY ?? 1),
);

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

function tokenFromUrl(sourceUrl) {
  try {
    return new URL(sourceUrl).searchParams.get("xsec_token") ?? "";
  } catch {
    return "";
  }
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

function extractTopics(desc) {
  const topics = [];
  const add = (value) => {
    const clean = String(value ?? "")
      .replace(/\s+/g, " ")
      .trim();
    if (clean && !topics.includes(clean)) topics.push(clean);
  };
  for (const match of String(desc ?? "").matchAll(
    /#([^#\n[\]]+?)\[话题\]#/g,
  )) {
    add(match[1]);
  }
  for (const match of String(desc ?? "").matchAll(
    /(?:^|\s)#([\p{L}\p{N}_·-]{2,30})(?=\s|$)/gu,
  )) {
    add(match[1]);
  }
  return topics;
}

function videoUrl(note) {
  const streams = Object.values(note?.video?.media?.stream ?? {}).flatMap(
    (group) => (Array.isArray(group) ? group : []),
  );
  return (
    streams.find((stream) => stream?.masterUrl)?.masterUrl ??
    streams.find((stream) => stream?.backupUrls?.[0])?.backupUrls?.[0] ??
    ""
  );
}

function notePayload(record) {
  return (
    record?.response?.data?.data?.note ??
    record?.data?.data?.note ??
    null
  );
}

function detailFile(directionId, noteId) {
  return path.join(rawRoot, directionId, `${noteId}.json`);
}

function legacyDetailFile(noteId) {
  return path.join(legacyRawRoot, `${noteId}.json`);
}

function sourceDetailFile(directionId, noteId) {
  const current = detailFile(directionId, noteId);
  if (fs.existsSync(current)) return { file: current, source: "batch05" };
  const legacy = legacyDetailFile(noteId);
  if (fs.existsSync(legacy)) return { file: legacy, source: "legacy_reuse" };
  return null;
}

function classifyFailure(message) {
  const text = String(message ?? "");
  if (/登录|login|cookie/i.test(text)) return "login";
  if (/验证码|安全验证|风控|账号异常|risk|security/i.test(text)) {
    return "security";
  }
  if (/频繁|限流|rate.?limit|too many/i.test(text)) return "rate_limit";
  if (/xsec|token|无权限|not found|笔记不存在/i.test(text)) return "token_or_note";
  return "other";
}

async function requestDetail(candidate) {
  const xsecToken = tokenFromUrl(candidate.source_url);
  if (!xsecToken) {
    throw new Error("missing_xsec_token");
  }
  let lastError;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      const response = await fetch(`${apiBase}/api/v1/feeds/detail`, {
        method: "POST",
        headers: { "content-type": "application/json; charset=utf-8" },
        body: JSON.stringify({
          feed_id: candidate.note_id,
          xsec_token: xsecToken,
          load_all_comments: false,
        }),
        signal: AbortSignal.timeout(detailTimeoutMs),
      });
      const text = await response.text();
      let payload = JSON.parse(text);
      if (typeof payload === "string") payload = JSON.parse(payload);
      if (!response.ok || payload?.success === false || !notePayload(payload)) {
        throw new Error(`${response.status}: ${text.slice(0, 1200)}`);
      }
      return payload;
    } catch (error) {
      lastError = error;
      if (attempt < maxAttempts) await sleep(3000 * attempt);
    }
  }
  throw lastError;
}

function normalizeDirection(direction, index) {
  const notes = [];
  for (const candidate of index.notes ?? []) {
    const source = sourceDetailFile(direction.id, candidate.note_id);
    if (!source) continue;
    const record = readJson(source.file);
    const note = notePayload(record);
    if (!note?.noteId) continue;
    const desc = String(note.desc ?? "");
    const comments = record?.response?.data?.data?.comments?.list ?? [];
    const images = (note.imageList ?? []).map((image) => ({
      width: image.width ?? 0,
      height: image.height ?? 0,
      url: image.urlDefault ?? image.urlPre ?? "",
      live_photo: Boolean(image.livePhoto),
    }));
    const topics = extractTopics(desc);
    notes.push({
      note_id: note.noteId,
      detail_level: "deep",
      title: note.title ?? candidate.title ?? "",
      text: desc,
      text_length: desc.trim().length,
      topics,
      note_type: note.type ?? "",
      published_at: note.time ? new Date(note.time).toISOString() : null,
      published_label: candidate.published_label ?? "",
      ip_location: note.ipLocation ?? "",
      author: {
        user_id: note.user?.userId ?? candidate.author?.user_id ?? "",
        nickname: note.user?.nickname ?? candidate.author?.nickname ?? "",
      },
      metrics: {
        likes: numberish(note.interactInfo?.likedCount),
        comments: numberish(note.interactInfo?.commentCount),
        collects: numberish(note.interactInfo?.collectedCount),
        shares: numberish(note.interactInfo?.sharedCount),
      },
      media: {
        image_count: images.length,
        images,
        video_url: videoUrl(note),
        video_duration_ms:
          numberish(note.video?.capa?.duration) ||
          numberish(note.video?.video?.duration),
      },
      first_page_comments: comments.map((comment) => ({
        comment_id: comment.id ?? "",
        content: comment.content ?? "",
        likes: numberish(comment.likeCount),
        author: comment.userInfo?.nickname ?? "",
        author_user_id: comment.userInfo?.userId ?? "",
      })),
      found_by: candidate.found_by ?? [],
      source_url: candidate.source_url,
      detail_source: source.source,
      collected_at:
        record.collected_at ?? record.generated_at ?? new Date().toISOString(),
      quality_flags: [
        ...(String(note.title ?? candidate.title ?? "").trim()
          ? []
          : ["missing_title"]),
        ...(desc.trim() ? [] : ["missing_text"]),
        ...(topics.length ? [] : ["no_standard_topics"]),
        ...(note.type === "video" && !desc.trim()
          ? ["video_caption_not_available"]
          : []),
      ],
    });
  }
  notes.sort((a, b) => a.note_id.localeCompare(b.note_id));
  const dataset = {
    schema_version: "0.2",
    generated_at: new Date().toISOString(),
    batch_id: "batch_05_two_breakthrough_directions",
    direction_id: direction.id,
    direction_label: direction.label,
    counts: {
      index_unique: index.notes_count ?? index.notes?.length ?? 0,
      deep_unique: notes.length,
      with_nonempty_text: notes.filter((note) => note.text_length > 0).length,
      with_topics: notes.filter((note) => note.topics.length > 0).length,
      video_notes: notes.filter((note) => note.note_type === "video").length,
      reused_legacy_details: notes.filter(
        (note) => note.detail_source === "legacy_reuse",
      ).length,
    },
    notes,
  };
  writeJson(direction.outputPath, dataset);
  return dataset;
}

function normalizeAll() {
  const datasets = [];
  for (const direction of directions) {
    const index = readJson(direction.indexPath, { notes_count: 0, notes: [] });
    datasets.push(normalizeDirection(direction, index));
  }
  const combined = {
    schema_version: "0.2",
    generated_at: new Date().toISOString(),
    batch_id: "batch_05_two_breakthrough_directions",
    directions: datasets.map((dataset) => ({
      direction_id: dataset.direction_id,
      direction_label: dataset.direction_label,
      counts: dataset.counts,
      output_file: path.basename(
        directions.find(
          (direction) => direction.id === dataset.direction_id,
        ).outputPath,
      ),
    })),
    counts: {
      index_unique_sum: datasets.reduce(
        (sum, dataset) => sum + dataset.counts.index_unique,
        0,
      ),
      deep_unique_sum: datasets.reduce(
        (sum, dataset) => sum + dataset.counts.deep_unique,
        0,
      ),
      with_nonempty_text_sum: datasets.reduce(
        (sum, dataset) => sum + dataset.counts.with_nonempty_text,
        0,
      ),
    },
  };
  writeJson(combinedPath, combined);
  return combined;
}

async function main() {
  fs.mkdirSync(rawRoot, { recursive: true });
  const state = readJson(statePath, {
    schema_version: "0.2",
    created_at: new Date().toISOString(),
    details: {},
    stop: null,
    stop_history: [],
  });
  if (normalizeOnly) {
    const combined = normalizeAll();
    console.log(JSON.stringify({ event: "normalized", ...combined.counts }));
    return;
  }
  if (state.stop) {
    state.stop_history = [...(state.stop_history ?? []), state.stop];
    state.stop = null;
    writeJson(statePath, state);
  }

  const selectedDirections = requestedDirection
    ? directions.filter((direction) => direction.id === requestedDirection)
    : directions;
  if (!selectedDirections.length) {
    throw new Error(`unknown_direction:${requestedDirection}`);
  }

  const pending = [];
  for (const direction of selectedDirections) {
    const index = readJson(direction.indexPath, { notes: [] });
    const prioritizedCandidates = [...(index.notes ?? [])].sort((a, b) => {
      const aRefresh = Date.parse(a.token_refreshed_at ?? "") || 0;
      const bRefresh = Date.parse(b.token_refreshed_at ?? "") || 0;
      return bRefresh - aRefresh || a.note_id.localeCompare(b.note_id);
    });
    for (const candidate of prioritizedCandidates) {
      if (pending.length >= limit) break;
      if (sourceDetailFile(direction.id, candidate.note_id)) continue;
      const prior = state.details[`${direction.id}:${candidate.note_id}`];
      if (prior?.status === "failed") continue;
      pending.push({ direction, candidate });
    }
    if (pending.length >= limit) break;
  }

  let consecutiveFailures = 0;
  let attempted = 0;
  for (let offset = 0; offset < pending.length; offset += detailConcurrency) {
    const batch = pending.slice(offset, offset + detailConcurrency);
    const results = await Promise.all(
      batch.map(async ({ direction, candidate }) => {
        try {
          const payload = await requestDetail(candidate);
          return { status: "completed", direction, candidate, payload };
        } catch (error) {
          return {
            status: "failed",
            direction,
            candidate,
            error,
          };
        }
      }),
    );

    for (const result of results) {
      attempted += 1;
      const { direction, candidate } = result;
      if (result.status === "completed") {
        const payload = result.payload;
        const output = detailFile(direction.id, candidate.note_id);
        writeJson(output, {
          collected_at: new Date().toISOString(),
          batch_id: "batch_05_two_breakthrough_directions",
          direction_id: direction.id,
          found_by: candidate.found_by ?? [],
          source_url: candidate.source_url,
          response: payload,
        });
        consecutiveFailures = 0;
        state.details[`${direction.id}:${candidate.note_id}`] = {
          status: "completed",
          completed_at: new Date().toISOString(),
        };
        writeJson(statePath, state);
        console.log(
          JSON.stringify({
            event: "detail_completed",
            direction_id: direction.id,
            note_id: candidate.note_id,
            title: notePayload(payload)?.title ?? candidate.title ?? "",
          }),
        );
      } else {
        const message = String(result.error?.message ?? result.error);
        const failureClass = classifyFailure(message);
        consecutiveFailures += 1;
        state.details[`${direction.id}:${candidate.note_id}`] = {
          status: "failed",
          failure_class: failureClass,
          message,
          failed_at: new Date().toISOString(),
        };
        writeJson(statePath, state);
        console.log(
          JSON.stringify({
            event: "detail_failed",
            direction_id: direction.id,
            note_id: candidate.note_id,
            failure_class: failureClass,
            message,
          }),
        );
        if (
          ["login", "security", "rate_limit"].includes(failureClass) ||
          consecutiveFailures >= maxConsecutiveFailures
        ) {
          state.stop = {
            at: new Date().toISOString(),
            reason:
              failureClass === "other"
                ? "consecutive_failures"
                : failureClass,
            consecutive_failures: consecutiveFailures,
            note_id: candidate.note_id,
            message,
          };
          writeJson(statePath, state);
          normalizeAll();
          console.log(JSON.stringify({ event: "stopped", ...state.stop }));
          return;
        }
      }
    }
    if (offset + detailConcurrency < pending.length) await sleep(delayMs);
  }
  const combined = normalizeAll();
  console.log(
    JSON.stringify({
      event: "chunk_completed",
      requested: limit,
      attempted,
      concurrency: detailConcurrency,
      ...combined.counts,
    }),
  );
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
