package usecases

import (
	"context"
	"fmt"
	"strconv"
	"sync"
	"testing"

	"github.com/google/uuid"
	"github.com/yourusername/message-service/internal/domain/contracts/providers"
	"github.com/yourusername/message-service/internal/domain/contracts/realtime"
	repositories "github.com/yourusername/message-service/internal/domain/contracts/repositories"
	domain "github.com/yourusername/message-service/internal/domain/entities"
	apperrors "github.com/yourusername/message-service/internal/pkg/errors"
)

type captureNotifier struct {
	mu        sync.Mutex
	userCalls []struct {
		ids []uuid.UUID
		n   realtime.Notification
	}
	roleCalls []struct {
		roleID int
		n      realtime.Notification
	}
}

func (c *captureNotifier) NotifyUsers(_ context.Context, userIDs []uuid.UUID, n realtime.Notification) {
	c.mu.Lock()
	defer c.mu.Unlock()
	cp := append([]uuid.UUID(nil), userIDs...)
	c.userCalls = append(c.userCalls, struct {
		ids []uuid.UUID
		n   realtime.Notification
	}{ids: cp, n: n})
}

type capturePusher struct {
	mu        sync.Mutex
	userCalls []struct {
		ids []uuid.UUID
		n   realtime.Notification
	}
}

type dispatcherUserProvider struct {
	pages []providers.UserPage
}

func (p *dispatcherUserProvider) GetUserIDs(_ context.Context, page, _ int) (providers.UserPage, error) {
	if page < 1 || page > len(p.pages) {
		return providers.UserPage{HasRoles: true}, nil
	}
	return p.pages[page-1], nil
}

func (c *capturePusher) PushToUsers(_ context.Context, userIDs []uuid.UUID, n realtime.Notification) {
	c.mu.Lock()
	defer c.mu.Unlock()
	cp := append([]uuid.UUID(nil), userIDs...)
	c.userCalls = append(c.userCalls, struct {
		ids []uuid.UUID
		n   realtime.Notification
	}{ids: cp, n: n})
}

func (c *captureNotifier) NotifyRole(_ context.Context, roleID int, n realtime.Notification) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.roleCalls = append(c.roleCalls, struct {
		roleID int
		n      realtime.Notification
	}{roleID: roleID, n: n})
}

type dispSettingsRepo struct {
	byKey map[string]*domain.SettingsChannel
}

func settingsKey(uid uuid.UUID, ch int) string {
	return uid.String() + ":" + strconv.Itoa(ch)
}

func (s *dispSettingsRepo) Save(context.Context, *domain.SettingsChannel) error { return nil }
func (s *dispSettingsRepo) FindByID(context.Context, int) (*domain.SettingsChannel, error) {
	return nil, apperrors.ErrNotFound
}
func (s *dispSettingsRepo) FindByUserAndChannel(_ context.Context, userID uuid.UUID, channelID int) (*domain.SettingsChannel, error) {
	if st, ok := s.byKey[settingsKey(userID, channelID)]; ok {
		return st, nil
	}
	// Как в postgres-репозитории: ErrNotFound обёрнут в fmt.Errorf.
	return nil, fmt.Errorf("settings repository: user %s channel %d: %w", userID, channelID, apperrors.ErrNotFound)
}
func (s *dispSettingsRepo) Update(context.Context, *domain.SettingsChannel) error { return nil }
func (s *dispSettingsRepo) Delete(context.Context, int) error                     { return nil }
func (s *dispSettingsRepo) FindAllByUserID(_ context.Context, userID uuid.UUID) ([]*domain.SettingsChannel, error) {
	out := make([]*domain.SettingsChannel, 0)
	for _, st := range s.byKey {
		if st != nil && st.UserID == userID {
			out = append(out, st)
		}
	}
	return out, nil
}

type channelRepoWithID struct {
	byID map[int]*domain.Channel
}

func (c *channelRepoWithID) Save(_ context.Context, ch *domain.Channel) error {
	if c.byID == nil {
		c.byID = map[int]*domain.Channel{}
	}
	c.byID[ch.ID] = ch
	return nil
}
func (c *channelRepoWithID) FindByID(_ context.Context, id int) (*domain.Channel, error) {
	if ch, ok := c.byID[id]; ok {
		return ch, nil
	}
	return nil, apperrors.ErrNotFound
}
func (c *channelRepoWithID) FindByEntity(context.Context, string, int) (*domain.Channel, error) {
	return nil, apperrors.ErrNotFound
}
func (c *channelRepoWithID) FindByIDs(context.Context, []int) ([]*domain.Channel, error) {
	return nil, nil
}
func (c *channelRepoWithID) FindAllByUserID(_ context.Context, userID uuid.UUID) ([]*domain.Channel, error) {
	out := make([]*domain.Channel, 0)
	for _, ch := range c.byID {
		if ch == nil {
			continue
		}
		for _, uid := range ch.UsersIds {
			if uid == userID {
				out = append(out, ch)
				break
			}
		}
	}
	return out, nil
}
func (c *channelRepoWithID) FindAll(context.Context) ([]*domain.Channel, error) { return nil, nil }
func (c *channelRepoWithID) Update(context.Context, *domain.Channel) error      { return nil }
func (c *channelRepoWithID) Delete(context.Context, int) error                  { return nil }
func (c *channelRepoWithID) AddUserToChannel(context.Context, int, uuid.UUID) error {
	return nil
}
func (c *channelRepoWithID) RemoveUserFromChannel(context.Context, int, uuid.UUID) error {
	return nil
}
func (c *channelRepoWithID) AddUsers(context.Context, int, []uuid.UUID) error { return nil }
func (c *channelRepoWithID) RemoveUsers(context.Context, int, []uuid.UUID) error {
	return nil
}

type chanUoW struct {
	ch  repositories.ChannelRepository
	st  repositories.SettingsChannelRepository
	msg repositories.MessageRepository
}

func (u *chanUoW) Do(ctx context.Context, fn func(context.Context, repositories.Repositories) error) error {
	return fn(ctx, &chanRepos{ch: u.ch, st: u.st, msg: u.msg})
}

type chanRepos struct {
	ch  repositories.ChannelRepository
	st  repositories.SettingsChannelRepository
	msg repositories.MessageRepository
}

func (r *chanRepos) Channels() repositories.ChannelRepository { return r.ch }
func (r *chanRepos) Messages() repositories.MessageRepository {
	if r.msg != nil {
		return r.msg
	}
	return &fakeMessageRepo{}
}
func (r *chanRepos) Settings() repositories.SettingsChannelRepository { return r.st }
func (r *chanRepos) Outbox() repositories.OutboxRepository {
	return &fakeOutboxRepo{}
}

func TestNotificationDispatcher_ChannelMuteAndDefault(t *testing.T) {
	u1 := uuid.MustParse("11111111-1111-1111-1111-111111111111")
	u2 := uuid.MustParse("22222222-2222-2222-2222-222222222222")
	u3 := uuid.MustParse("33333333-3333-3333-3333-333333333333")

	ch := &domain.Channel{ID: 5, UsersIds: []uuid.UUID{u1, u2, u3}}
	chRepo := &channelRepoWithID{byID: map[int]*domain.Channel{5: ch}}

	st := &dispSettingsRepo{byKey: map[string]*domain.SettingsChannel{}}
	st.byKey[settingsKey(u2, 5)] = &domain.SettingsChannel{UserID: u2, ChannelID: 5, IsSendPushMessage: false}
	st.byKey[settingsKey(u3, 5)] = &domain.SettingsChannel{UserID: u3, ChannelID: 5, IsSendPushMessage: true}

	notifier := &captureNotifier{}
	pusher := &capturePusher{}
	d := NewNotificationDispatcher(&chanUoW{ch: chRepo, st: st}, notifier, pusher, nil, nil)

	chID := 5
	msg := &domain.Message{ID: 9, Content: "hello", ChannelID: &chID}
	d.DispatchMessage(context.Background(), msg)

	if len(notifier.userCalls) != 1 {
		t.Fatalf("expected 1 NotifyUsers, got %d", len(notifier.userCalls))
	}
	got := notifier.userCalls[0].ids
	want := map[uuid.UUID]bool{u1: true, u3: true}
	if len(got) != 2 {
		t.Fatalf("recipients = %v, want u1+u3 (u2 muted)", got)
	}
	for _, id := range got {
		if !want[id] {
			t.Errorf("unexpected recipient %s", id)
		}
	}
	if notifier.userCalls[0].n.Content != "hello" || notifier.userCalls[0].n.ID != 9 {
		t.Errorf("payload = %+v", notifier.userCalls[0].n)
	}
	if len(pusher.userCalls) != 1 {
		t.Fatalf("expected 1 Web Push, got %d", len(pusher.userCalls))
	}
	if len(pusher.userCalls[0].ids) != 2 {
		t.Fatalf("web push recipients = %v, want u1+u3", pusher.userCalls[0].ids)
	}
}

func TestNotificationDispatcher_PersonalAndRole(t *testing.T) {
	notifier := &captureNotifier{}
	pusher := &capturePusher{}
	uid := uuid.MustParse("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
	roleUser := uuid.MustParse("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
	userProvider := &dispatcherUserProvider{pages: []providers.UserPage{{
		HasRoles: true,
		Users:    []providers.UserRef{{ID: roleUser, RoleID: 3}},
	}}}
	d := NewNotificationDispatcher(&chanUoW{
		ch: &channelRepoWithID{},
		st: &dispSettingsRepo{byKey: map[string]*domain.SettingsChannel{}},
	}, notifier, pusher, userProvider, nil)

	et := "trip"
	eid := 10
	msgUser := &domain.Message{
		ID: 1, Content: "personal", UserId: &uid,
		EntityType: &et, EntityID: &eid,
	}
	d.DispatchMessage(context.Background(), msgUser)
	if len(notifier.userCalls) != 1 || len(notifier.userCalls[0].ids) != 1 || notifier.userCalls[0].ids[0] != uid {
		t.Fatalf("personal notify = %+v", notifier.userCalls)
	}
	n := notifier.userCalls[0].n
	if n.EntityType == nil || *n.EntityType != "trip" || n.EntityID == nil || *n.EntityID != 10 {
		t.Fatalf("entity passthrough = %+v", n)
	}

	role := 3
	msgRole := &domain.Message{ID: 2, Content: "role", RoleId: &role}
	d.DispatchMessage(context.Background(), msgRole)
	if len(notifier.roleCalls) != 1 || notifier.roleCalls[0].roleID != 3 {
		t.Fatalf("role notify = %+v", notifier.roleCalls)
	}
	if len(pusher.userCalls) != 2 {
		t.Fatalf("personal and role must send Web Push, got %d", len(pusher.userCalls))
	}
	if got := pusher.userCalls[0].ids; len(got) != 1 || got[0] != uid {
		t.Fatalf("personal push recipients = %v, want %s", got, uid)
	}
	if got := pusher.userCalls[1].ids; len(got) != 1 || got[0] != roleUser {
		t.Fatalf("role push recipients = %v, want %s", got, roleUser)
	}
}

func TestNotificationDispatcher_LoginSuccessDoesNotSendDirectPush(t *testing.T) {
	notifier := &captureNotifier{}
	pusher := &capturePusher{}
	uid := uuid.MustParse("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
	d := NewNotificationDispatcher(nil, notifier, pusher, nil, nil)
	d.DispatchMessage(context.Background(), &domain.Message{
		ID: 1, Content: loginSuccessContent, UserId: &uid,
	})
	if len(notifier.userCalls) != 1 {
		t.Fatalf("login must still be sent over WS, got %d calls", len(notifier.userCalls))
	}
	if len(pusher.userCalls) != 0 {
		t.Fatalf("login must not send Web Push, got %d calls", len(pusher.userCalls))
	}
}

func TestNotificationDispatcher_NilSafe(t *testing.T) {
	var d *NotificationDispatcherImpl
	d.DispatchMessage(context.Background(), &domain.Message{ID: 1})

	d2 := NewNotificationDispatcher(nil, nil, nil, nil, nil)
	d2.DispatchMessage(context.Background(), &domain.Message{ID: 1})
}
