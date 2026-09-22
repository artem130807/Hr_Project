// internal/application/usecases/event_service.go
package usecases

import (
	"context"
	"errors"
	"fmt"
	"log/slog"

	service "github.com/yourusername/message-service/internal/application/usecases/contracts/service"
	repositories "github.com/yourusername/message-service/internal/domain/contracts/repositories"
	domain "github.com/yourusername/message-service/internal/domain/entities"
	apperrors "github.com/yourusername/message-service/internal/pkg/errors"
)

// Убеждаемся, что EventServiceImpl реализует контракт.
var _ service.EventService = (*EventServiceImpl)(nil)

// EventServiceImpl обрабатывает события из брокера:
//   - message.*.changed / downtime / approval → канал + текст;
//   - hiring_request / adaptation.talk_hr → ролевые уведомления;
//   - hr.event.created → личное сообщение + outbox notify (Telegram по расписанию);
//   - hr.hiring_request.created → outbox notify сразу (без откладки).
type EventServiceImpl struct {
	uow        repositories.UnitOfWork
	dispatcher service.NotificationDispatcher
	log        *slog.Logger
}

// NewEventService создаёт сервис обработки событий.
// log == nil подменяется на slog.Default().
// dispatcher может быть nil.
func NewEventService(
	uow repositories.UnitOfWork,
	dispatcher service.NotificationDispatcher,
	log *slog.Logger,
) *EventServiceImpl {
	if log == nil {
		log = slog.Default()
	}
	return &EventServiceImpl{uow: uow, dispatcher: dispatcher, log: log}
}

// Handle — точка входа асинхронной обработки (worker.Handler).
//
// Ошибки десериализации/пустые события не возвращаем (return nil), чтобы брокер
// Ack'нул и не зацикливал requeue poison-сообщений. Ошибки БД возвращаются
// (Nack + requeue) — они, как правило, временные.
func (s *EventServiceImpl) Handle(ctx context.Context, body []byte) error {
	if len(body) == 0 {
		return nil
	}

	eventType, err := peekEventType(body)
	if err != nil {
		s.log.Warn("event_service: invalid json, drop", "err", err, "size", len(body))
		return nil
	}
	if eventType == "" {
		s.log.Warn("event_service: empty event_type, drop")
		return nil
	}

	switch eventType {
	case hrEventCreatedType:
		return s.handleHrEventCreated(ctx, body)
	case hrHiringRequestCreatedType:
		return s.handleHrHiringRequestCreated(ctx, body)
	case "message.hiring_request.created", "message.adaptation.talk_hr", "message.adaptation.notification":
		return s.handleRoleTargetedEvent(ctx, body)
	default:
		// HR-срез: логистические события (машины, рейсы, простои, TMS) сюда не входят.
		s.log.Info("event_service: non-hr event ignored", "event_type", eventType)
		return nil
	}
}

// handleRoleTargetedEvent создаёт отдельное уведомление каждой роли без общего канала.
// Диспетчер доставляет сохранённые сообщения через WebSocket и WebPush.
func (s *EventServiceImpl) handleRoleTargetedEvent(ctx context.Context, body []byte) error {
	ce, err := DeserializeToChangeEvent(body)
	if err != nil {
		s.log.Warn("event_service: invalid role event, drop", "err", err)
		return nil
	}
	if ce.EntityID <= 0 || len(ce.TargetRoleIDs) == 0 {
		s.log.Warn("event_service: role event without entity or roles, drop", "event_type", ce.EventType)
		return nil
	}
	content, err := ce.RenderMessage()
	if err != nil {
		s.log.Warn("event_service: role event render failed, drop", "err", err, "event_type", ce.EventType)
		return nil
	}

	posted := make([]*domain.Message, 0, len(ce.TargetRoleIDs))
	err = s.uow.Do(ctx, func(ctx context.Context, repos repositories.Repositories) error {
		seen := make(map[int]struct{}, len(ce.TargetRoleIDs))
		for _, roleID := range ce.TargetRoleIDs {
			if roleID <= 0 {
				continue
			}
			if _, exists := seen[roleID]; exists {
				continue
			}
			seen[roleID] = struct{}{}
			msg, buildErr := domain.SendMessageToRole(content, roleID)
			if buildErr != nil {
				return fmt.Errorf("event_service: build role message: %w", buildErr)
			}
			msg.WithEntity(ce.EntityKind, ce.EntityID)
			if saveErr := repos.Messages().Save(ctx, msg); saveErr != nil {
				return fmt.Errorf("event_service: save role message: %w", saveErr)
			}
			posted = append(posted, msg)
		}
		if ce.EventType == "message.adaptation.talk_hr" || ce.EventType == "message.adaptation.notification" {
			payload, payloadErr := BuildAdaptationTalkHRNotifyPayload(ce, content)
			if payloadErr != nil {
				return fmt.Errorf("event_service: build adaptation notify: %w", payloadErr)
			}
			outbox, outboxErr := domain.NewPendingOutbox(hrEventNotifyType, payload)
			if outboxErr != nil {
				return fmt.Errorf("event_service: build adaptation outbox: %w", outboxErr)
			}
			if saveErr := repos.Outbox().Save(ctx, outbox); saveErr != nil {
				return fmt.Errorf("event_service: save adaptation outbox: %w", saveErr)
			}
		}
		return nil
	})
	if err != nil {
		return err
	}
	if s.dispatcher != nil {
		for _, msg := range posted {
			s.dispatcher.DispatchMessage(ctx, msg)
		}
	}
	return nil
}

// handleHrEventCreated создаёт личное сообщение получателю и outbox → hr.event.notify.
func (s *EventServiceImpl) handleHrEventCreated(ctx context.Context, body []byte) error {
	ev, err := parseHrEventCreated(body)
	if err != nil {
		s.log.Warn("event_service: invalid hr.event.created, drop", "err", err)
		return nil
	}

	userID, userErr := ev.RecipientUserID()
	if userErr != nil {
		s.log.Warn("event_service: hr.event.created without user_id — skip personal message, still notify Telegram",
			"err", userErr,
			"hr_event_id", ev.HrEventID,
			"telegram_user", ev.TelegramUser,
		)
	}

	content, err := ev.RenderMessage()
	if err != nil {
		s.log.Warn("event_service: hr.event.created render failed, drop",
			"err", err,
			"hr_event_id", ev.HrEventID,
		)
		return nil
	}

	notifyPayload, err := BuildHrEventNotifyPayload(ev, content, userID)
	if err != nil {
		s.log.Warn("event_service: hr.event.notify payload failed, drop",
			"err", err,
			"hr_event_id", ev.HrEventID,
		)
		return nil
	}

	var posted *domain.Message
	err = s.uow.Do(ctx, func(ctx context.Context, repos repositories.Repositories) error {
		if userErr == nil {
			msg, err := domain.SendMessageToUser(content, userID)
			if err != nil {
				return fmt.Errorf("event_service: build personal message: %w", err)
			}
			if ev.HrEventID > 0 {
				msg.WithEntity("hr_event", ev.HrEventID)
			}
			if err := repos.Messages().Save(ctx, msg); err != nil {
				return fmt.Errorf("event_service: save personal message: %w", err)
			}
			posted = msg
		}

		outbox, err := domain.NewPendingOutbox(hrEventNotifyType, notifyPayload)
		if err != nil {
			return fmt.Errorf("event_service: build outbox: %w", err)
		}
		if err := repos.Outbox().Save(ctx, outbox); err != nil {
			return fmt.Errorf("event_service: save outbox: %w", err)
		}

		s.log.Info("event_service: hr notify queued",
			"event_type", ev.EventType,
			"hr_event_id", ev.HrEventID,
			"user_id", formatOptionalUserID(userID, userErr),
			"personal_message", userErr == nil,
			"type", ev.Type,
			"event_date", ev.EventDate,
			"remind_before", ev.RemindBefore,
			"remind_at_time", ev.RemindAtTime,
			"outbox_id", outbox.ID,
			"outbox_event", hrEventNotifyType,
		)
		return nil
	})
	if err != nil {
		return err
	}
	if posted != nil && s.dispatcher != nil {
		s.dispatcher.DispatchMessage(ctx, posted)
	}
	return nil
}

// handleHrHiringRequestCreated кладёт outbox hr.event.notify с notify_at=сейчас.
// Личное in-app не создаём: канал «Заявки на подбор» уже рассылает UI.
func (s *EventServiceImpl) handleHrHiringRequestCreated(ctx context.Context, body []byte) error {
	ev, err := parseHrHiringRequestCreated(body)
	if err != nil {
		s.log.Warn("event_service: invalid hr.hiring_request.created, drop", "err", err)
		return nil
	}
	if ev.HiringRequestID <= 0 {
		s.log.Warn("event_service: hr.hiring_request.created empty id, drop")
		return nil
	}
	content, err := ev.RenderMessage()
	if err != nil {
		s.log.Warn("event_service: hr.hiring_request.created render failed, drop",
			"err", err, "hiring_request_id", ev.HiringRequestID)
		return nil
	}
	notifyPayload, err := BuildHrHiringRequestNotifyPayload(ev, content)
	if err != nil {
		s.log.Warn("event_service: hr.hiring_request.notify payload failed, drop",
			"err", err, "hiring_request_id", ev.HiringRequestID)
		return nil
	}

	return s.uow.Do(ctx, func(ctx context.Context, repos repositories.Repositories) error {
		outbox, err := domain.NewPendingOutbox(hrEventNotifyType, notifyPayload)
		if err != nil {
			return fmt.Errorf("event_service: build hiring_request outbox: %w", err)
		}
		if err := repos.Outbox().Save(ctx, outbox); err != nil {
			return fmt.Errorf("event_service: save hiring_request outbox: %w", err)
		}
		s.log.Info("event_service: hiring_request telegram queued",
			"event_type", ev.EventType,
			"hiring_request_id", ev.HiringRequestID,
			"actor_name", ev.ActorName,
			"outbox_id", outbox.ID,
			"outbox_event", hrEventNotifyType,
		)
		return nil
	})
}

// handleEntityChanged оставлен для разбора message.*.changed.
// Точка входа Handle его не вызывает: в этом срезе логистические события отбрасываются.
func (s *EventServiceImpl) handleEntityChanged(ctx context.Context, body []byte) error {
	ce, err := DeserializeToChangeEvent(body)
	if err != nil {
		s.log.Warn("event_service: invalid entity-changed json, drop", "err", err, "size", len(body))
		return nil
	}
	if ce.EventType == "" {
		s.log.Warn("event_service: empty event_type, drop", "event_type", ce.EventType)
		return nil
	}
	// EntityID == 0 допустим только для message.approval.distribution
	// (согласование распределения не имеет числовой сущности — только строковый uid).
	if ce.EntityID == 0 && ce.EntityKind != "distribution" {
		s.log.Warn("event_service: empty entity_id, drop",
			"event_type", ce.EventType, "entity_id", ce.EntityID)
		return nil
	}

	var posted *domain.Message
	err = s.uow.Do(ctx, func(ctx context.Context, repos repositories.Repositories) error {
		channelID, err := s.ensureChannel(ctx, repos, ce)
		if err != nil {
			return err
		}

		content, err := ce.RenderMessage()
		if err != nil {
			s.log.Warn("event_service: render failed, drop",
				"err", err,
				"event_type", ce.EventType,
				"entity_id", ce.EntityID,
				"fields_changed", len(ce.Changed),
			)
			return nil
		}

		msg, err := domain.SendMessageToChannel(content, channelID)
		if err != nil {
			return fmt.Errorf("event_service: build message: %w", err)
		}
		msg.WithEntity(ce.EntityKind, ce.EntityID)
		if err := repos.Messages().Save(ctx, msg); err != nil {
			return fmt.Errorf("event_service: save message: %w", err)
		}
		posted = msg

		s.log.Info("event_service: message posted",
			"event_type", ce.EventType,
			"entity_id", ce.EntityID,
			"channel_id", channelID,
			"company", ce.CompanyName,
			"actor_user_id", ce.ActorUserID,
			"fields_changed", len(ce.Changed),
		)
		return nil
	})
	if err != nil {
		return err
	}
	if posted != nil && s.dispatcher != nil {
		s.dispatcher.DispatchMessage(ctx, posted)
	}
	return nil
}

// ensureChannel находит глобальный канал для типа события, либо создаёт новый.
// Канал один на ChannelEvent (для связанных типов — общий: downtime.registered и
// downtime.resolved пишут в один канал «Простои»); идентифицируется парой
// (channelEvent, eventTypeChannelEntityID).
func (s *EventServiceImpl) ensureChannel(
	ctx context.Context,
	repos repositories.Repositories,
	ce ChangeEvent,
) (int, error) {
	channelEvent := ce.ChannelEvent()
	ch, err := repos.Channels().FindByEntity(ctx, channelEvent, eventTypeChannelEntityID)
	if err == nil && ch != nil {
		return ch.ID, nil
	}
	if err != nil && !errors.Is(err, apperrors.ErrNotFound) {
		return 0, fmt.Errorf("event_service: find channel: %w", err)
	}

	// Канала нет — создаём (имя стабильно, без привязки к конкретной сущности).
	ch, err = domain.NewChannel(ce.ChannelName(), channelEvent, eventTypeChannelEntityID)
	if err != nil {
		return 0, fmt.Errorf("event_service: new channel: %w", err)
	}
	if err := repos.Channels().Save(ctx, ch); err != nil {
		return 0, fmt.Errorf("event_service: create channel: %w", err)
	}
	s.log.Info("event_service: channel created",
		"event_type", ce.EventType,
		"channel_event", channelEvent,
		"channel_id", ch.ID,
		"name", ch.Name,
	)
	return ch.ID, nil
}
