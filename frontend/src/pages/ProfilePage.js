import React, { useEffect, useState } from 'react';
import MainLayout from '../layout/MainLayout';
import { useAuth } from '../context/AuthContext';
import { useAlertContext } from '../context/AlertContext';
import { BarChartIcon, CheckCircleIcon } from '../components/common/Icons';
import { interviewsWeekHint, PROFILE_METRIC_LABELS } from '../config/profileMetrics';
import { getHrProfileStats } from '../services/analyticsApi';

export default function ProfilePage() {
    const { user } = useAuth();
    const { showAlert } = useAlertContext();
    const [isEditing, setIsEditing] = useState(false);
    const [saving, setSaving] = useState(false);
    const [hireStats, setHireStats] = useState({
        hired: 0,
        in_work: 0,
        interviews: 0,
        interviews_this_week: 0,
    });
    const [statsLoading, setStatsLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                setStatsLoading(true);
                const res = await getHrProfileStats(user?.erp_user_id || user?.id);
                if (!cancelled) {
                    setHireStats({
                        hired: Number(res?.hired) || 0,
                        in_work: Number(res?.in_work) || 0,
                        interviews: Number(res?.interviews) || 0,
                        interviews_this_week: Number(res?.interviews_this_week) || 0,
                    });
                }
            } catch (e) {
                if (!cancelled) {
                    setHireStats({ hired: 0, in_work: 0, interviews: 0, interviews_this_week: 0 });
                    showAlert(`Не удалось загрузить статистику найма: ${e.message || e}`, "error");
                }
            } finally {
                if (!cancelled) setStatsLoading(false);
            }
        })();
        return () => { cancelled = true; };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [user?.erp_user_id, user?.id]);

    // Profile form state
    const [formData, setFormData] = useState({
        username: user?.username || '',
        name: user?.name || '',
        password: '',
        newPassword: ''
    });

    const mockHoursWorked = Math.floor(Math.random() * 60) + 100; // 100-160
    const mockHoursTotal = 160;
    const mockProgress = Math.round((mockHoursWorked / mockHoursTotal) * 100);

    const mockTasks = [
        { id: 1, title: 'Собеседование: Frontend Разработчик', time: '14:00', type: 'interview', status: 'pending' },
        { id: 2, title: 'Подготовить отчет за неделю', time: '17:00', type: 'task', status: 'pending' },
        { id: 3, title: 'Ознакомить кандидата с оффером', time: '10:00', type: 'onboarding', status: 'completed' }
    ];

    const chartBars = Array.from({ length: 7 }, () => Math.floor(Math.random() * 100) + 20);
    const maxBar = Math.max(...chartBars);

    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
    };

    const handleSave = async (e) => {
        e.preventDefault();
        try {
            setSaving(true);
            showAlert(
                "Изменение профиля и пароля выполняется в ERP. Локальная учётка HR удалена.",
                "warning"
            );
        } catch (error) {
            console.error('Ошибка при обновлении профиля:', error);
            showAlert('Ошибка при обновлении профиля.', 'error');
        } finally {
            setSaving(false);
        }
    };

    if (!user) return null;

    return (
        <MainLayout>
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-slate-900">Мой профиль</h1>
                    <p className="mt-1 text-sm text-slate-500">Управление личными данными и просмотр статистики.</p>
                </div>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
                
                {/* Left Column: Personal Info */}
                <div className="xl:col-span-1 space-y-6">
                    <div className="bg-white rounded-2xl shadow-sm border border-slate-200/60 overflow-hidden">
                        <div className="h-24 bg-gradient-to-r from-slate-800 to-slate-600"></div>
                        <div className="px-6 pb-6">
                            <div 
                                className="w-20 h-20 rounded-full bg-white flex items-center justify-center text-slate-700 font-bold text-3xl border-4 border-white shadow-md mb-3"
                                style={{ marginTop: '-2.5rem' }}
                            >
                                {user.name ? user.name.charAt(0).toUpperCase() : "U"}
                            </div>
                            <div>
                                <h2 className="text-xl font-bold text-slate-900">{user.name || 'Пользователь'}</h2>
                                <p className="text-sm font-medium text-slate-500 mt-1">@{user.username || user.login}</p>
                                <div className="flex items-center gap-2 mt-3">
                                    <span className="px-2.5 py-1 rounded-lg text-xs font-bold uppercase tracking-wider bg-slate-100 text-slate-700 border border-slate-200">
                                        {user.role}
                                    </span>
                                    {user.department && (
                                        <span className="text-sm text-slate-500 font-medium">{user.department}</span>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200/60">
                        <div className="flex justify-between items-center mb-6">
                            <h3 className="text-lg font-bold text-slate-900">Настройки профиля</h3>
                            {!isEditing && (
                                <button 
                                    onClick={() => setIsEditing(true)}
                                    className="text-sm font-semibold text-[#cda834] hover:text-[#b8942b] transition-colors"
                                >
                                    Изменить
                                </button>
                            )}
                        </div>

                        {isEditing ? (
                            <form onSubmit={handleSave} className="space-y-4">
                                <div>
                                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">ФИО</label>
                                    <input 
                                        type="text" 
                                        name="name"
                                        value={formData.name}
                                        onChange={handleInputChange}
                                        required
                                        className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#cda834]/50 focus:border-[#cda834] transition-all"
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Логин</label>
                                    <input 
                                        type="text" 
                                        name="username"
                                        value={formData.username}
                                        onChange={handleInputChange}
                                        required
                                        className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#cda834]/50 focus:border-[#cda834] transition-all"
                                    />
                                </div>
                                <div className="pt-4 border-t border-slate-100">
                                    <h4 className="text-sm font-bold text-slate-800 mb-4">Смена пароля</h4>
                                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Новый пароль (необязательно)</label>
                                    <input 
                                        type="password" 
                                        name="newPassword"
                                        value={formData.newPassword}
                                        onChange={handleInputChange}
                                        placeholder="Оставьте пустым, чтобы не менять"
                                        className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#cda834]/50 focus:border-[#cda834] transition-all"
                                    />
                                </div>
                                <div className="flex gap-3 pt-2">
                                    <button 
                                        type="button"
                                        onClick={() => setIsEditing(false)}
                                        className="flex-1 bg-white border border-slate-200 text-slate-700 px-4 py-2.5 rounded-xl hover:bg-slate-50 transition-colors shadow-sm text-sm font-medium"
                                    >
                                        Отмена
                                    </button>
                                    <button 
                                        type="submit"
                                        disabled={saving}
                                        className="flex-1 bg-[#cda834] text-white px-4 py-2.5 rounded-xl hover:bg-[#b8942b] transition-colors shadow-sm text-sm font-medium disabled:opacity-70"
                                    >
                                        {saving ? 'Сохранение...' : 'Сохранить'}
                                    </button>
                                </div>
                            </form>
                        ) : (
                            <div className="space-y-5">
                                <div>
                                    <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">ФИО</div>
                                    <div className="text-sm font-medium text-slate-800">{user.name || 'Не указано'}</div>
                                </div>
                                <div>
                                    <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Логин</div>
                                    <div className="text-sm font-medium text-slate-800">{user.username || user.login}</div>
                                </div>
                                <div>
                                    <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Пароль</div>
                                    <div className="text-sm font-medium text-slate-800">••••••••</div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Right Column: Stats & Tasks */}
                <div className="xl:col-span-2 space-y-6">
                    {/* Metrics Grid */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
                        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200/60 relative overflow-hidden group">
                            <div className="absolute -right-6 -top-6 w-24 h-24 bg-blue-50 rounded-full group-hover:scale-110 transition-transform"></div>
                            <div className="relative">
                                <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
                                    {PROFILE_METRIC_LABELS.interviews}
                                </div>
                                <div className="text-3xl font-black text-slate-900" data-testid="profile-interviews-count">
                                    {statsLoading ? "…" : hireStats.interviews}
                                </div>
                                <div
                                    className={`text-xs font-medium mt-2 flex items-center gap-1 ${
                                        hireStats.interviews_this_week > 0 ? "text-emerald-500" : "text-slate-400"
                                    }`}
                                    data-testid="profile-interviews-week"
                                >
                                    {hireStats.interviews_this_week > 0 ? (
                                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" /></svg>
                                    ) : null}
                                    {statsLoading ? "…" : interviewsWeekHint(hireStats.interviews_this_week)}
                                </div>
                            </div>
                        </div>

                        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200/60 relative overflow-hidden group">
                            <div className="absolute -right-6 -top-6 w-24 h-24 bg-emerald-50 rounded-full group-hover:scale-110 transition-transform"></div>
                            <div className="relative">
                                <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
                                    {PROFILE_METRIC_LABELS.hired}
                                </div>
                                <div className="text-3xl font-black text-slate-900" data-testid="profile-hired-count">
                                    {statsLoading ? "…" : hireStats.hired}
                                </div>
                                <div className="text-xs font-medium text-emerald-500 mt-2 flex items-center gap-1" data-testid="profile-in-work-count">
                                    {PROFILE_METRIC_LABELS.inWork}: {statsLoading ? "…" : hireStats.in_work}
                                </div>
                            </div>
                        </div>

                        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200/60 flex flex-col justify-center">
                            <div className="flex justify-between items-end mb-2">
                                <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                                    {PROFILE_METRIC_LABELS.hours}
                                </div>
                                <div className="text-sm font-bold text-slate-700">{mockHoursWorked} / {mockHoursTotal}</div>
                            </div>
                            <div className="w-full bg-slate-100 rounded-full h-2.5 mb-2 overflow-hidden border border-slate-200/50">
                                <div 
                                    className="bg-[#cda834] h-2.5 rounded-full transition-all duration-1000 ease-out" 
                                    style={{ width: `${mockProgress}%` }}
                                ></div>
                            </div>
                            <div className="text-xs font-medium text-slate-500 text-right">{mockProgress}% от нормы</div>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        {/* Tasks */}
                        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200/60">
                            <div className="flex items-center justify-between mb-6">
                                <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                                    <CheckCircleIcon className="w-5 h-5 text-slate-400" />
                                    Задачи на сегодня
                                </h3>
                            </div>
                            <div className="space-y-4">
                                {mockTasks.map(task => (
                                    <div key={task.id} className="flex items-start gap-4 p-4 rounded-xl border border-slate-100 bg-slate-50 hover:bg-slate-100 transition-colors">
                                        <div className={`mt-0.5 w-5 h-5 rounded-full flex items-center justify-center border-2 shrink-0 ${task.status === 'completed' ? 'bg-emerald-500 border-emerald-500 text-white' : 'border-slate-300 bg-white'}`}>
                                            {task.status === 'completed' && <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>}
                                        </div>
                                        <div>
                                            <div className={`text-sm font-bold ${task.status === 'completed' ? 'text-slate-400 line-through' : 'text-slate-800'}`}>
                                                {task.title}
                                            </div>
                                            <div className="text-xs font-medium text-slate-500 mt-1 flex items-center gap-1.5">
                                                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                                                {task.time}
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Chart */}
                        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200/60 flex flex-col">
                            <div className="flex items-center justify-between mb-6">
                                <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                                    <BarChartIcon />
                                    Моя активность
                                </h3>
                            </div>
                            <div className="h-48 flex items-end justify-between gap-3 px-2 flex-1">
                                {chartBars.map((val, i) => (
                                    <div key={i} className="w-full bg-slate-100 rounded-t-lg relative group cursor-pointer transition-all hover:bg-slate-200" style={{ height: '100%' }}>
                                        <div 
                                            className="absolute bottom-0 left-0 w-full bg-slate-800 rounded-t-lg transition-all duration-500 group-hover:bg-slate-700" 
                                            style={{ height: `${(val / maxBar) * 100}%` }}
                                        ></div>
                                    </div>
                                ))}
                            </div>
                            <div className="flex justify-between mt-3 px-2 text-xs font-medium text-slate-400">
                                <span>Пн</span>
                                <span>Вт</span>
                                <span>Ср</span>
                                <span>Чт</span>
                                <span>Пт</span>
                                <span>Сб</span>
                                <span>Вс</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </MainLayout>
    );
}