// internal/application/usecases/settingsChannel_service.go
package usecases

import (
	"context"
	"fmt"

	dto "github.com/yourusername/message-service/internal/application/dtos/settings"
	authContext "github.com/yourusername/message-service/internal/application/usecases/contracts/auth"
	service "github.com/yourusername/message-service/internal/application/usecases/contracts/service"
	repositories "github.com/yourusername/message-service/internal/domain/contracts/repositories"
	domain "github.com/yourusername/message-service/internal/domain/entities"
	apperrors "github.com/yourusername/message-service/internal/pkg/errors"

	"github.com/google/uuid"
)

// Убеждаемся, что SettingsChannelServiceImpl реализует контракт.
var _ service.SettingsChannelService = (*SettingsChannelServiceImpl)(nil)

// SettingsChannelServiceImpl — реализация SettingsChannelService поверх UnitOfWork.
type SettingsChannelServiceImpl struct {
	uow         repositories.UnitOfWork
	contextAuth authContext.ContextAuth
}

// NewSettingsChannelService создаёт сервис настроек канала.
func NewSettingsChannelService(
	uow repositories.UnitOfWork,
	contextAuth authContext.ContextAuth,
) *SettingsChannelServiceImpl {
	return &SettingsChannelServiceImpl{
		uow:         uow,
		contextAuth: contextAuth,
	}
}

func (s *SettingsChannelServiceImpl) currentUserID(ctx context.Context) (uuid.UUID, error) {
	userID, err := s.contextAuth.GetUserID(ctx)
	if err != nil {
		return uuid.Nil, apperrors.NewUnauthorized("user not authenticated")
	}
	if userID == uuid.Nil {
		return uuid.Nil, apperrors.NewUnauthorized("user not authenticated")
	}
	return userID, nil
}

func assertSettingsOwner(settings *domain.SettingsChannel, userID uuid.UUID) error {
	if settings == nil || settings.UserID != userID {
		return apperrors.NewUnauthorized("settings access denied")
	}
	return nil
}

// AddSettings создаёт настройки канала для текущего пользователя.
func (s *SettingsChannelServiceImpl) AddSettings(ctx context.Context, request *dto.CreateSettingsDto) (*dto.SettingsDto, error) {
	if request == nil {
		return nil, fmt.Errorf("settings service: add: %w", apperrors.ErrInvalidArgument)
	}

	userID, err := s.currentUserID(ctx)
	if err != nil {
		return nil, err
	}

	settings, err := domain.NewSettingsChannel(userID, request.ChannelID, request.IsSendPushMessage)
	if err != nil {
		return nil, fmt.Errorf("settings service: add: %w", err)
	}

	var result *domain.SettingsChannel
	err = s.uow.Do(ctx, func(ctx context.Context, repos repositories.Repositories) error {
		if err := repos.Settings().Save(ctx, settings); err != nil {
			return err
		}
		result = settings
		return nil
	})
	if err != nil {
		return nil, err
	}
	return toSettingsDto(result), nil
}

// RemoveSettings удаляет настройки по идентификатору (только владелец).
func (s *SettingsChannelServiceImpl) RemoveSettings(ctx context.Context, id int) error {
	if id <= 0 {
		return fmt.Errorf("settings service: remove: id: %w", apperrors.ErrInvalidArgument)
	}

	userID, err := s.currentUserID(ctx)
	if err != nil {
		return err
	}

	return s.uow.Do(ctx, func(ctx context.Context, repos repositories.Repositories) error {
		settings, err := repos.Settings().FindByID(ctx, id)
		if err != nil {
			return err
		}
		if err := assertSettingsOwner(settings, userID); err != nil {
			return err
		}
		return repos.Settings().Delete(ctx, id)
	})
}

// EditSettings обновляет флаг push-уведомлений (только владелец).
func (s *SettingsChannelServiceImpl) EditSettings(ctx context.Context, id int, request *dto.UpdateSettingsDto) (*dto.SettingsDto, error) {
	if request == nil {
		return nil, fmt.Errorf("settings service: edit: %w", apperrors.ErrInvalidArgument)
	}

	userID, err := s.currentUserID(ctx)
	if err != nil {
		return nil, err
	}

	var result *domain.SettingsChannel
	err = s.uow.Do(ctx, func(ctx context.Context, repos repositories.Repositories) error {
		settings, err := repos.Settings().FindByID(ctx, id)
		if err != nil {
			return err
		}
		if err := assertSettingsOwner(settings, userID); err != nil {
			return err
		}
		if request.IsSendPushMessage != nil {
			settings.UpdatePushSettings(*request.IsSendPushMessage)
		}
		if err := repos.Settings().Update(ctx, settings); err != nil {
			return err
		}
		result = settings
		return nil
	})
	if err != nil {
		return nil, err
	}
	return toSettingsDto(result), nil
}

// GetSettings возвращает настройки по идентификатору (только владелец).
func (s *SettingsChannelServiceImpl) GetSettings(ctx context.Context, id int) (*dto.SettingsDto, error) {
	if id <= 0 {
		return nil, fmt.Errorf("settings service: get: id: %w", apperrors.ErrInvalidArgument)
	}

	userID, err := s.currentUserID(ctx)
	if err != nil {
		return nil, err
	}

	var result *domain.SettingsChannel
	err = s.uow.Do(ctx, func(ctx context.Context, repos repositories.Repositories) error {
		settings, err := repos.Settings().FindByID(ctx, id)
		if err != nil {
			return err
		}
		if err := assertSettingsOwner(settings, userID); err != nil {
			return err
		}
		result = settings
		return nil
	})
	if err != nil {
		return nil, err
	}
	return toSettingsDto(result), nil
}

// GetAllByUser возвращает все настройки текущего пользователя.
func (s *SettingsChannelServiceImpl) GetAllByUser(ctx context.Context) ([]*dto.SettingsDto, error) {
	userID, err := s.currentUserID(ctx)
	if err != nil {
		return nil, err
	}

	var result []*domain.SettingsChannel
	err = s.uow.Do(ctx, func(ctx context.Context, repos repositories.Repositories) error {
		settings, err := repos.Settings().FindAllByUserID(ctx, userID)
		if err != nil {
			return err
		}
		result = settings
		return nil
	})
	if err != nil {
		return nil, err
	}

	dtos := make([]*dto.SettingsDto, len(result))
	for i, st := range result {
		dtos[i] = toSettingsDto(st)
	}
	return dtos, nil
}

func (s *SettingsChannelServiceImpl) FindByUserAndChannel(ctx context.Context, userID uuid.UUID, channelId int) (*dto.SettingsDto, error) {
	if userID == uuid.Nil {
		return nil, fmt.Errorf("settings service: get all by user: user id: %w", apperrors.ErrInvalidArgument)
	}
	var result *domain.SettingsChannel
	err := s.uow.Do(ctx, func(ctx context.Context, repos repositories.Repositories) error {
		settings, err := repos.Settings().FindByUserAndChannel(ctx, userID, channelId)
		if err != nil {
			return err
		}
		result = settings
		return nil
	})
	if err != nil {
		return nil, err
	}
	return toSettingsDto(result), nil
}

// toSettingsDto мапит доменную сущность в DTO.
func toSettingsDto(s *domain.SettingsChannel) *dto.SettingsDto {
	if s == nil {
		return nil
	}
	return &dto.SettingsDto{
		ID:                s.ID,
		UserID:            s.UserID,
		ChannelID:         s.ChannelID,
		IsSendPushMessage: s.IsSendPushMessage,
		CreatedAt:         s.CreatedAt,
	}
}
