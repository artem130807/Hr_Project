package usecases

import (
	"context"
	"errors"
	"testing"

	"github.com/google/uuid"

	messagefilters "github.com/yourusername/message-service/internal/application/usecases/contracts/filters/message_filters"
	repositories "github.com/yourusername/message-service/internal/domain/contracts/repositories"
	domain "github.com/yourusername/message-service/internal/domain/entities"
	apperrors "github.com/yourusername/message-service/internal/pkg/errors"
)

type stubContextAuth struct {
	userID uuid.UUID
	roleID int
	err    error
}

func (s stubContextAuth) GetUserID(context.Context) (uuid.UUID, error) {
	if s.err != nil {
		return uuid.Nil, s.err
	}
	return s.userID, nil
}

func (s stubContextAuth) GetRoleID(context.Context) (int, error) {
	if s.err != nil {
		return 0, s.err
	}
	return s.roleID, nil
}

// markReadMessageRepo — in-memory MessageRepository для сценария mark-as-read.
type markReadMessageRepo struct {
	messages []*domain.Message
	queries  []repositories.MessageQuery
}

func (r *markReadMessageRepo) Save(context.Context, *domain.Message) error { return nil }
func (r *markReadMessageRepo) FindByID(_ context.Context, id int) (*domain.Message, error) {
	for _, m := range r.messages {
		if m != nil && m.ID == id {
			return m, nil
		}
	}
	return nil, apperrors.ErrNotFound
}
func (r *markReadMessageRepo) FindByChannelID(context.Context, int) ([]*domain.Message, error) {
	return nil, nil
}
func (r *markReadMessageRepo) FindByUserID(context.Context, uuid.UUID) ([]*domain.Message, error) {
	return nil, nil
}
func (r *markReadMessageRepo) FindByRoleID(context.Context, int) ([]*domain.Message, error) {
	return nil, nil
}
func (r *markReadMessageRepo) FindByQuery(context.Context, repositories.MessageQuery) ([]*domain.Message, error) {
	return nil, nil
}
func (r *markReadMessageRepo) Update(context.Context, *domain.Message) error { return nil }
func (r *markReadMessageRepo) Delete(context.Context, int) error             { return nil }
func (r *markReadMessageRepo) FindUnsentByChannelID(context.Context, int) ([]*domain.Message, error) {
	return nil, nil
}
func (r *markReadMessageRepo) FindNotReadCountByUser(context.Context, uuid.UUID, int) (int, error) {
	return 0, nil
}
func (r *markReadMessageRepo) CountUnreadByChannelIDs(context.Context, []int) (map[int]int, error) {
	return map[int]int{}, nil
}

func (r *markReadMessageRepo) MarkAsReadByQuery(_ context.Context, q repositories.MessageQuery) (int, error) {
	r.queries = append(r.queries, q)
	n := 0
	for _, m := range r.messages {
		if m.IsRead {
			continue
		}
		if q.UserID != nil && (m.UserId == nil || *m.UserId != *q.UserID) {
			continue
		}
		if q.RoleID != nil && (m.RoleId == nil || *m.RoleId != *q.RoleID) {
			continue
		}
		if q.ChannelID != nil && (m.ChannelID == nil || *m.ChannelID != *q.ChannelID) {
			continue
		}
		m.MarkAsRead()
		n++
	}
	return n, nil
}

type markReadChannelRepo struct {
	byID map[int]*domain.Channel
}

func (c *markReadChannelRepo) Save(context.Context, *domain.Channel) error { return nil }
func (c *markReadChannelRepo) FindByID(_ context.Context, id int) (*domain.Channel, error) {
	if ch, ok := c.byID[id]; ok {
		return ch, nil
	}
	return nil, apperrors.ErrNotFound
}
func (c *markReadChannelRepo) FindByEntity(context.Context, string, int) (*domain.Channel, error) {
	return nil, apperrors.ErrNotFound
}
func (c *markReadChannelRepo) FindByIDs(context.Context, []int) ([]*domain.Channel, error) {
	return nil, nil
}
func (c *markReadChannelRepo) FindAllByUserID(context.Context, uuid.UUID) ([]*domain.Channel, error) {
	return nil, nil
}
func (c *markReadChannelRepo) FindAll(context.Context) ([]*domain.Channel, error) { return nil, nil }
func (c *markReadChannelRepo) Update(context.Context, *domain.Channel) error      { return nil }
func (c *markReadChannelRepo) Delete(context.Context, int) error                  { return nil }
func (c *markReadChannelRepo) AddUserToChannel(context.Context, int, uuid.UUID) error {
	return nil
}
func (c *markReadChannelRepo) RemoveUserFromChannel(context.Context, int, uuid.UUID) error {
	return nil
}
func (c *markReadChannelRepo) AddUsers(context.Context, int, []uuid.UUID) error { return nil }
func (c *markReadChannelRepo) RemoveUsers(context.Context, int, []uuid.UUID) error {
	return nil
}

type markReadRepos struct {
	msg *markReadMessageRepo
	ch  *markReadChannelRepo
}

func (r markReadRepos) Channels() repositories.ChannelRepository { return r.ch }
func (r markReadRepos) Messages() repositories.MessageRepository { return r.msg }
func (r markReadRepos) Settings() repositories.SettingsChannelRepository {
	return nil
}
func (r markReadRepos) Outbox() repositories.OutboxRepository { return &noopOutboxRepo{} }

type noopOutboxRepo struct{}

func (noopOutboxRepo) Save(context.Context, *domain.OutboxMessage) error { return nil }
func (noopOutboxRepo) FindPending(context.Context, int) ([]*domain.OutboxMessage, error) {
	return nil, nil
}
func (noopOutboxRepo) MarkPublished(context.Context, int64) error { return nil }

type markReadUoW struct{ repos markReadRepos }

func (u *markReadUoW) Do(ctx context.Context, fn func(context.Context, repositories.Repositories) error) error {
	return fn(ctx, u.repos)
}

func newMarkReadService(t *testing.T, userID uuid.UUID, roleID int, msg *markReadMessageRepo, ch *markReadChannelRepo) *MessageServiceImpl {
	t.Helper()
	if ch == nil {
		ch = &markReadChannelRepo{byID: map[int]*domain.Channel{}}
	}
	return NewMessageService(
		&markReadUoW{repos: markReadRepos{msg: msg, ch: ch}},
		stubContextAuth{userID: userID, roleID: roleID},
		nil,
	)
}

func TestMarkMessagesAsRead_PersonalMarksOnlyOwnUnread(t *testing.T) {
	uid := uuid.MustParse("11111111-1111-1111-1111-111111111111")
	other := uuid.MustParse("22222222-2222-2222-2222-222222222222")
	role := 3
	chID := 9

	ownUnread, _ := domain.SendMessageToUser("a", uid)
	ownUnread.ID = 1
	ownRead, _ := domain.SendMessageToUser("b", uid)
	ownRead.ID = 2
	ownRead.MarkAsRead()
	otherMsg, _ := domain.SendMessageToUser("c", other)
	otherMsg.ID = 3
	roleMsg, _ := domain.SendMessageToRole("d", role)
	roleMsg.ID = 4
	chMsg, _ := domain.SendMessageToChannel("e", chID)
	chMsg.ID = 5

	repo := &markReadMessageRepo{messages: []*domain.Message{ownUnread, ownRead, otherMsg, roleMsg, chMsg}}
	svc := newMarkReadService(t, uid, role, repo, nil)

	n, err := svc.MarkMessagesAsRead(context.Background(), &messagefilters.GetMessagesFilter{
		UserId: &uid,
	})
	if err != nil {
		t.Fatalf("MarkMessagesAsRead: %v", err)
	}
	if n != 1 {
		t.Fatalf("marked = %d, want 1", n)
	}
	if !ownUnread.IsRead {
		t.Fatal("own unread should become read")
	}
	if len(repo.queries) != 1 || repo.queries[0].UserID == nil || *repo.queries[0].UserID != uid {
		t.Fatalf("query = %+v", repo.queries)
	}
	if repo.queries[0].RoleID != nil || repo.queries[0].ChannelID != nil {
		t.Fatalf("personal query must not include role/channel: %+v", repo.queries[0])
	}
}

func TestMarkMessagesAsRead_RoleUsesJWTRoleNotClient(t *testing.T) {
	uid := uuid.MustParse("11111111-1111-1111-1111-111111111111")
	jwtRole := 4
	clientRole := 99

	unread, _ := domain.SendMessageToRole("r", jwtRole)
	unread.ID = 1
	repo := &markReadMessageRepo{messages: []*domain.Message{unread}}
	svc := newMarkReadService(t, uid, jwtRole, repo, nil)

	n, err := svc.MarkMessagesAsRead(context.Background(), &messagefilters.GetMessagesFilter{
		RoleId: &clientRole,
	})
	if err != nil {
		t.Fatalf("err: %v", err)
	}
	if n != 1 || !unread.IsRead {
		t.Fatalf("marked=%d isRead=%v", n, unread.IsRead)
	}
	if repo.queries[0].RoleID == nil || *repo.queries[0].RoleID != jwtRole {
		t.Fatalf("must force JWT role, got %+v", repo.queries[0])
	}
}

func TestMarkMessagesAsRead_ChannelRequiresMembership(t *testing.T) {
	uid := uuid.MustParse("11111111-1111-1111-1111-111111111111")
	outsider := uuid.MustParse("33333333-3333-3333-3333-333333333333")
	chID := 5

	unread, _ := domain.SendMessageToChannel("ch", chID)
	unread.ID = 1
	repo := &markReadMessageRepo{messages: []*domain.Message{unread}}
	chRepo := &markReadChannelRepo{byID: map[int]*domain.Channel{
		5: {ID: 5, UsersIds: []uuid.UUID{outsider}},
	}}
	svc := newMarkReadService(t, uid, 3, repo, chRepo)

	_, err := svc.MarkMessagesAsRead(context.Background(), &messagefilters.GetMessagesFilter{
		ChannelId: &chID,
	})
	if err == nil {
		t.Fatal("expected unauthorized for non-member")
	}
	var appErr *apperrors.AppError
	if !errors.As(err, &appErr) || appErr.Code != "UNAUTHORIZED" {
		t.Fatalf("want unauthorized AppError, got %v", err)
	}
	if len(repo.queries) != 0 {
		t.Fatal("must not mark when access denied")
	}
}

func TestMarkMessagesAsRead_ChannelMemberMarksUnread(t *testing.T) {
	uid := uuid.MustParse("11111111-1111-1111-1111-111111111111")
	chID := 5

	unread, _ := domain.SendMessageToChannel("ch", chID)
	unread.ID = 1
	read, _ := domain.SendMessageToChannel("old", chID)
	read.ID = 2
	read.MarkAsRead()

	repo := &markReadMessageRepo{messages: []*domain.Message{unread, read}}
	chRepo := &markReadChannelRepo{byID: map[int]*domain.Channel{
		5: {ID: 5, UsersIds: []uuid.UUID{uid}},
	}}
	svc := newMarkReadService(t, uid, 3, repo, chRepo)

	n, err := svc.MarkMessagesAsRead(context.Background(), &messagefilters.GetMessagesFilter{
		ChannelId: &chID,
	})
	if err != nil {
		t.Fatalf("err: %v", err)
	}
	if n != 1 || !unread.IsRead {
		t.Fatalf("marked=%d unread.IsRead=%v", n, unread.IsRead)
	}
}

func TestMarkMessagesAsRead_UnauthorizedWithoutUser(t *testing.T) {
	repo := &markReadMessageRepo{}
	svc := NewMessageService(
		&markReadUoW{repos: markReadRepos{msg: repo, ch: &markReadChannelRepo{}}},
		stubContextAuth{err: errors.New("no user")},
		nil,
	)
	_, err := svc.MarkMessagesAsRead(context.Background(), &messagefilters.GetMessagesFilter{})
	if err == nil {
		t.Fatal("expected error")
	}
}

func TestMarkMessageAsRead_PersonalOwn(t *testing.T) {
	uid := uuid.MustParse("11111111-1111-1111-1111-111111111111")
	msg, _ := domain.SendMessageToUser("hello", uid)
	msg.ID = 12
	repo := &markReadMessageRepo{messages: []*domain.Message{msg}}
	svc := newMarkReadService(t, uid, 3, repo, nil)

	got, err := svc.MarkMessageAsRead(context.Background(), 12)
	if err != nil {
		t.Fatalf("MarkMessageAsRead: %v", err)
	}
	if got == nil || !got.IsRead {
		t.Fatalf("dto is_read = %+v", got)
	}
	if !msg.IsRead {
		t.Fatal("entity must be marked read")
	}
}

func TestMarkMessageAsRead_PersonalForeignDenied(t *testing.T) {
	owner := uuid.MustParse("11111111-1111-1111-1111-111111111111")
	other := uuid.MustParse("22222222-2222-2222-2222-222222222222")
	msg, _ := domain.SendMessageToUser("secret", owner)
	msg.ID = 3
	repo := &markReadMessageRepo{messages: []*domain.Message{msg}}
	svc := newMarkReadService(t, other, 3, repo, nil)

	_, err := svc.MarkMessageAsRead(context.Background(), 3)
	if err == nil {
		t.Fatal("expected unauthorized")
	}
	if msg.IsRead {
		t.Fatal("must not mark foreign message")
	}
}

func TestMarkMessageAsRead_ChannelMember(t *testing.T) {
	uid := uuid.MustParse("11111111-1111-1111-1111-111111111111")
	chID := 8
	msg, _ := domain.SendMessageToChannel("car update", chID)
	msg.ID = 44
	repo := &markReadMessageRepo{messages: []*domain.Message{msg}}
	chRepo := &markReadChannelRepo{byID: map[int]*domain.Channel{
		8: {ID: 8, UsersIds: []uuid.UUID{uid}},
	}}
	svc := newMarkReadService(t, uid, 3, repo, chRepo)

	got, err := svc.MarkMessageAsRead(context.Background(), 44)
	if err != nil {
		t.Fatalf("err: %v", err)
	}
	if !got.IsRead || !msg.IsRead {
		t.Fatal("channel message must become read")
	}
}

func TestMarkMessageAsRead_ChannelOutsiderDenied(t *testing.T) {
	uid := uuid.MustParse("11111111-1111-1111-1111-111111111111")
	member := uuid.MustParse("99999999-9999-9999-9999-999999999999")
	chID := 8
	msg, _ := domain.SendMessageToChannel("car update", chID)
	msg.ID = 44
	repo := &markReadMessageRepo{messages: []*domain.Message{msg}}
	chRepo := &markReadChannelRepo{byID: map[int]*domain.Channel{
		8: {ID: 8, UsersIds: []uuid.UUID{member}},
	}}
	svc := newMarkReadService(t, uid, 3, repo, chRepo)

	_, err := svc.MarkMessageAsRead(context.Background(), 44)
	if err == nil {
		t.Fatal("expected unauthorized")
	}
	if msg.IsRead {
		t.Fatal("outsider must not mark channel message")
	}
}

func TestMarkMessageAsRead_RoleOwn(t *testing.T) {
	uid := uuid.MustParse("11111111-1111-1111-1111-111111111111")
	role := 4
	msg, _ := domain.SendMessageToRole("approval", role)
	msg.ID = 7
	repo := &markReadMessageRepo{messages: []*domain.Message{msg}}
	svc := newMarkReadService(t, uid, role, repo, nil)

	got, err := svc.MarkMessageAsRead(context.Background(), 7)
	if err != nil {
		t.Fatalf("err: %v", err)
	}
	if !got.IsRead || !msg.IsRead {
		t.Fatal("role message must become read")
	}
}

func TestMarkMessageAsRead_RoleMismatchDenied(t *testing.T) {
	uid := uuid.MustParse("11111111-1111-1111-1111-111111111111")
	msg, _ := domain.SendMessageToRole("approval", 4)
	msg.ID = 7
	repo := &markReadMessageRepo{messages: []*domain.Message{msg}}
	svc := newMarkReadService(t, uid, 3, repo, nil)

	_, err := svc.MarkMessageAsRead(context.Background(), 7)
	if err == nil {
		t.Fatal("expected unauthorized")
	}
	if msg.IsRead {
		t.Fatal("must not mark another role's message")
	}
}

func TestMarkMessageAsRead_IdempotentAlreadyRead(t *testing.T) {
	uid := uuid.MustParse("11111111-1111-1111-1111-111111111111")
	msg, _ := domain.SendMessageToUser("hello", uid)
	msg.ID = 1
	msg.MarkAsRead()
	repo := &markReadMessageRepo{messages: []*domain.Message{msg}}
	svc := newMarkReadService(t, uid, 3, repo, nil)

	got, err := svc.MarkMessageAsRead(context.Background(), 1)
	if err != nil {
		t.Fatalf("err: %v", err)
	}
	if !got.IsRead {
		t.Fatal("already-read must stay read")
	}
}

func TestMarkMessageAsRead_NotFound(t *testing.T) {
	uid := uuid.MustParse("11111111-1111-1111-1111-111111111111")
	svc := newMarkReadService(t, uid, 3, &markReadMessageRepo{}, nil)
	_, err := svc.MarkMessageAsRead(context.Background(), 99)
	if err == nil {
		t.Fatal("expected not found")
	}
}
