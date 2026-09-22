package webpush

import (
	"context"
	"encoding/json"
	"net/http"
	"sync"
	"testing"
	"time"

	"github.com/google/uuid"

	"github.com/yourusername/message-service/internal/domain/contracts/realtime"
	domain "github.com/yourusername/message-service/internal/domain/entities"
)

type fakeDeliverer struct {
	mu      sync.Mutex
	codes   map[string]int
	calls   []string
	payload []byte
}

func (f *fakeDeliverer) Deliver(_ context.Context, sub *domain.PushSubscription, payload []byte) (int, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.calls = append(f.calls, sub.Endpoint)
	f.payload = payload
	if f.codes != nil {
		if c, ok := f.codes[sub.Endpoint]; ok {
			return c, nil
		}
	}
	return http.StatusCreated, nil
}

type fakeSubRepo struct {
	mu   sync.Mutex
	subs []*domain.PushSubscription
}

func (f *fakeSubRepo) Upsert(context.Context, *domain.PushSubscription) error { return nil }
func (f *fakeSubRepo) DeleteByUserAndEndpoint(context.Context, uuid.UUID, string) error {
	return nil
}
func (f *fakeSubRepo) DeleteByEndpoint(_ context.Context, endpoint string) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	out := f.subs[:0]
	for _, s := range f.subs {
		if s.Endpoint != endpoint {
			out = append(out, s)
		}
	}
	f.subs = out
	return nil
}
func (f *fakeSubRepo) FindByUserIDs(_ context.Context, userIDs []uuid.UUID) ([]*domain.PushSubscription, error) {
	want := map[uuid.UUID]bool{}
	for _, id := range userIDs {
		want[id] = true
	}
	out := make([]*domain.PushSubscription, 0)
	for _, s := range f.subs {
		if want[s.UserID] {
			out = append(out, s)
		}
	}
	return out, nil
}

func TestSender_SendsOnlyMatchingUsersAndDropsGone(t *testing.T) {
	u1 := uuid.MustParse("11111111-1111-1111-1111-111111111111")
	u2 := uuid.MustParse("22222222-2222-2222-2222-222222222222")
	u3 := uuid.MustParse("33333333-3333-3333-3333-333333333333")
	repo := &fakeSubRepo{subs: []*domain.PushSubscription{
		{UserID: u1, Endpoint: "https://push/1", P256dh: "p", Auth: "a"},
		{UserID: u2, Endpoint: "https://push/2-gone", P256dh: "p", Auth: "a"},
		{UserID: u3, Endpoint: "https://push/3-skip", P256dh: "p", Auth: "a"},
	}}
	d := &fakeDeliverer{codes: map[string]int{
		"https://push/1":      http.StatusCreated,
		"https://push/2-gone": http.StatusGone,
	}}
	s := NewSenderWithDeliverer(repo, d, nil)

	et := "trip"
	eid := 10
	ch := 5
	s.send([]uuid.UUID{u1, u2}, realtime.Notification{
		Type:       "notification",
		ID:         9,
		Content:    "hello",
		ChannelID:  &ch,
		EntityType: &et,
		EntityID:   &eid,
		CreatedAt:  time.Date(2026, 9, 2, 12, 0, 0, 0, time.UTC),
	})

	d.mu.Lock()
	defer d.mu.Unlock()
	if len(d.calls) != 2 {
		t.Fatalf("deliver calls = %v, want u1+u2", d.calls)
	}
	var payload map[string]any
	if err := json.Unmarshal(d.payload, &payload); err != nil {
		t.Fatal(err)
	}
	if payload["url"] != "/trips/10" {
		t.Fatalf("url = %v", payload["url"])
	}
	if payload["content"] != "hello" {
		t.Fatalf("content = %v", payload["content"])
	}

	repo.mu.Lock()
	defer repo.mu.Unlock()
	if len(repo.subs) != 2 {
		t.Fatalf("after 410 expected 2 subs (u1+u3), got %d", len(repo.subs))
	}
	for _, sub := range repo.subs {
		if sub.Endpoint == "https://push/2-gone" {
			t.Fatal("gone subscription must be deleted")
		}
	}
}

func TestNewSender_NilWithoutKeys(t *testing.T) {
	if got := NewSender(&fakeSubRepo{}, "", "priv", "", nil); got != nil {
		t.Fatal("expected nil sender without public key")
	}
}
