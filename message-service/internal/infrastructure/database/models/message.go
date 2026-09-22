package models

import (
	"time"

	"github.com/google/uuid"
)

type Message struct {
	ID         int        `gorm:"primaryKey"`
	Content    string     `gorm:"column:content;not null"`
	IsRead     bool       `gorm:"column:is_read;default:false"`
	IsSend     bool       `gorm:"column:is_send;default:false"`
	UserId     *uuid.UUID `gorm:"column:user_id;index"`
	RoleId     *int       `gorm:"column:role_id;index"`
	ChannelID  *int       `gorm:"column:channel_id;index"`
	EntityType *string    `gorm:"column:entity_type"`
	EntityID   *int       `gorm:"column:entity_id;index"`
	CreatedAt  time.Time  `gorm:"column:created_at;autoCreateTime"`
}

func (Message) TableName() string {
	return "messages"
}
