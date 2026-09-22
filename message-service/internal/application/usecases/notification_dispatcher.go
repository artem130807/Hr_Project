package usecases

import (
	"context"
	"errors"
	"log/slog"

	service "github.com/yourusername/message-service/internal/application/usecases/contracts/service"
	providers "github.com/yourusername/message-service/internal/domain/contracts/providers"
	"github.com/yourusername/message-service/internal/domain/contracts/realtime"
	repositories "github.com/yourusername/message-service/internal/domain/contracts/repositories"
	domain "github.com/yourusername/message-service/internal/domain/entities"
	apperrors "github.com/yourusername/message-service/internal/pkg/errors"

	"github.com/google/uuid"
)

var _ service.NotificationDispatcher = (*NotificationDispatcherImpl)(nil)

// NotificationDispatcherImpl резолвит получателей и публикует через realtime.Notifier.
// Безопасно вызывать с notifier == nil (no-op) — удобно для тестов и постепенного rollout.
// webPusher шлёт OS-уведомления (Push API) для каналов, личных и ролевых
// сообщений. Канальные получатели учитывают settingsChannel; личные/ролевые
// не имеют mute-настройки.
type NotificationDispatcherImpl struct {
	uow       repositories.UnitOfWork
	notifier  realtime.Notifier
	webPusher realtime.WebPusher
	users     providers.UserProvider
	log       *slog.Logger
}

// NewNotificationDispatcher создаёт диспетчер.
func NewNotificationDispatcher(
	uow repositories.UnitOfWork,
	notifier realtime.Notifier,
	webPusher realtime.WebPusher,
	users providers.UserProvider,
	log *slog.Logger,
) *NotificationDispatcherImpl {
	if log == nil {
		log = slog.Default()
	}
	return &NotificationDispatcherImpl{
		uow:       uow,
		notifier:  notifier,
		webPusher: webPusher,
		users:     users,
		log:       log.With("component", "notification_dispatcher"),
	}
}

// DispatchMessage публикует realtime-уведомление по уже сохранённому сообщению.
func (d *NotificationDispatcherImpl) DispatchMessage(ctx context.Context, msg *domain.Message) {
	if d == nil || msg == nil {
		return
	}
	if d.notifier == nil && d.webPusher == nil {
		return
	}

	n := toRealtimeNotification(msg)

	switch {
	case msg.ChannelID != nil:
		if d.uow == nil {
			d.log.Warn("skip channel dispatch: uow is nil", "message_id", msg.ID)
			return
		}
		userIDs, err := d.resolveChannelRecipients(ctx, *msg.ChannelID)
		if err != nil {
			d.log.Warn("resolve channel recipients failed",
				"channel_id", *msg.ChannelID, "message_id", msg.ID, "err", err)
			return
		}
		if len(userIDs) == 0 {
			return
		}
		if d.notifier != nil {
			d.notifier.NotifyUsers(ctx, userIDs, n)
		}
		if d.webPusher != nil {
			d.webPusher.PushToUsers(ctx, userIDs, n)
		}

	case msg.UserId != nil:
		if d.notifier != nil {
			d.notifier.NotifyUsers(ctx, []uuid.UUID{*msg.UserId}, n)
		}
		if d.webPusher != nil && shouldSendDirectPush(msg) {
			d.webPusher.PushToUsers(ctx, []uuid.UUID{*msg.UserId}, n)
		}

	case msg.RoleId != nil:
		if d.notifier != nil {
			d.notifier.NotifyRole(ctx, *msg.RoleId, n)
		}
		if d.webPusher != nil && shouldSendDirectPush(msg) {
			userIDs, err := d.resolveRoleRecipients(ctx, *msg.RoleId)
			if err != nil {
				d.log.Warn("resolve role recipients failed",
					"role_id", *msg.RoleId, "message_id", msg.ID, "err", err)
				break
			}
			if len(userIDs) > 0 {
				d.webPusher.PushToUsers(ctx, userIDs, n)
			}
		}

	default:
		d.log.Warn("message has no target", "message_id", msg.ID)
	}
}

const loginSuccessContent = "Вы успешно вошли в систему."

// До появления event_kind не отправляем системный login_success как OS push:
// он создаётся при каждом входе и иначе превращается в шум. WS остаётся без изменений.
func shouldSendDirectPush(msg *domain.Message) bool {
	return msg != nil && msg.Content != loginSuccessContent
}

func (d *NotificationDispatcherImpl) resolveRoleRecipients(ctx context.Context, roleID int) ([]uuid.UUID, error) {
	if d.users == nil {
		return nil, errors.New("user provider is nil")
	}
	const pageSize = 500
	var out []uuid.UUID
	seen := make(map[uuid.UUID]struct{})
	for page := 1; ; page++ {
		users, err := d.users.GetUserIDs(ctx, page, pageSize)
		if err != nil {
			return nil, err
		}
		if !users.HasRoles {
			return nil, errors.New("user provider response has no role data")
		}
		for _, user := range users.Users {
			if user.RoleID != roleID {
				continue
			}
			if _, ok := seen[user.ID]; ok {
				continue
			}
			seen[user.ID] = struct{}{}
			out = append(out, user.ID)
		}
		if !users.HasMore {
			return out, nil
		}
	}
}

// resolveChannelRecipients возвращает участников канала, у которых push не выключен.
// Нет записи settings → push включён (как на фронте).
// IsSendPushMessage == false → mute, не шлём WS.
func (d *NotificationDispatcherImpl) resolveChannelRecipients(
	ctx context.Context,
	channelID int,
) ([]uuid.UUID, error) {
	var recipients []uuid.UUID
	err := d.uow.Do(ctx, func(ctx context.Context, repos repositories.Repositories) error {
		channel, err := repos.Channels().FindByID(ctx, channelID)
		if err != nil {
			return err
		}
		if len(channel.UsersIds) == 0 {
			return nil
		}
		out := make([]uuid.UUID, 0, len(channel.UsersIds))
		for _, uid := range channel.UsersIds {
			settings, err := repos.Settings().FindByUserAndChannel(ctx, uid, channelID)
			if err != nil {
				if errors.Is(err, apperrors.ErrNotFound) {
					// Нет настроек → push включён по умолчанию.
					out = append(out, uid)
					continue
				}
				return err
			}
			// Mute: IsSendPushMessage == false.
			if settings == nil || settings.IsSendPushMessage {
				out = append(out, uid)
			}
		}
		recipients = out
		return nil
	})
	return recipients, err
}

func toRealtimeNotification(msg *domain.Message) realtime.Notification {
	return realtime.Notification{
		Type:       "notification",
		ID:         msg.ID,
		Content:    msg.Content,
		IsRead:     msg.IsRead,
		IsSend:     msg.IsSend,
		UserID:     msg.UserId,
		RoleID:     msg.RoleId,
		ChannelID:  msg.ChannelID,
		EntityType: msg.EntityType,
		EntityID:   msg.EntityID,
		CreatedAt:  msg.CreatedAt,
	}
}
