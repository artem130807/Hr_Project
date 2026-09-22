package handlers

import (
	"net/http"

	dto "github.com/yourusername/message-service/internal/application/dtos/push"
	"github.com/yourusername/message-service/internal/application/usecases/contracts/service"
	"github.com/yourusername/message-service/internal/interfaces/http/request"
	"github.com/yourusername/message-service/internal/interfaces/http/response"
)

type PushHandler struct {
	svc service.PushSubscriptionService
}

func NewPushHandler(svc service.PushSubscriptionService) *PushHandler {
	return &PushHandler{svc: svc}
}

// VapidPublicKey — GET /api/push/vapid-public-key
func (h *PushHandler) VapidPublicKey(w http.ResponseWriter, r *http.Request) {
	if h == nil || h.svc == nil {
		response.JSON(w, http.StatusOK, dto.VapidPublicKeyDto{Enabled: false})
		return
	}
	key, err := h.svc.VapidPublicKey()
	if err != nil {
		response.Error(w, err)
		return
	}
	response.JSON(w, http.StatusOK, key)
}

// Subscribe — POST /api/push/subscriptions
func (h *PushHandler) Subscribe(w http.ResponseWriter, r *http.Request) {
	var req dto.SubscribeDto
	if err := request.DecodeJSON(r, &req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}
	if err := h.svc.Subscribe(r.Context(), &req); err != nil {
		response.Error(w, err)
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

// Unsubscribe — DELETE /api/push/subscriptions
func (h *PushHandler) Unsubscribe(w http.ResponseWriter, r *http.Request) {
	var req dto.UnsubscribeDto
	if err := request.DecodeJSON(r, &req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}
	if err := h.svc.Unsubscribe(r.Context(), &req); err != nil {
		response.Error(w, err)
		return
	}
	w.WriteHeader(http.StatusNoContent)
}
