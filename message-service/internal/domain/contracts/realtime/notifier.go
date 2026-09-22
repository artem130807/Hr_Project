// Package realtime — контракты доставки realtime-уведомлений подписчикам.
package realtime

import (
	"context"
	"time"

	"github.com/google/uuid"
)

// Notification — полезный payload, который уходит клиентам по WebSocket.
// Поля адресации зеркалят сущность Message (ровно один из UserID/RoleID/ChannelID).
type Notification struct {
	Type       string     `json:"type"` // всегда "notification"
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

// Notifier — транспорт realtime-доставки. Реализация не знает про каналы/настройки —
// только про «кому» и «что». Это позволяет переиспользовать сервис для любых
// будущих типов уведомлений.
type Notifier interface {
	// NotifyUsers шлёт payload указанным user_id (если они онлайн).
	NotifyUsers(ctx context.Context, userIDs []uuid.UUID, n Notification)

	// NotifyRole шлёт payload всем подключённым клиентам с данным role_id.
	NotifyRole(ctx context.Context, roleID int, n Notification)
}
