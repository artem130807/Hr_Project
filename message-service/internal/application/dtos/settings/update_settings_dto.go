package settings

// UpdateSettingsDto — входной DTO для изменения настроек канала пользователя.
type UpdateSettingsDto struct {
	IsSendPushMessage *bool `json:"is_send_push_message,omitempty"`
}
