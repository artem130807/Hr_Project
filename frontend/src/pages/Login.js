import { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";
import { defaultPathForRole } from "../config/navConfig";

export default function Login() {
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);
    const [success, setSuccess] = useState("");
    const { login, user, loading: authLoading } = useAuth();
    const navigate = useNavigate();

    useEffect(() => {
        if (!authLoading && user) {
            navigate(defaultPathForRole(user.role), { replace: true });
        }
    }, [authLoading, user, navigate]);

    const handleLogin = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError("");
        setSuccess("");

        try {
            const loggedIn = await login(username, password);
            setSuccess("Вход успешен");
            navigate(defaultPathForRole(loggedIn?.role), { replace: true });
        } catch (err) {
            const errorMessage = err?.message || "Ошибка входа"

            if(errorMessage.includes("User not found") || errorMessage.includes("404")) {
                setError("Пользователь не найден")
            } else if(errorMessage.includes("Unauthorized") || errorMessage.includes("401")) {
                setError("Неверный логин или пароль ")
            } else if(errorMessage.includes("CORS") || errorMessage.includes("Failed to fetch")) {
                setError("Ошибка подключения к серверу. Попробуйте позже")
            } else {
                setError(errorMessage)
            }
        } finally {
            setLoading(false);
        }
    };

    if (authLoading) {
        return (
            <div className="login-screen flex items-center justify-center min-h-screen text-slate-600">
                Проверка сессии…
            </div>
        );
    }

    if (user) {
        return null;
    }

    return (
        <div className="login-screen flex items-center justify-center min-h-screen px-4">
            <form
                onSubmit={handleLogin}
                className="bg-white p-8 rounded-3xl w-full max-w-md shadow-[0_24px_60px_rgba(15,23,42,0.12)]"
            >
                <p className="text-xs uppercase tracking-[0.18em] text-indigo-600 font-semibold">Подбор</p>
                <h1 className="text-[28px] mt-1 mb-1 text-slate-900 font-semibold tracking-tight">Hr платформа</h1>
                <p className="text-sm text-slate-500 mb-6">Вход для команды подбора</p>

                <label className="block text-sm font-medium text-slate-700 mb-1">Логин</label>
                <input
                    type="text"
                    autoComplete="username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="w-full mb-4 border border-slate-200 rounded-xl px-3 py-2.5 focus:border-indigo-500 focus:outline-none focus:ring-4 focus:ring-indigo-100"
                    required
                />

                <label className="block text-sm font-medium text-slate-700 mb-1">Пароль</label>
                <input
                    type="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full mb-4 border border-slate-200 rounded-xl px-3 py-2.5 focus:border-indigo-500 focus:outline-none focus:ring-4 focus:ring-indigo-100"
                    required
                />

                {error && <div className="text-rose-600 text-sm mb-3">{error}</div>}
                {success && <div className="text-emerald-600 text-sm mb-3">{success}</div>}

                <button
                    type="submit"
                    className="w-full bg-indigo-600 text-white font-semibold py-2.5 rounded-xl hover:bg-indigo-700 disabled:opacity-60"
                    disabled={loading}
                >
                    {loading ? "Проверка..." : "Войти"}
                </button>
            </form>
        </div>
    );
}
