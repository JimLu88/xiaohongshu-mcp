import fs from "node:fs";
import path from "node:path";

const apiBase = process.env.PANSE_XHS_API ?? "http://127.0.0.1:18060";
const campaignDir = path.resolve("research", "panse_multi_direction");
const campaignPath = path.join(campaignDir, "campaign.json");
const rawSearchDir = path.join(campaignDir, "raw", "search");
const rawDetailDir = path.join(campaignDir, "raw", "detail");
const rawBrowserDetailDir = path.join(campaignDir, "raw", "browser_detail");
const statePath = path.join(campaignDir, "state.json");
const candidatesPath = path.join(campaignDir, "candidates.json");
const selectedPath = path.join(campaignDir, "selected.json");
const datasetPath = path.join(campaignDir, "dataset.json");
const errorsPath = path.join(campaignDir, "errors.ndjson");

const args = new Set(process.argv.slice(2));
const normalizeOnly = args.has("--normalize-only");
const runSearch = args.size === 0 || args.has("--search") || args.has("--all");
const runDetail = args.size === 0 || args.has("--detail") || args.has("--all");
const searchDelayMs = Number(process.env.PANSE_SEARCH_DELAY_MS ?? 2500);
const detailDelayMs = Number(process.env.PANSE_DETAIL_DELAY_MS ?? 1800);
const detailConcurrency = Math.max(
  1,
  Number(process.env.PANSE_DETAIL_CONCURRENCY ?? 1),
);
const maxAttempts = Number(process.env.PANSE_MAX_ATTEMPTS ?? 3);
const maxConsecutiveDetailFailures = Math.max(
  1,
  Number(process.env.PANSE_MAX_CONSECUTIVE_DETAIL_FAILURES ?? 3),
);

function ensureDirs() {
  for (const dir of [
    campaignDir,
    rawSearchDir,
    rawDetailDir,
    rawBrowserDetailDir,
  ]) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

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

function appendError(error) {
  fs.appendFileSync(
    errorsPath,
    `${JSON.stringify({ at: new Date().toISOString(), ...error })}\n`,
    "utf8",
  );
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function safeSegment(value) {
  return String(value)
    .normalize("NFKC")
    .replace(/[<>:"/\\|?*\u0000-\u001f]/g, "_")
    .replace(/\s+/g, "_")
    .slice(0, 80);
}

function parseApiPayload(text) {
  let value = JSON.parse(text);
  if (typeof value === "string") value = JSON.parse(value);
  return value;
}

async function request(endpoint, body, context) {
  let lastError;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      const response = await fetch(`${apiBase}${endpoint}`, {
        method: body ? "POST" : "GET",
        headers: body
          ? { "content-type": "application/json; charset=utf-8" }
          : undefined,
        body: body ? JSON.stringify(body) : undefined,
        signal: AbortSignal.timeout(90_000),
      });
      const text = await response.text();
      const payload = parseApiPayload(text);
      if (!response.ok || payload?.success === false) {
        throw new Error(`${response.status}: ${JSON.stringify(payload)}`);
      }
      return payload;
    } catch (error) {
      lastError = error;
      appendError({
        stage: context.stage,
        track_id: context.track_id,
        key: context.key,
        attempt,
        message: String(error?.message ?? error),
      });
      if (attempt < maxAttempts) {
        await sleep([3500, 9000, 20000][attempt - 1] ?? 20000);
      }
    }
  }
  throw lastError;
}

function numberish(value) {
  const text = String(value ?? "").trim().toLowerCase();
  if (!text) return 0;
  const number = Number.parseFloat(text.replace(/,/g, ""));
  if (!Number.isFinite(number)) return 0;
  if (text.includes("万") || text.includes("w")) return Math.round(number * 10000);
  return Math.round(number);
}

function candidateFromFeed(feed, track, query, position, collectedAt) {
  const card = feed?.noteCard ?? {};
  const interact = card.interactInfo ?? {};
  const user = card.user ?? {};
  return {
    note_id: feed?.id ?? "",
    xsec_token: feed?.xsecToken ?? "",
    token_collected_at: collectedAt ?? null,
    title: card.displayTitle ?? "",
    note_type: card.type ?? "",
    author: {
      user_id: user.userId ?? "",
      nickname: user.nickname ?? user.nickName ?? "",
    },
    search_metrics: {
      likes: numberish(interact.likedCount),
      comments: numberish(interact.commentCount),
      collects: numberish(interact.collectedCount),
      shares: numberish(interact.sharedCount),
    },
    cover_url: card.cover?.urlDefault ?? card.cover?.urlPre ?? "",
    found_by: [
      {
        track_id: track.id,
        track_group: track.group,
        track_label: track.label,
        keyword: query.keyword,
        sort_by: query.sort_by,
        position,
      },
    ],
  };
}

function mergeCandidate(target, incoming) {
  target.found_by.push(...incoming.found_by);
  const targetTokenTime = Date.parse(target.token_collected_at ?? "") || 0;
  const incomingTokenTime = Date.parse(incoming.token_collected_at ?? "") || 0;
  if (
    incoming.xsec_token &&
    (!target.xsec_token || incomingTokenTime >= targetTokenTime)
  ) {
    target.xsec_token = incoming.xsec_token;
    target.token_collected_at = incoming.token_collected_at;
  }
  if (!target.cover_url && incoming.cover_url) target.cover_url = incoming.cover_url;
  for (const key of ["likes", "comments", "collects", "shares"]) {
    target.search_metrics[key] = Math.max(
      target.search_metrics[key] ?? 0,
      incoming.search_metrics[key] ?? 0,
    );
  }
}

function searchKey(track, query, queryIndex) {
  return `${track.id}__${String(queryIndex + 1).padStart(2, "0")}__${safeSegment(query.keyword)}__${safeSegment(query.sort_by)}`;
}

async function verifyLogin() {
  const health = await request("/health", undefined, {
    stage: "health",
    key: "health",
  });
  const login = await request("/api/v1/login/status", undefined, {
    stage: "login",
    key: "login",
  });
  const loggedIn =
    login?.data?.logged_in ??
    login?.data?.is_logged_in ??
    login?.data?.isLoggedIn ??
    false;
  console.log(
    JSON.stringify({
      event: "preflight",
      health: health?.status ?? health?.data?.status ?? "ok",
      logged_in: Boolean(loggedIn),
    }),
  );
  if (!loggedIn) {
    throw new Error("小红书登录态已失效，需要重新扫码登录。");
  }
}

async function collectSearches(campaign, state) {
  let completed = 0;
  const total = campaign.tracks.reduce((n, track) => n + track.queries.length, 0);

  for (const track of campaign.tracks) {
    for (const [queryIndex, query] of track.queries.entries()) {
      const key = searchKey(track, query, queryIndex);
      const output = path.join(rawSearchDir, `${key}.json`);
      if (fs.existsSync(output)) {
        completed += 1;
        console.log(JSON.stringify({ event: "search_cached", completed, total, key }));
        continue;
      }
      try {
        const payload = await request(
          "/api/v1/feeds/search",
          {
            keyword: query.keyword,
            filters: { sort_by: query.sort_by },
          },
          { stage: "search", track_id: track.id, key },
        );
        writeJson(output, {
          collected_at: new Date().toISOString(),
          track_id: track.id,
          track_group: track.group,
          track_label: track.label,
          query,
          response: payload,
        });
        const count = payload?.data?.feeds?.length ?? 0;
        completed += 1;
        state.searches[key] = {
          status: "completed",
          count,
          completed_at: new Date().toISOString(),
        };
        writeJson(statePath, state);
        console.log(
          JSON.stringify({ event: "search_completed", completed, total, key, count }),
        );
      } catch (error) {
        completed += 1;
        state.searches[key] = {
          status: "failed",
          message: String(error?.message ?? error),
          failed_at: new Date().toISOString(),
        };
        writeJson(statePath, state);
        console.log(
          JSON.stringify({
            event: "search_failed",
            completed,
            total,
            key,
            message: String(error?.message ?? error),
          }),
        );
      }
      await sleep(searchDelayMs);
    }
  }
}

function buildCandidates(campaign) {
  const trackById = new Map(campaign.tracks.map((track) => [track.id, track]));
  const byId = new Map();
  for (const filename of fs.readdirSync(rawSearchDir).filter((name) => name.endsWith(".json"))) {
    const record = readJson(path.join(rawSearchDir, filename));
    const track = trackById.get(record.track_id);
    if (!track) continue;
    const feeds = record?.response?.data?.feeds ?? [];
    feeds.forEach((feed, index) => {
      if (!feed?.id || !feed?.xsecToken) return;
      const candidate = candidateFromFeed(
        feed,
        track,
        record.query,
        index,
        record.collected_at,
      );
      if (byId.has(candidate.note_id)) {
        mergeCandidate(byId.get(candidate.note_id), candidate);
      } else {
        byId.set(candidate.note_id, candidate);
      }
    });
  }
  const candidates = [...byId.values()].sort((a, b) =>
    a.note_id.localeCompare(b.note_id),
  );
  writeJson(candidatesPath, {
    schema_version: "0.1",
    generated_at: new Date().toISOString(),
    unique_count: candidates.length,
    candidates,
  });
  return candidates;
}

function engagementScore(candidate) {
  const m = candidate.search_metrics;
  return (
    Math.log1p(m.likes) +
    1.35 * Math.log1p(m.collects) +
    1.15 * Math.log1p(m.comments)
  );
}

function balancedPick(candidates, quota) {
  const ordered = [...candidates].sort(
    (a, b) => engagementScore(b) - engagementScore(a),
  );
  if (ordered.length <= quota) return ordered;
  const highCount = Math.max(1, Math.round(quota * 0.6));
  const newestCount = Math.max(1, Math.round(quota * 0.2));
  const lowCount = Math.max(0, quota - highCount - newestCount);
  const chosen = [];
  const ids = new Set();
  const add = (candidate) => {
    if (candidate && !ids.has(candidate.note_id)) {
      ids.add(candidate.note_id);
      chosen.push(candidate);
    }
  };

  ordered.slice(0, highCount).forEach(add);
  candidates
    .filter((candidate) =>
      candidate.found_by.some((source) => source.sort_by === "最新"),
    )
    .slice(0, newestCount)
    .forEach(add);
  ordered.slice(-Math.max(lowCount * 3, lowCount)).reverse().forEach((candidate) => {
    if (chosen.length < quota) add(candidate);
  });
  ordered.forEach((candidate) => {
    if (chosen.length < quota) add(candidate);
  });
  return chosen.slice(0, quota);
}

function selectCandidates(campaign, candidates) {
  const exclusionRecord = readJson(
    path.join(campaignDir, "selection_exclusions.json"),
    { note_ids: [] },
  );
  const excludedNoteIds = new Set(exclusionRecord.note_ids ?? []);
  const selectedById = new Map();
  const trackSummary = [];

  for (const track of campaign.tracks) {
    const allTrackCandidates = candidates.filter((candidate) =>
      candidate.found_by.some((source) => source.track_id === track.id),
    );
    const trackCandidates = allTrackCandidates.filter(
      (candidate) => !excludedNoteIds.has(candidate.note_id),
    );
    let picked;
    if (track.group === "competitor" && track.official_account_names?.length) {
      const officialNames = new Set(track.official_account_names);
      const officialCandidates = trackCandidates.filter((candidate) =>
        officialNames.has(candidate.author.nickname),
      );
      const otherCandidates = trackCandidates.filter(
        (candidate) => !officialNames.has(candidate.author.nickname),
      );
      const officialQuota = Math.min(
        track.official_minimum ?? 0,
        officialCandidates.length,
        track.quota,
      );
      const officialPicked = balancedPick(officialCandidates, officialQuota);
      const otherPicked = balancedPick(
        otherCandidates,
        track.quota - officialPicked.length,
      );
      picked = [...officialPicked, ...otherPicked];
    } else if (track.group === "collaborator" && track.account) {
      const exactAccountCandidates = trackCandidates.filter(
        (candidate) => candidate.author.nickname === track.account,
      );
      picked = balancedPick(exactAccountCandidates, track.quota);
    } else {
      picked = balancedPick(trackCandidates, track.quota);
    }
    for (const candidate of picked) {
      if (!selectedById.has(candidate.note_id)) {
        selectedById.set(candidate.note_id, {
          ...candidate,
          selected_for: [],
        });
      }
      selectedById.get(candidate.note_id).selected_for.push({
        track_id: track.id,
        track_group: track.group,
        track_label: track.label,
      });
    }
    trackSummary.push({
      track_id: track.id,
      track_group: track.group,
      track_label: track.label,
      candidate_count: trackCandidates.length,
      excluded_candidate_count:
        allTrackCandidates.length - trackCandidates.length,
      quota: track.quota,
      selected_count: picked.length,
      selected_official_count:
        track.group === "competitor"
          ? picked.filter((candidate) =>
              track.official_account_names?.includes(candidate.author.nickname),
            ).length
          : undefined,
    });
  }

  const selected = [...selectedById.values()];
  writeJson(selectedPath, {
    schema_version: "0.1",
    generated_at: new Date().toISOString(),
    selected_unique_count: selected.length,
    requested_before_dedupe: trackSummary.reduce(
      (sum, track) => sum + track.selected_count,
      0,
    ),
    track_summary: trackSummary,
    selected,
  });
  return selected;
}

async function collectDetails(selected, state) {
  let completed = 0;
  let consecutiveFailures = 0;
  const pending = [];
  for (const candidate of selected) {
    const output = path.join(rawDetailDir, `${candidate.note_id}.json`);
    if (fs.existsSync(output)) {
      completed += 1;
      console.log(
        JSON.stringify({
          event: "detail_cached",
          completed,
          total: selected.length,
          note_id: candidate.note_id,
        }),
      );
      continue;
    }
    pending.push(candidate);
  }

  for (let index = 0; index < pending.length; index += detailConcurrency) {
    const batch = pending.slice(index, index + detailConcurrency);
    const results = await Promise.all(
      batch.map(async (candidate) => {
        const output = path.join(rawDetailDir, `${candidate.note_id}.json`);
        try {
          const payload = await request(
            "/api/v1/feeds/detail",
            {
              feed_id: candidate.note_id,
              xsec_token: candidate.xsec_token,
              load_all_comments: false,
            },
            { stage: "detail", key: candidate.note_id },
          );
          writeJson(output, {
            collected_at: new Date().toISOString(),
            selected_for: candidate.selected_for,
            found_by: candidate.found_by,
            response: payload,
          });
          return {
            status: "completed",
            candidate,
            at: new Date().toISOString(),
          };
        } catch (error) {
          return {
            status: "failed",
            candidate,
            at: new Date().toISOString(),
            message: String(error?.message ?? error),
          };
        }
      }),
    );

    for (const result of results) {
      completed += 1;
      if (result.status === "completed") {
        consecutiveFailures = 0;
        state.details[result.candidate.note_id] = {
          status: "completed",
          completed_at: result.at,
        };
        console.log(
          JSON.stringify({
            event: "detail_completed",
            completed,
            total: selected.length,
            note_id: result.candidate.note_id,
            title: result.candidate.title,
          }),
        );
      } else {
        state.details[result.candidate.note_id] = {
          status: "failed",
          message: result.message,
          failed_at: result.at,
        };
        consecutiveFailures += 1;
        console.log(
          JSON.stringify({
            event: "detail_failed",
            completed,
            total: selected.length,
            note_id: result.candidate.note_id,
            message: result.message,
          }),
        );
      }
    }
    writeJson(statePath, state);
    if (consecutiveFailures >= maxConsecutiveDetailFailures) {
      console.log(
        JSON.stringify({
          event: "detail_stopped",
          reason: "consecutive_failures",
          consecutive_failures: consecutiveFailures,
          limit: maxConsecutiveDetailFailures,
        }),
      );
      break;
    }
    if (index + detailConcurrency < pending.length) await sleep(detailDelayMs);
  }
}

function extractTopics(desc) {
  const topics = [];
  for (const match of String(desc ?? "").matchAll(/#([^#\n[\]]+)\[话题\]#/g)) {
    const value = match[1].trim();
    if (value && !topics.includes(value)) topics.push(value);
  }
  return topics;
}

function normalizeDetails(campaign, candidates, selected) {
  const selectedById = new Map(selected.map((item) => [item.note_id, item]));
  const candidateById = new Map(
    candidates.map((item) => [item.note_id, item]),
  );
  const trackById = new Map(
    campaign.tracks.map((track) => [track.id, track]),
  );
  const notes = [];
  for (const filename of fs.readdirSync(rawDetailDir).filter((name) => name.endsWith(".json"))) {
    const record = readJson(path.join(rawDetailDir, filename));
    const note = record?.response?.data?.data?.note;
    if (!note?.noteId) continue;
    const candidate =
      selectedById.get(note.noteId) ?? candidateById.get(note.noteId);
    if (!candidate) continue;
    const comments = record?.response?.data?.data?.comments?.list ?? [];
    const desc = note.desc ?? "";
    const selectedForSources = [
      ...(record.selected_for ?? []),
      ...(candidate.selected_for ?? []),
      ...candidate.found_by.map((source) => ({
        track_id: source.track_id,
        track_group: source.track_group,
        track_label: source.track_label,
      })),
    ];
    const selectedFor = [
      ...new Map(
        selectedForSources.map((source) => [source.track_id, source]),
      ).values(),
    ];
    const searchableText = `${note.title ?? ""}\n${desc}`.normalize("NFKC");
    const trackValidation = selectedFor.map((source) => {
      const track = trackById.get(source.track_id);
      if (!track) {
        return {
          track_id: source.track_id,
          status: "unknown_track",
          confirmed: false,
        };
      }
      if (track.group === "competitor") {
        if (track.official_account_names?.includes(note.user?.nickname)) {
          return {
            track_id: track.id,
            status: "confirmed_official_account",
            confirmed: true,
          };
        }
        if (track.brand && searchableText.includes(track.brand)) {
          return {
            track_id: track.id,
            status: "confirmed_brand_mention",
            confirmed: true,
          };
        }
        return {
          track_id: track.id,
          status: "search_only_no_brand_evidence",
          confirmed: false,
        };
      }
      if (track.group === "collaborator") {
        return {
          track_id: track.id,
          status:
            note.user?.nickname === track.account
              ? "confirmed_account"
              : "search_only_wrong_account",
          confirmed: note.user?.nickname === track.account,
        };
      }
      return {
        track_id: track.id,
        status: "direction_search_sample",
        confirmed: true,
      };
    });
    notes.push({
      note_id: note.noteId,
      title: note.title ?? "",
      text: desc,
      topics: extractTopics(desc),
      note_type: note.type ?? candidate.note_type ?? "",
      published_at: note.time ? new Date(note.time).toISOString() : null,
      ip_location: note.ipLocation ?? "",
      author: {
        user_id: note.user?.userId ?? candidate.author.user_id,
        nickname: note.user?.nickname ?? candidate.author.nickname,
      },
      metrics: {
        likes: numberish(note.interactInfo?.likedCount),
        comments: numberish(note.interactInfo?.commentCount),
        collects: numberish(note.interactInfo?.collectedCount),
        shares: numberish(note.interactInfo?.sharedCount),
      },
      media: {
        image_count: note.imageList?.length ?? 0,
        images: (note.imageList ?? []).map((image) => ({
          width: image.width ?? 0,
          height: image.height ?? 0,
          url: image.urlDefault ?? image.urlPre ?? "",
          live_photo: Boolean(image.livePhoto),
        })),
        video_url: note.video?.media?.stream?.h264?.[0]?.masterUrl ?? "",
        video_duration_ms: numberish(note.video?.capa?.duration),
      },
      first_page_comments: comments.map((comment) => ({
        comment_id: comment.id ?? "",
        content: comment.content ?? "",
        likes: numberish(comment.likeCount),
        author: comment.userInfo?.nickname ?? "",
        author_user_id: comment.userInfo?.userId ?? "",
        author_reply_count: (comment.subComments ?? []).filter((reply) =>
          reply.showTags?.includes("is_author"),
        ).length,
      })),
      commercial_marker_detected:
        /(?:商业合作|品牌合作|广告合作|报备|赞助)/i.test(desc),
      selected_for: selectedFor,
      track_validation: trackValidation,
      quality_flags: [
        ...(note.title?.trim() ? [] : ["missing_title"]),
        ...(desc.trim() ? [] : ["missing_text"]),
        ...(extractTopics(desc).length ? [] : ["no_standard_topics"]),
        ...trackValidation
          .filter((validation) => !validation.confirmed)
          .map(
            (validation) =>
              `unconfirmed_track:${validation.track_id}:${validation.status}`,
          ),
      ],
      found_by: record.found_by ?? candidate.found_by,
      collected_at: record.collected_at,
      source_url: `https://www.xiaohongshu.com/explore/${encodeURIComponent(note.noteId)}?xsec_token=${encodeURIComponent(note.xsecToken ?? candidate.xsec_token)}&xsec_source=pc_search`,
    });
  }

  const seenNoteIds = new Set(notes.map((note) => note.note_id));
  for (const filename of fs
    .readdirSync(rawBrowserDetailDir)
    .filter((name) => name.endsWith(".json"))) {
    const batch = readJson(path.join(rawBrowserDetailDir, filename), {
      notes: [],
    });
    for (const browserNote of batch.notes ?? []) {
      if (!browserNote.note_id || seenNoteIds.has(browserNote.note_id)) continue;
      const selectedFor = browserNote.selected_for ?? [];
      const searchableText =
        `${browserNote.title ?? ""}\n${browserNote.text ?? ""}`.normalize(
          "NFKC",
        );
      const trackValidation = selectedFor.map((source) => {
        const track = trackById.get(source.track_id);
        if (!track) {
          return {
            track_id: source.track_id,
            status: "unknown_track",
            confirmed: false,
          };
        }
        if (track.group === "competitor") {
          if (
            track.official_account_names?.includes(
              browserNote.author?.nickname,
            )
          ) {
            return {
              track_id: track.id,
              status: "confirmed_official_account",
              confirmed: true,
            };
          }
          if (track.brand && searchableText.includes(track.brand)) {
            return {
              track_id: track.id,
              status: "confirmed_brand_mention",
              confirmed: true,
            };
          }
          return {
            track_id: track.id,
            status: "search_only_no_brand_evidence",
            confirmed: false,
          };
        }
        if (track.group === "collaborator") {
          return {
            track_id: track.id,
            status:
              browserNote.author?.nickname === track.account
                ? "confirmed_account"
                : "search_only_wrong_account",
            confirmed: browserNote.author?.nickname === track.account,
          };
        }
        return {
          track_id: track.id,
          status: "direction_search_sample",
          confirmed: true,
        };
      });
      const topics = browserNote.topics ?? [];
      const text = browserNote.text ?? "";
      notes.push({
        note_id: browserNote.note_id,
        title: browserNote.title ?? "",
        text,
        topics,
        note_type: browserNote.note_type ?? "",
        published_at: null,
        published_label: browserNote.published_label ?? "",
        ip_location: "",
        author: {
          user_id: browserNote.author?.user_id ?? "",
          nickname: browserNote.author?.nickname ?? "",
        },
        metrics: {
          likes: numberish(browserNote.metrics?.likes),
          comments: numberish(browserNote.metrics?.comments),
          collects: numberish(browserNote.metrics?.collects),
          shares: numberish(browserNote.metrics?.shares),
        },
        media: {
          image_count: browserNote.media?.image_count ?? 0,
          images: (browserNote.media?.images ?? []).map((image) => ({
            width: image.width ?? 0,
            height: image.height ?? 0,
            url: image.url ?? "",
            live_photo: Boolean(image.live_photo),
          })),
          video_url: browserNote.media?.video_url ?? "",
          video_duration_ms: numberish(
            browserNote.media?.video_duration_ms,
          ),
        },
        first_page_comments: (browserNote.first_page_comments ?? []).map(
          (comment) => ({
            comment_id: comment.comment_id ?? "",
            content: comment.content ?? "",
            likes: numberish(comment.likes),
            author: comment.author ?? "",
            author_user_id: comment.author_user_id ?? "",
            author_reply_count: 0,
            info: comment.info ?? "",
            is_sub_comment: Boolean(comment.is_sub_comment),
          }),
        ),
        commercial_marker_detected:
          /(?:商业合作|品牌合作|广告合作|报备|赞助)/i.test(text),
        selected_for: selectedFor,
        track_validation: trackValidation,
        quality_flags: [
          ...(browserNote.title?.trim() ? [] : ["missing_title"]),
          ...(text.trim() ? [] : ["missing_text"]),
          ...(topics.length ? [] : ["no_standard_topics"]),
          ...trackValidation
            .filter((validation) => !validation.confirmed)
            .map(
              (validation) =>
                `unconfirmed_track:${validation.track_id}:${validation.status}`,
            ),
        ],
        found_by: browserNote.found_by ?? [],
        collected_at:
          browserNote.browser_collected_at ?? batch.collected_at ?? null,
        collection_source: batch.source ?? "codex_in_app_browser",
        source_url: browserNote.source_url ?? "",
      });
      seenNoteIds.add(browserNote.note_id);
    }
  }

  notes.sort((a, b) => a.note_id.localeCompare(b.note_id));
  const completedTrackCounts = new Map();
  for (const note of notes) {
    for (const track of note.selected_for) {
      completedTrackCounts.set(
        track.track_id,
        (completedTrackCounts.get(track.track_id) ?? 0) + 1,
      );
    }
  }
  const trackCoverage = campaign.tracks.map((track) => ({
    track_id: track.id,
    track_group: track.group,
    track_label: track.label,
    quota: track.quota,
    completed_count: completedTrackCounts.get(track.id) ?? 0,
  }));

  writeJson(datasetPath, {
    schema_version: "0.1",
    generated_at: new Date().toISOString(),
    project: campaign.project,
    campaign_batch: campaign.current_batch,
    collection_boundary: campaign.safety,
    notes_count: notes.length,
    track_coverage: trackCoverage,
    notes,
  });
  return notes;
}

async function main() {
  ensureDirs();
  const campaign = readJson(campaignPath);
  if (!campaign) throw new Error(`缺少采集配置：${campaignPath}`);
  const state = readJson(statePath, {
    schema_version: "0.1",
    created_at: new Date().toISOString(),
    searches: {},
    details: {},
  });

  if (!normalizeOnly) await verifyLogin();
  if (runSearch) await collectSearches(campaign, state);
  const candidates = buildCandidates(campaign);
  const selected = selectCandidates(campaign, candidates);
  console.log(
    JSON.stringify({
      event: "selection_built",
      candidates: candidates.length,
      selected_unique: selected.length,
    }),
  );
  if (runDetail) await collectDetails(selected, state);
  const notes = normalizeDetails(campaign, candidates, selected);
  console.log(
    JSON.stringify({
      event: "dataset_built",
      notes: notes.length,
      output: datasetPath,
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
