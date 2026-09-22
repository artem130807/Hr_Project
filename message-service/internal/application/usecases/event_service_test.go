package usecases

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"testing"
	"time"

	"github.com/google/uuid"

	repositories "github.com/yourusername/message-service/internal/domain/contracts/repositories"
	domain "github.com/yourusername/message-service/internal/domain/entities"
	apperrors "github.com/yourusername/message-service/internal/pkg/errors"
)

// --- фейковые репозитории ---

type fakeChannelRepo struct {
	byEntity map[string]*domain.Channel
	saved    []*domain.Channel
	nextID   int
}

func newFakeChannelRepo() *fakeChannelRepo {
	return &fakeChannelRepo{byEntity: map[string]*domain.Channel{}, nextID: 100}
}

func (f *fakeChannelRepo) key(entityType string, entityID int) string {
	return fmt.Sprintf("%s:%d", entityType, entityID)
}

func (f *fakeChannelRepo) Save(_ context.Context, ch *domain.Channel) error {
	if ch.ID == 0 {
		f.nextID++
		ch.ID = f.nextID
	}
	f.byEntity[f.key(ch.EntityType, ch.EntityID)] = ch
	f.saved = append(f.saved, ch)
	return nil
}

func (f *fakeChannelRepo) FindByEntity(_ context.Context, entityType string, entityID int) (*domain.Channel, error) {
	if c, ok := f.byEntity[f.key(entityType, entityID)]; ok {
		return c, nil
	}
	return nil, apperrors.ErrNotFound
}

func (f *fakeChannelRepo) FindByIDs(ctx context.Context, ids []int) ([]*domain.Channel, error) {
	return []*domain.Channel{}, nil
}

// остальные методы интерфейса ChannelRepository
func (f *fakeChannelRepo) FindByID(context.Context, int) (*domain.Channel, error) {
	return nil, apperrors.ErrNotFound
}
func (f *fakeChannelRepo) FindAllByUserID(context.Context, uuid.UUID) ([]*domain.Channel, error) {
	return nil, nil
}
func (f *fakeChannelRepo) FindAll(context.Context) ([]*domain.Channel, error) { return f.saved, nil }
func (f *fakeChannelRepo) Update(context.Context, *domain.Channel) error      { return nil }
func (f *fakeChannelRepo) Delete(context.Context, int) error                  { return nil }
func (f *fakeChannelRepo) AddUserToChannel(context.Context, int, uuid.UUID) error {
	return nil
}
func (f *fakeChannelRepo) RemoveUserFromChannel(context.Context, int, uuid.UUID) error {
	return nil
}
func (f *fakeChannelRepo) AddUsers(context.Context, int, []uuid.UUID) error { return nil }
func (f *fakeChannelRepo) RemoveUsers(context.Context, int, []uuid.UUID) error {
	return nil
}

type fakeMessageRepo struct {
	saved []*domain.Message
}

type fakeNotificationDispatcher struct {
	dispatched []*domain.Message
}

func (f *fakeNotificationDispatcher) DispatchMessage(_ context.Context, msg *domain.Message) {
	f.dispatched = append(f.dispatched, msg)
}

func (f *fakeMessageRepo) Save(_ context.Context, m *domain.Message) error {
	f.saved = append(f.saved, m)
	return nil
}

// неиспользуемые методы контракта MessageRepository
func (f *fakeMessageRepo) FindByID(context.Context, int) (*domain.Message, error) {
	return nil, apperrors.ErrNotFound
}
func (f *fakeMessageRepo) FindByChannelID(context.Context, int) ([]*domain.Message, error) {
	return nil, nil
}
func (f *fakeMessageRepo) FindByUserID(context.Context, uuid.UUID) ([]*domain.Message, error) {
	return nil, nil
}
func (f *fakeMessageRepo) FindByRoleID(context.Context, int) ([]*domain.Message, error) {
	return nil, nil
}
func (f *fakeMessageRepo) FindByQuery(context.Context, repositories.MessageQuery) ([]*domain.Message, error) {
	return nil, nil
}
func (f *fakeMessageRepo) MarkAsReadByQuery(context.Context, repositories.MessageQuery) (int, error) {
	return 0, nil
}
func (f *fakeMessageRepo) Update(context.Context, *domain.Message) error { return nil }
func (f *fakeMessageRepo) Delete(context.Context, int) error             { return nil }
func (f *fakeMessageRepo) FindUnsentByChannelID(context.Context, int) ([]*domain.Message, error) {
	return nil, nil
}
func (f *fakeMessageRepo) FindNotReadCountByUser(ctx context.Context, userId uuid.UUID, roleId int) (int, error) {
	return 0, nil
}
func (f *fakeMessageRepo) CountUnreadByChannelIDs(context.Context, []int) (map[int]int, error) {
	return map[int]int{}, nil
}

type fakeOutboxRepo struct {
	saved   []*domain.OutboxMessage
	nextID  int64
	pending []*domain.OutboxMessage
}

func (f *fakeOutboxRepo) Save(_ context.Context, msg *domain.OutboxMessage) error {
	f.nextID++
	msg.ID = f.nextID
	cp := *msg
	cp.Payload = append([]byte(nil), msg.Payload...)
	f.saved = append(f.saved, &cp)
	f.pending = append(f.pending, &cp)
	return nil
}

func (f *fakeOutboxRepo) FindPending(_ context.Context, limit int) ([]*domain.OutboxMessage, error) {
	if limit < 1 || limit > len(f.pending) {
		limit = len(f.pending)
	}
	out := make([]*domain.OutboxMessage, 0, limit)
	for i := 0; i < limit; i++ {
		out = append(out, f.pending[i])
	}
	return out, nil
}

func (f *fakeOutboxRepo) MarkPublished(_ context.Context, id int64) error {
	kept := f.pending[:0]
	for _, p := range f.pending {
		if p.ID != id {
			kept = append(kept, p)
		} else {
			p.Status = domain.OutboxStatusPublished
		}
	}
	f.pending = kept
	return nil
}

type fakeRepos struct {
	ch     *fakeChannelRepo
	msg    *fakeMessageRepo
	outbox *fakeOutboxRepo
}

func (r fakeRepos) Channels() repositories.ChannelRepository         { return r.ch }
func (r fakeRepos) Messages() repositories.MessageRepository         { return r.msg }
func (r fakeRepos) Settings() repositories.SettingsChannelRepository { return nil }
func (r fakeRepos) Outbox() repositories.OutboxRepository {
	if r.outbox == nil {
		return &fakeOutboxRepo{}
	}
	return r.outbox
}

type fakeUoW struct{ repos fakeRepos }

func (u *fakeUoW) Do(ctx context.Context, fn func(context.Context, repositories.Repositories) error) error {
	return fn(ctx, u.repos)
}

// --- тесты ---

// Сценарий 1: канала нет → создаётся + сообщение постится.
func TestEventService_Handle_DropsInvalid(t *testing.T) {
	chRepo := newFakeChannelRepo()
	msgRepo := &fakeMessageRepo{}
	svc := NewEventService(&fakeUoW{repos: fakeRepos{ch: chRepo, msg: msgRepo, outbox: &fakeOutboxRepo{}}}, nil, nil)

	if err := svc.Handle(context.Background(), []byte("{bad")); err != nil {
		t.Fatalf("invalid body must drop (nil), got: %v", err)
	}
	if err := svc.Handle(context.Background(), []byte{}); err != nil {
		t.Fatalf("empty body must return nil, got: %v", err)
	}
	if len(chRepo.saved) != 0 || len(msgRepo.saved) != 0 {
		t.Errorf("nothing should be saved for invalid bodies")
	}
}

func sampleTripChangedBody() []byte {
	return []byte(`{
		"event_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
		"event_type": "message.trip.changed",
		"occurred_at": "2026-08-11T12:00:00+00:00",
		"trip_id": 100,
		"company_name": "Москва-Казань",
		"actor_user_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
		"changed": {
			"work_status": {"old": "В работе", "new": "В пути"}
		}
	}`)
}

func TestEventService_Handle_HiringRequestCreated(t *testing.T) {
	chRepo := newFakeChannelRepo()
	msgRepo := &fakeMessageRepo{}
	dispatcher := &fakeNotificationDispatcher{}
	svc := NewEventService(&fakeUoW{repos: fakeRepos{ch: chRepo, msg: msgRepo, outbox: &fakeOutboxRepo{}}}, dispatcher, nil)

	if err := svc.Handle(context.Background(), sampleHiringRequestCreatedBody()); err != nil {
		t.Fatalf("handle: %v", err)
	}
	if len(chRepo.saved) != 0 {
		t.Fatalf("expected no channel, got %d", len(chRepo.saved))
	}
	if len(msgRepo.saved) != 3 {
		t.Fatalf("expected 3 role messages, got %d", len(msgRepo.saved))
	}
	m := msgRepo.saved[0]
	if m.Content != "Создана заявка на подбор З-42\nДолжность: Логист" {
		t.Errorf("content = %q, want pre-rendered passthrough", m.Content)
	}
	if m.EntityType == nil || *m.EntityType != "hiring_request" || m.EntityID == nil || *m.EntityID != 42 {
		t.Errorf("entity = %v/%v, want hiring_request/42", m.EntityType, m.EntityID)
	}
	if m.RoleId == nil || *m.RoleId != 2 || m.ChannelID != nil {
		t.Errorf("audience = role %v/channel %v, want role 2 only", m.RoleId, m.ChannelID)
	}
	if len(dispatcher.dispatched) != 3 {
		t.Fatalf("expected 3 realtime dispatches, got %d", len(dispatcher.dispatched))
	}
}

// Сценарий: роли дублируются безопасно, канал не создаётся.
func TestEventService_Handle_HiringRequestCreatedDeduplicatesRoles(t *testing.T) {
	chRepo := newFakeChannelRepo()
	msgRepo := &fakeMessageRepo{}
	svc := NewEventService(&fakeUoW{repos: fakeRepos{ch: chRepo, msg: msgRepo, outbox: &fakeOutboxRepo{}}}, nil, nil)

	if err := svc.Handle(context.Background(), sampleHiringRequestCreatedBody()); err != nil {
		t.Fatalf("handle first: %v", err)
	}
	if len(chRepo.saved) != 0 {
		t.Fatalf("expected no channels, got %d", len(chRepo.saved))
	}
	if len(msgRepo.saved) != 3 {
		t.Fatalf("expected 3 unique role messages, got %d", len(msgRepo.saved))
	}
	for _, msg := range msgRepo.saved {
		if msg.RoleId == nil || msg.ChannelID != nil {
			t.Errorf("message must target role only: %+v", msg)
		}
	}
}

func TestEventService_Handle_AdaptationTalkHR_RoleAndTelegramOutbox(t *testing.T) {
	chRepo := newFakeChannelRepo()
	msgRepo := &fakeMessageRepo{}
	outboxRepo := &fakeOutboxRepo{}
	dispatcher := &fakeNotificationDispatcher{}
	svc := NewEventService(&fakeUoW{repos: fakeRepos{ch: chRepo, msg: msgRepo, outbox: outboxRepo}}, dispatcher, nil)
	body := []byte(`{"event_id":"66666666-6666-6666-6666-666666666666","event_type":"message.adaptation.talk_hr","occurred_at":"2026-09-10T10:00:00Z","checkpoint_id":77,"target_role_ids":[4],"text":"Иванов просит поговорить с HR"}`)

	if err := svc.Handle(context.Background(), body); err != nil {
		t.Fatalf("handle: %v", err)
	}
	if len(chRepo.saved) != 0 || len(msgRepo.saved) != 1 {
		t.Fatalf("channels/messages = %d/%d, want 0/1", len(chRepo.saved), len(msgRepo.saved))
	}
	if msgRepo.saved[0].RoleId == nil || *msgRepo.saved[0].RoleId != 4 {
		t.Fatalf("role = %v, want 4", msgRepo.saved[0].RoleId)
	}
	if len(outboxRepo.saved) != 1 || outboxRepo.saved[0].EventType != hrEventNotifyType {
		t.Fatalf("outbox = %+v, want one hr.event.notify", outboxRepo.saved)
	}
	var notify HrEventNotify
	if err := json.Unmarshal(outboxRepo.saved[0].Payload, &notify); err != nil {
		t.Fatalf("decode outbox: %v", err)
	}
	if notify.Type != "adaptation_talk_hr" || notify.HrEventID != 77 {
		t.Fatalf("notify = %+v", notify)
	}
	if len(dispatcher.dispatched) != 1 || dispatcher.dispatched[0] != msgRepo.saved[0] {
		t.Fatalf("realtime dispatches = %d, want saved role message", len(dispatcher.dispatched))
	}
}

func TestEventService_Handle_AdaptationNotification_RolesRealtimeAndOutbox(t *testing.T) {
	chRepo := newFakeChannelRepo()
	msgRepo := &fakeMessageRepo{}
	outboxRepo := &fakeOutboxRepo{}
	dispatcher := &fakeNotificationDispatcher{}
	svc := NewEventService(&fakeUoW{repos: fakeRepos{ch: chRepo, msg: msgRepo, outbox: outboxRepo}}, dispatcher, nil)
	body := []byte(`{"event_id":"77777777-7777-7777-7777-777777777777","event_type":"message.adaptation.notification","occurred_at":"2026-09-10T12:00:00Z","checkpoint_id":91,"target_role_ids":[4,4,7],"notification_type":"data_collected","text":"Ответы по адаптации собраны"}`)

	if err := svc.Handle(context.Background(), body); err != nil {
		t.Fatalf("handle: %v", err)
	}
	if len(chRepo.saved) != 0 {
		t.Fatalf("adaptation notification must not create a channel, got %d", len(chRepo.saved))
	}
	if len(msgRepo.saved) != 2 || len(dispatcher.dispatched) != 2 {
		t.Fatalf("messages/realtime = %d/%d, want 2/2", len(msgRepo.saved), len(dispatcher.dispatched))
	}
	for _, msg := range msgRepo.saved {
		if msg.RoleId == nil || msg.ChannelID != nil {
			t.Fatalf("message must target a role only: %+v", msg)
		}
	}
	if len(outboxRepo.saved) != 1 {
		t.Fatalf("outbox = %d, want one web-push/telegram event", len(outboxRepo.saved))
	}
	var notify HrEventNotify
	if err := json.Unmarshal(outboxRepo.saved[0].Payload, &notify); err != nil {
		t.Fatalf("decode outbox: %v", err)
	}
	if notify.Type != "data_collected" || notify.HrEventID != 91 {
		t.Fatalf("notify = %+v", notify)
	}
}

func handlePreRendered(t *testing.T, body []byte) (*fakeChannelRepo, *fakeMessageRepo) {
	t.Helper()
	chRepo := newFakeChannelRepo()
	msgRepo := &fakeMessageRepo{}
	svc := NewEventService(&fakeUoW{repos: fakeRepos{ch: chRepo, msg: msgRepo, outbox: &fakeOutboxRepo{}}}, nil, nil)
	if err := svc.Handle(context.Background(), body); err != nil {
		t.Fatalf("handle: %v", err)
	}
	return chRepo, msgRepo
}

func TestEventService_Handle_DropsUnknownEventWithZeroEntity(t *testing.T) {
	chRepo := newFakeChannelRepo()
	msgRepo := &fakeMessageRepo{}
	svc := NewEventService(&fakeUoW{repos: fakeRepos{ch: chRepo, msg: msgRepo, outbox: &fakeOutboxRepo{}}}, nil, nil)

	body := []byte(`{"event_type":"message.unknown.kind","trip_id":0,"text":"x"}`)
	if err := svc.Handle(context.Background(), body); err != nil {
		t.Fatalf("must drop (nil), got: %v", err)
	}
	if len(msgRepo.saved) != 0 {
		t.Errorf("unknown event with empty entity must not be saved")
	}
}

// Сценарий: pre-rendered событие с пустым text — poison, Ack (nil), ничего не сохраняется.
func TestEventService_Handle_DropsEmptyPreRenderedText(t *testing.T) {
	chRepo := newFakeChannelRepo()
	msgRepo := &fakeMessageRepo{}
	svc := NewEventService(&fakeUoW{repos: fakeRepos{ch: chRepo, msg: msgRepo, outbox: &fakeOutboxRepo{}}}, nil, nil)

	body := []byte(`{"event_type": "message.downtime.registered", "trip_id": 5, "text": ""}`)
	if err := svc.Handle(context.Background(), body); err != nil {
		t.Fatalf("must drop (nil), got: %v", err)
	}
	if len(msgRepo.saved) != 0 {
		t.Errorf("nothing should be saved for empty text")
	}
}

func sampleHrEventCreatedBody() []byte {
	return []byte(`{
		"event_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
		"event_type": "hr.event.created",
		"occurred_at": "2026-08-18T12:00:00+00:00",
		"hr_event_id": 55,
		"type": "birthday",
		"employee_name": "Иван Иванов",
		"telegram_user": "@ivan_hr",
		"event_date": "2026-05-01",
		"remind_before": 3,
		"user_id": "11111111-1111-1111-1111-111111111111",
		"userId": "11111111-1111-1111-1111-111111111111"
	}`)
}

func TestEventService_Handle_HrEventCreated_PersonalMessage(t *testing.T) {
	chRepo := newFakeChannelRepo()
	msgRepo := &fakeMessageRepo{}
	outboxRepo := &fakeOutboxRepo{}
	svc := NewEventService(&fakeUoW{repos: fakeRepos{ch: chRepo, msg: msgRepo, outbox: outboxRepo}}, nil, nil)

	if err := svc.Handle(context.Background(), sampleHrEventCreatedBody()); err != nil {
		t.Fatalf("handle: %v", err)
	}
	if len(chRepo.saved) != 0 {
		t.Errorf("hr.event.created must not create a channel, got %d", len(chRepo.saved))
	}
	if len(msgRepo.saved) != 1 {
		t.Fatalf("expected 1 personal message, got %d", len(msgRepo.saved))
	}
	m := msgRepo.saved[0]
	if m.ChannelID != nil {
		t.Errorf("personal message must not have channel_id, got %v", m.ChannelID)
	}
	wantUID := uuid.MustParse("11111111-1111-1111-1111-111111111111")
	if m.UserId == nil || *m.UserId != wantUID {
		t.Errorf("user_id = %v, want %s", m.UserId, wantUID)
	}
	if !strings.Contains(m.Content, "День рождения") || !strings.Contains(m.Content, "Иван Иванов") {
		t.Errorf("content = %q", m.Content)
	}
	if m.EntityType == nil || *m.EntityType != "hr_event" {
		t.Errorf("entity_type = %v, want hr_event", m.EntityType)
	}
	if m.EntityID == nil || *m.EntityID != 55 {
		t.Errorf("entity_id = %v, want 55", m.EntityID)
	}
	if len(outboxRepo.saved) != 1 {
		t.Fatalf("expected 1 outbox row, got %d", len(outboxRepo.saved))
	}
	ob := outboxRepo.saved[0]
	if ob.EventType != hrEventNotifyType {
		t.Errorf("outbox event_type = %q", ob.EventType)
	}
	var notify HrEventNotify
	if err := json.Unmarshal(ob.Payload, &notify); err != nil {
		t.Fatalf("outbox payload: %v", err)
	}
	if notify.NotifyAt != "2026-04-28T00:00:00Z" {
		t.Errorf("notify_at = %q, want 2026-04-28T00:00:00Z", notify.NotifyAt)
	}
	if notify.UserID != wantUID.String() || notify.Content == "" {
		t.Errorf("notify payload incomplete: %+v", notify)
	}
}

func TestEventService_Handle_HrEventCreated_WithSamaraTime(t *testing.T) {
	chRepo := newFakeChannelRepo()
	msgRepo := &fakeMessageRepo{}
	outboxRepo := &fakeOutboxRepo{}
	svc := NewEventService(&fakeUoW{repos: fakeRepos{ch: chRepo, msg: msgRepo, outbox: outboxRepo}}, nil, nil)

	body := []byte(`{
		"event_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
		"event_type": "hr.event.created",
		"occurred_at": "2026-08-19T08:00:00Z",
		"hr_event_id": 77,
		"type": "birthday",
		"employee_name": "Иван",
		"event_date": "2026-08-19",
		"remind_before": 0,
		"remind_at_time": "15:00",
		"user_id": "11111111-1111-1111-1111-111111111111"
	}`)
	if err := svc.Handle(context.Background(), body); err != nil {
		t.Fatalf("handle: %v", err)
	}
	if len(outboxRepo.saved) != 1 {
		t.Fatalf("expected outbox, got %d", len(outboxRepo.saved))
	}
	var notify HrEventNotify
	if err := json.Unmarshal(outboxRepo.saved[0].Payload, &notify); err != nil {
		t.Fatal(err)
	}
	// 15:00 Samara = 11:00 UTC
	if notify.NotifyAt != "2026-08-19T11:00:00Z" {
		t.Errorf("notify_at=%q want 2026-08-19T11:00:00Z", notify.NotifyAt)
	}
	if notify.RemindAtTime != "15:00" {
		t.Errorf("remind_at_time=%q", notify.RemindAtTime)
	}
}

func TestEventService_Handle_HrEventCreated_NotifiesTelegramWithoutUserID(t *testing.T) {
	chRepo := newFakeChannelRepo()
	msgRepo := &fakeMessageRepo{}
	outboxRepo := &fakeOutboxRepo{}
	svc := NewEventService(&fakeUoW{repos: fakeRepos{ch: chRepo, msg: msgRepo, outbox: outboxRepo}}, nil, nil)

	body := []byte(`{
		"event_type": "hr.event.created",
		"hr_event_id": 1,
		"type": "other",
		"event_date": "2026-08-19",
		"remind_before": 0,
		"telegram_user": "@Artem56798"
	}`)
	if err := svc.Handle(context.Background(), body); err != nil {
		t.Fatalf("must succeed, got: %v", err)
	}
	if len(msgRepo.saved) != 0 {
		t.Errorf("no personal message without user_id, got %d", len(msgRepo.saved))
	}
	if len(outboxRepo.saved) != 1 {
		t.Fatalf("Telegram notify outbox required, got %d", len(outboxRepo.saved))
	}
	var notify HrEventNotify
	if err := json.Unmarshal(outboxRepo.saved[0].Payload, &notify); err != nil {
		t.Fatal(err)
	}
	if notify.EventType != hrEventNotifyType || notify.Content == "" {
		t.Errorf("notify payload incomplete: %+v", notify)
	}
	if notify.UserID != "" {
		t.Errorf("user_id should be empty, got %q", notify.UserID)
	}
	if notify.NotifyAt != "2026-08-19T00:00:00Z" {
		t.Errorf("notify_at=%q", notify.NotifyAt)
	}
}

func sampleHrHiringRequestCreatedBody() []byte {
	return []byte(`{
		"event_id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
		"event_type": "hr.hiring_request.created",
		"occurred_at": "2026-09-08T07:00:00Z",
		"hiring_request_id": 42,
		"position": "Логист",
		"department": "логистический",
		"headcount": 2,
		"initiator_name": "Петров",
		"actor_user_id": "u-1",
		"actor_name": "Иванов Иван",
		"text": "Создана заявка на подбор З-42\nДолжность: Логист\nСоздал: Иванов Иван"
	}`)
}

func TestEventService_Handle_HrHiringRequestCreated_OutboxImmediate(t *testing.T) {
	chRepo := newFakeChannelRepo()
	msgRepo := &fakeMessageRepo{}
	outboxRepo := &fakeOutboxRepo{}
	svc := NewEventService(&fakeUoW{repos: fakeRepos{ch: chRepo, msg: msgRepo, outbox: outboxRepo}}, nil, nil)

	if err := svc.Handle(context.Background(), sampleHrHiringRequestCreatedBody()); err != nil {
		t.Fatalf("handle: %v", err)
	}
	if len(chRepo.saved) != 0 {
		t.Errorf("hr.hiring_request.created must not create a channel, got %d", len(chRepo.saved))
	}
	if len(msgRepo.saved) != 0 {
		t.Errorf("must not create personal message, got %d", len(msgRepo.saved))
	}
	if len(outboxRepo.saved) != 1 {
		t.Fatalf("expected 1 outbox row, got %d", len(outboxRepo.saved))
	}
	var notify HrEventNotify
	if err := json.Unmarshal(outboxRepo.saved[0].Payload, &notify); err != nil {
		t.Fatal(err)
	}
	if notify.Type != hiringRequestNotifyKind || notify.HiringRequestID != 42 {
		t.Errorf("notify=%+v", notify)
	}
	if notify.ActorName != "Иванов Иван" || !strings.Contains(notify.Content, "Создал: Иванов Иван") {
		t.Errorf("content/actor=%q %q", notify.Content, notify.ActorName)
	}
	notifyAt, err := time.Parse(time.RFC3339, notify.NotifyAt)
	if err != nil {
		t.Fatalf("notify_at: %v", err)
	}
	if time.Since(notifyAt) > time.Minute {
		t.Errorf("notify_at=%s should be now", notify.NotifyAt)
	}
}

func TestEventService_Handle_HrHiringRequestCreated_DropsEmptyID(t *testing.T) {
	outboxRepo := &fakeOutboxRepo{}
	svc := NewEventService(&fakeUoW{repos: fakeRepos{ch: newFakeChannelRepo(), msg: &fakeMessageRepo{}, outbox: outboxRepo}}, nil, nil)
	body := []byte(`{"event_type":"hr.hiring_request.created","hiring_request_id":0,"text":"x"}`)
	if err := svc.Handle(context.Background(), body); err != nil {
		t.Fatalf("handle: %v", err)
	}
	if len(outboxRepo.saved) != 0 {
		t.Errorf("empty id must drop, got %d", len(outboxRepo.saved))
	}
}

func TestEventService_Handle_HrHiringRequestCreated_NullHeadcount(t *testing.T) {
	outboxRepo := &fakeOutboxRepo{}
	svc := NewEventService(&fakeUoW{repos: fakeRepos{ch: newFakeChannelRepo(), msg: &fakeMessageRepo{}, outbox: outboxRepo}}, nil, nil)
	body := []byte(`{
		"event_type": "hr.hiring_request.created",
		"hiring_request_id": 8,
		"headcount": null,
		"text": "Создана заявка на подбор З-8\nСоздал: Петров"
	}`)
	if err := svc.Handle(context.Background(), body); err != nil {
		t.Fatalf("handle: %v", err)
	}
	if len(outboxRepo.saved) != 1 {
		t.Fatalf("null headcount must not drop event, got %d", len(outboxRepo.saved))
	}
}

func TestEventService_Handle_IgnoresLogisticsEvents(t *testing.T) {
	chRepo := newFakeChannelRepo()
	msgRepo := &fakeMessageRepo{}
	svc := NewEventService(&fakeUoW{repos: fakeRepos{ch: chRepo, msg: msgRepo, outbox: &fakeOutboxRepo{}}}, nil, nil)
	for _, body := range [][]byte{
		sampleCarChangedBody(),
		[]byte(`{"event_type":"message.trip.changed","trip_id":1,"text":"x"}`),
		[]byte(`{"event_type":"message.downtime.registered","text":"x","executor_id":1}`),
		[]byte(`{"event_type":"message.tms.sync_blocked","text":"x","tms_id":"1"}`),
	} {
		if err := svc.Handle(context.Background(), body); err != nil {
			t.Fatalf("handle: %v", err)
		}
	}
	if len(chRepo.saved) != 0 || len(msgRepo.saved) != 0 {
		t.Fatalf("logistics events must be ignored, channels=%d messages=%d", len(chRepo.saved), len(msgRepo.saved))
	}
}
