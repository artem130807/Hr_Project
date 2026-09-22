// domain/settings_channel.go
package domain

import (
	"errors"
	"time"

	"github.com/google/uuid"
)

// SettingsChannel — настройки пользователя для конкретного канала.
type SettingsChannel struct {
	ID                int
	UserID            uuid.UUID
	ChannelID         int
	IsSendPushMessage bool // отправлять ли push-уведомления
	CreatedAt         time.Time
}

// NewSettingsChannel создаёт настройки.
func NewSettingsChannel(userID uuid.UUID, channelID int, isSendPushMessage bool) (*SettingsChannel, error) {
	if userID == uuid.Nil || channelID <= 0 {
		return nil, errors.New("Айди пользователя и айди канала не могут быть отрицательными")
	}
	return &SettingsChannel{
		UserID:            userID,
		ChannelID:         channelID,
		IsSendPushMessage: isSendPushMessage,
		CreatedAt:         time.Now().UTC(),
	}, nil
}

// UpdatePushSettings обновляет флаг отправки push.
func (s *SettingsChannel) UpdatePushSettings(isSendPushMessage bool) {
	s.IsSendPushMessage = isSendPushMessage
}
