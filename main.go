package main

import (
	"flag"
	"os"

	"github.com/sirupsen/logrus"
	"github.com/xpzouying/xiaohongshu-mcp/browser"
	"github.com/xpzouying/xiaohongshu-mcp/configs"
	"github.com/xpzouying/xiaohongshu-mcp/cookies"
)

// version 构建版本号，发布时通过 -ldflags "-X main.version=vX.Y.Z" 注入。
var version = "dev"

func main() {
	var (
		headless bool
		port     string
	)
	flag.BoolVar(&headless, "headless", true, "是否无头模式")
	flag.StringVar(&port, "port", configuredPort(), "端口（默认 18060，可由 XHS_MCP_PORT 覆盖）")
	flag.Parse()
	if value := os.Getenv(portEnvironmentVariable); value != "" {
		logrus.Infof("using %s override: %s", portEnvironmentVariable, port)
	}

	logrus.Infof("xiaohongshu-mcp version: %s", version)

	// 只用内置浏览器。启动时就备好，缺它直接退出，不拖到第一个请求才失败。
	binPath, err := browser.EnsureBrowser()
	if err != nil {
		logrus.Fatalf("%v", err)
	}
	logrus.Infof("using browser binary: %s", binPath)

	configs.InitHeadless(headless)
	// 入口层解析出 seed 和代理，经 configs 透传给浏览器工厂。
	// seed 取值：环境变量 > 会话文件 > 新生成并写回，保证同一账号每次启动一致。
	configs.SetFingerprintSeed(configs.ResolveFingerprintSeed(
		cookies.NewLoadCookie(cookies.GetCookiesFilePath())))
	configs.SetProxy(configs.ProxyFromEnv())

	// 初始化服务
	xiaohongshuService := NewXiaohongshuService()

	// 创建并启动应用服务器
	appServer := NewAppServer(xiaohongshuService)
	if err := appServer.Start(port); err != nil {
		logrus.Fatalf("failed to run server: %v", err)
	}
}
