// cmd/api/main.go
//
// Точка входа message-service.
//
// Запускает:
//   - HTTP API-сервер (REST + WebSocket /api/ws)
//   - фоновый цикл синхронизации участников каналов со справочником
//     пользователей erp-backend (channelsync.Worker);
//   - потребитель очереди message.entity_changed (детальные события об
//     изменениях полей машины/водителя/прицепа от erp-backend).
//
// Корректно завершает работу по SIGINT/SIGTERM.
package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	gormlogger "gorm.io/gorm/logger"

	"github.com/yourusername/message-service/internal/application/channelsync"
	"github.com/yourusername/message-service/internal/application/outboxrelay"
	"github.com/yourusername/message-service/internal/application/usecases"
	"github.com/yourusername/message-service/internal/application/worker"
	"github.com/yourusername/message-service/internal/infrastructure/auth"
	"github.com/yourusername/message-service/internal/infrastructure/database"
	"github.com/yourusername/message-service/internal/infrastructure/database/models"
	"github.com/yourusername/message-service/internal/infrastructure/erp"
	rabbitmq "github.com/yourusername/message-service/internal/infrastructure/rabbitMq"
	webpushinfra "github.com/yourusername/message-service/internal/infrastructure/webpush"
	wsinfra "github.com/yourusername/message-service/internal/infrastructure/websocket"
	"github.com/yourusername/message-service/internal/interfaces/http/handlers"
	"github.com/yourusername/message-service/internal/interfaces/http/middleware"
	"github.com/yourusername/message-service/internal/interfaces/http/routes"
	"github.com/yourusername/message-service/internal/pkg/config"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		slog.Error("config load failed", "error", err)
		os.Exit(1)
	}

	log := newLogger(cfg.LogLevel)
	log.Info("message-service starting",
		"erp_base_url", cfg.ERP.BaseURL,
		"sync_interval", cfg.SyncInterval,
		"page_size", cfg.ChannelSync.PageSize,
		"entity_changed_queue", cfg.Rabbit.Queue,
		"hr_notify_queue", cfg.Rabbit.NotifyQueue,
		"rabbit_enabled", cfg.Rabbit.URL != "",
		"web_push_enabled", cfg.VAPIDPublicKey != "" && cfg.VAPIDPrivateKey != "",
	)

	db, err := initDB(cfg.PostgresDSN, cfg.AutoMigrate, log)
	if err != nil {
		log.Error("db init failed", "error", err)
		os.Exit(1)
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	var bg sync.WaitGroup
	uow := database.NewUnitOfWork(db)

	// --- 1) Realtime (WebSocket hub) ---
	wsHub := wsinfra.NewHub(log)
	bg.Add(1)
	go func() {
		defer bg.Done()
		wsHub.Run()
	}()

	// --- 2) Инициализация сервисов аутентификации ---
	authService := auth.NewJWTService(&cfg)
	contextAuth := middleware.NewContextAuth()

	// --- 3) Инициализация сервисов приложения ---
	pushRepo := database.NewGormPushSubscriptionRepository(db)
	webPusher := webpushinfra.NewSender(pushRepo, cfg.VAPIDPublicKey, cfg.VAPIDPrivateKey, cfg.VAPIDSubject, log)
	userProvider := erp.NewClient(cfg.ERP)
	dispatcher := usecases.NewNotificationDispatcher(uow, wsHub, webPusher, userProvider, log)
	messageService := usecases.NewMessageService(uow, contextAuth, dispatcher)
	settingsService := usecases.NewSettingsChannelService(uow, contextAuth)
	channelService := usecases.NewChannelService(uow, contextAuth)
	pushService := usecases.NewPushSubscriptionService(pushRepo, contextAuth, cfg.VAPIDPublicKey)

	// --- 4) Инициализация HTTP-хендлеров ---
	messageHandler := handlers.NewMessageHandler(messageService)
	settingsHandler := handlers.NewSettingsChannelHandler(settingsService)
	channelHandler := handlers.NewChannelHandler(channelService)
	wsHandler := handlers.NewWSHandler(wsHub, authService)
	pushHandler := handlers.NewPushHandler(pushService)

	// --- 5) Роутер ---
	router := routes.NewRouter(
		messageHandler,
		settingsHandler,
		channelHandler,
		wsHandler,
		pushHandler,
		authService,
		cfg.InternalServiceToken,
	)

	// --- 6) Запуск HTTP-сервера ---
	// Без WriteTimeout/ReadTimeout: иначе WebSocket обрывается по дедлайну.
	httpServer := &http.Server{
		Addr:              cfg.HTTPAddr,
		Handler:           router,
		ReadHeaderTimeout: 10 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	bg.Add(1)
	go func() {
		defer bg.Done()
		log.Info("HTTP server listening", "addr", httpServer.Addr)
		if err := httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Error("http server failed", "error", err)
			os.Exit(1)
		}
	}()

	// --- 7) Фоновая синхронизация участников каналов ---
	{
		syncWorker := channelsync.New(uow, userProvider, cfg.ChannelSync, log)
		bg.Add(1)
		go func() {
			defer bg.Done()
			runSyncLoop(ctx, syncWorker, cfg.SyncInterval, log)
		}()
	}

	// --- 8) Потребитель детальных событий message.entity_changed ---
	var entityConsumer *rabbitmq.Consumer
	var notifyPublisher *rabbitmq.Publisher
	if cfg.Rabbit.URL != "" {
		consumer, err := rabbitmq.NewConsumer(cfg.Rabbit)
		if err != nil {
			log.Error("rabbitmq consumer init failed",
				"queue", cfg.Rabbit.Queue, "err", err)
			os.Exit(1)
		}
		entityConsumer = consumer

		eventSvc := usecases.NewEventService(uow, dispatcher, log)
		consumeWorker := worker.New(
			entityConsumer,
			eventSvc.Handle,
			config.WorkerConfig{
				Concurrency: cfg.Worker.Concurrency,
				Buffer:      cfg.Worker.Buffer,
			},
			log.With("queue", cfg.Rabbit.Queue),
		)

		bg.Add(1)
		go func() {
			defer bg.Done()
			log.Info("entity-changed consume worker starting",
				"queue", cfg.Rabbit.Queue,
				"concurrency", cfg.Worker.Concurrency,
			)
			if err := consumeWorker.Run(ctx); err != nil {
				log.Error("entity-changed worker stopped", "err", err)
			}
		}()

		pub, err := rabbitmq.NewPublisher(cfg.Rabbit, cfg.Rabbit.NotifyQueue)
		if err != nil {
			log.Error("rabbitmq notify publisher init failed",
				"queue", cfg.Rabbit.NotifyQueue, "err", err)
			os.Exit(1)
		}
		notifyPublisher = pub
		relay := outboxrelay.New(uow, notifyPublisher, cfg.OutboxPollInterval, 50, log.With("component", "outbox"))
		bg.Add(1)
		go func() {
			defer bg.Done()
			log.Info("outbox relay starting",
				"queue", cfg.Rabbit.NotifyQueue,
				"interval", cfg.OutboxPollInterval,
			)
			if err := relay.Run(ctx); err != nil {
				log.Error("outbox relay stopped", "err", err)
			}
		}()
	} else {
		log.Info("RABBITMQ_URL not set — entity-changed consumer and outbox relay disabled")
	}

	// --- 9) Graceful shutdown ---
	<-ctx.Done()
	log.Info("shutdown signal received, waiting for background tasks")

	// Останавливаем HTTP-сервер с таймаутом
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := httpServer.Shutdown(shutdownCtx); err != nil {
		log.Error("http server shutdown error", "error", err)
	}
	wsHub.Close()

	waitDone := make(chan struct{})
	go func() {
		bg.Wait()
		close(waitDone)
	}()
	select {
	case <-waitDone:
	case <-time.After(15 * time.Second):
		log.Warn("background tasks did not stop in time, forcing shutdown")
	}

	if entityConsumer != nil {
		if err := entityConsumer.Close(); err != nil {
			log.Error("rabbitmq consumer close", "err", err)
		}
	}
	if notifyPublisher != nil {
		if err := notifyPublisher.Close(); err != nil {
			log.Error("rabbitmq publisher close", "err", err)
		}
	}
	if sqlDB, err := db.DB(); err == nil {
		_ = sqlDB.Close()
	}
	log.Info("message-service stopped")
}

// runSyncLoop запускает полный цикл синхронизации немедленно, затем повторяет
// его каждые interval. Цикл завершается при отмене ctx.
func runSyncLoop(ctx context.Context, worker *channelsync.Worker, interval time.Duration, log *slog.Logger) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		if err := worker.Run(ctx); err != nil {
			log.Error("channel sync cycle failed", "error", err)
		}
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
		}
	}
}

// initDB открывает postgres-соединение и настраивает пул.
// При autoMigrate=true создаёт/обновляет таблицы по GORM-моделям (local).
func initDB(dsn string, autoMigrate bool, log *slog.Logger) (*gorm.DB, error) {
	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{
		Logger: gormlogger.Default.LogMode(gormlogger.Warn),
	})
	if err != nil {
		return nil, errors.New("open postgres: " + err.Error())
	}

	sqlDB, err := db.DB()
	if err != nil {
		return nil, errors.New("acquire sql.DB: " + err.Error())
	}
	sqlDB.SetMaxOpenConns(10)
	sqlDB.SetMaxIdleConns(2)
	sqlDB.SetConnMaxLifetime(30 * time.Minute)

	if autoMigrate {
		if err := db.AutoMigrate(
			&models.Channel{},
			&models.Message{},
			&models.SettingsChannel{},
			&models.OutboxMessage{},
			&models.PushSubscription{},
		); err != nil {
			return nil, errors.New("auto migrate: " + err.Error())
		}
		log.Info("postgres auto-migrate completed")
	} else if err := db.AutoMigrate(&models.PushSubscription{}); err != nil {
		log.Warn("push_subscriptions migrate failed", "error", err)
	}

	log.Info("postgres connected")
	return db, nil
}

// newLogger создаёт slog-логгер на stdout с заданным уровнем.
func newLogger(level string) *slog.Logger {
	var lvl slog.Level
	switch level {
	case "debug":
		lvl = slog.LevelDebug
	case "warn":
		lvl = slog.LevelWarn
	case "error":
		lvl = slog.LevelError
	default:
		lvl = slog.LevelInfo
	}
	return slog.New(slog.NewTextHandler(os.Stdout, &slog.HandlerOptions{Level: lvl}))
}
