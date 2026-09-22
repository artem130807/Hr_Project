package usecases

import (
	"context"
	"sync"
	"testing"

	"github.com/google/uuid"

	dto "github.com/yourusername/message-service/internal/application/dtos/push"
	domain "github.com/yourusername/message-service/internal/domain/entities"
	apperrors "github.com/yourusername/message-service/internal/pkg/errors"
)

type memPushRepo struct {
	mu   sync.Mutex
	byEP map[string]*domain.PushSubscription
}

func (m *memPushRepo) Upsert(_ context.Context, sub *domain.PushSubscription) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.byEP == nil {
		m.byEP = map[string]*domain.PushSubscription{}
	}
	cp := *sub
	cp.ID = len(m.byEP) + 1
	m.byEP[sub.Endpoint] = &cp
	sub.ID = cp.ID
	return nil
}

func (m *memPushRepo) DeleteByUserAndEndpoint(_ context.Context, userID uuid.UUID, endpoint string) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	got, ok := m.byEP[endpoint]
	if ok && got.UserID == userID {
		delete(m.byEP, endpoint)
	}
	return nil
}

func (m *memPushRepo) DeleteByEndpoint(_ context.Context, endpoint string) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	delete(m.byEP, endpoint)
	return nil
}

func (m *memPushRepo) FindByUserIDs(_ context.Context, userIDs []uuid.UUID) ([]*domain.PushSubscription, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	want := map[uuid.UUID]bool{}
	for _, id := range userIDs {
		want[id] = true
	}
	out := make([]*domain.PushSubscription, 0)
	for _, sub := range m.byEP {
		if want[sub.UserID] {
			cp := *sub
			out = append(out, &cp)
		}
	}
	return out, nil
}

func TestPushSubscriptionService_VapidDisabledWithoutKey(t *testing.T) {
	svc := NewPushSubscriptionService(&memPushRepo{}, stubContextAuth{userID: uuid.MustParse("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")}, "")
	got, err := svc.VapidPublicKey()
	if err != nil {
		t.Fatal(err)
	}
	if got.Enabled || got.PublicKey != "" {
		t.Fatalf("disabled key = %+v", got)
	}
	err = svc.Subscribe(context.Background(), &dto.SubscribeDto{
		Endpoint: "https://push.example/abc",
		Keys:     dto.SubscribeKeys{P256dh: "p", Auth: "a"},
	})
	if err == nil {
		t.Fatal("subscribe must fail when VAPID is disabled")
	}
}

func TestPushSubscriptionService_SubscribeAndUnsubscribe(t *testing.T) {
	uid := uuid.MustParse("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
	repo := &memPushRepo{}
	svc := NewPushSubscriptionService(repo, stubContextAuth{userID: uid, roleID: 2}, "BK_public")

	key, err := svc.VapidPublicKey()
	if err != nil || !key.Enabled || key.PublicKey != "BK_public" {
		t.Fatalf("vapid = %+v err=%v", key, err)
	}

	err = svc.Subscribe(context.Background(), &dto.SubscribeDto{
		Endpoint: "https://push.example/abc",
		Keys:     dto.SubscribeKeys{P256dh: "p", Auth: "a"},
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(repo.byEP) != 1 {
		t.Fatalf("stored %d", len(repo.byEP))
	}

	other := uuid.MustParse("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
	svcOther := NewPushSubscriptionService(repo, stubContextAuth{userID: other, roleID: 2}, "BK_public")
	if err := svcOther.Unsubscribe(context.Background(), &dto.UnsubscribeDto{Endpoint: "https://push.example/abc"}); err != nil {
		t.Fatal(err)
	}
	if len(repo.byEP) != 1 {
		t.Fatal("other user must not delete someone else's subscription")
	}

	if err := svc.Unsubscribe(context.Background(), &dto.UnsubscribeDto{Endpoint: "https://push.example/abc"}); err != nil {
		t.Fatal(err)
	}
	if len(repo.byEP) != 0 {
		t.Fatal("owner unsubscribe should delete")
	}
}

func TestPushSubscriptionService_RejectsHTTPEndpoint(t *testing.T) {
	uid := uuid.MustParse("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
	svc := NewPushSubscriptionService(&memPushRepo{}, stubContextAuth{userID: uid}, "BK")
	err := svc.Subscribe(context.Background(), &dto.SubscribeDto{
		Endpoint: "http://insecure.example/x",
		Keys:     dto.SubscribeKeys{P256dh: "p", Auth: "a"},
	})
	if err == nil {
		t.Fatal("expected validation error")
	}
	var app *apperrors.AppError
	if !errorAsApp(err, &app) {
		t.Fatalf("want AppError, got %T %v", err, err)
	}
}

func errorAsApp(err error, target **apperrors.AppError) bool {
	if err == nil {
		return false
	}
	e, ok := err.(*apperrors.AppError)
	if !ok {
		return false
	}
	*target = e
	return true
}
