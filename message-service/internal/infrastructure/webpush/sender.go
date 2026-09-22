package webpush

import (
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"strings"
	"time"

	"github.com/SherClockHolmes/webpush-go"
	"github.com/google/uuid"

	"github.com/yourusername/message-service/internal/domain/contracts/realtime"
	repositories "github.com/yourusername/message-service/internal/domain/contracts/repositories"
	domain "github.com/yourusername/message-service/internal/domain/entities"
)

var _ realtime.WebPusher = (*Sender)(nil)

// Deliverer отправляет один Web Push. Вынесен для моков.
type Deliverer interface {
	Deliver(ctx context.Context, sub *domain.PushSubscription, payload []byte) (status int, err error)
}

type vapidDeliverer struct {
	public  string
	private string
	subject string
}

func (d vapidDeliverer) Deliver(ctx context.Context, sub *domain.PushSubscription, payload []byte) (int, error) {
	resp, err := webpush.SendNotificationWithContext(ctx, payload, &webpush.Subscription{
		Endpoint: sub.Endpoint,
		Keys: webpush.Keys{
			Auth:   sub.Auth,
			P256dh: sub.P256dh,
		},
	}, &webpush.Options{
		Subscriber:      d.subject,
		VAPIDPublicKey:  d.public,
		VAPIDPrivateKey: d.private,
		TTL:             12 * 3600,
		Urgency:         webpush.UrgencyHigh,
	})
	if err != nil {
		return 0, err
	}
	defer resp.Body.Close()
	return resp.StatusCode, nil
}

// Sender реализует realtime.WebPusher.
type Sender struct {
	repo      repositories.PushSubscriptionRepository
	deliverer Deliverer
	log       *slog.Logger
}

func NewSender(
	repo repositories.PushSubscriptionRepository,
	publicKey, privateKey, subject string,
	log *slog.Logger,
) *Sender {
	if log == nil {
		log = slog.Default()
	}
	publicKey = strings.TrimSpace(publicKey)
	privateKey = strings.TrimSpace(privateKey)
	if subject == "" {
		subject = "mailto:noreply@localhost"
	}
	if publicKey == "" || privateKey == "" || repo == nil {
		return nil
	}
	return &Sender{
		repo: repo,
		deliverer: vapidDeliverer{
			public:  publicKey,
			private: privateKey,
			subject: subject,
		},
		log: log.With("component", "web_push"),
	}
}

func NewSenderWithDeliverer(
	repo repositories.PushSubscriptionRepository,
	deliverer Deliverer,
	log *slog.Logger,
) *Sender {
	if log == nil {
		log = slog.Default()
	}
	return &Sender{repo: repo, deliverer: deliverer, log: log.With("component", "web_push")}
}

// PushToUsers шлёт Web Push офлайн. Не блокирует HTTP-запрос создания сообщения.
func (s *Sender) PushToUsers(_ context.Context, userIDs []uuid.UUID, n realtime.Notification) {
	if s == nil || s.repo == nil || s.deliverer == nil || len(userIDs) == 0 {
		return
	}
	ids := append([]uuid.UUID(nil), userIDs...)
	go s.send(ids, n)
}

func (s *Sender) send(userIDs []uuid.UUID, n realtime.Notification) {
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()

	subs, err := s.repo.FindByUserIDs(ctx, userIDs)
	if err != nil {
		s.log.Warn("list subscriptions failed", "err", err)
		return
	}
	if len(subs) == 0 {
		return
	}

	payload, err := json.Marshal(pushPayload{
		Type:       n.Type,
		ID:         n.ID,
		Content:    n.Content,
		IsRead:     n.IsRead,
		IsSend:     n.IsSend,
		UserID:     n.UserID,
		RoleID:     n.RoleID,
		ChannelID:  n.ChannelID,
		EntityType: n.EntityType,
		EntityID:   n.EntityID,
		CreatedAt:  n.CreatedAt,
		URL:        n.ClickPath(),
	})
	if err != nil {
		s.log.Warn("marshal push payload", "err", err)
		return
	}

	for _, sub := range subs {
		if sub == nil {
			continue
		}
		status, err := s.deliverer.Deliver(ctx, sub, payload)
		if err != nil {
			s.log.Warn("web push deliver failed", "endpoint", sub.Endpoint, "err", err)
			continue
		}
		if status == http.StatusGone || status == http.StatusNotFound {
			if delErr := s.repo.DeleteByEndpoint(ctx, sub.Endpoint); delErr != nil {
				s.log.Warn("delete stale subscription", "err", delErr)
			}
			continue
		}
		if status >= 400 {
			s.log.Warn("web push rejected", "status", status, "endpoint", sub.Endpoint)
		}
	}
}

type pushPayload struct {
	Type       string      `json:"type"`
	ID         int         `json:"id"`
	Content    string      `json:"content"`
	IsRead     bool        `json:"is_read"`
	IsSend     bool        `json:"is_send"`
	UserID     *uuid.UUID  `json:"user_id,omitempty"`
	RoleID     *int        `json:"role_id,omitempty"`
	ChannelID  *int        `json:"channel_id,omitempty"`
	EntityType *string     `json:"entity_type,omitempty"`
	EntityID   *int        `json:"entity_id,omitempty"`
	CreatedAt  time.Time  `json:"created_at"`
	URL        string      `json:"url"`
}
