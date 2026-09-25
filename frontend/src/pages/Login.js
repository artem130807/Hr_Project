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
            <div className="flex items-center justify-center min-h-screen bg-[#f5f5f5] text-slate-600">
                Проверка сессии…
            </div>
        );
    }

    if (user) {
        return null;
    }

    return (
        <div className="flex items-center justify-center min-h-screen bg-[#f5f5f5]">
            <form
                onSubmit={handleLogin}
                className="bg-white p-8 rounded shadow w-96 border border-[#4f46e5]"
            >
                <h2 className="text-2xl mb-4 text-black font-bold">Вход в систему</h2>

                <input
                    type="text"
                    placeholder="Имя пользователя"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="w-full mb-4 border border-[#666666] rounded p-2 focus:border-[#4f46e5] focus:outline-none"
                    required
                />

                <input
                    type="password"
                    placeholder="Пароль"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full mb-4 border border-[#666666] rounded p-2 focus:border-[#4f46e5] focus:outline-none"
                    required
                />

                {error && <div className="text-red-500 mb-2">{error}</div>}
                {success && <div className="text-green-600 mb-2">{success}</div>}

                <div className="flex space-x-2">
                    <button
                        type="submit"
                        className="flex-1 bg-[#4f46e5] text-white font-medium p-2 rounded hover:bg-[#4338ca]"
                        disabled={loading}
                    >
                        {loading ? "Проверка..." : "Войти"}
                    </button>
                </div>
            </form>
        </div>
    );
}
