package message

import "github.com/google/uuid"

// CreateMessageDto — входной DTO для создания сообщения.
// Адресатом является ровно один из: ChannelID, UserID, RoleID
// (соответствует фабрикам SendMessageToChannel/User/Role в домене).
// EntityType/EntityID — опциональная deep-link ссылка (trip/executor/…).
type CreateMessageDto struct {
	Content    string     `json:"content" binding:"required"`
	ChannelID  *int       `json:"channel_id,omitempty"`
	UserID     *uuid.UUID `json:"user_id,omitempty"`
	RoleID     *int       `json:"role_id,omitempty"`
	EntityType *string    `json:"entity_type,omitempty"`
	EntityID   *int       `json:"entity_id,omitempty"`
}
