package settings

import (
	"time"

	"github.com/google/uuid"
)

// SettingsDto — ответное представление настроек канала пользователя.
type SettingsDto struct {
	ID                int       `json:"id"`
	UserID            uuid.UUID `json:"user_id"`
	ChannelID         int       `json:"channel_id"`
	IsSendPushMessage bool      `json:"is_send_push_message"`
	CreatedAt         time.Time `json:"created_at"`
}
