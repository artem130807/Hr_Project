// internal/domain/contracts/providers/user_provider.go
package providers

import (
	"context"

	"github.com/google/uuid"
)

// UserProvider — доменный порт источника списка пользователей из внешней
// системы (erp-backend). Инфраструктура (HTTP-клиент к erp-backend)
// реализует этот интерфейс; прикладной слой (channelsync.Worker) зависит
// только от абстракции и не знает деталей транспорта.
//
// Поддержка постраничной выборки позволяет обрабатывать большие справочники
// пользователей без загрузки всего списка в память и без разовой высокой
// нагрузки на erp-backend и message-service.
type UserProvider interface {
	// GetUserIDs возвращает страницу со списком идентификаторов пользователей.
	// page начинается с 1; pageSize — желаемый размер страницы.
	// Поле HasMore=true сигнализирует о наличии следующих страниц.
	GetUserIDs(ctx context.Context, page, pageSize int) (UserPage, error)
}

// UserRef — пользователь из справочника erp-backend (id + роль для ACL каналов).
type UserRef struct {
	ID       uuid.UUID
	RoleID   int
	RoleName string
}

// UserPage — одна страница списка пользователей.
type UserPage struct {
	UserIDs  []uuid.UUID // идентификаторы текущей страницы (обратная совместимость)
	Users    []UserRef   // те же люди с ролью, если erp-backend отдал поле users
	HasRoles bool        // true, если в ответе было поле users (даже пустое)
	Page     int         // номер возвращённой страницы
	Total    int         // общее число записей (0, если источник не отдаёт)
	HasMore  bool        // true, если есть следующая страница
}
