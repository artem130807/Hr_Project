package middleware

import (
	"context"
	"net/http"
	"strings"

	"github.com/yourusername/message-service/internal/domain/contracts/auth"
)

type contextKey string

const (
	UserIDKey     contextKey = "user_id"
	UserRoleIDKey contextKey = "role_id"
)

func JWTAuth(authService auth.AuthService) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			authHeader := r.Header.Get("Authorization")
			if authHeader == "" {
				http.Error(w, "Missing authorization header", http.StatusUnauthorized)
				return
			}

			parts := strings.Split(authHeader, " ")
			if len(parts) != 2 || strings.ToLower(parts[0]) != "bearer" {
				http.Error(w, "Invalid authorization header format. Use: Bearer <token>", http.StatusUnauthorized)
				return
			}
			tokenString := parts[1]

			claims, err := authService.ExtractClaims(r.Context(), tokenString)
			if err != nil {
				http.Error(w, "Invalid or expired token", http.StatusUnauthorized)
				return
			}

			ctx := context.WithValue(r.Context(), UserIDKey, claims.UserID)
			ctx = context.WithValue(ctx, UserRoleIDKey, claims.RoleID)

			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}
