package domain

import (
	"errors"
	"strings"
	"time"

	"github.com/google/uuid"
)

// PushSubscription — Web Push подписка браузера (Push API).
// Endpoint уникален: при смене пользователя тот же браузер перезаписывает строку.
type PushSubscription struct {
	ID        int
	UserID    uuid.UUID
	Endpoint  string
	P256dh    string
	Auth      string
	CreatedAt time.Time
	UpdatedAt time.Time
}

// NewPushSubscription валидирует поля подписки Push API.
func NewPushSubscription(userID uuid.UUID, endpoint, p256dh, auth string) (*PushSubscription, error) {
	if userID == uuid.Nil {
		return nil, errors.New("user_id is required")
	}
	endpoint = strings.TrimSpace(endpoint)
	p256dh = strings.TrimSpace(p256dh)
	auth = strings.TrimSpace(auth)
	if endpoint == "" || !strings.HasPrefix(endpoint, "https://") {
		return nil, errors.New("endpoint must be https URL")
	}
	if len(endpoint) > 2048 {
		return nil, errors.New("endpoint is too long")
	}
	if p256dh == "" || auth == "" {
		return nil, errors.New("p256dh and auth keys are required")
	}
	now := time.Now().UTC()
	return &PushSubscription{
		UserID:    userID,
		Endpoint:  endpoint,
		P256dh:    p256dh,
		Auth:      auth,
		CreatedAt: now,
		UpdatedAt: now,
	}, nil
}
