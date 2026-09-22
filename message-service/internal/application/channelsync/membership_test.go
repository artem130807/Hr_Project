package channelsync

import "testing"

func TestRoleAllowedForChannel_OpenChannelsAcceptAnyRole(t *testing.T) {
	for _, entity := range []string{"message.downtime", "message.car.changed", ""} {
		if !RoleAllowedForChannel(entity, "Менеджер") {
			t.Errorf("%q should accept manager", entity)
		}
	}
}

func TestRoleAllowedForChannel_HiringRequestAllowlist(t *testing.T) {
	allowed := []string{"Админ", "admin", "Руководитель", "leader", "HR", "Hr", "hr", "Руководитель отдела", "dept_leader"}
	for _, role := range allowed {
		if !RoleAllowedForChannel(HiringRequestChannelEvent, role) {
			t.Errorf("hiring_request should allow %q", role)
		}
	}
	denied := []string{"Менеджер", "manager", "Старший менеджер", "senior_manager", "superadmin", ""}
	for _, role := range denied {
		if RoleAllowedForChannel(HiringRequestChannelEvent, role) {
			t.Errorf("hiring_request must deny %q", role)
		}
	}
}

func TestChannelHasRoleACL(t *testing.T) {
	if !ChannelHasRoleACL(HiringRequestChannelEvent) {
		t.Fatal("hiring_request must have role ACL")
	}
	if ChannelHasRoleACL("message.approval") {
		t.Fatal("approval stays open (all ERP users)")
	}
}
