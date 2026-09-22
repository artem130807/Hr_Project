package domain

import (
	"strings"
	"testing"

	"github.com/google/uuid"
)

func TestNewPushSubscription_RequiresHTTPSAndKeys(t *testing.T) {
	uid := uuid.MustParse("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
	_, err := NewPushSubscription(uid, "http://insecure/x", "p", "a")
	if err == nil {
		t.Fatal("http endpoint must be rejected")
	}
	got, err := NewPushSubscription(uid, "https://fcm.googleapis.com/fcm/send/abc", "p", "a")
	if err != nil {
		t.Fatal(err)
	}
	if got.Endpoint == "" || got.UserID != uid {
		t.Fatalf("got %+v", got)
	}
	_, err = NewPushSubscription(uid, "https://x/"+strings.Repeat("a", 2048), "p", "a")
	if err == nil {
		t.Fatal("oversized endpoint must be rejected")
	}
}
