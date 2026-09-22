// internal/infrastructure/logger/logger.go
package logger

import (
	"log/slog"
	"os"
	"strings"
)

// New создаёт slog-логгер с текстовым или JSON-форматом в зависимости от env.
// level — строка ("debug", "info", "warn", "error"); пустая строка = info.
// jsonFmt — true для JSON-вывода (удобно для production/сборщиков логов).
func New(level string, jsonFmt bool) *slog.Logger {
	lvl := parseLevel(level)

	var handler slog.Handler
	opts := &slog.HandlerOptions{Level: lvl}
	if jsonFmt {
		handler = slog.NewJSONHandler(os.Stdout, opts)
	} else {
		handler = slog.NewTextHandler(os.Stdout, opts)
	}
	return slog.New(handler)
}

func parseLevel(level string) slog.Level {
	switch strings.ToLower(strings.TrimSpace(level)) {
	case "debug":
		return slog.LevelDebug
	case "warn", "warning":
		return slog.LevelWarn
	case "error":
		return slog.LevelError
	default:
		return slog.LevelInfo
	}
}
