import fs from "node:fs";
import path from "node:path";

const apiBase = process.env.PANSE_XHS_API ?? "http://127.0.0.1:18060";
const output = path.resolve(
  process.argv[2] ?? "research/panse_multi_direction/login_qrcode.png",
);

const response = await fetch(`${apiBase}/api/v1/login/qrcode`, {
  signal: AbortSignal.timeout(90_000),
});
const payload = await response.json();
if (!response.ok || payload?.success === false) {
  throw new Error(`${response.status}: ${JSON.stringify(payload)}`);
}

if (payload?.data?.is_logged_in) {
  console.log(JSON.stringify({ already_logged_in: true }));
  process.exit(0);
}

const dataUrl = payload?.data?.img ?? "";
const match = dataUrl.match(/^data:image\/png;base64,(.+)$/);
if (!match) throw new Error("登录接口没有返回有效的 PNG 二维码。");

fs.mkdirSync(path.dirname(output), { recursive: true });
fs.writeFileSync(output, Buffer.from(match[1], "base64"));
console.log(
  JSON.stringify({
    already_logged_in: false,
    output,
    timeout_seconds: Number(payload?.data?.timeout ?? 0),
  }),
);
