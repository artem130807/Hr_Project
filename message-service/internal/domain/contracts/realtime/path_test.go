package realtime

import (
	"testing"
)

func TestNotification_ClickPath(t *testing.T) {
	trip := "trip"
	executor := "executor"
	car := "car"
	trailer := "trailer"
	driver := "driver"
	unknown := "warehouse"
	id := 42
	ch := 7

	tests := []struct {
		name string
		n    Notification
		want string
	}{
		{name: "trip", n: Notification{EntityType: &trip, EntityID: &id}, want: "/trips/42"},
		{name: "executor", n: Notification{EntityType: &executor, EntityID: &id}, want: "/executors/42"},
		{name: "car", n: Notification{EntityType: &car, EntityID: &id}, want: "/cars/42"},
		{name: "trailer matches inbox click", n: Notification{EntityType: &trailer, EntityID: &id}, want: "/cars/42"},
		{name: "driver", n: Notification{EntityType: &driver, EntityID: &id}, want: "/drivers/42"},
		{name: "unknown entity falls back to channel inbox", n: Notification{EntityType: &unknown, EntityID: &id, ChannelID: &ch}, want: "/notifications?section=channels&channelId=7"},
		{name: "channel without entity", n: Notification{ChannelID: &ch}, want: "/notifications?section=channels&channelId=7"},
		{name: "personal without entity", n: Notification{}, want: "/notifications"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := tt.n.ClickPath(); got != tt.want {
				t.Fatalf("ClickPath() = %q, want %q", got, tt.want)
			}
		})
	}
}
