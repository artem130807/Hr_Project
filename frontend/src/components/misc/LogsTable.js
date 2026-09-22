import { useEffect, useState } from "react";
import { getAuditLogs } from "../../services/hrOpsApi";
import { useAlertContext } from "../../context/AlertContext";

export default function LogsTable() {
    const [logs, setLogs] = useState([]);
    const [loading, setLoading] = useState(true);
    const { showAlert } = useAlertContext();

    useEffect(() => {
        (async () => {
            try {
                setLoading(true);
                const data = await getAuditLogs({ limit: 200 });
                setLogs(Array.isArray(data) ? data : []);
            } catch (e) {
                showAlert(`Не удалось загрузить журнал: ${e.message || e}`, "error");
                setLogs([]);
            } finally {
                setLoading(false);
            }
        })();
    }, [showAlert]);

    return (
        <div className="overflow-auto border border-slate-200/60 rounded-2xl bg-white shadow-sm">
            <table className="min-w-full table-auto text-left text-sm">
                <thead className="bg-slate-50 text-slate-600">
                    <tr>
                        <th className="p-3">Дата</th>
                        <th className="p-3">Пользователь</th>
                        <th className="p-3">Действие</th>
                        <th className="p-3">Сущность</th>
                        <th className="p-3">Детали</th>
                    </tr>
                </thead>
                <tbody>
                    {loading ? (
                        <tr>
                            <td className="p-3 text-slate-400" colSpan={5}>Загрузка...</td>
                        </tr>
                    ) : logs.length === 0 ? (
                        <tr>
                            <td className="p-3 text-slate-400" colSpan={5}>Записей пока нет</td>
                        </tr>
                    ) : (
                        logs.map((log) => (
                            <tr key={log.id} className="border-t border-slate-100">
                                <td className="p-3 whitespace-nowrap">
                                    {log.created_at ? new Date(log.created_at).toLocaleString("ru-RU") : "—"}
                                </td>
                                <td className="p-3">{log.actor_name || (log.actor_id ? `#${log.actor_id}` : "—")}</td>
                                <td className="p-3 font-medium">{log.action}</td>
                                <td className="p-3">
                                    {log.entity_type}
                                    {log.entity_id != null ? ` #${log.entity_id}` : ""}
                                </td>
                                <td className="p-3 text-slate-600 max-w-md truncate" title={log.details || ""}>
                                    {log.details || "—"}
                                </td>
                            </tr>
                        ))
                    )}
                </tbody>
            </table>
        </div>
    );
}
