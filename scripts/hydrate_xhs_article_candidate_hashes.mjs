import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";


function sha256(value) {
  return createHash("sha256").update(String(value), "utf8").digest("hex");
}


function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}


function resolveJsonPointer(document, pointer) {
  if (pointer === "" || pointer === "/") return document;
  if (!String(pointer).startsWith("/")) {
    throw new Error(`JSON pointer must start with /: ${pointer}`);
  }
  return String(pointer)
    .slice(1)
    .split("/")
    .map((part) => part.replace(/~1/gu, "/").replace(/~0/gu, "~"))
    .reduce((current, part) => {
      if (current === undefined || current === null || !(part in current)) {
        throw new Error(`JSON pointer segment not found: ${part} in ${pointer}`);
      }
      return current[part];
    }, document);
}


function localPathFromLocator(repoRoot, locator) {
  const clean = String(locator).split("#", 1)[0];
  if (/^https?:\/\//u.test(clean)) return null;
  return path.resolve(repoRoot, clean);
}


function hydrateCandidate(repoRoot, candidate) {
  candidate.source_contract.brief_sha256 = sha256(candidate.sourced_article_brief);

  for (const evidence of candidate.evidence_pack ?? []) {
    let sourceBody;
    if (typeof evidence.source_snapshot === "string") {
      sourceBody = evidence.source_snapshot;
    } else if (evidence.local_json_pointer) {
      const localPath = localPathFromLocator(repoRoot, evidence.source_locator);
      if (!localPath) {
        throw new Error(
          `${candidate.candidate_id}: local_json_pointer requires a local source_locator`,
        );
      }
      const localDocument = readJson(localPath);
      sourceBody = resolveJsonPointer(localDocument, evidence.local_json_pointer);
    } else {
      throw new Error(
        `${candidate.candidate_id}: evidence lacks source_snapshot or local_json_pointer`,
      );
    }
    if (typeof sourceBody !== "string" || sourceBody.trim() === "") {
      throw new Error(`${candidate.candidate_id}: evidence source body is empty`);
    }
    evidence.content_sha256 = sha256(sourceBody);
  }
  return candidate;
}


function parseArgs(argv) {
  const args = { input: "", output: "" };
  for (let index = 0; index < argv.length; index += 1) {
    if (argv[index] === "--input") args.input = argv[index + 1] ?? "";
    if (argv[index] === "--output") args.output = argv[index + 1] ?? "";
  }
  return args;
}


function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.input || !args.output) {
    throw new Error(
      "Usage: node hydrate_xhs_article_candidate_hashes.mjs --input <source.json> --output <candidates.json>",
    );
  }
  const inputPath = path.resolve(args.input);
  const outputPath = path.resolve(args.output);
  const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
  const payload = readJson(inputPath);
  payload.generated_at = new Date().toISOString();
  payload.generated_from = path.relative(repoRoot, inputPath).replaceAll("\\", "/");
  payload.hash_hydration = {
    algorithm: "sha256",
    brief_basis: "exact UTF-8 sourced_article_brief",
    evidence_basis:
      "exact UTF-8 source_snapshot or exact string at local_json_pointer",
  };
  payload.candidates = (payload.candidates ?? []).map((candidate) =>
    hydrateCandidate(repoRoot, candidate),
  );
  const output = `${JSON.stringify(payload, null, 2)}\n`;
  if (output.includes('"AUTO"')) {
    throw new Error("AUTO hash placeholder remains after hydration");
  }
  fs.writeFileSync(outputPath, output, "utf8");
  process.stdout.write(
    `${JSON.stringify({ output: outputPath, candidates: payload.candidates.length })}\n`,
  );
}


try {
  main();
} catch (error) {
  process.stderr.write(`${error.stack ?? error.message}\n`);
  process.exitCode = 1;
}
