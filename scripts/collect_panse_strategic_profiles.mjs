import fs from "node:fs";
import path from "node:path";

const apiBase = process.env.PANSE_XHS_API ?? "http://127.0.0.1:18060";
const base = path.resolve("research", "panse_multi_direction");
const rawDir = path.join(base, "raw", "profile");
const campaign = JSON.parse(
  fs.readFileSync(path.join(base, "campaign.json"), "utf8"),
);
const candidates = JSON.parse(
  fs.readFileSync(path.join(base, "candidates.json"), "utf8"),
).candidates;

fs.mkdirSync(rawDir, { recursive: true });

function writeJson(file, value) {
  const temp = `${file}.tmp`;
  fs.writeFileSync(temp, `${JSON.stringify(value, null, 2)}\n`, "utf8");
  fs.renameSync(temp, file);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function numberish(value) {
  const text = String(value ?? "").trim().toLowerCase();
  if (!text) return 0;
  const number = Number.parseFloat(text.replace(/,/g, ""));
  if (!Number.isFinite(number)) return 0;
  if (text.includes("万") || text.includes("w")) return Math.round(number * 10000);
  return Math.round(number);
}

function profileCandidates() {
  const requestedNames = new Set();
  for (const track of campaign.tracks) {
    for (const name of track.official_account_names ?? []) requestedNames.add(name);
    if (track.account) requestedNames.add(track.account);
  }

  const matches = new Map();
  for (const candidate of candidates) {
    const name = candidate.author.nickname;
    if (!requestedNames.has(name) || !candidate.author.user_id) continue;
    const key = `${name}::${candidate.author.user_id}`;
    if (!matches.has(key)) {
      matches.set(key, {
        requested_name: name,
        user_id: candidate.author.user_id,
        xsec_token: candidate.xsec_token,
        candidate_count: 0,
        max_interactions: 0,
      });
    }
    const match = matches.get(key);
    match.candidate_count += 1;
    match.max_interactions = Math.max(
      match.max_interactions,
      candidate.search_metrics.likes +
        candidate.search_metrics.comments +
        candidate.search_metrics.collects,
    );
    if (!match.xsec_token && candidate.xsec_token) {
      match.xsec_token = candidate.xsec_token;
    }
  }

  const bestByName = new Map();
  for (const match of matches.values()) {
    const current = bestByName.get(match.requested_name);
    if (
      !current ||
      match.candidate_count > current.candidate_count ||
      (match.candidate_count === current.candidate_count &&
        match.max_interactions > current.max_interactions)
    ) {
      bestByName.set(match.requested_name, match);
    }
  }
  return [...bestByName.values()];
}

async function requestProfile(target) {
  let lastError;
  for (let attempt = 1; attempt <= 2; attempt += 1) {
    try {
      const response = await fetch(`${apiBase}/api/v1/user/profile`, {
        method: "POST",
        headers: { "content-type": "application/json; charset=utf-8" },
        body: JSON.stringify({
          user_id: target.user_id,
          xsec_token: target.xsec_token,
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
      if (attempt < 2) await sleep(8000);
    }
  }
  throw lastError;
}

function interactionMap(interactions) {
  return Object.fromEntries(
    (interactions ?? []).map((item) => [item.type ?? item.name, numberish(item.count)]),
  );
}

const targets = profileCandidates();
const results = [];
for (const [index, target] of targets.entries()) {
  const output = path.join(rawDir, `${target.user_id}.json`);
  let record;
  if (fs.existsSync(output)) {
    record = JSON.parse(fs.readFileSync(output, "utf8"));
    console.log(
      JSON.stringify({
        event: "profile_cached",
        completed: index + 1,
        total: targets.length,
        account: target.requested_name,
      }),
    );
  } else {
    try {
      const response = await requestProfile(target);
      record = {
        collected_at: new Date().toISOString(),
        target,
        response,
      };
      writeJson(output, record);
      console.log(
        JSON.stringify({
          event: "profile_completed",
          completed: index + 1,
          total: targets.length,
          account: target.requested_name,
        }),
      );
    } catch (error) {
      results.push({
        requested_name: target.requested_name,
        user_id: target.user_id,
        status: "failed",
        message: String(error?.message ?? error),
      });
      console.log(
        JSON.stringify({
          event: "profile_failed",
          completed: index + 1,
          total: targets.length,
          account: target.requested_name,
          message: String(error?.message ?? error),
        }),
      );
      continue;
    }
    await sleep(5000);
  }

  const data = record?.response?.data?.data ?? {};
  const basic = data.userBasicInfo ?? {};
  const interactions = interactionMap(data.interactions);
  results.push({
    requested_name: target.requested_name,
    user_id: target.user_id,
    status: "completed",
    nickname: basic.nickname ?? target.requested_name,
    red_id: basic.redId ?? "",
    bio: basic.desc ?? "",
    ip_location: basic.ipLocation ?? "",
    following: interactions.follows ?? 0,
    followers: interactions.fans ?? 0,
    total_likes_and_collects: interactions.interaction ?? 0,
    profile_feeds_loaded: data.feeds?.length ?? 0,
    collected_at: record.collected_at,
  });
}

writeJson(path.join(base, "strategic_profiles.json"), {
  schema_version: "0.1",
  generated_at: new Date().toISOString(),
  requested_count: targets.length,
  completed_count: results.filter((item) => item.status === "completed").length,
  profiles: results,
});
console.log(
  JSON.stringify({
    event: "strategic_profiles_built",
    requested: targets.length,
    completed: results.filter((item) => item.status === "completed").length,
  }),
);
