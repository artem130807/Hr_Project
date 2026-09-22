// infrastructure/database/unit_of_work.go
package database

import (
	"context"
	"errors"
	"fmt"

	repositories "github.com/yourusername/message-service/internal/domain/contracts/repositories"
	"gorm.io/gorm"
)

// Убеждаемся, что gormUnitOfWork реализует контракты UnitOfWork и Repositories.
var (
	_ repositories.UnitOfWork   = (*gormUnitOfWork)(nil)
	_ repositories.Repositories = (*unitOfWorkRepositories)(nil)
)

// gormUnitOfWork — реализация Unit of Work поверх GORM.
//
// Особенности реализации:
//   - Не хранит транзакцию в полях структуры, благодаря чему объект
//     потокобезопасен и может переиспользоваться (singleton per DB).
//   - Каждая транзакция создаётся заново внутри Do через db.Transaction,
//     который сам отвечает за commit/rollback в зависимости от того,
//     вернёт ли fn ошибку или запанирует.
//   - Репозитории, передаваемые в fn, привязаны именно к этой транзакции.
type gormUnitOfWork struct {
	db *gorm.DB
}

// NewUnitOfWork создаёт UnitOfWork на основе *gorm.DB.
func NewUnitOfWork(db *gorm.DB) repositories.UnitOfWork {
	return &gormUnitOfWork{db: db}
}

// Do выполняет fn внутри одной транзакции.
// При успешном завершении fn — коммитит, при ошибке или панике — откатывает.
// Переданный ctx пробрасывается во все запросы внутри транзакции.
func (u *gormUnitOfWork) Do(ctx context.Context, fn func(ctx context.Context, repos repositories.Repositories) error) error {
	if fn == nil {
		return errors.New("unit of work: fn is nil")
	}

	reposFactory := func(tx *gorm.DB) repositories.Repositories {
		return newUnitOfWorkRepositories(tx)
	}

	err := u.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		return fn(ctx, reposFactory(tx))
	})
	if err != nil {
		return fmt.Errorf("unit of work: %w", err)
	}
	return nil
}

// unitOfWorkRepositories — агрегатор репозиториев, привязанных к одной транзакции.
type unitOfWorkRepositories struct {
	channels *GormChannelRepository
	messages *GormMessageRepository
	settings *GormSettingsRepository
	outbox   *GormOutboxRepository
}

// newUnitOfWorkRepositories создаёт новый набор репозиториев на переданном *gorm.DB.
func newUnitOfWorkRepositories(db *gorm.DB) *unitOfWorkRepositories {
	return &unitOfWorkRepositories{
		channels: NewGormChannelRepository(db),
		messages: NewGormMessageRepository(db),
		settings: NewGormSettingsRepository(db),
		outbox:   NewGormOutboxRepository(db),
	}
}

// Channels возвращает репозиторий каналов.
func (r *unitOfWorkRepositories) Channels() repositories.ChannelRepository {
	return r.channels
}

// Messages возвращает репозиторий сообщений.
func (r *unitOfWorkRepositories) Messages() repositories.MessageRepository {
	return r.messages
}

// Settings возвращает репозиторий настроек канала.
func (r *unitOfWorkRepositories) Settings() repositories.SettingsChannelRepository {
	return r.settings
}

// Outbox возвращает репозиторий transactional outbox.
func (r *unitOfWorkRepositories) Outbox() repositories.OutboxRepository {
	return r.outbox
}
