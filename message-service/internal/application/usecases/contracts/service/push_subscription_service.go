package service

import (
	"context"

	dto "github.com/yourusername/message-service/internal/application/dtos/push"
)

// PushSubscriptionService — регистрация Web Push подписок текущего пользователя.
type PushSubscriptionService interface {
	VapidPublicKey() (*dto.VapidPublicKeyDto, error)
	Subscribe(ctx context.Context, req *dto.SubscribeDto) error
	Unsubscribe(ctx context.Context, req *dto.UnsubscribeDto) error
}
