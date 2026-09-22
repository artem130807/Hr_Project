package channelsync

import (
	"context"
	"testing"
	"time"

	"github.com/google/uuid"

	providers "github.com/yourusername/message-service/internal/domain/contracts/providers"
	repositories "github.com/yourusername/message-service/internal/domain/contracts/repositories"
	domain "github.com/yourusername/message-service/internal/domain/entities"
	"github.com/yourusername/message-service/internal/pkg/config"
)

type stubUserProvider struct {
	pages []providers.UserPage
	i     int
}

func (s *stubUserProvider) GetUserIDs(context.Context, int, int) (providers.UserPage, error) {
	if s.i >= len(s.pages) {
		return providers.UserPage{}, nil
	}
	p := s.pages[s.i]
	s.i++
	return p, nil
}

type memChannelRepo struct {
	list []*domain.Channel
}

func (r *memChannelRepo) Save(context.Context, *domain.Channel) error { return nil }
func (r *memChannelRepo) FindByID(context.Context, int) (*domain.Channel, error) {
	return nil, nil
}
func (r *memChannelRepo) FindByEntity(context.Context, string, int) (*domain.Channel, error) {
	return nil, nil
}
func (r *memChannelRepo) FindAllByUserID(context.Context, uuid.UUID) ([]*domain.Channel, error) {
	return nil, nil
}
func (r *memChannelRepo) FindAll(context.Context) ([]*domain.Channel, error) {
	return r.list, nil
}
func (r *memChannelRepo) Update(context.Context, *domain.Channel) error { return nil }
func (r *memChannelRepo) Delete(context.Context, int) error             { return nil }
func (r *memChannelRepo) AddUserToChannel(context.Context, int, uuid.UUID) error {
	return nil
}
func (r *memChannelRepo) RemoveUserFromChannel(context.Context, int, uuid.UUID) error {
	return nil
}
func (r *memChannelRepo) FindByIDs(context.Context, []int) ([]*domain.Channel, error) {
	return nil, nil
}

func (r *memChannelRepo) AddUsers(_ context.Context, channelID int, userIDs []uuid.UUID) error {
	// Как в Postgres: обновляется БД, in-memory Channel дополняет Worker.applyPage.
	return nil
}

func (r *memChannelRepo) RemoveUsers(_ context.Context, channelID int, userIDs []uuid.UUID) error {
	ch := r.byID(channelID)
	if ch == nil {
		return nil
	}
	drop := toUUIDSet(userIDs)
	kept := ch.UsersIds[:0]
	for _, id := range ch.UsersIds {
		if !drop[id] {
			kept = append(kept, id)
		}
	}
	ch.UsersIds = kept
	return nil
}

func (r *memChannelRepo) byID(id int) *domain.Channel {
	for _, ch := range r.list {
		if ch.ID == id {
			return ch
		}
	}
	return nil
}

type memRepos struct{ ch *memChannelRepo }

func (r memRepos) Channels() repositories.ChannelRepository         { return r.ch }
func (r memRepos) Messages() repositories.MessageRepository         { return nil }
func (r memRepos) Settings() repositories.SettingsChannelRepository { return nil }
func (r memRepos) Outbox() repositories.OutboxRepository            { return nil }

type memUoW struct{ repos memRepos }

func (u *memUoW) Do(ctx context.Context, fn func(context.Context, repositories.Repositories) error) error {
	return fn(ctx, u.repos)
}

func testCfg() config.ChannelSyncConfig {
	return config.ChannelSyncConfig{
		PageSize:       50,
		RateLimit:      time.Nanosecond,
		RequestTimeout: time.Second,
	}
}

func mustUser(role string) providers.UserRef {
	return providers.UserRef{ID: uuid.New(), RoleName: role}
}

func channelByType(list []*domain.Channel, entityType string) *domain.Channel {
	for _, ch := range list {
		if ch.EntityType == entityType {
			return ch
		}
	}
	return nil
}

func TestWorker_HiringRequestChannelOnlyAllowlistedRoles(t *testing.T) {
	admin := mustUser("Админ")
	leader := mustUser("Руководитель")
	hr := mustUser("HR")
	dept := mustUser("Руководитель отдела")
	manager := mustUser("Менеджер")

	open := &domain.Channel{ID: 1, Name: "Простои", EntityType: "message.downtime", EntityID: 1}
	hiring := &domain.Channel{ID: 2, Name: "Заявки на подбор", EntityType: HiringRequestChannelEvent, EntityID: 1}
	repo := &memChannelRepo{list: []*domain.Channel{open, hiring}}

	page := providers.UserPage{
		HasRoles: true,
		HasMore:  false,
		Users:    []providers.UserRef{admin, leader, hr, dept, manager},
		UserIDs:  []uuid.UUID{admin.ID, leader.ID, hr.ID, dept.ID, manager.ID},
	}
	w := New(&memUoW{repos: memRepos{ch: repo}}, &stubUserProvider{pages: []providers.UserPage{page}}, testCfg(), nil)
	if err := w.Run(context.Background()); err != nil {
		t.Fatalf("run: %v", err)
	}

	open = channelByType(repo.list, "message.downtime")
	hiring = channelByType(repo.list, HiringRequestChannelEvent)
	if len(open.UsersIds) != 5 {
		t.Fatalf("open channel members = %d, want 5", len(open.UsersIds))
	}
	have := toUUIDSet(hiring.UsersIds)
	if !have[admin.ID] || !have[leader.ID] || !have[hr.ID] || !have[dept.ID] {
		t.Fatalf("hiring missing allowlisted users: %v", hiring.UsersIds)
	}
	if have[manager.ID] {
		t.Fatal("manager must not see hiring_request channel")
	}
	if len(hiring.UsersIds) != 4 {
		t.Fatalf("hiring members = %d, want 4", len(hiring.UsersIds))
	}
}

func TestWorker_PrunesUnauthorizedFromHiringChannel(t *testing.T) {
	admin := mustUser("Админ")
	manager := mustUser("Менеджер")
	hiring := &domain.Channel{
		ID:         2,
		Name:       "Заявки на подбор",
		EntityType: HiringRequestChannelEvent,
		EntityID:   1,
		UsersIds:   []uuid.UUID{admin.ID, manager.ID},
	}
	repo := &memChannelRepo{list: []*domain.Channel{hiring}}
	page := providers.UserPage{
		HasRoles: true,
		HasMore:  false,
		Users:    []providers.UserRef{admin, manager},
		UserIDs:  []uuid.UUID{admin.ID, manager.ID},
	}
	w := New(&memUoW{repos: memRepos{ch: repo}}, &stubUserProvider{pages: []providers.UserPage{page}}, testCfg(), nil)
	if err := w.Run(context.Background()); err != nil {
		t.Fatalf("run: %v", err)
	}
	have := toUUIDSet(hiring.UsersIds)
	if !have[admin.ID] {
		t.Fatal("admin must stay")
	}
	if have[manager.ID] {
		t.Fatal("manager must be pruned from hiring_request")
	}
}

func TestWorker_WithoutRoleMetadataDoesNotFillOrPruneHiring(t *testing.T) {
	manager := mustUser("Менеджер")
	hiring := &domain.Channel{
		ID:         2,
		EntityType: HiringRequestChannelEvent,
		EntityID:   1,
		UsersIds:   []uuid.UUID{manager.ID},
	}
	open := &domain.Channel{ID: 1, EntityType: "message.downtime", EntityID: 1}
	repo := &memChannelRepo{list: []*domain.Channel{open, hiring}}
	newbie := uuid.New()
	page := providers.UserPage{
		HasRoles: false,
		HasMore:  false,
		UserIDs:  []uuid.UUID{manager.ID, newbie},
	}
	w := New(&memUoW{repos: memRepos{ch: repo}}, &stubUserProvider{pages: []providers.UserPage{page}}, testCfg(), nil)
	if err := w.Run(context.Background()); err != nil {
		t.Fatalf("run: %v", err)
	}
	if len(hiring.UsersIds) != 1 || hiring.UsersIds[0] != manager.ID {
		t.Fatalf("hiring membership must stay untouched without roles, got %v", hiring.UsersIds)
	}
	if len(open.UsersIds) != 2 {
		t.Fatalf("open channel should still sync all ids, got %d", len(open.UsersIds))
	}
}
