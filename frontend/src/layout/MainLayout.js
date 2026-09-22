import Sidebar from "../components/common/Sidebar";
import NotificationBell from "../components/notifications/NotificationBell";

export default function MainLayout({ children, className }) {
    return (
        <div className="flex h-screen overflow-hidden bg-[#eef2ff] text-slate-800">
            <Sidebar />
            <div className="flex-1 min-w-0 flex flex-col overflow-y-auto">
                <header className="sticky top-0 z-30 flex items-center justify-between gap-3 px-4 sm:px-8 py-3 bg-white/85 backdrop-blur-md border-b border-slate-200/80">
                    <div className="text-sm font-medium text-slate-500">Рабочее место</div>
                    <NotificationBell />
                </header>
                <div className={`flex-1 px-4 sm:px-8 py-6 min-w-0 ${className ?? ""}`}>
                    <div className="max-w-[1600px] mx-auto">{children}</div>
                </div>
            </div>
        </div>
    );
}
