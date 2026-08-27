import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { buildArticlePreflightQueue } from "./build_xhs_article_preflight_queue.mjs";


const MODULE_DIR = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(MODULE_DIR, "..");
const DEFAULT_INPUT = path.resolve(
  PROJECT_ROOT,
  "research",
  "panse_multi_direction",
  "first_wave_article_candidates_v1.json",
);


function sha256(value) {
  return createHash("sha256").update(String(value ?? ""), "utf8").digest("hex");
}


function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}


function resolveDottedPointer(value, pointer) {
  return String(pointer ?? "")
    .split(".")
    .filter(Boolean)
    .reduce((current, key) => current?.[key], value);
}


function parseArgs(argv) {
  const args = { input: DEFAULT_INPUT, queueOutput: "" };
  for (let index = 0; index < argv.length; index += 1) {
    if (argv[index] === "--input") args.input = path.resolve(argv[index + 1] ?? "");
    if (argv[index] === "--queue-output") {
      args.queueOutput = path.resolve(argv[index + 1] ?? "");
    }
  }
  return args;
}


export function validateFirstWaveCandidates(payload) {
  const candidates = Array.isArray(payload?.candidates) ? payload.candidates : [];
  const errors = [];
  const hashSuggestions = [];
  const localSources = [];
  const snapshotSources = [];

  for (const candidate of candidates) {
    const candidateId = String(candidate?.candidate_id ?? "");
    const brief = String(candidate?.sourced_article_brief ?? "");
    const actualBriefSha = sha256(brief);
    const storedBriefSha = String(candidate?.source_contract?.brief_sha256 ?? "");
    if (storedBriefSha !== actualBriefSha) {
      errors.push(`${candidateId}: brief_sha256 mismatch`);
      hashSuggestions.push({
        candidate_id: candidateId,
        field: "source_contract.brief_sha256",
        current: storedBriefSha,
        expected: actualBriefSha,
      });
    }

    for (let index = 0; index < (candidate?.evidence_pack ?? []).length; index += 1) {
      const evidence = candidate.evidence_pack[index];
      const label = `${candidateId}: evidence_pack[${index}]`;
      if (typeof evidence?.source_snapshot === "string") {
        const expected = sha256(evidence.source_snapshot);
        snapshotSources.push({
          candidate_id: candidateId,
          evidence_index: index,
          chars: evidence.source_snapshot.length,
          sha256: expected,
        });
        if (evidence.content_sha256 !== expected) {
          errors.push(`${label} source_snapshot SHA-256 mismatch`);
          hashSuggestions.push({
            candidate_id: candidateId,
            field: `evidence_pack[${index}].content_sha256`,
            current: evidence.content_sha256,
            expected,
          });
        }
      }
      if (typeof evidence?.local_json_pointer === "string") {
        const sourcePath = path.resolve(PROJECT_ROOT, evidence.source_locator);
        if (!fs.existsSync(sourcePath)) {
          errors.push(`${label} local source not found: ${sourcePath}`);
          continue;
        }
        const sourcePayload = readJson(sourcePath);
        const body = resolveDottedPointer(sourcePayload, evidence.local_json_pointer);
        const bodyText = typeof body === "string" ? body : "";
        const expected = sha256(bodyText);
        localSources.push({
          candidate_id: candidateId,
          evidence_index: index,
          source_path: path.relative(PROJECT_ROOT, sourcePath),
          chars: bodyText.length,
          sha256: expected,
        });
        if (!bodyText.trim()) {
          errors.push(`${label} local body is empty`);
        }
        if (evidence.content_sha256 !== expected) {
          errors.push(`${label} local body SHA-256 mismatch`);
          hashSuggestions.push({
            candidate_id: candidateId,
            field: `evidence_pack[${index}].content_sha256`,
            current: evidence.content_sha256,
            expected,
          });
        }
      }
      if (evidence?.local_file_sha256 === true) {
        const sourcePath = path.isAbsolute(evidence.source_locator)
          ? evidence.source_locator
          : path.resolve(PROJECT_ROOT, evidence.source_locator);
        if (!fs.existsSync(sourcePath)) {
          errors.push(`${label} local file not found: ${sourcePath}`);
          continue;
        }
        const body = fs.readFileSync(sourcePath);
        const expected = createHash("sha256").update(body).digest("hex");
        localSources.push({
          candidate_id: candidateId,
          evidence_index: index,
          source_path: sourcePath,
          bytes: body.length,
          sha256: expected,
        });
        if (body.length === 0) {
          errors.push(`${label} local file is empty`);
        }
        if (evidence.content_sha256 !== expected) {
          errors.push(`${label} local file SHA-256 mismatch`);
          hashSuggestions.push({
            candidate_id: candidateId,
            field: `evidence_pack[${index}].content_sha256`,
            current: evidence.content_sha256,
            expected,
          });
        }
      }
    }
  }

  const queue = buildArticlePreflightQueue(payload, "2026-08-01T13:00:00+08:00");
  return {
    passed: errors.length === 0,
    input_candidates: candidates.length,
    errors,
    hash_suggestions: hashSuggestions,
    verified_local_sources: localSources,
    verified_snapshot_sources: snapshotSources,
    queue,
  };
}


function main() {
  const args = parseArgs(process.argv.slice(2));
  const result = validateFirstWaveCandidates(readJson(args.input));
  if (args.queueOutput && result.passed) {
    fs.writeFileSync(args.queueOutput, `${JSON.stringify(result.queue, null, 2)}\n`, "utf8");
  }
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  if (!result.passed) process.exitCode = 1;
}


if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main();
}
