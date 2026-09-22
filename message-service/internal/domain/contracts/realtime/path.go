package realtime

import (
	"fmt"
	"strings"
)

// ClickPath — путь SPA ERP для клика по уведомлению.
// Совпадает с notificationRoute/notificationPath на фронте:
// trip → /trips/:id, executor → /executors/:id, car|trailer → /cars/:id, driver → /drivers/:id.
// Нет сущности — inbox канала или общий inbox (для OS-уведомления нужен URL).
func (n Notification) ClickPath() string {
	if path := entityPath(n.EntityType, n.EntityID); path != "" {
		return path
	}
	if n.ChannelID != nil && *n.ChannelID > 0 {
		return fmt.Sprintf("/notifications?section=channels&channelId=%d", *n.ChannelID)
	}
	return "/notifications"
}

func entityPath(entityType *string, entityID *int) string {
	if entityType == nil || entityID == nil || *entityID <= 0 {
		return ""
	}
	id := *entityID
	switch strings.ToLower(strings.TrimSpace(*entityType)) {
	case "trip":
		return fmt.Sprintf("/trips/%d", id)
	case "executor":
		return fmt.Sprintf("/executors/%d", id)
	case "car", "trailer":
		return fmt.Sprintf("/cars/%d", id)
	case "driver":
		return fmt.Sprintf("/drivers/%d", id)
	default:
		return ""
	}
}
