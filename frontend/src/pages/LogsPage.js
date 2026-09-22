import MainLayout from "../layout/MainLayout";
import LogsTable from "../components/misc/LogsTable";

export default function LogsPage() {
    return (
        <MainLayout className="p-6">
            <h1 className="text-3xl font-bold tracking-tight text-slate-900 mb-2">Журнал действий</h1>
            <p className="text-sm text-slate-500 mb-6">Аудит ключевых операций: заявки, найм, публикации, комментарии.</p>
            <LogsTable />
        </MainLayout>
    );
}
