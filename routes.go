package main

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/modelcontextprotocol/go-sdk/mcp"
)

// setupRoutes 设置路由配置
func setupRoutes(appServer *AppServer) *gin.Engine {
	// 设置 Gin 模式
	gin.SetMode(gin.ReleaseMode)

	router := gin.New()
	router.Use(gin.Logger())
	router.Use(gin.Recovery())

	// 添加中间件
	router.Use(errorHandlingMiddleware())
	router.Use(corsMiddleware())

	// 本地人工登录页。页面只在内存中展示二维码，不持久化认证材料。
	router.GET("/", appServer.loginPageHandler)
	router.GET("/login", appServer.loginPageHandler)
	router.GET("/research", appServer.researchPageHandler)

	// 健康检查
	router.GET("/health", healthHandler)
	router.GET("/healthz", tachikomaHealthzHandler)
	router.GET("/tachikoma/v1/contract", tachikomaContractHandler)

	// MCP 端点 - 使用官方 SDK 的 Streamable HTTP Handler
	mcpHandler := mcp.NewStreamableHTTPHandler(
		func(r *http.Request) *mcp.Server {
			return appServer.mcpServer
		},
		&mcp.StreamableHTTPOptions{
			JSONResponse: true, // 支持 JSON 响应
			// 换取客户端可跳过 initialize 握手直接调工具。代价是服务端无法反向
			// 请求客户端（sampling / elicitation / roots），眼下一处都没用到；
			// 要用得先摘掉这行。
			Stateless: true,
		},
	)
	router.Any("/mcp", gin.WrapH(mcpHandler))
	router.Any("/mcp/*path", gin.WrapH(mcpHandler))

	// API 路由组
	api := router.Group("/api/v1")
	{
		api.GET("/login/status", appServer.checkLoginStatusHandler)
		api.GET("/login/qrcode", appServer.getLoginQrcodeHandler)
		productionGuard := tachikomaProductionGuard(appServer.tachikomaRegistry, defaultActionTimeout)
		productionReadGuard := tachikomaProductionReadGuard(defaultActionTimeout)
		api.DELETE("/login/cookies", productionGuard, appServer.deleteCookiesHandler)
		api.POST("/publish", productionGuard, appServer.publishHandler)
		api.POST("/publish_video", productionGuard, appServer.publishVideoHandler)
		api.GET("/feeds/list", productionReadGuard, appServer.listFeedsHandler)
		api.GET("/feeds/search", productionReadGuard, appServer.searchFeedsHandler)
		api.POST("/feeds/search", productionReadGuard, appServer.searchFeedsHandler)
		api.POST("/feeds/detail", productionReadGuard, appServer.getFeedDetailHandler)
		api.POST("/user/profile", productionReadGuard, appServer.userProfileHandler)
		api.POST("/feeds/comment", productionGuard, appServer.postCommentHandler)
		api.POST("/feeds/comment/reply", productionGuard, appServer.replyCommentHandler)
		api.POST("/feeds/like", productionGuard, appServer.likeFeedHandler)
		api.POST("/feeds/favorite", productionGuard, appServer.favoriteFeedHandler)
		api.GET("/user/me", productionReadGuard, appServer.myProfileHandler)
	}

	return router
}
