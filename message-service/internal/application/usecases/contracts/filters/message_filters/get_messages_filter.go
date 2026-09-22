package messagefilters

import (
	"time"

	"github.com/google/uuid"
)

type GetMessagesFilter struct {
	UserId    *uuid.UUID `json:"user_id,omitempty"`
	RoleId    *int       `json:"role_id,omitempty"`
	ChannelId *int       `json:"channel_id,omitempty"`
	IsRead    *bool      `json:"is_read,omitempty"`
	CreatedAt *time.Time `json:"created_at,omitempty"`
}
