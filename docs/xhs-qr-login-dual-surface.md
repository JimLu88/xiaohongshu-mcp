# 小红书登录二维码双入口

## 两条入口

两条入口共用 `scripts/lib/xhs_qr_login.py` 的状态库和同一张
`current-qr.png`，不会各自获取、缓存或判断二维码：

1. AI 对话入口读取状态中的 `markdown_image`，直接展示绝对本地图片路径。
2. 本地备用页访问 `http://127.0.0.1:18765/`，从同一状态库显示图片和
   `active / expired / scanned / confirmed / failed` 状态。

启动备用页：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\start_xhs_qr_login_portal.ps1 -AccountSlot 5 -PlanDate 2026-08-31
```

也可以在 PowerShell 7 中启动：

```powershell
pwsh.exe -NoProfile -ExecutionPolicy Bypass -File scripts\start_xhs_qr_login_portal.ps1 -AccountSlot 5 -PlanDate 2026-08-31
```

`AccountSlot` 和 `PlanDate` 必须明确传入。程序会从
`account_role_binding_v1.json` 和该日期的 `account_N_daily_plan.json` 同时核对账号，
只有 slot、日期、账号、脱敏手机、设备、预期昵称、运营名称和角色全部一致才启动。
启动器保持纯 ASCII，以同时兼容 Windows PowerShell 5.1 与 PowerShell 7；网页仍显示中文。
只检查启动器和入口文件、但不启动服务时，两种终端均可追加 `-ValidateOnly`。

页面只在用户点击后获取或刷新二维码。程序先同时核对页面上的“我”链接和只返回
布尔判断的本人接口探针。只有两者都精确匹配目标 slot 的公开 profile ID，才返回
`confirmed` 并直接复用原登录状态，不注销、不刷新二维码。若确实未登录，才显示该
slot 的二维码；若身份不符，必须由用户点击“切换账号并获取二维码”并再次确认；若
出现验证码、安全验证、频率限制或账号异常，立即停止且不刷新、不换号。每个过期
代次只允许一次刷新，不存在后台无限刷新。

## 安全边界

- 五个账号分别使用 `playwright_browser_slot_1` 至
  `playwright_browser_slot_5`。每个 MCP 按需启动，并固定使用
  `D:\AI\tachikoma\.runtime\playwright-browser-profiles\slot-N`；五个登录资料互不覆盖，
  也不读取、复制或接管用户日常 Chrome 资料。
- 二维码运行状态也按 `slot-N` 分目录，不能让一个账号的二维码状态被另一个账号复用。
- 状态文件只保存短时二维码图片、图片路径、哈希、时间、代次和有限状态码；图片可直接显示在
  当前 01 对话和本地备用页。不保存 Cookie、Token、验证码、完整手机号、二维码解码后的字符串、
  session storage 或聊天内容。每个二维码代次同时绑定
  `account_slot / masked_phone / device / expected_nickname / working_name / login_purpose`
  六项脱敏上下文。
- 只有未过期、上下文完整且与当前明确目标 slot 精确一致的 `active / scanned` 状态
  才会向 AI、CLI、本地页和 `/qr.png` 返回图片。旧 schema、缺项、陈旧日期或冲突状态
  一律不显示二维码。
- 扫码和手机确认只能由用户完成；程序不绕过登录、验证码或风控。
- 服务停止、二维码确认或失败时调用 `browser_close`。
- 登录有效期只在平台响应明确给出 `x-session-expires-at` 或 `x-auth-expires-at` 时记录
  到期时间；普通缓存 `Expires` 只记录“存在”这个布尔值，不推算登录剩余时长。
