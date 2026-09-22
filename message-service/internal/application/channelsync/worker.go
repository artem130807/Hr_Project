// internal/application/channelsync/worker.go
//
// Фоновый воркер синхронизации участников каналов со справочником
// пользователей erp-backend.
//
// Алгоритм:
//  1. Загрузить все каналы один раз (предполагается, что их немного).
//  2. Построить in-memory множества участников каждого канала для O(1) проверки.
//  3. Постранично (page_size, например 50) получать пользователей из erp-backend.
//  4. Для каждой страницы вычислять, каких пользователей ещё нет в каждом канале
//     (с учётом ACL: канал «Заявки на подбор» — только Админ/Руководитель/HR/
//     Руководитель отдела), и атомарно добавлять их через ChannelRepository.AddUsers.
//  4b. После полного обхода справочника вычистить из ACL-каналов тех, кого
//     больше нет в allowlist (менеджеры и пр., попавшие туда старым sync).
//  5. Между страницами выдерживать RateLimit, чтобы не нагружать системы.
//  6. Каждый запрос к erp-backend ограничен RequestTimeout; весь Run — ctx.
//
// Каналы грузятся один раз (а не на каждой странице), чтобы избежать
// N одинаковых выборок; актуальность участников гарантирует атомарный
// AddUsers — он не затирает поле, а дополняет массив в БД.
package channelsync

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	"github.com/google/uuid"

	providers "github.com/yourusername/message-service/internal/domain/contracts/providers"
	repositories "github.com/yourusername/message-service/internal/domain/contracts/repositories"
	domain "github.com/yourusername/message-service/internal/domain/entities"
	"github.com/yourusername/message-service/internal/pkg/config"
)

// Worker синхронизирует участников каналов со справочником erp-backend.
type Worker struct {
	userProvider providers.UserProvider
	uow          repositories.UnitOfWork
	cfg          config.ChannelSyncConfig
	log          *slog.Logger
}

// New создаёт воркер синхронизации каналов.
// Нормализует конфиг (минимум 1 на странице; дефолты для таймаутов/паузы),
// подставляет slog.Default() при отсутствии логгера.
func New(uow repositories.UnitOfWork, userProvider providers.UserProvider, cfg config.ChannelSyncConfig, log *slog.Logger) *Worker {
	if cfg.PageSize < 1 {
		cfg.PageSize = 50
	}
	if cfg.RateLimit <= 0 {
		cfg.RateLimit = 500 * time.Millisecond
	}
	if cfg.RequestTimeout <= 0 {
		cfg.RequestTimeout = 10 * time.Second
	}
	if log == nil {
		log = slog.Default()
	}
	return &Worker{
		userProvider: userProvider,
		uow:          uow,
		cfg:          cfg,
		log:          log,
	}
}

// Run выполняет полный цикл синхронизации и блокируется до его завершения,
// отмены ctx или фатальной ошибки. Возвращает nil для «мягкого» завершения
// по ctx и ошибку — в остальных случаях.
func (w *Worker) Run(ctx context.Context) error {
	w.log.Info("channel sync started",
		"page_size", w.cfg.PageSize, "rate_limit", w.cfg.RateLimit)

	channels, err := w.loadChannels(ctx)
	if err != nil {
		return fmt.Errorf("channelsync: load channels: %w", err)
	}
	if len(channels) == 0 {
		w.log.Info("channelsync: no channels to sync, exiting")
		return nil
	}

	// Множества участников на канал для быстрой проверки «уже есть?».
	memberSets := make([]map[uuid.UUID]bool, len(channels))
	for i, ch := range channels {
		memberSets[i] = toUUIDSet(ch.UsersIds)
	}

	page := 1
	totalAdded := 0
	sawRoles := false
	eligible := make([]map[uuid.UUID]bool, len(channels))
	for i := range channels {
		eligible[i] = map[uuid.UUID]bool{}
	}
	for {
		if err := ctx.Err(); err != nil {
			w.log.Info("channelsync: cancelled", "page", page, "users_added", totalAdded)
			return nil
		}

		userPage, err := w.fetchPage(ctx, page)
		if err != nil {
			return fmt.Errorf("channelsync: page %d: %w", page, err)
		}
		if userPage.HasRoles {
			sawRoles = true
		}
		w.log.Info("channelsync: fetched users",
			"page", page, "count", len(userPage.UserIDs), "has_more", userPage.HasMore, "has_roles", userPage.HasRoles)

		if len(userPage.UserIDs) == 0 && len(userPage.Users) == 0 {
			break
		}

		added, err := w.applyPage(ctx, channels, memberSets, eligible, userPage)
		if err != nil {
			return fmt.Errorf("channelsync: apply page %d: %w", page, err)
		}
		totalAdded += added

		if !userPage.HasMore {
			break
		}
		page++

		// Rate-limit между страницами.
		select {
		case <-ctx.Done():
			w.log.Info("channelsync: cancelled during rate-limit",
				"page", page, "users_added", totalAdded)
			return nil
		case <-time.After(w.cfg.RateLimit):
		}
	}

	pruned, err := w.pruneRestricted(ctx, channels, memberSets, eligible, sawRoles)
	if err != nil {
		return fmt.Errorf("channelsync: prune: %w", err)
	}

	w.log.Info("channel sync finished", "pages", page, "users_added", totalAdded, "users_pruned", pruned)
	return nil
}

// loadChannels загружает все каналы в одной транзакции.
func (w *Worker) loadChannels(ctx context.Context) ([]*domain.Channel, error) {
	var channels []*domain.Channel
	err := w.uow.Do(ctx, func(ctx context.Context, repos repositories.Repositories) error {
		var err error
		channels, err = repos.Channels().FindAll(ctx)
		return err
	})
	return channels, err
}

// fetchPage запрашивает страницу пользователей с отдельным таймаутом,
// чтобы один «зависший» запрос не блокировал весь цикл.
func (w *Worker) fetchPage(ctx context.Context, page int) (providers.UserPage, error) {
	pageCtx, cancel := context.WithTimeout(ctx, w.cfg.RequestTimeout)
	defer cancel()
	return w.userProvider.GetUserIDs(pageCtx, page, w.cfg.PageSize)
}

// applyPage вычисляет, каких пользователей страницы нужно добавить в каждый
// канал, и атомарно дописывает их через AddUsers в одной транзакции.
func (w *Worker) applyPage(
	ctx context.Context,
	channels []*domain.Channel,
	memberSets []map[uuid.UUID]bool,
	eligible []map[uuid.UUID]bool,
	page providers.UserPage,
) (int, error) {
	refs := pageUsers(page)
	additions := make([][]uuid.UUID, len(channels))
	total := 0
	for i, ch := range channels {
		restricted := ChannelHasRoleACL(ch.EntityType)
		if restricted && !page.HasRoles {
			w.log.Warn("channelsync: skip ACL channel without role metadata",
				"channel_id", ch.ID, "entity_type", ch.EntityType)
			continue
		}
		for _, u := range refs {
			if restricted && !RoleAllowedForChannel(ch.EntityType, u.RoleName) {
				continue
			}
			eligible[i][u.ID] = true
			if !memberSets[i][u.ID] {
				additions[i] = append(additions[i], u.ID)
				memberSets[i][u.ID] = true
				total++
			}
		}
	}
	if total == 0 {
		return 0, nil
	}

	err := w.uow.Do(ctx, func(ctx context.Context, repos repositories.Repositories) error {
		for i, ch := range channels {
			if len(additions[i]) == 0 {
				continue
			}
			if err := repos.Channels().AddUsers(ctx, ch.ID, additions[i]); err != nil {
				return err
			}
		}
		return nil
	})
	if err != nil {
		return 0, err
	}

	for i := range channels {
		channels[i].UsersIds = append(channels[i].UsersIds, additions[i]...)
	}
	w.log.Info("channelsync: applied page", "added", total, "channels_touched", countNonEmpty(additions))
	return total, nil
}

// pruneRestricted убирает из ACL-каналов тех, кого нет в allowlist по итогам
// полного прохода справочника. Без HasRoles не трогаем состав (старый ERP).
func (w *Worker) pruneRestricted(
	ctx context.Context,
	channels []*domain.Channel,
	memberSets []map[uuid.UUID]bool,
	eligible []map[uuid.UUID]bool,
	sawRoles bool,
) (int, error) {
	if !sawRoles {
		return 0, nil
	}
	removals := make([][]uuid.UUID, len(channels))
	total := 0
	for i, ch := range channels {
		if !ChannelHasRoleACL(ch.EntityType) {
			continue
		}
		for uid := range memberSets[i] {
			if eligible[i][uid] {
				continue
			}
			removals[i] = append(removals[i], uid)
			delete(memberSets[i], uid)
			total++
		}
	}
	if total == 0 {
		return 0, nil
	}

	err := w.uow.Do(ctx, func(ctx context.Context, repos repositories.Repositories) error {
		for i, ch := range channels {
			if len(removals[i]) == 0 {
				continue
			}
			if err := repos.Channels().RemoveUsers(ctx, ch.ID, removals[i]); err != nil {
				return err
			}
		}
		return nil
	})
	if err != nil {
		return 0, err
	}
	for i := range channels {
		if len(removals[i]) == 0 {
			continue
		}
		drop := toUUIDSet(removals[i])
		kept := channels[i].UsersIds[:0]
		for _, uid := range channels[i].UsersIds {
			if !drop[uid] {
				kept = append(kept, uid)
			}
		}
		channels[i].UsersIds = kept
	}
	w.log.Info("channelsync: pruned restricted channels", "removed", total)
	return total, nil
}

func pageUsers(page providers.UserPage) []providers.UserRef {
	if page.HasRoles {
		return page.Users
	}
	out := make([]providers.UserRef, 0, len(page.UserIDs))
	for _, id := range page.UserIDs {
		out = append(out, providers.UserRef{ID: id})
	}
	return out
}

// toUUIDSet строит множество UUID из слайса для O(1) проверки вхождения.
func toUUIDSet(ids []uuid.UUID) map[uuid.UUID]bool {
	set := make(map[uuid.UUID]bool, len(ids))
	for _, id := range ids {
		set[id] = true
	}
	return set
}

// countNonEmpty возвращает число непустых слайсов в additions.
func countNonEmpty(additions [][]uuid.UUID) int {
	n := 0
	for _, a := range additions {
		if len(a) > 0 {
			n++
		}
	}
	return n
}
