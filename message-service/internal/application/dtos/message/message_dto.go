package message

import (
	"time"

	"github.com/google/uuid"
)

// MessageDto — ответное представление сообщения.
type MessageDto struct {
	ID         int        `json:"id"`
	Content    string     `json:"content"`
	IsRead     bool       `json:"is_read"`
	IsSend     bool       `json:"is_send"`
	UserID     *uuid.UUID `json:"user_id,omitempty"`
	RoleID     *int       `json:"role_id,omitempty"`
	ChannelID  *int       `json:"channel_id,omitempty"`
	EntityType *string    `json:"entity_type,omitempty"`
	EntityID   *int       `json:"entity_id,omitempty"`
	CreatedAt  time.Time  `json:"created_at"`
}
