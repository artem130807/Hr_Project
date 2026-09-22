package usecases

import (
	"context"
	"fmt"
	"strings"

	dto "github.com/yourusername/message-service/internal/application/dtos/push"
	authContext "github.com/yourusername/message-service/internal/application/usecases/contracts/auth"
	service "github.com/yourusername/message-service/internal/application/usecases/contracts/service"
	repositories "github.com/yourusername/message-service/internal/domain/contracts/repositories"
	domain "github.com/yourusername/message-service/internal/domain/entities"
	apperrors "github.com/yourusername/message-service/internal/pkg/errors"

	"github.com/google/uuid"
)

var _ service.PushSubscriptionService = (*PushSubscriptionServiceImpl)(nil)

type PushSubscriptionServiceImpl struct {
	repo        repositories.PushSubscriptionRepository
	contextAuth authContext.ContextAuth
	publicKey   string
}

func NewPushSubscriptionService(
	repo repositories.PushSubscriptionRepository,
	contextAuth authContext.ContextAuth,
	vapidPublicKey string,
) *PushSubscriptionServiceImpl {
	return &PushSubscriptionServiceImpl{
		repo:        repo,
		contextAuth: contextAuth,
		publicKey:   strings.TrimSpace(vapidPublicKey),
	}
}

func (s *PushSubscriptionServiceImpl) currentUserID(ctx context.Context) (uuid.UUID, error) {
	userID, err := s.contextAuth.GetUserID(ctx)
	if err != nil {
		return uuid.Nil, apperrors.NewUnauthorized("user not authenticated")
	}
	if userID == uuid.Nil {
		return uuid.Nil, apperrors.NewUnauthorized("user not authenticated")
	}
	return userID, nil
}

func (s *PushSubscriptionServiceImpl) VapidPublicKey() (*dto.VapidPublicKeyDto, error) {
	if s.publicKey == "" {
		return &dto.VapidPublicKeyDto{Enabled: false}, nil
	}
	return &dto.VapidPublicKeyDto{PublicKey: s.publicKey, Enabled: true}, nil
}

func (s *PushSubscriptionServiceImpl) Subscribe(ctx context.Context, req *dto.SubscribeDto) error {
	if s.publicKey == "" {
		return apperrors.NewErrInvalidArgument("web push is disabled")
	}
	if s.repo == nil {
		return apperrors.NewInternalError("push subscriptions not configured")
	}
	if req == nil {
		return apperrors.NewErrInvalidArgument("body is required")
	}
	userID, err := s.currentUserID(ctx)
	if err != nil {
		return err
	}
	sub, err := domain.NewPushSubscription(userID, req.Endpoint, req.Keys.P256dh, req.Keys.Auth)
	if err != nil {
		return apperrors.NewErrInvalidArgument(err.Error())
	}
	if err := s.repo.Upsert(ctx, sub); err != nil {
		return fmt.Errorf("push subscribe: %w", err)
	}
	return nil
}

func (s *PushSubscriptionServiceImpl) Unsubscribe(ctx context.Context, req *dto.UnsubscribeDto) error {
	if s.repo == nil {
		return nil
	}
	if req == nil || strings.TrimSpace(req.Endpoint) == "" {
		return apperrors.NewErrInvalidArgument("endpoint is required")
	}
	userID, err := s.currentUserID(ctx)
	if err != nil {
		return err
	}
	if err := s.repo.DeleteByUserAndEndpoint(ctx, userID, strings.TrimSpace(req.Endpoint)); err != nil {
		return fmt.Errorf("push unsubscribe: %w", err)
	}
	return nil
}
