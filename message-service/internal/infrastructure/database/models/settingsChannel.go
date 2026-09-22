package models

import (
	"time"

	"github.com/google/uuid"
)

// SettingsChannel — GORM-модель настроек пользователя для канала.
type SettingsChannel struct {
	ID                int       `gorm:"primaryKey"`
	UserID            uuid.UUID `gorm:"column:user_id;not null;index:idx_settings_user_channel,unique"`
	ChannelID         int       `gorm:"column:channel_id;not null;index:idx_settings_user_channel,unique"`
	IsSendPushMessage bool      `gorm:"column:is_send_push_message;default:false"`
	CreatedAt         time.Time `gorm:"column:created_at;autoCreateTime"`
}

// TableName задаёт имя таблицы для настроек канала.
func (SettingsChannel) TableName() string { return "settings_channels" }
