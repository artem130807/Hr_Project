package models

import "time"

// Channel — GORM-модель канала.
type Channel struct {
	ID         int       `gorm:"primaryKey"`
	Name       string    `gorm:"column:name"`
	EntityType string    `gorm:"column:entity_type;not null;uniqueIndex:idx_channel_entity"`
	EntityID   int       `gorm:"column:entity_id;not null;uniqueIndex:idx_channel_entity"`
	CreatedAt  time.Time `gorm:"column:created_at;autoCreateTime"`
	UsersIds   UUIDs     `gorm:"type:uuid[];column:user_ids"`
	Messages   []Message `gorm:"foreignKey:ChannelID;references:ID"`
}

// TableName задаёт имя таблицы для каналов.
func (Channel) TableName() string { return "channels" }
