package settings

// CreateSettingsDto — входной DTO для создания настроек канала.
// UserID берётся из request context внутри сервиса.
type CreateSettingsDto struct {
	ChannelID         int  `json:"channel_id" binding:"required,min=1"`
	IsSendPushMessage bool `json:"is_send_push_message"`
}
