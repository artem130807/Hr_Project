import { useEffect, useState } from "react";
import { deleteT2OAuthTokens, getT2OAuthTokens, isT2AtsConnected, putT2OAuthTokens } from "../../services/t2AuthApi";
import { useAlertContext } from "../../context/AlertContext";

export default function T2AtsConnectPanel() {
    const { showAlert } = useAlertContext();
    const [open, setOpen] = useState(false);
    const [connected, setConnected] = useState(false);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [accessToken, setAccessToken] = useState("");
    const [refreshToken, setRefreshToken] = useState("");

    async function loadStatus() {
        setLoading(true);
        try {
            const data = await getT2OAuthTokens();
            setConnected(isT2AtsConnected(data));
        } catch {
            setConnected(false);
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        loadStatus();
    }, []);

    async function handleSave(e) {
        e.preventDefault();
        const access = accessToken.trim();
        const refresh = refreshToken.trim();
        if (!access || !refresh) {
            showAlert?.("Вставьте оба токена из кабинета АТС t2", "error");
            return;
        }
        setSaving(true);
        try {
            await putT2OAuthTokens({ access_token: access, refresh_token: refresh });
            setAccessToken("");
            setRefreshToken("");
            setConnected(true);
            setOpen(false);
            showAlert?.("Токены АТС сохранены. Звонки подтянутся при следующей синхронизации.", "success");
        } catch (err) {
            showAlert?.(err?.message || "Не удалось сохранить токены АТС", "error");
        } finally {
            setSaving(false);
        }
    }

    async function handleDisconnect() {
        setSaving(true);
        try {
            await deleteT2OAuthTokens();
            setConnected(false);
            showAlert?.("Подключение АТС отключено", "success");
        } catch (err) {
            showAlert?.(err?.message || "Не удалось отключить АТС", "error");
        } finally {
            setSaving(false);
        }
    }

    return (
        <div className="mb-4 rounded-2xl border border-slate-200 bg-white px-4 py-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                    <div className="text-sm font-semibold text-slate-800">АТС t2</div>
                    <p className="text-xs text-slate-500 mt-0.5" data-testid="t2-ats-status">
                        {loading
                            ? "Проверяем подключение…"
                            : connected
                                ? "Токены сохранены в платформе. Обновляются самостоятельно."
                                : "Вставьте пару токенов из кабинета АТС — иначе звонки не появятся."}
                    </p>
                </div>
                <div className="flex gap-2">
                    {connected && (
                        <button
                            type="button"
                            onClick={handleDisconnect}
                            disabled={saving}
                            className="h-9 px-3 rounded-xl border border-slate-200 text-sm text-slate-600 hover:bg-slate-50"
                        >
                            Отключить
                        </button>
                    )}
                    <button
                        type="button"
                        onClick={() => setOpen((v) => !v)}
                        data-testid="t2-ats-toggle"
                        className="h-9 px-3 rounded-xl bg-[#4f46e5] text-sm font-semibold text-white hover:opacity-90"
                    >
                        {connected ? "Заменить токены" : "Вставить токены"}
                    </button>
                </div>
            </div>
            {open && (
                <form className="mt-3 grid gap-2 sm:grid-cols-2" onSubmit={handleSave}>
                    <label className="block sm:col-span-2 text-xs text-slate-500">
                        Кабинет АТС → профиль организации → «Токен API» → скопировать Access и Refresh. Оба поля обязательны.
                    </label>
                    <input
                        type="password"
                        autoComplete="off"
                        placeholder="Access token"
                        value={accessToken}
                        onChange={(e) => setAccessToken(e.target.value)}
                        data-testid="t2-access-token"
                        className="h-10 px-3 rounded-xl border border-slate-200 text-sm"
                    />
                    <input
                        type="password"
                        autoComplete="off"
                        placeholder="Refresh token"
                        value={refreshToken}
                        onChange={(e) => setRefreshToken(e.target.value)}
                        data-testid="t2-refresh-token"
                        className="h-10 px-3 rounded-xl border border-slate-200 text-sm"
                    />
                    <div className="sm:col-span-2 flex justify-end">
                        <button
                            type="submit"
                            disabled={saving}
                            data-testid="t2-ats-save"
                            className="h-10 px-4 rounded-xl bg-slate-900 text-sm font-semibold text-white disabled:opacity-50"
                        >
                            {saving ? "Сохраняем…" : "Сохранить в платформу"}
                        </button>
                    </div>
                </form>
            )}
        </div>
    );
}
