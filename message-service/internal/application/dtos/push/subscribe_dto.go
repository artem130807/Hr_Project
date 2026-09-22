package push

// SubscribeDto — тело POST /api/push/subscriptions (стандартный PushSubscription.toJSON()).
type SubscribeDto struct {
	Endpoint string        `json:"endpoint"`
	Keys     SubscribeKeys `json:"keys"`
}

type SubscribeKeys struct {
	P256dh string `json:"p256dh"`
	Auth   string `json:"auth"`
}

// UnsubscribeDto — тело DELETE /api/push/subscriptions.
type UnsubscribeDto struct {
	Endpoint string `json:"endpoint"`
}

// VapidPublicKeyDto — публичный ключ для PushManager.subscribe.
type VapidPublicKeyDto struct {
	PublicKey string `json:"public_key"`
	Enabled   bool   `json:"enabled"`
}
