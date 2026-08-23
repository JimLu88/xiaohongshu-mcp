package main

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestConfiguredPortDefaultsAndEnvironmentOverride(t *testing.T) {
	t.Setenv(portEnvironmentVariable, "")
	assert.Equal(t, "127.0.0.1:18060", configuredPort())
	t.Setenv(portEnvironmentVariable, "19060")
	assert.Equal(t, "127.0.0.1:19060", configuredPort())
	t.Setenv(portEnvironmentVariable, ":19061")
	assert.Equal(t, "127.0.0.1:19061", configuredPort())
	t.Setenv(portEnvironmentVariable, "127.0.0.1:19062")
	assert.Equal(t, "127.0.0.1:18060", configuredPort())
	t.Setenv(portEnvironmentVariable, "70000")
	assert.Equal(t, "127.0.0.1:18060", configuredPort())
}

func TestHealthzReturnsStableIdentityWithoutCredentials(t *testing.T) {
	t.Setenv(productionEnabledVariable, "")
	router := gin.New()
	router.GET("/healthz", tachikomaHealthzHandler)
	recorder := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	router.ServeHTTP(recorder, req)
	require.Equal(t, http.StatusOK, recorder.Code)
	var identity tachikomaIdentity
	require.NoError(t, json.Unmarshal(recorder.Body.Bytes(), &identity))
	assert.Equal(t, tachikomaServiceName, identity.Service)
	assert.Equal(t, tachikomaContractVersion, identity.ContractVersion)
	assert.True(t, identity.Ready)
	assert.True(t, identity.DependenciesReady)
	assert.Equal(t, "production_execution_disabled", identity.Mode)
}

func TestContractIsReadOnlyAndCredentialFree(t *testing.T) {
	router := gin.New()
	router.GET("/tachikoma/v1/contract", tachikomaContractHandler)
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, httptest.NewRequest(http.MethodGet, "/tachikoma/v1/contract", nil))
	require.Equal(t, http.StatusOK, recorder.Code)
	assert.Contains(t, recorder.Body.String(), `"service":"xiaohongshu-mcp"`)
	assert.Contains(t, recorder.Body.String(), `"actions"`)
	assert.Contains(t, recorder.Body.String(), `"publish-video"`)
	assert.Contains(t, recorder.Body.String(), `"comment-reply"`)
	assert.Contains(t, recorder.Body.String(), `"reset-session"`)
}

func TestProductionRoutesAreGuardedBeforeBusinessHandlers(t *testing.T) {
	t.Setenv(productionEnabledVariable, "")
	router := setupRoutes(NewAppServer(NewXiaohongshuService()))
	paths := []struct {
		method string
		path   string
	}{
		{http.MethodDelete, "/api/v1/login/cookies"},
		{http.MethodPost, "/api/v1/publish"},
		{http.MethodPost, "/api/v1/publish_video"},
		{http.MethodPost, "/api/v1/feeds/comment"},
		{http.MethodPost, "/api/v1/feeds/comment/reply"},
		{http.MethodPost, "/api/v1/feeds/like"},
		{http.MethodPost, "/api/v1/feeds/favorite"},
	}
	for _, item := range paths {
		t.Run(item.method+" "+item.path, func(t *testing.T) {
			recorder := httptest.NewRecorder()
			router.ServeHTTP(recorder, httptest.NewRequest(item.method, item.path, nil))
			assert.Equal(t, http.StatusForbidden, recorder.Code)
			assert.Contains(t, recorder.Body.String(), "PRODUCTION_EXECUTION_DISABLED")
		})
	}
}

func TestProductionReadRoutesAreGuardedBeforeBusinessHandlers(t *testing.T) {
	t.Setenv(productionReadVariable, "")
	router := setupRoutes(NewAppServer(NewXiaohongshuService()))
	paths := []struct {
		method string
		path   string
	}{
		{http.MethodGet, "/api/v1/feeds/list"},
		{http.MethodGet, "/api/v1/feeds/search?keyword=probe"},
		{http.MethodPost, "/api/v1/feeds/detail"},
		{http.MethodPost, "/api/v1/user/profile"},
		{http.MethodGet, "/api/v1/user/me"},
	}
	for _, item := range paths {
		t.Run(item.method+" "+item.path, func(t *testing.T) {
			recorder := httptest.NewRecorder()
			router.ServeHTTP(recorder, httptest.NewRequest(item.method, item.path, nil))
			assert.Equal(t, http.StatusForbidden, recorder.Code)
			assert.Contains(t, recorder.Body.String(), "PRODUCTION_READ_DISABLED")
		})
	}
}

func TestProductionGuardFailsClosedWhenDisabled(t *testing.T) {
	t.Setenv(productionEnabledVariable, "not-true")
	router := guardedTestRouter(t, time.Second)
	recorder := performGuardedRequest(router, "disabled", true)
	assert.Equal(t, http.StatusForbidden, recorder.Code)
	assert.Contains(t, recorder.Body.String(), "PRODUCTION_EXECUTION_DISABLED")
}

func TestProductionGuardRejectsIdentityMismatchAndMissingApproval(t *testing.T) {
	t.Setenv(productionEnabledVariable, "true")
	router := guardedTestRouter(t, time.Second)

	req := httptest.NewRequest(http.MethodPost, "/write", nil)
	req.Header.Set(expectedServiceHeader, "wrong-service")
	req.Header.Set(taskIDHeader, "task-1")
	req.Header.Set(approvalIDHeader, "approval-1")
	req.Header.Set(idempotencyKeyHeader, "mismatch")
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, req)
	assert.Equal(t, http.StatusConflict, recorder.Code)
	assert.Contains(t, recorder.Body.String(), "SERVICE_IDENTITY_MISMATCH")

	recorder = performGuardedRequest(router, "missing-approval", false)
	assert.Equal(t, http.StatusForbidden, recorder.Code)
	assert.Contains(t, recorder.Body.String(), "TASK_APPROVAL_REQUIRED")
}

func TestProductionGuardEnforcesIdempotency(t *testing.T) {
	t.Setenv(productionEnabledVariable, "true")
	router := guardedTestRouter(t, time.Second)
	first := performGuardedRequest(router, "same-key", true)
	require.Equal(t, http.StatusNoContent, first.Code)
	second := performGuardedRequest(router, "same-key", true)
	assert.Equal(t, http.StatusConflict, second.Code)
	assert.Contains(t, second.Body.String(), "IDEMPOTENCY_CONFLICT")
}

func TestProductionGuardKeepsIdempotencyKeyAfterHandlerFailure(t *testing.T) {
	t.Setenv(productionEnabledVariable, "true")
	registry := newIdempotencyRegistry()
	router := gin.New()
	router.POST("/write", tachikomaProductionGuard(registry, time.Second), func(c *gin.Context) {
		c.JSON(http.StatusBadGateway, gin.H{"code": "RESULT_UNKNOWN"})
	})

	firstRecorder := httptest.NewRecorder()
	router.ServeHTTP(firstRecorder, approvedRequest("unknown-result"))
	require.Equal(t, http.StatusBadGateway, firstRecorder.Code)

	secondRecorder := httptest.NewRecorder()
	router.ServeHTTP(secondRecorder, approvedRequest("unknown-result"))
	assert.Equal(t, http.StatusConflict, secondRecorder.Code)
	assert.Contains(t, secondRecorder.Body.String(), "IDEMPOTENCY_CONFLICT")
}

func TestProductionGuardAppliesTimeout(t *testing.T) {
	t.Setenv(productionEnabledVariable, "true")
	registry := newIdempotencyRegistry()
	router := gin.New()
	router.POST("/write", tachikomaProductionGuard(registry, 20*time.Millisecond), func(c *gin.Context) {
		<-c.Request.Context().Done()
		c.JSON(http.StatusGatewayTimeout, gin.H{"code": "UPSTREAM_TIMEOUT"})
	})
	req := approvedRequest("timeout-key")
	req.Header.Set(timeoutMillisecondsHeader, "1")
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, req)
	assert.Equal(t, http.StatusGatewayTimeout, recorder.Code)
	assert.Contains(t, recorder.Body.String(), "UPSTREAM_TIMEOUT")
}

func TestProductionGuardRejectsMalformedTimeoutAndMissingIdempotency(t *testing.T) {
	t.Setenv(productionEnabledVariable, "true")
	router := guardedTestRouter(t, time.Second)
	req := approvedRequest("bad-timeout")
	req.Header.Set(timeoutMillisecondsHeader, "never")
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, req)
	assert.Equal(t, http.StatusBadRequest, recorder.Code)
	assert.Contains(t, recorder.Body.String(), "INVALID_TIMEOUT")

	req = approvedRequest("")
	recorder = httptest.NewRecorder()
	router.ServeHTTP(recorder, req)
	assert.Equal(t, http.StatusBadRequest, recorder.Code)
	assert.Contains(t, recorder.Body.String(), "IDEMPOTENCY_KEY_REQUIRED")
}

func TestMCPProductionGuardBlocksBeforeToolHandler(t *testing.T) {
	t.Setenv(productionEnabledVariable, "")
	called := false
	handler := withMCPProductionGuard(newIdempotencyRegistry(), time.Second,
		func(context.Context, *mcp.CallToolRequest, any) (*mcp.CallToolResult, any, error) {
			called = true
			return &mcp.CallToolResult{}, nil, nil
		})
	result, _, err := handler(context.Background(), &mcp.CallToolRequest{}, nil)
	require.NoError(t, err)
	assert.False(t, called)
	assert.True(t, result.IsError)
	assert.Contains(t, result.Content[0].(*mcp.TextContent).Text, "PRODUCTION_EXECUTION_DISABLED")
}

func TestMCPProductionGuardRequiresFreshHeadersAndIdempotency(t *testing.T) {
	t.Setenv(productionEnabledVariable, "true")
	registry := newIdempotencyRegistry()
	called := 0
	handler := withMCPProductionGuard(registry, time.Second,
		func(context.Context, *mcp.CallToolRequest, any) (*mcp.CallToolResult, any, error) {
			called++
			return &mcp.CallToolResult{}, nil, nil
		})

	req := &mcp.CallToolRequest{Extra: &mcp.RequestExtra{Header: make(http.Header)}}
	req.Extra.Header.Set(expectedServiceHeader, tachikomaServiceName)
	req.Extra.Header.Set(taskIDHeader, "task-1")
	req.Extra.Header.Set(approvalIDHeader, "approval-1")
	req.Extra.Header.Set(idempotencyKeyHeader, "mcp-key")
	first, _, err := handler(context.Background(), req, nil)
	require.NoError(t, err)
	assert.False(t, first.IsError)
	assert.Equal(t, 1, called)

	second, _, err := handler(context.Background(), req, nil)
	require.NoError(t, err)
	assert.True(t, second.IsError)
	assert.Equal(t, 1, called)
	assert.Contains(t, second.Content[0].(*mcp.TextContent).Text, "IDEMPOTENCY_CONFLICT")
}

func TestMCPProductionReadGuardBlocksBeforeToolHandler(t *testing.T) {
	t.Setenv(productionReadVariable, "")
	called := false
	handler := withMCPProductionReadGuard(time.Second,
		func(context.Context, *mcp.CallToolRequest, any) (*mcp.CallToolResult, any, error) {
			called = true
			return &mcp.CallToolResult{}, nil, nil
		})
	result, _, err := handler(context.Background(), &mcp.CallToolRequest{}, nil)
	require.NoError(t, err)
	assert.False(t, called)
	assert.True(t, result.IsError)
	assert.Contains(t, result.Content[0].(*mcp.TextContent).Text, "PRODUCTION_READ_DISABLED")
}

func guardedTestRouter(t *testing.T, timeout time.Duration) *gin.Engine {
	t.Helper()
	gin.SetMode(gin.TestMode)
	router := gin.New()
	router.POST("/write", tachikomaProductionGuard(newIdempotencyRegistry(), timeout), func(c *gin.Context) {
		c.Status(http.StatusNoContent)
	})
	return router
}

func performGuardedRequest(router *gin.Engine, key string, includeApproval bool) *httptest.ResponseRecorder {
	req := approvedRequest(key)
	if !includeApproval {
		req.Header.Del(approvalIDHeader)
	}
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, req)
	return recorder
}

func approvedRequest(key string) *http.Request {
	req := httptest.NewRequest(http.MethodPost, "/write", nil)
	req.Header.Set(expectedServiceHeader, tachikomaServiceName)
	req.Header.Set(taskIDHeader, "task-1")
	req.Header.Set(approvalIDHeader, "approval-1")
	if key != "" {
		req.Header.Set(idempotencyKeyHeader, key)
	}
	return req
}
