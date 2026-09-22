package channel

import (
	"time"

	"github.com/google/uuid"
)

// ChannelDto — ответное представление канала.
type ChannelDto struct {
	ID          int           `json:"id"`
	Name        string        `json:"name"`
	EntityType  string        `json:"entity_type"`
	EntityID    int           `json:"entity_id"`
	UnreadCount int           `json:"unread_count"`
	CreatedAt   time.Time     `json:"created_at"`
	UsersIds    []uuid.UUID   `json:"user_ids,omitempty"`
	Messages    []MessageView `json:"messages,omitempty"`
}

// MessageView — краткое представление сообщения внутри канала.
type MessageView struct {
	ID        int       `json:"id"`
	Content   string    `json:"content"`
	IsRead    bool      `json:"is_read"`
	IsSend    bool      `json:"is_send"`
	CreatedAt time.Time `json:"created_at"`
}
