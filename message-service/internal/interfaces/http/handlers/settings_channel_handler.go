package handlers

import (
	"net/http"

	"github.com/yourusername/message-service/internal/application/dtos/settings"
	"github.com/yourusername/message-service/internal/application/usecases/contracts/service"
	"github.com/yourusername/message-service/internal/interfaces/http/request"
	"github.com/yourusername/message-service/internal/interfaces/http/response"
)

// SettingsChannelHandler — HTTP-обработчик для настроек каналов.
type SettingsChannelHandler struct {
	settingsService service.SettingsChannelService
}

// NewSettingsChannelHandler создаёт новый экземпляр хэндлера.
func NewSettingsChannelHandler(settingsService service.SettingsChannelService) *SettingsChannelHandler {
	return &SettingsChannelHandler{
		settingsService: settingsService,
	}
}

// AddSettings — POST /api/settings
func (h *SettingsChannelHandler) AddSettings(w http.ResponseWriter, r *http.Request) {
	var req settings.CreateSettingsDto
	if err := request.DecodeJSON(r, &req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	settingsDto, err := h.settingsService.AddSettings(r.Context(), &req)
	if err != nil {
		response.Error(w, err)
		return
	}

	response.JSON(w, http.StatusCreated, settingsDto)
}

// GetSettings — GET /api/settings/{id}
func (h *SettingsChannelHandler) GetSettings(w http.ResponseWriter, r *http.Request) {
	id, err := request.IDFromPath(r, "id")
	if err != nil {
		http.Error(w, "Invalid settings ID", http.StatusBadRequest)
		return
	}

	settingsDto, err := h.settingsService.GetSettings(r.Context(), id)
	if err != nil {
		response.Error(w, err)
		return
	}

	response.JSON(w, http.StatusOK, settingsDto)
}

// EditSettings — PUT /api/settings/{id}
func (h *SettingsChannelHandler) EditSettings(w http.ResponseWriter, r *http.Request) {
	id, err := request.IDFromPath(r, "id")
	if err != nil {
		http.Error(w, "Invalid settings ID", http.StatusBadRequest)
		return
	}

	var req settings.UpdateSettingsDto
	if err := request.DecodeJSON(r, &req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	settingsDto, err := h.settingsService.EditSettings(r.Context(), id, &req)
	if err != nil {
		response.Error(w, err)
		return
	}

	response.JSON(w, http.StatusOK, settingsDto)
}

// RemoveSettings — DELETE /api/settings/{id}
func (h *SettingsChannelHandler) RemoveSettings(w http.ResponseWriter, r *http.Request) {
	id, err := request.IDFromPath(r, "id")
	if err != nil {
		http.Error(w, "Invalid settings ID", http.StatusBadRequest)
		return
	}

	if err := h.settingsService.RemoveSettings(r.Context(), id); err != nil {
		response.Error(w, err)
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// GetAllByUser — GET /api/settings/user
func (h *SettingsChannelHandler) GetAllByUser(w http.ResponseWriter, r *http.Request) {
	settingsList, err := h.settingsService.GetAllByUser(r.Context())
	if err != nil {
		response.Error(w, err)
		return
	}

	response.JSON(w, http.StatusOK, settingsList)
}
