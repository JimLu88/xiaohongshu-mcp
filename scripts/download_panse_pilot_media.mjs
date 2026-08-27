import fs from "node:fs";
import path from "node:path";

const researchDir = path.resolve("research", "panse_pilot_5");
const mediaDir = path.join(researchDir, "media");

async function download(url, target) {
  if (fs.existsSync(target) && fs.statSync(target).size > 0) {
    return { target, reused: true, bytes: fs.statSync(target).size };
  }
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`${response.status} while downloading ${url}`);
  }
  const bytes = Buffer.from(await response.arrayBuffer());
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, bytes);
  return { target, reused: false, bytes: bytes.length };
}

function bestVideoUrl(video) {
  const groups = Object.values(video?.media?.stream ?? {});
  const streams = groups.flat().filter((item) => item?.masterUrl);
  streams.sort((a, b) => {
    const pixelsA = Number(a.width ?? 0) * Number(a.height ?? 0);
    const pixelsB = Number(b.width ?? 0) * Number(b.height ?? 0);
    return pixelsB - pixelsA;
  });
  return streams[0]?.masterUrl ?? "";
}

const sampleFiles = fs
  .readdirSync(researchDir)
  .filter((name) => name.startsWith("sample_") && name.endsWith(".json"))
  .sort();

const results = [];
for (const filename of sampleFiles) {
  const sample = JSON.parse(
    fs.readFileSync(path.join(researchDir, filename), "utf8"),
  );
  const note = sample?.data?.data?.note ?? {};
  const sampleName = filename.replace(/\.json$/i, "");
  const sampleDir = path.join(mediaDir, sampleName);

  const images = note.imageList ?? [];
  for (let index = 0; index < images.length; index += 1) {
    const url = images[index]?.urlDefault ?? images[index]?.urlPre;
    if (!url) continue;
    const target = path.join(
      sampleDir,
      `image_${String(index + 1).padStart(2, "0")}.webp`,
    );
    results.push({
      sample: sampleName,
      kind: "image",
      ...(await download(url, target)),
    });
  }

  const videoUrl = bestVideoUrl(note.video);
  if (videoUrl) {
    const target = path.join(sampleDir, "video.mp4");
    results.push({
      sample: sampleName,
      kind: "video",
      ...(await download(videoUrl, target)),
    });
  }
}

const manifestPath = path.join(mediaDir, "download_manifest.json");
fs.mkdirSync(mediaDir, { recursive: true });
fs.writeFileSync(
  manifestPath,
  `${JSON.stringify(
    {
      generated_at: new Date().toISOString(),
      file_count: results.length,
      total_bytes: results.reduce((sum, item) => sum + item.bytes, 0),
      files: results,
    },
    null,
    2,
  )}\n`,
  "utf8",
);

console.log(
  JSON.stringify(
    {
      manifest: manifestPath,
      file_count: results.length,
      total_bytes: results.reduce((sum, item) => sum + item.bytes, 0),
    },
    null,
    2,
  ),
);
