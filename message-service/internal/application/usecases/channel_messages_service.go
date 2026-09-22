// internal/application/usecases/channel_service.go
package usecases

import (
	"context"

	"github.com/google/uuid"
	dto "github.com/yourusername/message-service/internal/application/dtos/channel"
	authContext "github.com/yourusername/message-service/internal/application/usecases/contracts/auth"
	service "github.com/yourusername/message-service/internal/application/usecases/contracts/service"
	repositories "github.com/yourusername/message-service/internal/domain/contracts/repositories"
	domain "github.com/yourusername/message-service/internal/domain/entities"
	apperrors "github.com/yourusername/message-service/internal/pkg/errors"
)

// Убеждаемся, что ChannelServiceImpl реализует контракт.
var _ service.ChannelService = (*ChannelServiceImpl)(nil)

// ChannelServiceImpl — реализация сервиса каналов.
type ChannelServiceImpl struct {
	uow         repositories.UnitOfWork
	contextAuth authContext.ContextAuth
}

// NewChannelService создаёт новый сервис каналов.
func NewChannelService(
	uow repositories.UnitOfWork,
	contextAuth authContext.ContextAuth,
) *ChannelServiceImpl {
	return &ChannelServiceImpl{
		uow:         uow,
		contextAuth: contextAuth,
	}
}

// AddChannel создаёт новый канал.
func (s *ChannelServiceImpl) AddChannel(ctx context.Context, request *dto.CreateChannelDto) (*dto.ChannelDto, error) {
	if request == nil {
		return nil, apperrors.NewBadRequest("request cannot be nil")
	}
	if request.Name == "" {
		return nil, apperrors.NewBadRequest("name is required")
	}
	if request.EntityType == "" {
		return nil, apperrors.NewBadRequest("entity_type is required")
	}
	if request.EntityID <= 0 {
		return nil, apperrors.NewBadRequest("entity_id must be positive")
	}

	channel, err := domain.NewChannel(request.Name, request.EntityType, request.EntityID)
	if err != nil {
		return nil, apperrors.NewBadRequest(err.Error())
	}

	if request.UsersIds != nil {
		for _, userID := range request.UsersIds {
			if err := channel.AddUser(userID); err != nil {
				return nil, apperrors.NewBadRequest(err.Error())
			}
		}
	}

	var result *domain.Channel
	err = s.uow.Do(ctx, func(ctx context.Context, repos repositories.Repositories) error {
		if err := repos.Channels().Save(ctx, channel); err != nil {
			return err
		}
		result = channel
		return nil
	})
	if err != nil {
		return nil, err
	}

	return toChannelDto(result), nil
}

// RemoveChannel удаляет канал по идентификатору.
func (s *ChannelServiceImpl) RemoveChannel(ctx context.Context, channelID int) error {
	if channelID <= 0 {
		return apperrors.NewBadRequest("channel id must be positive")
	}

	return s.uow.Do(ctx, func(ctx context.Context, repos repositories.Repositories) error {
		_, err := repos.Channels().FindByID(ctx, channelID)
		if err != nil {
			return apperrors.NewNotFound("channel not found")
		}
		return repos.Channels().Delete(ctx, channelID)
	})
}

// EditChannel обновляет данные канала.
func (s *ChannelServiceImpl) EditChannel(ctx context.Context, channelID int, request *dto.UpdateChannelDto) (*dto.ChannelDto, error) {
	if request == nil {
		return nil, apperrors.NewBadRequest("request cannot be nil")
	}
	if channelID <= 0 {
		return nil, apperrors.NewBadRequest("channel id must be positive")
	}

	var result *domain.Channel
	err := s.uow.Do(ctx, func(ctx context.Context, repos repositories.Repositories) error {
		channel, err := repos.Channels().FindByID(ctx, channelID)
		if err != nil {
			return apperrors.NewNotFound("channel not found")
		}

		if request.Name != nil {
			channel.Name = *request.Name
		}
		if request.EntityType != nil {
			channel.EntityType = *request.EntityType
		}
		if request.EntityID != nil {
			channel.EntityID = *request.EntityID
		}

		if request.UsersIds != nil {
			currentUsers := channel.UsersIds
			for _, uid := range currentUsers {
				_ = channel.RemoveUser(uid)
			}
			for _, uid := range *request.UsersIds {
				if err := channel.AddUser(uid); err != nil {
					return err
				}
			}
		}

		if err := repos.Channels().Update(ctx, channel); err != nil {
			return err
		}
		result = channel
		return nil
	})
	if err != nil {
		return nil, err
	}

	return toChannelDto(result), nil
}

// GetChannel возвращает канал по идентификатору.
func (s *ChannelServiceImpl) GetChannel(ctx context.Context, channelID int) (*dto.ChannelDto, error) {
	if channelID <= 0 {
		return nil, apperrors.NewBadRequest("channel id must be positive")
	}

	var result *domain.Channel
	err := s.uow.Do(ctx, func(ctx context.Context, repos repositories.Repositories) error {
		channel, err := repos.Channels().FindByID(ctx, channelID)
		if err != nil {
			return apperrors.NewNotFound("channel not found")
		}
		result = channel
		return nil
	})
	if err != nil {
		return nil, err
	}

	return toChannelDto(result), nil
}

// GetChannelsByPush возвращает каналы, где пользователь — участник (user_ids).
// Опциональный isPush фильтрует по mute в settings:
//   - нет записи settings → push включён (как в notification_dispatcher);
//   - IsSendPushMessage == false → канал скрыт при isPush=true и показан при isPush=false.
func (s *ChannelServiceImpl) GetChannelsByPush(ctx context.Context, isPush *bool) ([]*dto.ChannelDto, error) {
	userID, err := s.contextAuth.GetUserID(ctx)
	if err != nil {
		return nil, apperrors.NewUnauthorized("user not authenticated")
	}
	if userID == uuid.Nil {
		return nil, apperrors.NewBadRequest("user id is required")
	}

	var channels []*domain.Channel
	unreadByChannel := map[int]int{}
	err = s.uow.Do(ctx, func(ctx context.Context, repos repositories.Repositories) error {
		memberChannels, err := repos.Channels().FindAllByUserID(ctx, userID)
		if err != nil {
			return err
		}
		if isPush == nil || len(memberChannels) == 0 {
			channels = memberChannels
		} else {
			settings, err := repos.Settings().FindAllByUserID(ctx, userID)
			if err != nil {
				return err
			}
			pushByChannel := make(map[int]bool, len(settings))
			for _, st := range settings {
				if st == nil {
					continue
				}
				pushByChannel[st.ChannelID] = st.IsSendPushMessage
			}

			filtered := make([]*domain.Channel, 0, len(memberChannels))
			for _, ch := range memberChannels {
				if ch == nil {
					continue
				}
				enabled, hasSettings := pushByChannel[ch.ID]
				if !hasSettings {
					enabled = true // default: push on
				}
				if enabled == *isPush {
					filtered = append(filtered, ch)
				}
			}
			channels = filtered
		}

		ids := make([]int, 0, len(channels))
		for _, ch := range channels {
			if ch != nil && ch.ID > 0 {
				ids = append(ids, ch.ID)
			}
		}
		counts, err := repos.Messages().CountUnreadByChannelIDs(ctx, ids)
		if err != nil {
			return err
		}
		if counts != nil {
			unreadByChannel = counts
		}
		return nil
	})
	if err != nil {
		return nil, err
	}

	dtos := toChannelDtos(channels)
	for _, d := range dtos {
		if d != nil {
			d.UnreadCount = unreadByChannel[d.ID]
		}
	}
	return dtos, nil
}

// toChannelDto мапит доменную сущность в DTO.
func toChannelDto(c *domain.Channel) *dto.ChannelDto {
	if c == nil {
		return nil
	}
	return &dto.ChannelDto{
		ID:         c.ID,
		Name:       c.Name,
		EntityType: c.EntityType,
		EntityID:   c.EntityID,
		CreatedAt:  c.CreatedAt,
		UsersIds:   c.UsersIds,
	}
}

// toChannelDtos мапит список доменных сущностей в список DTO.
func toChannelDtos(channels []*domain.Channel) []*dto.ChannelDto {
	if channels == nil {
		return []*dto.ChannelDto{}
	}
	dtos := make([]*dto.ChannelDto, len(channels))
	for i, c := range channels {
		dtos[i] = toChannelDto(c)
	}
	return dtos
}
