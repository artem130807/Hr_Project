package handlers

import (
	"net/http"
	"strings"

	"github.com/yourusername/message-service/internal/domain/contracts/auth"
	wsinfra "github.com/yourusername/message-service/internal/infrastructure/websocket"
)

// WSHandler обслуживает WebSocket-подключения уведомлений.
type WSHandler struct {
	hub         *wsinfra.Hub
	authService auth.AuthService
}

// NewWSHandler создаёт хендлер.
func NewWSHandler(hub *wsinfra.Hub, authService auth.AuthService) *WSHandler {
	return &WSHandler{hub: hub, authService: authService}
}

// Connect апгрейдит соединение. JWT: Authorization Bearer или ?token=.
func (h *WSHandler) Connect(w http.ResponseWriter, r *http.Request) {
	token := extractWSToken(r)
	if token == "" {
		http.Error(w, "Missing token", http.StatusUnauthorized)
		return
	}
	claims, err := h.authService.ExtractClaims(r.Context(), token)
	if err != nil {
		http.Error(w, "Invalid or expired token", http.StatusUnauthorized)
		return
	}
	h.hub.ServeWS(w, r, claims.UserID, claims.RoleID)
}

func extractWSToken(r *http.Request) string {
	if authHeader := r.Header.Get("Authorization"); authHeader != "" {
		parts := strings.SplitN(authHeader, " ", 2)
		if len(parts) == 2 && strings.EqualFold(parts[0], "Bearer") {
			return strings.TrimSpace(parts[1])
		}
	}
	return strings.TrimSpace(r.URL.Query().Get("token"))
}
