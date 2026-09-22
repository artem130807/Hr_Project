// internal/pkg/config/config.go
package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"
)

// RabbitConfig — параметры подключения и потребления из RabbitMQ.
type RabbitConfig struct {
	URL          string        // amqp://user:pass@host:port/vhost
	Queue        string        // имя потребляемой очередии
	NotifyQueue  string        // очередь публикации hr.event.notify
	ConsumerTag  string        // идентификатор consumer-а для брокера
	DurableQueue bool          // durable-очередь (переживает рестарт брокера)
	Prefetch     int           // QoS prefetch count (unacked сообщений на consumer)
	DialTimeout  time.Duration // таймаут установки соединения
}

// WorkerConfig — параметры пула воркеров.
type WorkerConfig struct {
	Concurrency int // число параллельных обработчиков
	Buffer      int // буфер канала распределения jobs
}

// ERPConfig — параметры обращения к erp-backend (источник пользователей).
type ERPConfig struct {
	BaseURL        string        // например, http://erp-backend.internal
	RequestTimeout time.Duration // таймаут одного HTTP-запроса
	ServiceToken   string        // X-Service-Token (MESSAGE_SERVICE_TOKEN в erp-backend)
}

// ChannelSyncConfig — параметры фоновой синхронизации участников каналов
// со справочником пользователей erp-backend.
type ChannelSyncConfig struct {
	PageSize       int           // размер страницы при выборке пользователей (например, 50)
	RateLimit      time.Duration // пауза между страницами для снижения нагрузки
	RequestTimeout time.Duration // таймаут одного запроса к erp-backend
}

// AppConfig — агрегирующая конфигурация приложения, собираемая из env.
type AppConfig struct {
	PostgresDSN           string
	JWTSecret             string
	HTTPAddr              string // например ":8080"
	AutoMigrate           bool   // создавать/обновлять схему при старте (удобно для local)
	InternalServiceToken  string // X-Service-Token для ERP → POST /api/internal/*
	ERP                   ERPConfig
	ChannelSync           ChannelSyncConfig
	SyncInterval          time.Duration // периодичность запуска channelsync.Worker.Run
	Rabbit                RabbitConfig  // потребитель очереди детальных событий message.entity_changed
	Worker                WorkerConfig  // пул обработчиков очереди
	OutboxPollInterval    time.Duration // интервал relay transactional outbox
	LogLevel              string
	VAPIDPublicKey        string // публичный ключ Web Push (PushManager.subscribe)
	VAPIDPrivateKey       string
	VAPIDSubject          string // mailto: или https: URL (RFC 8292)
}

// Load читает конфигурацию из переменных окружения и валидирует обязательные.
func Load() (AppConfig, error) {
	erpTimeout := getEnvDuration("ERP_REQUEST_TIMEOUT", 10*time.Second)

	cfg := AppConfig{
		PostgresDSN:          strings.TrimSpace(os.Getenv("DATABASE_DSN")),
		JWTSecret:            strings.TrimSpace(os.Getenv("JWT_SECRET")),
		HTTPAddr:             getEnv("HTTP_ADDR", ":8080"),
		AutoMigrate:          getEnvBool("AUTO_MIGRATE", false),
		InternalServiceToken: strings.TrimSpace(os.Getenv("INTERNAL_SERVICE_TOKEN")),
		ERP: ERPConfig{
			BaseURL:        strings.TrimRight(strings.TrimSpace(os.Getenv("ERP_BASE_URL")), "/"),
			RequestTimeout: erpTimeout,
			ServiceToken:   strings.TrimSpace(os.Getenv("ERP_SERVICE_TOKEN")),
		},
		ChannelSync: ChannelSyncConfig{
			PageSize:       getEnvInt("CHANNEL_SYNC_PAGE_SIZE", 50),
			RateLimit:      getEnvDuration("CHANNEL_SYNC_RATE_LIMIT", 500*time.Millisecond),
			RequestTimeout: erpTimeout,
		},
		SyncInterval: getEnvDuration("CHANNEL_SYNC_INTERVAL", 5*time.Minute),
		Rabbit: RabbitConfig{
			URL:          strings.TrimSpace(os.Getenv("RABBITMQ_URL")),
			Queue:        getEnv("RABBITMQ_QUEUE_ENTITY_CHANGED", "message.entity_changed"),
			NotifyQueue:  getEnv("RABBITMQ_QUEUE_HR_NOTIFY", "hr.event.notify"),
			ConsumerTag:  getEnv("RABBITMQ_CONSUMER_TAG", "message-service"),
			DurableQueue: getEnvBool("RABBITMQ_DURABLE", true),
			Prefetch:     getEnvInt("RABBITMQ_PREFETCH", 1),
			DialTimeout:  getEnvDuration("RABBITMQ_DIAL_TIMEOUT", 10*time.Second),
		},
		Worker: WorkerConfig{
			// Prefetch по умолчанию 1 → один in-flight; concurrency > 1 почти бесполезен.
			Concurrency: getEnvInt("WORKER_CONCURRENCY", 1),
			Buffer:      getEnvInt("WORKER_BUFFER", 0),
		},
		OutboxPollInterval: getEnvDuration("OUTBOX_POLL_INTERVAL", 2*time.Second),
		LogLevel:           strings.ToLower(strings.TrimSpace(getEnv("LOG_LEVEL", "info"))),
		VAPIDPublicKey:     strings.TrimSpace(os.Getenv("VAPID_PUBLIC_KEY")),
		VAPIDPrivateKey:    strings.TrimSpace(os.Getenv("VAPID_PRIVATE_KEY")),
		VAPIDSubject:       getEnv("VAPID_SUBJECT", "mailto:noreply@localhost"),
	}

	if cfg.PostgresDSN == "" {
		cfg.PostgresDSN = buildPostgresDSN(
			os.Getenv("DB_HOST"), os.Getenv("DB_PORT"),
			os.Getenv("DB_USER"), os.Getenv("DB_PASS"),
			os.Getenv("DB_NAME"),
		)
	}

	var missing []string
	if cfg.PostgresDSN == "" {
		missing = append(missing, "DATABASE_DSN (или DB_HOST/DB_NAME/...)")
	}
	if cfg.JWTSecret == "" {
		missing = append(missing, "JWT_SECRET")
	}
	if cfg.ERP.BaseURL == "" {
		missing = append(missing, "ERP_BASE_URL")
	}
	if cfg.ERP.ServiceToken == "" {
		missing = append(missing, "ERP_SERVICE_TOKEN")
	}
	if len(missing) > 0 {
		return cfg, fmt.Errorf("config: не заданы обязательные переменные: %s", strings.Join(missing, ", "))
	}
	return cfg, nil
}

// buildPostgresDSN собирает DSN вида key=value из отдельных DB_* переменных.
func buildPostgresDSN(host, port, user, pass, name string) string {
	if host == "" || name == "" {
		return ""
	}
	if port == "" {
		port = "5432"
	}
	return fmt.Sprintf(
		"host=%s port=%s user=%s password=%s dbname=%s sslmode=disable TimeZone=UTC",
		host, port, user, pass, name,
	)
}

func getEnv(key, fallback string) string {
	if v := strings.TrimSpace(os.Getenv(key)); v != "" {
		return v
	}
	return fallback
}

func getEnvInt(key string, fallback int) int {
	v := strings.TrimSpace(os.Getenv(key))
	if v == "" {
		return fallback
	}
	n, err := strconv.Atoi(v)
	if err != nil {
		return fallback
	}
	return n
}

func getEnvBool(key string, fallback bool) bool {
	v := strings.ToLower(strings.TrimSpace(os.Getenv(key)))
	switch v {
	case "1", "true", "yes", "y", "on":
		return true
	case "0", "false", "no", "n", "off":
		return false
	default:
		return fallback
	}
}

func getEnvDuration(key string, fallback time.Duration) time.Duration {
	v := strings.TrimSpace(os.Getenv(key))
	if v == "" {
		return fallback
	}
	// Поддерживаем и "30s", и число секунд ("30").
	if d, err := time.ParseDuration(v); err == nil {
		return d
	}
	if n, err := strconv.Atoi(v); err == nil {
		return time.Duration(n) * time.Second
	}
	return fallback
}
