package middleware

import (
	"net/http"
	"strings"
)

// ServiceTokenAuth проверяет X-Service-Token для внутренних вызовов (erp-backend → message-service).
func ServiceTokenAuth(expectedToken string) func(http.Handler) http.Handler {
	expected := strings.TrimSpace(expectedToken)
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if expected == "" {
				http.Error(w, "Internal API disabled (INTERNAL_SERVICE_TOKEN not set)", http.StatusServiceUnavailable)
				return
			}
			got := strings.TrimSpace(r.Header.Get("X-Service-Token"))
			if got == "" || got != expected {
				http.Error(w, "Invalid service token", http.StatusForbidden)
				return
			}
			next.ServeHTTP(w, r)
		})
	}
}
