import React from 'react';
import { BarChartIcon } from '../common/Icons';

export default function EmployeeStatsModal({ employee, onClose }) {
    if (!employee) return null;

    // Mock data for statistics
    const mockTrips = Math.floor(Math.random() * 50) + 10;
    const mockRevenue = (mockTrips * 25000 + Math.floor(Math.random() * 500000)).toLocaleString('ru-RU');
    const mockHoursWorked = Math.floor(Math.random() * 60) + 100; // 100-160
    const mockHoursTotal = 160;
    const mockProgress = Math.round((mockHoursWorked / mockHoursTotal) * 100);
    
    // Mock chart data (last 7 days/weeks/etc.)
    const chartBars = Array.from({ length: 7 }, () => Math.floor(Math.random() * 100) + 20);
    const maxBar = Math.max(...chartBars);

    // Mock interactions
    const mockInteractions = [
        { id: 1, type: "Рейс закрыт", details: "Рейс #4502 (Москва - Санкт-Петербург)", time: "Сегодня, 14:30" },
        { id: 2, type: "Вход в систему", details: "Рабочее место: Офис 1", time: "Сегодня, 09:00" },
        { id: 3, type: "Отчет сформирован", details: "Отчет за неделю", time: "Вчера, 18:15" },
        { id: 4, type: "Задача", details: "Обзвон кандидатов", time: "Вчера, 12:00" },
    ];

    return (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4 sm:p-6" onClick={onClose}>
            <div className="bg-white rounded-3xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden" onClick={e => e.stopPropagation()}>
                
                {/* Header */}
                <div className="px-8 py-6 border-b border-slate-100 flex justify-between items-center bg-slate-50/50 shrink-0">
                    <div className="flex items-center gap-4">
                        <div className="w-14 h-14 rounded-full bg-slate-200 flex items-center justify-center text-slate-700 font-bold text-xl border-2 border-white shadow-sm">
                            {(employee.full_name || employee.name || employee.username || "U").charAt(0).toUpperCase()}
                        </div>
                        <div>
                            <h2 className="text-xl font-bold text-slate-900">
                                {employee.full_name || employee.name || employee.username}
                            </h2>
                            <div className="flex items-center gap-2 mt-1">
                                <span className="px-2.5 py-0.5 rounded-md text-xs font-bold uppercase tracking-wider bg-slate-200 text-slate-700 border border-slate-300">
                                    {employee.role}
                                </span>
                                {employee.department && (
                                    <span className="text-sm text-slate-500 font-medium">{employee.department}</span>
                                )}
                            </div>
                        </div>
                    </div>
                    <button onClick={onClose} className="p-2 text-slate-400 hover:text-slate-600 hover:bg-white rounded-full transition-colors shadow-sm bg-slate-100 border border-slate-200">
                        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                    </button>
                </div>

                {/* Body */}
                <div className="p-8 overflow-y-auto custom-scrollbar flex-1 space-y-8 bg-slate-50">
                    
                    {/* Metrics Grid */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200/60 relative overflow-hidden group">
                            <div className="absolute -right-6 -top-6 w-24 h-24 bg-blue-50 rounded-full group-hover:scale-110 transition-transform"></div>
                            <div className="relative">
                                <div className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-2">Закрыто рейсов</div>
                                <div className="text-4xl font-black text-slate-900">{mockTrips}</div>
                                <div className="text-xs font-medium text-emerald-500 mt-2 flex items-center gap-1">
                                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" /></svg>
                                    +12% за месяц
                                </div>
                            </div>
                        </div>

                        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200/60 relative overflow-hidden group">
                            <div className="absolute -right-6 -top-6 w-24 h-24 bg-emerald-50 rounded-full group-hover:scale-110 transition-transform"></div>
                            <div className="relative">
                                <div className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-2">Принесено выручки</div>
                                <div className="text-3xl font-black text-slate-900">{mockRevenue} <span className="text-xl text-slate-400">₽</span></div>
                                <div className="text-xs font-medium text-emerald-500 mt-2 flex items-center gap-1">
                                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" /></svg>
                                    Отличный показатель
                                </div>
                            </div>
                        </div>

                        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200/60 flex flex-col justify-center">
                            <div className="flex justify-between items-end mb-2">
                                <div className="text-sm font-bold text-slate-400 uppercase tracking-wider">Время работы</div>
                                <div className="text-sm font-bold text-slate-700">{mockHoursWorked} / {mockHoursTotal} ч.</div>
                            </div>
                            <div className="w-full bg-slate-100 rounded-full h-3 mb-2 overflow-hidden border border-slate-200/50">
                                <div 
                                    className="bg-[#cda834] h-3 rounded-full transition-all duration-1000 ease-out" 
                                    style={{ width: `${mockProgress}%` }}
                                ></div>
                            </div>
                            <div className="text-xs font-medium text-slate-500 text-right">{mockProgress}% от плана</div>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        {/* Chart Area */}
                        <div className="lg:col-span-2 bg-white rounded-2xl p-6 shadow-sm border border-slate-200/60">
                            <div className="flex items-center justify-between mb-6">
                                <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                                    <BarChartIcon />
                                    График эффективности
                                </h3>
                                <select className="text-xs font-bold text-slate-500 uppercase tracking-wider bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:border-[#cda834]">
                                    <option>За неделю</option>
                                    <option>За месяц</option>
                                    <option>За год</option>
                                </select>
                            </div>
                            <div className="h-48 flex items-end justify-between gap-2 px-2">
                                {chartBars.map((val, i) => (
                                    <div key={i} className="w-full bg-slate-100 rounded-t-lg relative group cursor-pointer transition-all hover:bg-slate-200" style={{ height: '100%' }}>
                                        <div 
                                            className="absolute bottom-0 left-0 w-full bg-[#cda834]/80 rounded-t-lg transition-all duration-500 group-hover:bg-[#cda834]" 
                                            style={{ height: `${(val / maxBar) * 100}%` }}
                                        ></div>
                                        {/* Tooltip mock */}
                                        <div className="absolute -top-8 left-1/2 -translate-x-1/2 bg-slate-800 text-white text-xs py-1 px-2 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none">
                                            Значение: {val}
                                        </div>
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

                        {/* Interactions Area */}
                        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200/60 flex flex-col">
                            <h3 className="text-base font-bold text-slate-900 mb-6 flex items-center gap-2">
                                <svg className="w-5 h-5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                                Взаимодействия
                            </h3>
                            <div className="flex-1 relative">
                                <div className="absolute left-3.5 top-2 bottom-0 w-px bg-slate-200"></div>
                                <div className="space-y-5">
                                    {mockInteractions.map((interaction, idx) => (
                                        <div key={interaction.id} className="relative pl-10">
                                            <div className={`absolute left-[11px] top-1.5 w-2 h-2 rounded-full border-2 border-white ring-1 ring-slate-300 ${idx === 0 ? 'bg-[#cda834] ring-[#cda834]/50' : 'bg-slate-400'}`}></div>
                                            <div className="text-xs font-bold text-slate-500 mb-0.5">{interaction.time}</div>
                                            <div className="text-sm font-semibold text-slate-900">{interaction.type}</div>
                                            <div className="text-xs font-medium text-slate-500 mt-1">{interaction.details}</div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                            <button className="w-full mt-4 py-2 bg-slate-50 hover:bg-slate-100 text-slate-600 text-xs font-bold uppercase tracking-wider rounded-xl transition-colors border border-slate-200">
                                Показать все
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
