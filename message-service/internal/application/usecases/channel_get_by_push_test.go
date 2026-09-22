package usecases

import (
	"context"
	"testing"

	"github.com/google/uuid"

	domain "github.com/yourusername/message-service/internal/domain/entities"
)

func TestGetChannelsByPush_ListsByMembershipWithoutSettings(t *testing.T) {
	uid := uuid.MustParse("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
	other := uuid.MustParse("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

	chMember := &domain.Channel{ID: 1, Name: "Изменения по машине", UsersIds: []uuid.UUID{uid, other}}
	chOther := &domain.Channel{ID: 2, Name: "Чужой", UsersIds: []uuid.UUID{other}}
	chRepo := &channelRepoWithID{byID: map[int]*domain.Channel{1: chMember, 2: chOther}}
	stRepo := &dispSettingsRepo{byKey: map[string]*domain.SettingsChannel{}}

	svc := NewChannelService(&chanUoW{ch: chRepo, st: stRepo}, stubContextAuth{userID: uid, roleID: 2})
	got, err := svc.GetChannelsByPush(context.Background(), nil)
	if err != nil {
		t.Fatalf("GetChannelsByPush: %v", err)
	}
	if len(got) != 1 || got[0].ID != 1 {
		t.Fatalf("want only member channel #1, got %+v", got)
	}
}

func TestGetChannelsByPush_FiltersMuteViaSettings(t *testing.T) {
	uid := uuid.MustParse("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
	chOn := &domain.Channel{ID: 10, Name: "on-default", UsersIds: []uuid.UUID{uid}}
	chMuted := &domain.Channel{ID: 11, Name: "muted", UsersIds: []uuid.UUID{uid}}
	chExplicitOn := &domain.Channel{ID: 12, Name: "explicit-on", UsersIds: []uuid.UUID{uid}}

	chRepo := &channelRepoWithID{byID: map[int]*domain.Channel{
		10: chOn, 11: chMuted, 12: chExplicitOn,
	}}
	stRepo := &dispSettingsRepo{byKey: map[string]*domain.SettingsChannel{
		settingsKey(uid, 11): {UserID: uid, ChannelID: 11, IsSendPushMessage: false},
		settingsKey(uid, 12): {UserID: uid, ChannelID: 12, IsSendPushMessage: true},
	}}

	svc := NewChannelService(&chanUoW{ch: chRepo, st: stRepo}, stubContextAuth{userID: uid, roleID: 2})

	wantPush := true
	gotOn, err := svc.GetChannelsByPush(context.Background(), &wantPush)
	if err != nil {
		t.Fatalf("isPush=true: %v", err)
	}
	idsOn := map[int]bool{}
	for _, ch := range gotOn {
		idsOn[ch.ID] = true
	}
	if !idsOn[10] || !idsOn[12] || idsOn[11] {
		t.Fatalf("isPush=true got ids %v, want {10,12}", idsOn)
	}

	wantMuted := false
	gotOff, err := svc.GetChannelsByPush(context.Background(), &wantMuted)
	if err != nil {
		t.Fatalf("isPush=false: %v", err)
	}
	if len(gotOff) != 1 || gotOff[0].ID != 11 {
		t.Fatalf("isPush=false got %+v, want only #11", gotOff)
	}
}

type countingMessageRepo struct {
	fakeMessageRepo
	counts map[int]int
}

func (c *countingMessageRepo) CountUnreadByChannelIDs(_ context.Context, ids []int) (map[int]int, error) {
	out := map[int]int{}
	for _, id := range ids {
		if n, ok := c.counts[id]; ok {
			out[id] = n
		}
	}
	return out, nil
}

func TestGetChannelsByPush_FillsUnreadCount(t *testing.T) {
	uid := uuid.MustParse("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
	chCars := &domain.Channel{ID: 1, Name: "Изменения по машине", UsersIds: []uuid.UUID{uid}}
	chTrips := &domain.Channel{ID: 2, Name: "Изменения по рейсу", UsersIds: []uuid.UUID{uid}}
	chRepo := &channelRepoWithID{byID: map[int]*domain.Channel{1: chCars, 2: chTrips}}
	stRepo := &dispSettingsRepo{byKey: map[string]*domain.SettingsChannel{}}
	msgRepo := &countingMessageRepo{counts: map[int]int{1: 4, 2: 0}}

	svc := NewChannelService(
		&chanUoW{ch: chRepo, st: stRepo, msg: msgRepo},
		stubContextAuth{userID: uid, roleID: 2},
	)
	got, err := svc.GetChannelsByPush(context.Background(), nil)
	if err != nil {
		t.Fatalf("GetChannelsByPush: %v", err)
	}
	byID := map[int]int{}
	for _, ch := range got {
		byID[ch.ID] = ch.UnreadCount
	}
	if byID[1] != 4 {
		t.Fatalf("channel 1 unread = %d, want 4", byID[1])
	}
	if byID[2] != 0 {
		t.Fatalf("channel 2 unread = %d, want 0", byID[2])
	}
}
