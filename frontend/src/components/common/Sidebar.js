import {NavLink} from "react-router-dom";
import {useAuth} from "../../context/AuthContext";
import {getInviteUrl} from "../../services/userApi";
import {useAlertContext} from "../../context/AlertContext";
import {useState, useEffect} from "react";
import {checkHHAuth, getHHAuthLink} from "../../services/hhAuthApi";
import AutoSelectSection from "../sidebar/AutoSelectSection";
import {menuItemsForRole, isNavGroup, defaultPathForRole} from "../../config/navConfig";
import * as Icons from "./Icons";

export default function Sidebar() {
    const {user, logout} = useAuth();
    const {showAlert} = useAlertContext();
    const [loading, setLoading] = useState(false);
    const [hhAuthPassed, setHhAuthPassed] = useState(null);
    const [showHHModal, setShowHHModal] = useState(false);
    const [openGroups, setOpenGroups] = useState({ Тесты: true });

    const canManageHHAuth =
        user.role === "hr" ||
        user.role === "owner" ||
        user.role === "dev" ||
        user.role === "admin";

    useEffect(() => {
        if (canManageHHAuth) {
            checkHHAuthStatus();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [user.role]);

    const checkHHAuthStatus = async () => {
        try {
            const response = await checkHHAuth();
            setHhAuthPassed(Boolean(response?.auth_passed));
        } catch (err) {
            console.error("Ошибка проверки HH авторизации:", err);
            setHhAuthPassed(false);
        }
    };

    const handleHHAuthClick = () => {
        if (!hhAuthPassed) {
            setShowHHModal(true);
        }
    };

    const handleHHAuth = async () => {
        try {
            setLoading(true);
            const link = await getHHAuthLink();
            let authUrl = typeof link === 'string' ? link.replace(/^["']|["']$/g, '') : link;
            if (authUrl && !authUrl.startsWith('http://') && !authUrl.startsWith('https://')) {
                authUrl = 'https://' + authUrl;
            }
            window.open(authUrl, '_blank');
            setShowHHModal(false);
        } catch (err) {
            showAlert(`Ошибка: ${err.message}`, "error");
        } finally {
            setLoading(false);
        }
    };

    const menuItems = menuItemsForRole(user?.role);
    const homePath = defaultPathForRole(user?.role);

    const handleTelegramLink = async () => {
        try {
            setLoading(true);
            const response = await getInviteUrl(user.id, "hr");
            let inviteUrl = typeof response === 'string' ? response : response.url || response.invite_url || response.link;
            if (inviteUrl && !inviteUrl.startsWith('http://') && !inviteUrl.startsWith('https://')) {
                inviteUrl = 'https://' + inviteUrl;
            }
            if (inviteUrl) {
                window.open(inviteUrl, '_blank');
            } else {
                showAlert("Не удалось получить ссылку из ответа", "error");
            }
        } catch (err) {
            showAlert(`Ошибка: ${err.message}`, "error");
        } finally {
            setLoading(false);
        }
    };

    const toggleGroup = (label) => {
        setOpenGroups((prev) => ({ ...prev, [label]: !prev[label] }));
    };

    return (
        <div className="w-64 h-screen bg-white text-slate-700 border-r border-slate-200 flex flex-col shadow-sm flex-shrink-0 relative z-20">
            <div className="p-6 pb-4 flex justify-center">
                <NavLink to={homePath} className="block hover:opacity-90 transition-opacity">
                    <img src="/icons/alt_logo.png" alt="site-logo" className="w-[100px] object-contain"/>
                </NavLink>
            </div>
            
            <div className="flex-1 overflow-y-auto px-4 custom-scrollbar">
                <nav className="flex flex-col space-y-1 mb-6">
                    {menuItems.map((item) => {
                        const Icon = Icons[item.icon] || Icons.FileTextIcon;
                        if (isNavGroup(item)) {
                            const opened = openGroups[item.label] !== false;
                            return (
                                <div key={item.label} className="space-y-1">
                                    <button
                                        type="button"
                                        onClick={() => toggleGroup(item.label)}
                                        className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition-all"
                                        data-testid={`nav-group-${item.label}`}
                                    >
                                        <Icon className="w-5 h-5 opacity-80" />
                                        <span className="text-sm flex-1 text-left font-medium">{item.label}</span>
                                        <svg
                                            className={`w-4 h-4 text-slate-400 transition-transform ${opened ? "rotate-90" : ""}`}
                                            fill="none"
                                            viewBox="0 0 24 24"
                                            stroke="currentColor"
                                        >
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                        </svg>
                                    </button>
                                    {opened && (
                                        <div className="ml-3 pl-3 border-l border-slate-100 space-y-0.5">
                                            {item.children.map((child) => (
                                                <NavLink
                                                    to={child.to}
                                                    key={child.to}
                                                    end={child.to === "/tests"}
                                                    className={({isActive}) =>
                                                        `flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all ${
                                                            isActive
                                                                ? "bg-yellow-50 text-yellow-800 font-semibold"
                                                                : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                                                        }`
                                                    }
                                                >
                                                    {child.label}
                                                </NavLink>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            );
                        }
                        return (
                            <NavLink 
                                to={item.to} 
                                key={item.to} 
                                className={({isActive}) => 
                                    `flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 ${
                                        isActive 
                                        ? "bg-yellow-50 text-yellow-800 font-semibold shadow-sm border border-yellow-100/50" 
                                        : "hover:bg-slate-50 text-slate-600 hover:text-slate-900"
                                    }`
                                }
                            >
                                <Icon className="w-5 h-5 opacity-80" />
                                <span className="text-sm">{item.label}</span>
                            </NavLink>
                        );
                    })}
                </nav>

                {canManageHHAuth && (
                    <div className="mb-6 space-y-3 px-1">
                        {user.role === "hr" && (
                        <button
                            onClick={handleTelegramLink}
                            disabled={loading}
                            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-slate-100 text-slate-700 rounded-xl hover:bg-slate-200 disabled:opacity-50 text-sm font-medium transition-colors"
                        >
                            {loading ? "Загрузка..." : "Telegram Бот"}
                        </button>
                        )}

                        {hhAuthPassed === null ? (
                            <div className="px-4 py-2 bg-slate-100 text-slate-500 rounded-xl text-sm text-center border border-slate-200">
                                Проверка HH.ru...
                            </div>
                        ) : hhAuthPassed ? (
                            <div className="px-4 py-2 bg-green-50 text-green-700 rounded-xl text-sm text-center border border-green-200/50 font-medium">
                                HH.ru Подключен
                            </div>
                        ) : (
                            <button
                                onClick={handleHHAuthClick}
                                className="w-full px-4 py-2.5 bg-[#e0bb48] text-black rounded-xl hover:bg-[#d4af3a] shadow-sm text-sm font-medium transition-colors"
                            >
                                Войти на HH.ru
                            </button>
                        )}
                    </div>
                )}

                {(user.role === "hr" || user.role === "dev" || user.role === "owner") && (
                    <div className="mb-6 px-1">
                        <AutoSelectSection />
                    </div>
                )}
            </div>

            <div className="p-4 border-t border-slate-100 bg-slate-50">
                <div 
                    onClick={() => window.location.href = '/profile'}
                    className="flex items-center gap-3 px-2 mb-4 cursor-pointer hover:bg-slate-200/50 p-2 rounded-xl transition-colors group"
                    title="Перейти в профиль"
                >
                    <div className="w-10 h-10 rounded-full bg-slate-200 flex items-center justify-center text-slate-600 font-bold text-sm border-2 border-white shadow-sm group-hover:scale-105 transition-transform shrink-0">
                        {user.name ? user.name.charAt(0).toUpperCase() : "U"}
                    </div>
                    <div className="flex-1 overflow-hidden">
                        <div className="text-sm font-bold text-slate-800 truncate leading-tight group-hover:text-slate-900 transition-colors">
                            {user.name || user.username || "Пользователь"}
                        </div>
                        <div className="text-xs font-medium text-slate-500 uppercase tracking-wider mt-0.5 truncate">
                            {user.role} {user.department ? `· ${user.department}` : ""}
                        </div>
                    </div>
                </div>
                <button
                    type="button"
                    onClick={logout}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2 text-slate-600 rounded-xl hover:bg-red-50 hover:text-red-600 text-sm font-medium transition-colors"
                >
                    <Icons.LogOutIcon className="w-4 h-4" />
                    Выйти
                </button>
            </div>

            {showHHModal && (
                <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-[100] p-4">
                    <div className="bg-white rounded-2xl p-8 max-w-md mx-auto shadow-2xl">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-10 h-10 rounded-full bg-yellow-100 flex items-center justify-center text-yellow-600">
                                <Icons.BanIcon className="w-5 h-5"/>
                            </div>
                            <h3 className="text-xl font-bold text-slate-900">Важно!</h3>
                        </div>
                        <p className="text-slate-600 mb-8 leading-relaxed">
                            Авторизуйтесь от лица <strong className="text-slate-900">главного менеджера</strong> на hh.ru. Если вы им не являетесь — попросите главного HR менеджера авторизоваться через свой аккаунт.
                        </p>
                        <div className="flex gap-3 justify-end">
                            <button
                                onClick={() => setShowHHModal(false)}
                                className="px-5 py-2.5 bg-slate-100 text-slate-700 rounded-xl hover:bg-slate-200 font-medium transition-colors"
                            >
                                Отмена
                            </button>
                            <button
                                onClick={handleHHAuth}
                                disabled={loading}
                                className="px-5 py-2.5 bg-[#e0bb48] text-black rounded-xl hover:bg-[#d4af3a] font-medium shadow-sm transition-colors disabled:opacity-50"
                            >
                                {loading ? "Переход..." : "Понятно, войти"}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
