import React, { createContext, useContext, useEffect, useState } from "react";
import { http, resetAuthClearedFlag, refreshSession, AUTH_CLEARED_EVENT } from "../utils/http";
import {
    getAccessToken,
    getAccessTokenPayload,
    getRefreshToken,
    getStoredUser,
    setSessionTokens,
    setStoredUser,
    clearSession,
    isAccessTokenExpired,
} from "../utils/tokenStorage";
import { unsyncWebPushSubscription } from "../services/webPushClient";
import { appPath } from "../utils/publicUrl";

const AuthContext = createContext(null);


export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;

        async function hydrate() {
            const savedUser = getStoredUser();
            let access = getAccessToken();
            const refresh = getRefreshToken();

            // Orphan tokens without a stored user cannot restore the session.
            if (!savedUser) {
                if (access || refresh) clearSession();
                if (!cancelled) {
                    setUser(null);
                    setLoading(false);
                }
                return;
            }

            if (!access && !refresh) {
                if (!cancelled) {
                    setUser(null);
                    setLoading(false);
                }
                return;
            }

            // Renew when access is missing or near/past expiry. Fresh access is kept
            // as-is; signature invalidation after backend restart is handled by the
            // 401 → refresh path in http.js without wiping the session.
            if (refresh && (!access || isAccessTokenExpired())) {
                const ok = await refreshSession();
                access = getAccessToken();
                if (!ok && (!access || isAccessTokenExpired())) {
                    clearSession();
                    if (!cancelled) {
                        setUser(null);
                        setLoading(false);
                    }
                    return;
                }
            } else if (!refresh && (!access || isAccessTokenExpired())) {
                clearSession();
                if (!cancelled) {
                    setUser(null);
                    setLoading(false);
                }
                return;
            }

            if (!cancelled) {
                const claims = getAccessTokenPayload();
                const hydratedUser = savedUser.role_id == null && claims?.role_id != null
                    ? { ...savedUser, role_id: claims.role_id }
                    : savedUser;
                if (hydratedUser !== savedUser) setStoredUser(hydratedUser);
                setUser(hydratedUser);
                setLoading(false);
            }
        }

        hydrate();

        const onCleared = () => {
            if (!cancelled) setUser(null);
        };
        window.addEventListener(AUTH_CLEARED_EVENT, onCleared);

        return () => {
            cancelled = true;
            window.removeEventListener(AUTH_CLEARED_EVENT, onCleared);
        };
    }, []);


    const login = async (username, password) => {
        try {
            resetAuthClearedFlag();
            const formData = new URLSearchParams();
            formData.append('username', username);
            formData.append('password', password);
            formData.append('grant_type', 'password');
            
            const data = await http.post("/token/user", formData, { auth: false });
            if (!data?.access_token) {
                throw new Error("Сервер не вернул access token");
            }
            if (!data?.refresh_token) {
                throw new Error(
                    "Сервер не вернул refresh token — сессия не сохранится. Проверьте ERP auth (/auth/token)."
                );
            }
            setSessionTokens(data);

            try {
                const me = await http.get("/me");
                if (!me?.id && !me?.username) {
                    throw new Error("Не удалось получить профиль пользователя");
                }

                const claims = getAccessTokenPayload();
                const userData = {
                    id: me.erp_user_id || me.id,
                    name: me.full_name || me.username,
                    role: me.role,
                    role_id: me.role_id ?? me.role?.id ?? claims?.role_id ?? null,
                    department: me.department || null,
                    username: me.username,
                    erp_user_id: me.erp_user_id || me.id,
                };

                setUser(userData);
                setStoredUser(userData);
                return userData;
            } catch (lookupErr) {
                clearSession();
                throw lookupErr;
            }
        } catch (err) {
            let errorMessage = err?.message || "Ошибка входа"

            if(errorMessage.includes("User not found") || errorMessage.includes("404")) {
                throw new Error("Пользователь не найден")
            } else if(errorMessage.includes("Unauthorized") || errorMessage.includes("401") || errorMessage.includes("Incorrect username")) {
                throw new Error("Неверный логин или пароль")
            } else if(errorMessage.includes("CORS") || errorMessage.includes("Failed to fetch") || errorMessage.includes("Нет связи")) {
                throw new Error("Ошибка подключения к серверу")
            } else {
                throw err
            }
        }
    };

    const logout = async () => {
        const refresh = getRefreshToken();
        const access = getAccessToken();
        await unsyncWebPushSubscription();
        try {
            if (refresh) {
                // refresh_token alone is enough for revoke — avoid Bearer 401→refresh loop
                await http.post("/token/logout", { refresh_token: refresh }, { auth: false });
            } else if (access) {
                await http.post("/token/logout", {}, { auth: true });
            }
        } catch (e) {
            // Best-effort server revoke; always clear local session
            console.warn("Logout revoke failed:", e?.message || e);
        }
        setUser(null);
        clearSession();
        resetAuthClearedFlag();
        window.location.replace(appPath("/"));
    };

    return (
        <AuthContext.Provider value={{ user, loading, login, logout, setUser }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    return useContext(AuthContext);
}
