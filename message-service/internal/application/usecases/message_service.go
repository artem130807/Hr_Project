// internal/application/usecases/message_service.go
package usecases

import (
	"context"
	"errors"
	"fmt"

	"github.com/google/uuid"
	dto "github.com/yourusername/message-service/internal/application/dtos/message"
	authContext "github.com/yourusername/message-service/internal/application/usecases/contracts/auth"
	messagefilters "github.com/yourusername/message-service/internal/application/usecases/contracts/filters/message_filters"
	service "github.com/yourusername/message-service/internal/application/usecases/contracts/service"
	repositories "github.com/yourusername/message-service/internal/domain/contracts/repositories"
	domain "github.com/yourusername/message-service/internal/domain/entities"
	apperrors "github.com/yourusername/message-service/internal/pkg/errors"
)

// Убеждаемся, что MessageService реализует контракт.
var _ service.MessageService = (*MessageServiceImpl)(nil)

// MessageServiceImpl — реализация MessageService поверх UnitOfWork.
type MessageServiceImpl struct {
	uow         repositories.UnitOfWork
	contextAuth authContext.ContextAuth
	dispatcher  service.NotificationDispatcher
}

// NewMessageService создаёт сервис сообщений.
// dispatcher может быть nil — тогда realtime-уведомления не отправляются.
func NewMessageService(
	uow repositories.UnitOfWork,
	contextAuth authContext.ContextAuth,
	dispatcher service.NotificationDispatcher,
) *MessageServiceImpl {
	return &MessageServiceImpl{uow: uow, contextAuth: contextAuth, dispatcher: dispatcher}
}

// AddMessage создаёт сообщение. Адресат определяется DTO: ровно один из
// (ChannelID, UserID, RoleID); валидация и конструирование инкапсулированы
// в доменных фабриках SendMessageToChannel/User/Role.
func (s *MessageServiceImpl) AddMessage(ctx context.Context, request *dto.CreateMessageDto) (*dto.MessageDto, error) {
	if request == nil {
		return nil, apperrors.NewBadRequest("message cannot be nil")
	}
	message, err := buildDomainMessage(request)
	if err != nil {
		return nil, apperrors.NewBadRequest(err.Error())
	}
	var result *domain.Message
	err = s.uow.Do(ctx, func(ctx context.Context, repos repositories.Repositories) error {
		if err := repos.Messages().Save(ctx, message); err != nil {
			switch {
			case errors.Is(err, apperrors.ErrNotFound):
				return apperrors.NewNotFound(err.Error())
			case errors.Is(err, apperrors.ErrAlreadyExists):
				return apperrors.NewConflict(err.Error())
			default:
				return apperrors.NewInternalError(err.Error())
			}
		}
		result = message
		return nil
	})
	if err != nil {
		return nil, err
	}
	if s.dispatcher != nil {
		s.dispatcher.DispatchMessage(ctx, result)
	}
	return toMessageDto(result), nil
}

// RemoveMessage удаляет сообщение по идентификатору.
func (s *MessageServiceImpl) RemoveMessage(ctx context.Context, messageID int) error {
	if messageID <= 0 {
		return fmt.Errorf("message service: remove: id: %w", apperrors.ErrInvalidArgument)
	}
	return s.uow.Do(ctx, func(ctx context.Context, repos repositories.Repositories) error {
		return repos.Messages().Delete(ctx, messageID)
	})
}

// FindNotReadCountByUser возвращает число непрочитанных сообщений текущего пользователя.
func (s *MessageServiceImpl) FindNotReadCountByUser(ctx context.Context) (int, error) {
	userID, err := s.contextAuth.GetUserID(ctx)
	if err != nil {
		return 0, apperrors.NewUnauthorized("user not authenticated")
	}

	roleID, err := s.contextAuth.GetRoleID(ctx)
	if err != nil {
		return 0, apperrors.NewUnauthorized("user role_id not found")
	}

	var count int
	err = s.uow.Do(ctx, func(ctx context.Context, repos repositories.Repositories) error {
		var repoErr error
		count, repoErr = repos.Messages().FindNotReadCountByUser(ctx, userID, roleID)
		return repoErr
	})
	if err != nil {
		return 0, fmt.Errorf("failed to count unread messages: %w", err)
	}

	return count, nil
}

// EditMessage изменяет содержимое сообщения. Бизнес-правило «нельзя править
// после отправки» инкапсулировано в доменном методе Message.UpdateContent.
func (s *MessageServiceImpl) EditMessage(ctx context.Context, messageID int, request *dto.UpdateMessageDto) (*dto.MessageDto, error) {
	if request == nil {
		return nil, fmt.Errorf("message service: edit: %w", apperrors.ErrInvalidArgument)
	}

	var result *domain.Message
	err := s.uow.Do(ctx, func(ctx context.Context, repos repositories.Repositories) error {
		message, err := repos.Messages().FindByID(ctx, messageID)
		if err != nil {
			return err
		}
		if err := message.UpdateContent(request.Content); err != nil {
			return err
		}
		if err := repos.Messages().Update(ctx, message); err != nil {
			return err
		}
		result = message
		return nil
	})
	if err != nil {
		return nil, err
	}
	return toMessageDto(result), nil
}

// GetMessage возвращает сообщение по идентификатору.
func (s *MessageServiceImpl) GetMessage(ctx context.Context, messageID int) (*dto.MessageDto, error) {
	if messageID <= 0 {
		return nil, fmt.Errorf("message service: get: id: %w", apperrors.ErrInvalidArgument)
	}

	var result *domain.Message
	err := s.uow.Do(ctx, func(ctx context.Context, repos repositories.Repositories) error {
		message, err := repos.Messages().FindByID(ctx, messageID)
		if err != nil {
			return err
		}
		result = message
		return nil
	})
	if err != nil {
		return nil, err
	}
	return toMessageDto(result), nil
}

// GetMessagesByFilter ищет сообщения по фильтру. Application-фильтр
// транслируется в доменный MessageQuery, чтобы репозиторий оставался
// независимым от слоя приложения.
//
// Identity (user_id / role_id) всегда берётся из context — клиент не может
// подменить чужой user/role. channel_id допускается только если пользователь
// участник канала.
//
// Порядок ответа: от новых к старым (лента уведомлений ERP).
func (s *MessageServiceImpl) GetMessagesByFilter(ctx context.Context, f *messagefilters.GetMessagesFilter) ([]*dto.MessageDto, error) {
	userID, _, query, err := s.resolveAudienceQuery(ctx, f)
	if err != nil {
		return nil, err
	}

	var result []*domain.Message
	err = s.uow.Do(ctx, func(ctx context.Context, repos repositories.Repositories) error {
		if query.ChannelID != nil {
			channel, err := repos.Channels().FindByID(ctx, *query.ChannelID)
			if err != nil {
				return err
			}
			if !channelContainsUser(channel, userID) {
				return apperrors.NewUnauthorized("channel access denied")
			}
		}
		messages, err := repos.Messages().FindByQuery(ctx, query)
		if err != nil {
			return err
		}
		result = messages
		return nil
	})
	if err != nil {
		return nil, err
	}

	dtos := make([]*dto.MessageDto, 0, len(result))
	for _, m := range result {
		dtos = append(dtos, toMessageDto(m))
	}
	return dtos, nil
}

// MarkMessagesAsRead помечает все непрочитанные сообщения выбранной аудитории.
// Нормализация фильтра и проверка доступа к каналу — как у GetMessagesByFilter.
func (s *MessageServiceImpl) MarkMessagesAsRead(ctx context.Context, f *messagefilters.GetMessagesFilter) (int, error) {
	userID, _, query, err := s.resolveAudienceQuery(ctx, f)
	if err != nil {
		return 0, err
	}

	var marked int
	err = s.uow.Do(ctx, func(ctx context.Context, repos repositories.Repositories) error {
		if query.ChannelID != nil {
			channel, err := repos.Channels().FindByID(ctx, *query.ChannelID)
			if err != nil {
				return err
			}
			if !channelContainsUser(channel, userID) {
				return apperrors.NewUnauthorized("channel access denied")
			}
		}
		n, err := repos.Messages().MarkAsReadByQuery(ctx, query)
		if err != nil {
			return err
		}
		marked = n
		return nil
	})
	if err != nil {
		return 0, err
	}
	return marked, nil
}

// MarkMessageAsRead помечает одно сообщение прочитанным.
// Доступ: личное — только адресат; роль — JWT-роль; канал — участник.
func (s *MessageServiceImpl) MarkMessageAsRead(ctx context.Context, messageID int) (*dto.MessageDto, error) {
	if messageID <= 0 {
		return nil, apperrors.NewBadRequest("invalid message id")
	}

	userID, err := s.contextAuth.GetUserID(ctx)
	if err != nil {
		return nil, apperrors.NewUnauthorized("user not authenticated")
	}
	roleID, err := s.contextAuth.GetRoleID(ctx)
	if err != nil {
		return nil, apperrors.NewUnauthorized("user role_id not found")
	}

	var result *domain.Message
	err = s.uow.Do(ctx, func(ctx context.Context, repos repositories.Repositories) error {
		message, err := repos.Messages().FindByID(ctx, messageID)
		if err != nil {
			if errors.Is(err, apperrors.ErrNotFound) {
				return apperrors.NewNotFound("message not found")
			}
			return err
		}
		if err := ensureMessageAccess(repos, ctx, message, userID, roleID); err != nil {
			return err
		}
		if !message.IsRead {
			message.MarkAsRead()
			if err := repos.Messages().Update(ctx, message); err != nil {
				return err
			}
		}
		result = message
		return nil
	})
	if err != nil {
		return nil, err
	}
	return toMessageDto(result), nil
}

func ensureMessageAccess(
	repos repositories.Repositories,
	ctx context.Context,
	message *domain.Message,
	userID uuid.UUID,
	roleID int,
) error {
	if message == nil {
		return apperrors.NewNotFound("message not found")
	}
	if message.UserId != nil {
		if *message.UserId != userID {
			return apperrors.NewUnauthorized("message access denied")
		}
		return nil
	}
	if message.RoleId != nil {
		if *message.RoleId != roleID {
			return apperrors.NewUnauthorized("message access denied")
		}
		return nil
	}
	if message.ChannelID != nil {
		channel, err := repos.Channels().FindByID(ctx, *message.ChannelID)
		if err != nil {
			if errors.Is(err, apperrors.ErrNotFound) {
				return apperrors.NewUnauthorized("message access denied")
			}
			return err
		}
		if !channelContainsUser(channel, userID) {
			return apperrors.NewUnauthorized("message access denied")
		}
		return nil
	}
	return apperrors.NewUnauthorized("message access denied")
}

// resolveAudienceQuery нормализует application-фильтр в доменный MessageQuery
// с identity из JWT (ровно один адресат: user | role | channel).
func (s *MessageServiceImpl) resolveAudienceQuery(
	ctx context.Context,
	f *messagefilters.GetMessagesFilter,
) (uuid.UUID, int, repositories.MessageQuery, error) {
	userID, err := s.contextAuth.GetUserID(ctx)
	if err != nil {
		return uuid.Nil, 0, repositories.MessageQuery{}, apperrors.NewUnauthorized("user not authenticated")
	}

	roleID, err := s.contextAuth.GetRoleID(ctx)
	if err != nil {
		return uuid.Nil, 0, repositories.MessageQuery{}, apperrors.NewUnauthorized("user role_id not found")
	}

	if f == nil {
		f = &messagefilters.GetMessagesFilter{}
	}

	// Копия, чтобы не мутировать входной указатель вызывающего.
	norm := *f
	switch {
	case norm.ChannelId != nil:
		norm.UserId = nil
		norm.RoleId = nil
	case norm.RoleId != nil:
		norm.UserId = nil
		norm.RoleId = &roleID
		norm.ChannelId = nil
	default:
		norm.UserId = &userID
		norm.RoleId = nil
		norm.ChannelId = nil
	}

	return userID, roleID, toMessageQuery(&norm), nil
}

func channelContainsUser(channel *domain.Channel, userID uuid.UUID) bool {
	if channel == nil {
		return false
	}
	for _, id := range channel.UsersIds {
		if id == userID {
			return true
		}
	}
	return false
}

// buildDomainMessage выбирает нужную доменную фабрику по заполненному адресату.
func buildDomainMessage(request *dto.CreateMessageDto) (*domain.Message, error) {
	targets := 0
	if request.ChannelID != nil {
		targets++
	}
	if request.UserID != nil {
		targets++
	}
	if request.RoleID != nil {
		targets++
	}
	if targets != 1 {
		return nil, fmt.Errorf("exactly one of channel_id/user_id/role_id must be set: %w", apperrors.ErrInvalidArgument)
	}

	var (
		msg *domain.Message
		err error
	)
	switch {
	case request.ChannelID != nil:
		msg, err = domain.SendMessageToChannel(request.Content, *request.ChannelID)
	case request.UserID != nil:
		msg, err = domain.SendMessageToUser(request.Content, *request.UserID)
	default:
		msg, err = domain.SendMessageToRole(request.Content, *request.RoleID)
	}
	if err != nil {
		return nil, err
	}
	if request.EntityType != nil && request.EntityID != nil {
		msg.WithEntity(*request.EntityType, *request.EntityID)
	}
	return msg, nil
}

// toMessageQuery мапит application-фильтр в доменный запрос.
func toMessageQuery(f *messagefilters.GetMessagesFilter) repositories.MessageQuery {
	if f == nil {
		return repositories.MessageQuery{}
	}
	return repositories.MessageQuery{
		UserID:       f.UserId,
		RoleID:       f.RoleId,
		ChannelID:    f.ChannelId,
		IsRead:       f.IsRead,
		CreatedAfter: f.CreatedAt,
	}
}

// toMessageDto мапит доменную сущность в DTO.
func toMessageDto(m *domain.Message) *dto.MessageDto {
	if m == nil {
		return nil
	}
	return &dto.MessageDto{
		ID:         m.ID,
		Content:    m.Content,
		IsRead:     m.IsRead,
		IsSend:     m.IsSend,
		UserID:     m.UserId,
		RoleID:     m.RoleId,
		ChannelID:  m.ChannelID,
		EntityType: m.EntityType,
		EntityID:   m.EntityID,
		CreatedAt:  m.CreatedAt,
	}
}
