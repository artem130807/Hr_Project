package channelsync

import "strings"

// EntityType канала «Заявки на подбор» (ChangeEvent.ChannelEvent).
const HiringRequestChannelEvent = "message.hiring_request"

// Роли, которым виден канал заявок на подбор.
// Имена ERP (Админ, Руководитель, HR, Руководитель отдела) и HR-slug'и.
var hiringRequestRoleNames = map[string]struct{}{
	"админ":               {},
	"admin":               {},
	"руководитель":        {},
	"leader":              {},
	"hr":                  {},
	"руководитель отдела": {},
	"dept_leader":         {},
}

// ChannelHasRoleACL — канал с ограниченным составом (не «все из ERP»).
func ChannelHasRoleACL(entityType string) bool {
	return entityType == HiringRequestChannelEvent
}

func normalizeRoleName(name string) string {
	return strings.ToLower(strings.TrimSpace(name))
}

// RoleAllowedForChannel: открытый канал — любой; закрытый — только allowlist.
func RoleAllowedForChannel(entityType, roleName string) bool {
	if !ChannelHasRoleACL(entityType) {
		return true
	}
	_, ok := hiringRequestRoleNames[normalizeRoleName(roleName)]
	return ok
}
