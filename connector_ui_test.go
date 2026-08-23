package main

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestLoginPageIsHumanReadableAndDoesNotPersistQR(t *testing.T) {
	gin.SetMode(gin.TestMode)
	router := gin.New()
	router.GET("/", (&AppServer{}).loginPageHandler)

	recorder := httptest.NewRecorder()
	request := httptest.NewRequest(http.MethodGet, "/", nil)
	router.ServeHTTP(recorder, request)

	if recorder.Code != http.StatusOK {
		t.Fatalf("GET / status = %d, want %d", recorder.Code, http.StatusOK)
	}
	if got := recorder.Header().Get("Content-Type"); !strings.HasPrefix(got, "text/html") {
		t.Fatalf("Content-Type = %q, want text/html", got)
	}
	if got := recorder.Header().Get("Cache-Control"); !strings.Contains(got, "no-store") {
		t.Fatalf("Cache-Control = %q, want no-store", got)
	}
	if got := recorder.Header().Get("Content-Security-Policy"); !strings.Contains(got, "connect-src 'self'") || !strings.Contains(got, "img-src 'self' data:") {
		t.Fatalf("unexpected Content-Security-Policy: %q", got)
	}

	body := recorder.Body.String()
	for _, expected := range []string{
		"AI SEARCH OS · 独立连接器",
		"/api/v1/login/qrcode",
		"二维码仅在当前页面内存中展示，不写入磁盘",
		"不要刷新页面",
	} {
		if !strings.Contains(body, expected) {
			t.Fatalf("login page missing %q", expected)
		}
	}
	for _, forbidden := range []string{"login_qrcode.png", "document.cookie", "localStorage", "sessionStorage", "setInterval", "/api/v1/login/status"} {
		if strings.Contains(body, forbidden) {
			t.Fatalf("login page contains forbidden persistence marker %q", forbidden)
		}
	}
}
