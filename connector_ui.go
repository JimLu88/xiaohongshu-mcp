package main

import (
	"net/http"

	"github.com/gin-gonic/gin"
)

const connectorLoginPage = `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Search OS｜小红书独立连接器</title>
  <style>
    :root { color-scheme: dark; font-family: system-ui, -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif; }
    * { box-sizing: border-box; }
    body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: #111; color: #f5f5f5; }
    main { width: min(520px, calc(100vw - 32px)); padding: 32px; border: 1px solid #333; border-radius: 20px; background: #1b1b1b; text-align: center; box-shadow: 0 24px 70px #0009; }
    .eyebrow { color: #ff5a70; font-weight: 750; letter-spacing: .04em; }
    h1 { margin: 10px 0 8px; font-size: clamp(25px, 6vw, 34px); }
    .subtitle { margin: 0 0 20px; color: #aaa; line-height: 1.65; }
    #qr { display: block; width: min(300px, 76vw); aspect-ratio: 1; margin: 20px auto; padding: 14px; border-radius: 16px; background: #fff; image-rendering: pixelated; }
    #qr[hidden] { display: none; }
    #status { min-height: 48px; display: grid; place-items: center; margin: 14px 0; padding: 12px; border-radius: 12px; background: #262626; line-height: 1.5; }
    #status.success { color: #83e6ad; background: #173324; }
    #status.error { color: #ff9ca8; background: #3b1e22; }
    .actions { display: flex; justify-content: center; gap: 10px; flex-wrap: wrap; }
    button { border: 1px solid #444; border-radius: 10px; padding: 10px 15px; background: #2d2d2d; color: #fff; cursor: pointer; font: inherit; }
    button:hover { background: #383838; }
    .boundary { margin: 20px 0 0; color: #8f8f8f; font-size: 13px; line-height: 1.65; }
  </style>
</head>
<body>
  <main>
    <div class="eyebrow">AI SEARCH OS · 独立连接器</div>
    <h1>小红书只读搜索登录</h1>
    <p class="subtitle">使用小红书 App 扫描二维码，并在手机端确认。</p>
    <img id="qr" alt="小红书登录二维码" hidden>
    <div id="status" role="status" aria-live="polite">正在生成二维码…</div>
    <div class="actions">
      <button id="refresh" type="button">刷新二维码</button>
    </div>
    <p class="boundary">二维码仅在当前页面内存中展示，不写入磁盘。扫码并在手机端确认后，请直接回到 Codex；不要刷新页面。评论、关注、发布等操作仍保持关闭。</p>
  </main>
  <script>
    const qr = document.querySelector('#qr');
    const statusBox = document.querySelector('#status');
    const refreshButton = document.querySelector('#refresh');

    function setStatus(message, kind = '') {
      statusBox.textContent = message;
      statusBox.className = kind;
    }

    async function loadQRCode() {
      refreshButton.disabled = true;
      qr.hidden = true;
      setStatus('正在生成二维码…');
      try {
        const response = await fetch('/api/v1/login/qrcode', { cache: 'no-store' });
        const payload = await response.json();
        if (!response.ok || !payload.success || !payload.data || !payload.data.img) {
          throw new Error(payload.message || '二维码接口没有返回图像');
        }
        if (payload.data.is_logged_in) {
          setStatus('连接器已经登录，可以返回 Codex 继续测试。', 'success');
          return;
        }
        qr.src = payload.data.img;
        qr.hidden = false;
        setStatus('二维码已生成，请扫码并在手机端确认。');
      } catch (error) {
        setStatus('二维码生成失败：' + error.message, 'error');
      } finally {
        refreshButton.disabled = false;
      }
    }

    refreshButton.addEventListener('click', loadQRCode);
    loadQRCode();
  </script>
</body>
</html>`

func (s *AppServer) loginPageHandler(c *gin.Context) {
	c.Header("Cache-Control", "no-store, max-age=0")
	c.Header("Pragma", "no-cache")
	c.Header("Content-Security-Policy", "default-src 'none'; connect-src 'self'; img-src 'self' data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
	c.Data(http.StatusOK, "text/html; charset=utf-8", []byte(connectorLoginPage))
}
