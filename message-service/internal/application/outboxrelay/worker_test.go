package outboxrelay

import (
	"context"
	"sync"
	"testing"
	"time"

	repositories "github.com/yourusername/message-service/internal/domain/contracts/repositories"
	domain "github.com/yourusername/message-service/internal/domain/entities"
)

type fakePublisher struct {
	mu    sync.Mutex
	bodies [][]byte
	err   error
}

func (p *fakePublisher) Publish(_ context.Context, body []byte) error {
	if p.err != nil {
		return p.err
	}
	p.mu.Lock()
	defer p.mu.Unlock()
	p.bodies = append(p.bodies, append([]byte(nil), body...))
	return nil
}

func (p *fakePublisher) Close() error { return nil }

type fakeOutboxRepo struct {
	pending []*domain.OutboxMessage
}

func (f *fakeOutboxRepo) Save(context.Context, *domain.OutboxMessage) error { return nil }

func (f *fakeOutboxRepo) FindPending(_ context.Context, limit int) ([]*domain.OutboxMessage, error) {
	if limit > len(f.pending) {
		limit = len(f.pending)
	}
	return append([]*domain.OutboxMessage(nil), f.pending[:limit]...), nil
}

func (f *fakeOutboxRepo) MarkPublished(_ context.Context, id int64) error {
	kept := f.pending[:0]
	for _, p := range f.pending {
		if p.ID != id {
			kept = append(kept, p)
		}
	}
	f.pending = kept
	return nil
}

type fakeRepos struct {
	outbox *fakeOutboxRepo
}

func (r fakeRepos) Channels() repositories.ChannelRepository         { return nil }
func (r fakeRepos) Messages() repositories.MessageRepository         { return nil }
func (r fakeRepos) Settings() repositories.SettingsChannelRepository { return nil }
func (r fakeRepos) Outbox() repositories.OutboxRepository            { return r.outbox }

type fakeUoW struct{ repos fakeRepos }

func (u *fakeUoW) Do(ctx context.Context, fn func(context.Context, repositories.Repositories) error) error {
	return fn(ctx, u.repos)
}

func TestOutboxRelay_PublishesAndMarks(t *testing.T) {
	repo := &fakeOutboxRepo{
		pending: []*domain.OutboxMessage{
			{ID: 1, EventType: "hr.event.notify", Payload: []byte(`{"event_type":"hr.event.notify"}`), Status: domain.OutboxStatusPending},
		},
	}
	pub := &fakePublisher{}
	w := New(&fakeUoW{repos: fakeRepos{outbox: repo}}, pub, time.Hour, 10, nil)

	if err := w.flush(context.Background()); err != nil {
		t.Fatal(err)
	}
	if len(pub.bodies) != 1 {
		t.Fatalf("published=%d", len(pub.bodies))
	}
	if len(repo.pending) != 0 {
		t.Fatalf("pending left=%d", len(repo.pending))
	}
}
