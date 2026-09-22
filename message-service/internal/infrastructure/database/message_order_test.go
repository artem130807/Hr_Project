package database

import "testing"

func TestMessageFeedOrderIsNewestFirst(t *testing.T) {
	if messageFeedOrderDesc != "created_at DESC, id DESC" {
		t.Fatalf("feed order = %q, want newest-first", messageFeedOrderDesc)
	}
}

func TestMessageQueueOrderIsOldestFirst(t *testing.T) {
	if messageQueueOrderAsc != "created_at ASC, id ASC" {
		t.Fatalf("queue order = %q, want oldest-first FIFO", messageQueueOrderAsc)
	}
}
