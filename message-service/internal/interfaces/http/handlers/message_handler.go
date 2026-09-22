package handlers

import (
	"net/http"

	"github.com/yourusername/message-service/internal/application/dtos/message"
	"github.com/yourusername/message-service/internal/application/usecases/contracts/service"
	"github.com/yourusername/message-service/internal/interfaces/http/request"
	"github.com/yourusername/message-service/internal/interfaces/http/response"
)

type MessageHandler struct {
	messageService service.MessageService
}

func NewMessageHandler(messageService service.MessageService) *MessageHandler {
	return &MessageHandler{
		messageService: messageService,
	}
}

func (h *MessageHandler) SendMessage(w http.ResponseWriter, r *http.Request) {
	var req message.CreateMessageDto
	if err := request.DecodeJSON(r, &req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	msg, err := h.messageService.AddMessage(r.Context(), &req)
	if err != nil {
		response.Error(w, err)
		return
	}

	response.JSON(w, http.StatusCreated, msg)
}

func (h *MessageHandler) GetMessage(w http.ResponseWriter, r *http.Request) {
	messageID, err := request.IDFromPath(r, "id")
	if err != nil {
		http.Error(w, "Invalid message ID", http.StatusBadRequest)
		return
	}

	msg, err := h.messageService.GetMessage(r.Context(), messageID)
	if err != nil {
		response.Error(w, err)
		return
	}

	response.JSON(w, http.StatusOK, msg)
}

func (h *MessageHandler) GetMessagesByFilter(w http.ResponseWriter, r *http.Request) {
	req, err := request.MessagesFilterFromQuery(r)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	msg, err := h.messageService.GetMessagesByFilter(r.Context(), req)
	if err != nil {
		response.Error(w, err)
		return
	}
	response.JSON(w, http.StatusOK, msg)
}

// GetUnreadCount — GET /api/messages/unread-count
func (h *MessageHandler) GetUnreadCount(w http.ResponseWriter, r *http.Request) {
	count, err := h.messageService.FindNotReadCountByUser(r.Context())
	if err != nil {
		response.Error(w, err)
		return
	}
	response.JSON(w, http.StatusOK, map[string]int{"count": count})
}

// MarkMessageAsRead — PUT /api/messages/{id}
// Помечает одно сообщение прочитанным (is_read=true). Тело запроса не обязательно.
func (h *MessageHandler) MarkMessageAsRead(w http.ResponseWriter, r *http.Request) {
	messageID, err := request.IDFromPath(r, "id")
	if err != nil {
		http.Error(w, "Invalid message ID", http.StatusBadRequest)
		return
	}
	msg, err := h.messageService.MarkMessageAsRead(r.Context(), messageID)
	if err != nil {
		response.Error(w, err)
		return
	}
	response.JSON(w, http.StatusOK, msg)
}

// MarkMessagesAsRead — POST /api/messages/read?user_id|role_id|channel_id=
func (h *MessageHandler) MarkMessagesAsRead(w http.ResponseWriter, r *http.Request) {
	req, err := request.MessagesFilterFromQuery(r)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	marked, err := h.messageService.MarkMessagesAsRead(r.Context(), req)
	if err != nil {
		response.Error(w, err)
		return
	}
	response.JSON(w, http.StatusOK, map[string]int{"marked": marked})
}
