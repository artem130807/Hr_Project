package domain

import (
	"testing"

	"github.com/google/uuid"
)

func TestMessage_WithEntity(t *testing.T) {
	msg, err := SendMessageToRole("hi", 3)
	if err != nil {
		t.Fatal(err)
	}
	msg.WithEntity(" Trip ", 42)
	if msg.EntityType == nil || *msg.EntityType != "trip" {
		t.Fatalf("EntityType = %v, want trip", msg.EntityType)
	}
	if msg.EntityID == nil || *msg.EntityID != 42 {
		t.Fatalf("EntityID = %v, want 42", msg.EntityID)
	}

	msg.WithEntity("", 1)
	if *msg.EntityType != "trip" || *msg.EntityID != 42 {
		t.Fatal("empty type should not clear entity")
	}
	msg.WithEntity("executor", 0)
	if *msg.EntityType != "trip" {
		t.Fatal("zero id should not clear entity")
	}
}

func TestMessage_MarkAsRead(t *testing.T) {
	msg, err := SendMessageToUser("hi", uuid.MustParse("11111111-1111-1111-1111-111111111111"))
	if err != nil {
		t.Fatal(err)
	}
	if msg.IsRead {
		t.Fatal("new message must be unread")
	}
	msg.MarkAsRead()
	if !msg.IsRead {
		t.Fatal("MarkAsRead must set IsRead")
	}
	msg.MarkAsRead()
	if !msg.IsRead {
		t.Fatal("second MarkAsRead must keep IsRead")
	}
}
