import Sidebar from "../components/common/Sidebar";
import NotificationBell from "../components/notifications/NotificationBell";

export default function MainLayout({ children, className }) {
    return (
        <div className="flex bg-slate-50 min-h-screen text-slate-800">
            <Sidebar />
            <div className="flex-1 min-w-0 flex flex-col">
                <header className="sticky top-0 z-30 flex items-center justify-end gap-3 px-8 py-3 bg-slate-50/90 backdrop-blur-sm border-b border-slate-200/60">
                    <NotificationBell />
                </header>
                <div className={`flex-1 p-8 pt-6 min-w-0 ${className ?? ""}`}>
                    <div className="max-w-[1600px] mx-auto">{children}</div>
                </div>
            </div>
        </div>
    );
}
