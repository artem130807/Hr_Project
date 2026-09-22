// internal/interfaces/http/handlers/channel_handler.go
package handlers

import (
	"net/http"
	"strconv"

	"github.com/yourusername/message-service/internal/application/dtos/channel"
	"github.com/yourusername/message-service/internal/application/usecases/contracts/service"
	"github.com/yourusername/message-service/internal/interfaces/http/request"
	"github.com/yourusername/message-service/internal/interfaces/http/response"
)

// ChannelHandler — HTTP-обработчик для каналов.
type ChannelHandler struct {
	channelService service.ChannelService
}

// NewChannelHandler создаёт новый экземпляр хэндлера.
func NewChannelHandler(channelService service.ChannelService) *ChannelHandler {
	return &ChannelHandler{
		channelService: channelService,
	}
}

// AddChannel — POST /api/channels
func (h *ChannelHandler) AddChannel(w http.ResponseWriter, r *http.Request) {
	var req channel.CreateChannelDto
	if err := request.DecodeJSON(r, &req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	ch, err := h.channelService.AddChannel(r.Context(), &req)
	if err != nil {
		response.Error(w, err)
		return
	}

	response.JSON(w, http.StatusCreated, ch)
}

// GetChannel — GET /api/channels/{id}
func (h *ChannelHandler) GetChannel(w http.ResponseWriter, r *http.Request) {
	id, err := request.IDFromPath(r, "id")
	if err != nil {
		http.Error(w, "Invalid channel ID", http.StatusBadRequest)
		return
	}

	ch, err := h.channelService.GetChannel(r.Context(), id)
	if err != nil {
		response.Error(w, err)
		return
	}

	response.JSON(w, http.StatusOK, ch)
}

// EditChannel — PUT /api/channels/{id}
func (h *ChannelHandler) EditChannel(w http.ResponseWriter, r *http.Request) {
	id, err := request.IDFromPath(r, "id")
	if err != nil {
		http.Error(w, "Invalid channel ID", http.StatusBadRequest)
		return
	}

	var req channel.UpdateChannelDto
	if err := request.DecodeJSON(r, &req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	ch, err := h.channelService.EditChannel(r.Context(), id, &req)
	if err != nil {
		response.Error(w, err)
		return
	}

	response.JSON(w, http.StatusOK, ch)
}

// RemoveChannel — DELETE /api/channels/{id}
func (h *ChannelHandler) RemoveChannel(w http.ResponseWriter, r *http.Request) {
	id, err := request.IDFromPath(r, "id")
	if err != nil {
		http.Error(w, "Invalid channel ID", http.StatusBadRequest)
		return
	}

	if err := h.channelService.RemoveChannel(r.Context(), id); err != nil {
		response.Error(w, err)
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// GetChannelsByPush — GET /api/channels/push
// Список каналов по участию (user_ids). Query isPush — опциональный фильтр mute.
func (h *ChannelHandler) GetChannelsByPush(w http.ResponseWriter, r *http.Request) {
	var isPush *bool
	if val := r.URL.Query().Get("isPush"); val != "" {
		b, err := strconv.ParseBool(val)
		if err != nil {
			http.Error(w, "Invalid isPush parameter, must be true or false", http.StatusBadRequest)
			return
		}
		isPush = &b
	}

	channels, err := h.channelService.GetChannelsByPush(r.Context(), isPush)
	if err != nil {
		response.Error(w, err)
		return
	}

	response.JSON(w, http.StatusOK, channels)
}
