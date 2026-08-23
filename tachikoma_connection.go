package main

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
)

const (
	tachikomaServiceName      = "xiaohongshu-mcp"
	tachikomaContractVersion  = "v1"
	defaultHTTPPort           = "18060"
	portEnvironmentVariable   = "XHS_MCP_PORT"
	productionReadVariable    = "XHS_MCP_PRODUCTION_READ_ENABLED"
	productionEnabledVariable = "XHS_MCP_PRODUCTION_EXECUTION_ENABLED"
	expectedServiceHeader     = "X-Tachikoma-Expected-Service"
	taskIDHeader              = "X-Tachikoma-Task-ID"
	approvalIDHeader          = "X-Tachikoma-Approval-ID"
	idempotencyKeyHeader      = "Idempotency-Key"
	timeoutMillisecondsHeader = "X-Tachikoma-Timeout-Ms"
	defaultActionTimeout      = 30 * time.Second
)

type tachikomaIdentity struct {
	Service                    string `json:"service"`
	Version                    string `json:"version"`
	ContractVersion            string `json:"contract_version"`
	Ready                      bool   `json:"ready"`
	DependenciesReady          bool   `json:"dependencies_ready"`
	Mode                       string `json:"mode"`
	ProductionReadEnabled      bool   `json:"production_read_enabled"`
	ProductionExecutionEnabled bool   `json:"production_execution_enabled"`
}

type tachikomaBusinessAction struct {
	ChainID     string `json:"chain_id"`
	Step        string `json:"step"`
	Method      string `json:"method"`
	Path        string `json:"path"`
	Risk        string `json:"risk"`
	Approval    string `json:"approval"`
	Idempotency string `json:"idempotency"`
	Status      string `json:"status"`
	Input       any    `json:"input_schema"`
	Output      any    `json:"output_schema"`
}

type idempotencyRegistry struct {
	mu   sync.Mutex
	keys map[string]struct{}
}

func newIdempotencyRegistry() *idempotencyRegistry {
	return &idempotencyRegistry{keys: make(map[string]struct{})}
}

func (r *idempotencyRegistry) reserve(key string) bool {
	r.mu.Lock()
	defer r.mu.Unlock()
	if _, exists := r.keys[key]; exists {
		return false
	}
	r.keys[key] = struct{}{}
	return true
}

func configuredPort() string {
	value := strings.TrimSpace(os.Getenv(portEnvironmentVariable))
	if value == "" {
		value = defaultHTTPPort
	}
	value = strings.TrimPrefix(value, ":")
	port, err := strconv.Atoi(value)
	if err != nil || port < 1 || port > 65535 {
		value = defaultHTTPPort
	}
	return "127.0.0.1:" + value
}

func productionExecutionEnabled() bool {
	return strings.EqualFold(strings.TrimSpace(os.Getenv(productionEnabledVariable)), "true")
}

func productionReadEnabled() bool {
	return strings.EqualFold(strings.TrimSpace(os.Getenv(productionReadVariable)), "true")
}

func tachikomaMode() string {
	if productionExecutionEnabled() {
		return "approval_gated"
	}
	return "production_execution_disabled"
}

func tachikomaHealthzHandler(c *gin.Context) {
	c.JSON(http.StatusOK, tachikomaIdentity{
		Service:                    tachikomaServiceName,
		Version:                    version,
		ContractVersion:            tachikomaContractVersion,
		Ready:                      true,
		DependenciesReady:          true,
		Mode:                       tachikomaMode(),
		ProductionReadEnabled:      productionReadEnabled(),
		ProductionExecutionEnabled: productionExecutionEnabled(),
	})
}

func tachikomaContractHandler(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"service":                      tachikomaServiceName,
		"contract_version":             tachikomaContractVersion,
		"default_port":                 18060,
		"health_path":                  "/healthz",
		"production_read_enabled":      productionReadEnabled(),
		"production_execution_enabled": productionExecutionEnabled(),
		"actions":                      tachikomaBusinessActions(),
	})
}

func tachikomaBusinessActions() []tachikomaBusinessAction {
	searchInput := gin.H{"keyword": "string|required", "filters": "object|optional"}
	feedInput := gin.H{"feed_id": "string|required", "xsec_token": "string|required", "load_all_comments": "boolean|optional"}
	profileInput := gin.H{"user_id": "string|required", "xsec_token": "string|required"}
	feedActionInput := gin.H{"feed_id": "string|required", "xsec_token": "string|required"}
	standardOutput := gin.H{"success": "boolean", "data": "object", "message": "string"}
	return []tachikomaBusinessAction{
		{ChainID: "product-content-chain", Step: "reference-search", Method: http.MethodGet, Path: "/api/v1/feeds/search", Risk: "production_read", Approval: "task_specific_collection", Idempotency: "not_applicable", Status: "live_read_pass_2026_08_24", Input: searchInput, Output: standardOutput},
		{ChainID: "product-content-chain", Step: "reference-detail", Method: http.MethodPost, Path: "/api/v1/feeds/detail", Risk: "production_read", Approval: "task_specific_collection", Idempotency: "request_hash_recommended", Status: "live_read_pass_2026_08_24", Input: feedInput, Output: standardOutput},
		{ChainID: "product-content-chain", Step: "author-profile", Method: http.MethodPost, Path: "/api/v1/user/profile", Risk: "production_read", Approval: "task_specific_collection", Idempotency: "request_hash_recommended", Status: "endpoint_discovered_live_test_not_run", Input: profileInput, Output: standardOutput},
		{ChainID: "product-content-chain", Step: "publish", Method: http.MethodPost, Path: "/api/v1/publish", Risk: "external_side_effect", Approval: "fresh_task_specific_approval", Idempotency: "required_header", Status: "guarded_not_live_tested", Input: gin.H{"title": "string|required", "content": "string|required", "images": "array|required"}, Output: standardOutput},
		{ChainID: "product-content-chain", Step: "publish-video", Method: http.MethodPost, Path: "/api/v1/publish_video", Risk: "external_side_effect", Approval: "fresh_task_specific_approval", Idempotency: "required_header", Status: "guarded_not_live_tested", Input: gin.H{"title": "string|required", "content": "string|required", "video": "string|required"}, Output: standardOutput},
		{ChainID: "customer-conversation-chain", Step: "comment", Method: http.MethodPost, Path: "/api/v1/feeds/comment", Risk: "external_side_effect", Approval: "fresh_task_specific_approval", Idempotency: "required_header", Status: "guarded_not_live_tested", Input: gin.H{"feed_id": "string|required", "xsec_token": "string|required", "content": "string|required"}, Output: standardOutput},
		{ChainID: "customer-conversation-chain", Step: "comment-reply", Method: http.MethodPost, Path: "/api/v1/feeds/comment/reply", Risk: "external_side_effect", Approval: "fresh_task_specific_approval", Idempotency: "required_header", Status: "guarded_not_live_tested", Input: gin.H{"feed_id": "string|required", "xsec_token": "string|required", "comment_id_or_user_id": "string|required", "content": "string|required"}, Output: standardOutput},
		{ChainID: "customer-conversation-chain", Step: "like", Method: http.MethodPost, Path: "/api/v1/feeds/like", Risk: "external_side_effect", Approval: "fresh_task_specific_approval", Idempotency: "required_header", Status: "guarded_not_live_tested", Input: feedActionInput, Output: standardOutput},
		{ChainID: "customer-conversation-chain", Step: "favorite", Method: http.MethodPost, Path: "/api/v1/feeds/favorite", Risk: "external_side_effect", Approval: "fresh_task_specific_approval", Idempotency: "required_header", Status: "guarded_not_live_tested", Input: feedActionInput, Output: standardOutput},
		{ChainID: "software-delivery-chain", Step: "reset-session", Method: http.MethodDelete, Path: "/api/v1/login/cookies", Risk: "destructive_local_state", Approval: "fresh_task_specific_approval", Idempotency: "required_header", Status: "guarded_not_live_tested", Input: gin.H{}, Output: standardOutput},
	}
}

func tachikomaProductionGuard(registry *idempotencyRegistry, maxTimeout time.Duration) gin.HandlerFunc {
	return func(c *gin.Context) {
		if !productionExecutionEnabled() {
			abortConnectionRequest(c, http.StatusForbidden, "PRODUCTION_EXECUTION_DISABLED", "production execution is disabled")
			return
		}
		if c.GetHeader(expectedServiceHeader) != tachikomaServiceName {
			abortConnectionRequest(c, http.StatusConflict, "SERVICE_IDENTITY_MISMATCH", "expected service identity does not match")
			return
		}
		if strings.TrimSpace(c.GetHeader(taskIDHeader)) == "" || strings.TrimSpace(c.GetHeader(approvalIDHeader)) == "" {
			abortConnectionRequest(c, http.StatusForbidden, "TASK_APPROVAL_REQUIRED", "fresh task-specific approval is required")
			return
		}
		key := strings.TrimSpace(c.GetHeader(idempotencyKeyHeader))
		if key == "" {
			abortConnectionRequest(c, http.StatusBadRequest, "IDEMPOTENCY_KEY_REQUIRED", "Idempotency-Key is required")
			return
		}

		timeout, err := requestTimeout(c.GetHeader(timeoutMillisecondsHeader), maxTimeout)
		if err != nil {
			abortConnectionRequest(c, http.StatusBadRequest, "INVALID_TIMEOUT", err.Error())
			return
		}
		if !registry.reserve(key) {
			abortConnectionRequest(c, http.StatusConflict, "IDEMPOTENCY_CONFLICT", "idempotency key has already been used")
			return
		}

		ctx, cancel := context.WithTimeout(c.Request.Context(), timeout)
		defer cancel()
		c.Request = c.Request.WithContext(ctx)
		c.Next()
	}
}

func tachikomaProductionReadGuard(maxTimeout time.Duration) gin.HandlerFunc {
	return func(c *gin.Context) {
		if !productionReadEnabled() {
			abortConnectionRequest(c, http.StatusForbidden, "PRODUCTION_READ_DISABLED", "production platform reading is disabled")
			return
		}
		if c.GetHeader(expectedServiceHeader) != tachikomaServiceName {
			abortConnectionRequest(c, http.StatusConflict, "SERVICE_IDENTITY_MISMATCH", "expected service identity does not match")
			return
		}
		if strings.TrimSpace(c.GetHeader(taskIDHeader)) == "" || strings.TrimSpace(c.GetHeader(approvalIDHeader)) == "" {
			abortConnectionRequest(c, http.StatusForbidden, "TASK_APPROVAL_REQUIRED", "fresh task-specific collection approval is required")
			return
		}
		timeout, err := requestTimeout(c.GetHeader(timeoutMillisecondsHeader), maxTimeout)
		if err != nil {
			abortConnectionRequest(c, http.StatusBadRequest, "INVALID_TIMEOUT", err.Error())
			return
		}
		ctx, cancel := context.WithTimeout(c.Request.Context(), timeout)
		defer cancel()
		c.Request = c.Request.WithContext(ctx)
		c.Next()
	}
}

func requestTimeout(raw string, maximum time.Duration) (time.Duration, error) {
	if maximum <= 0 {
		return 0, fmt.Errorf("maximum timeout must be positive")
	}
	if strings.TrimSpace(raw) == "" {
		return maximum, nil
	}
	milliseconds, err := strconv.Atoi(strings.TrimSpace(raw))
	if err != nil || milliseconds <= 0 {
		return 0, fmt.Errorf("timeout must be a positive integer in milliseconds")
	}
	requested := time.Duration(milliseconds) * time.Millisecond
	if requested > maximum {
		return 0, fmt.Errorf("timeout exceeds maximum of %d milliseconds", maximum.Milliseconds())
	}
	return requested, nil
}

func abortConnectionRequest(c *gin.Context, status int, code, message string) {
	c.AbortWithStatusJSON(status, gin.H{
		"error":   message,
		"code":    code,
		"service": tachikomaServiceName,
	})
}
