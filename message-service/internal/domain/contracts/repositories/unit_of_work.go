package repositories

import "context"

// Repositories — агрегатор всех репозиториев, доступных в рамках
// одной единицы работы (Unit of Work). Внутри транзакции все методы
// возвращают репозитории, привязанные к текущему соединению/транзакции.
type Repositories interface {
	Channels() ChannelRepository
	Messages() MessageRepository
	Settings() SettingsChannelRepository
	Outbox() OutboxRepository
}

// UnitOfWork реализует паттерн Unit of Work: выполняет переданную функцию
// в рамках одной транзакции. По успешном завершении — коммитит, при ошибке
// или панике — откатывает. Контракт намеренно не предоставляет ручные
// Begin/Commit/Rollback, чтобы исключить утечку незакрытых транзакций и
// сделать использование безопасным (включая многопоточное).
type UnitOfWork interface {
	Do(ctx context.Context, fn func(ctx context.Context, repos Repositories) error) error
}
