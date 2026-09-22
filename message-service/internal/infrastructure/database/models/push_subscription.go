package models

import (
	"time"

	"github.com/google/uuid"
)

// PushSubscription — GORM-модель Web Push подписки браузера.
type PushSubscription struct {
	ID        int       `gorm:"primaryKey"`
	UserID    uuid.UUID `gorm:"column:user_id;type:uuid;not null;index:idx_push_subscriptions_user_id"`
	Endpoint  string    `gorm:"column:endpoint;type:text;not null;uniqueIndex"`
	P256dh    string    `gorm:"column:p256dh;type:text;not null"`
	Auth      string    `gorm:"column:auth;type:text;not null"`
	CreatedAt time.Time `gorm:"column:created_at;autoCreateTime"`
	UpdatedAt time.Time `gorm:"column:updated_at;autoUpdateTime"`
}

func (PushSubscription) TableName() string { return "push_subscriptions" }
