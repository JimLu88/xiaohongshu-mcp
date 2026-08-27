import fs from "node:fs";
import path from "node:path";

const apiBase = "http://127.0.0.1:18060/api/v1";
const outputDir = path.resolve("research", "panse_pilot_5");

function parseResponse(text) {
  let value = JSON.parse(text);
  if (typeof value === "string") {
    value = JSON.parse(value);
  }
  return value;
}

async function request(endpoint, options = {}) {
  const response = await fetch(`${apiBase}${endpoint}`, options);
  const text = await response.text();
  const payload = parseResponse(text);
  if (!response.ok || payload?.success === false) {
    throw new Error(
      `${response.status} ${endpoint}: ${JSON.stringify(payload)}`,
    );
  }
  return payload;
}

function saveJson(filename, payload) {
  fs.mkdirSync(outputDir, { recursive: true });
  const target = path.join(outputDir, filename);
  fs.writeFileSync(target, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
  return target;
}

function summarizeFeed(feed) {
  const card = feed?.noteCard ?? {};
  const user = card.user ?? {};
  const interact = card.interactInfo ?? {};
  return {
    index: feed?.index,
    id: feed?.id,
    token: feed?.xsecToken,
    title: card.displayTitle ?? "",
    author: user.nickname ?? user.nickName ?? "",
    user_id: user.userId ?? "",
    likes: interact.likedCount ?? "",
    comments: interact.commentCount ?? "",
    collects: interact.collectedCount ?? "",
    cover: card.cover?.urlDefault ?? card.cover?.urlPre ?? "",
  };
}

async function search(keyword, filename, filtersJson = "{}") {
  const filters = JSON.parse(filtersJson);
  const payload = await request("/feeds/search", {
    method: "POST",
    headers: { "content-type": "application/json; charset=utf-8" },
    body: JSON.stringify({ keyword, filters }),
  });
  const target = saveJson(filename, payload);
  const feeds = payload?.data?.feeds ?? [];
  console.log(
    JSON.stringify(
      {
        keyword,
        saved_to: target,
        count: feeds.length,
        feeds: feeds.map(summarizeFeed),
      },
      null,
      2,
    ),
  );
}

async function detail(feedId, token, filename) {
  const payload = await request("/feeds/detail", {
    method: "POST",
    headers: { "content-type": "application/json; charset=utf-8" },
    body: JSON.stringify({
      feed_id: feedId,
      xsec_token: token,
      load_all_comments: false,
    }),
  });
  const target = saveJson(filename, payload);
  console.log(
    JSON.stringify(
      {
        feed_id: feedId,
        saved_to: target,
        top_level_keys: Object.keys(payload?.data?.data ?? {}),
      },
      null,
      2,
    ),
  );
}

async function profile(userId, token, filename) {
  const payload = await request("/user/profile", {
    method: "POST",
    headers: { "content-type": "application/json; charset=utf-8" },
    body: JSON.stringify({ user_id: userId, xsec_token: token }),
  });
  const target = saveJson(filename, payload);
  console.log(
    JSON.stringify(
      {
        user_id: userId,
        saved_to: target,
        top_level_keys: Object.keys(payload?.data?.data ?? {}),
      },
      null,
      2,
    ),
  );
}

const [command, ...args] = process.argv.slice(2);

if (command === "search" && args.length >= 2) {
  await search(args[0], args[1], args[2]);
} else if (command === "detail" && args.length >= 3) {
  await detail(args[0], args[1], args[2]);
} else if (command === "profile" && args.length >= 3) {
  await profile(args[0], args[1], args[2]);
} else {
  console.error(
    [
      "Usage:",
      "  node scripts/xhs_readonly_probe.mjs search <keyword> <output.json> [filters-json]",
      "  node scripts/xhs_readonly_probe.mjs detail <feed-id> <xsec-token> <output.json>",
      "  node scripts/xhs_readonly_probe.mjs profile <user-id> <xsec-token> <output.json>",
    ].join("\n"),
  );
  process.exit(2);
}
