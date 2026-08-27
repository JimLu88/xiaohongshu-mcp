import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const moduleDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(moduleDir, "..");
const registryPath = path.join(
  repoRoot,
  "research",
  "panse_multi_direction",
  "account_role_binding_v1.json",
);
const replyContractPath = path.join(
  repoRoot,
  "research",
  "panse_multi_direction",
  "xhs_reply_style_contract_v3.json",
);
const launchConfigPath = path.join(
  repoRoot,
  "research",
  "panse_multi_direction",
  "five_direction_launch_config.json",
);
const profilePackagePath = path.join(
  repoRoot,
  "research",
  "panse_multi_direction",
  "four_account_profiles_v1.json",
);
const dayOneMatrixPath = path.join(
  repoRoot,
  "research",
  "panse_multi_direction",
  "day01_theme_matrix_v1.json",
);

const registryText = fs.readFileSync(registryPath, "utf8");
const registry = JSON.parse(registryText);
const replyContract = JSON.parse(fs.readFileSync(replyContractPath, "utf8"));
const launchConfig = JSON.parse(fs.readFileSync(launchConfigPath, "utf8"));
const profilePackage = JSON.parse(fs.readFileSync(profilePackagePath, "utf8"));
const dayOneMatrix = JSON.parse(fs.readFileSync(dayOneMatrixPath, "utf8"));
const errors = [];
const accounts = Array.isArray(registry.accounts) ? registry.accounts : [];
const voiceIds = new Set(
  replyContract.voice_preflights.map((profile) => profile.voice_id),
);

if (registry.decision_status !== "finalized_by_user_request") {
  errors.push("binding decision is not finalized");
}
if (accounts.length !== 5) errors.push("expected exactly five accounts");

const slots = accounts.map((account) => account.slot);
if (new Set(slots).size !== 5 || slots.slice().sort().join(",") !== "1,2,3,4,5") {
  errors.push("slots must be unique and cover 1-5");
}
const accountIds = accounts.map((account) => account.account_id);
if (new Set(accountIds).size !== 5) errors.push("account_id values must be unique");
const workingNames = accounts.map((account) => account.working_name);
if (new Set(workingNames).size !== 5) errors.push("working names must be unique");

for (const account of accounts) {
  if (!account.phone_ref?.startsWith("private-map:slot-")) {
    errors.push(`slot ${account.slot} has no private phone reference`);
  }
  if (!/^1\d{2}\*{4}\d{4}$/u.test(account.phone_mask ?? "")) {
    errors.push(`slot ${account.slot} has an invalid phone mask`);
  }
  if (!account.device || !account.public_role || !account.bio_candidate) {
    errors.push(`slot ${account.slot} is missing device, role, or bio`);
  }
  if (!Array.isArray(account.content_responsibilities) || account.content_responsibilities.length < 3) {
    errors.push(`slot ${account.slot} has an incomplete content responsibility set`);
  }
  if (!Array.isArray(account.warmup_topic_pool) || account.warmup_topic_pool.length < 5) {
    errors.push(`slot ${account.slot} has an incomplete warmup topic pool`);
  }
  for (const voiceId of account.comment_voice_ids ?? []) {
    if (!voiceIds.has(voiceId)) {
      errors.push(`slot ${account.slot} references unknown voice ${voiceId}`);
    }
  }
}

const canonicalById = new Map(accounts.map((account) => [account.account_id, account]));
const externalBindings = [
  {
    source: "launch official account",
    records: [launchConfig.official_account],
  },
  {
    source: "launch account list",
    records: launchConfig.accounts,
  },
  {
    source: "profile package",
    records: profilePackage.accounts,
  },
  {
    source: "day one matrix",
    records: dayOneMatrix.accounts,
  },
];
for (const group of externalBindings) {
  for (const record of group.records ?? []) {
    const canonical = canonicalById.get(record.account_id);
    if (!canonical) {
      errors.push(`${group.source} has unknown account ${record.account_id}`);
      continue;
    }
    for (const field of ["slot", "working_name", "phone_ref", "phone_mask", "device"]) {
      if (record[field] != null && record[field] !== canonical[field]) {
        errors.push(`${group.source} drifted for ${record.account_id}.${field}`);
      }
    }
  }
}

if (launchConfig.account_role_binding_path !== "research/panse_multi_direction/account_role_binding_v1.json") {
  errors.push("launch config does not reference the canonical binding registry");
}
if (profilePackage.account_role_binding_path !== "research/panse_multi_direction/account_role_binding_v1.json") {
  errors.push("profile package does not reference the canonical binding registry");
}

const rawPhonePattern = /(?<!\d)1\d{10}(?!\d)/u;
if (rawPhonePattern.test(registryText)) {
  errors.push("raw phone number found in project registry");
}
if (registry.shared_rules?.required_generation_model_id !== "gpt-5.6-sol") {
  errors.push("required generation model drifted");
}
if (registry.shared_rules?.fallback_generation_model_allowed !== false) {
  errors.push("fallback generation model must remain disabled");
}

if (errors.length > 0) {
  console.error(JSON.stringify({ passed: false, errors }, null, 2));
  process.exit(1);
}

console.log(
  JSON.stringify(
    {
      passed: true,
      account_count: accounts.length,
      slots,
      bindings: accounts.map((account) => ({
        slot: account.slot,
        phone_mask: account.phone_mask,
        device: account.device,
        account_id: account.account_id,
        working_name: account.working_name,
        binding_status: account.binding_status,
      })),
      raw_phone_numbers_stored: false,
      required_generation_model_id:
        registry.shared_rules.required_generation_model_id,
      publish_allowed: false,
    },
    null,
    2,
  ),
);
