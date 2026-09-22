export default function AnalyticsTable({ data }) {
    return (
        <div data-testid="analytics-table">
            <h2 className="text-xl font-semibold mb-2 text-slate-900">Таблица воронки</h2>
            <table className="w-full table-auto border-collapse border border-slate-200 rounded-xl overflow-hidden">
                <thead>
                    <tr className="bg-slate-50">
                        <th className="border border-slate-200 px-4 py-2 text-left text-slate-600 font-medium">
                            Статус
                        </th>
                        <th className="border border-slate-200 px-4 py-2 text-slate-600 font-medium">
                            Кол-во кандидатов
                        </th>
                    </tr>
                </thead>
                <tbody>
                    {(data || []).map((row, index) => (
                        <tr key={`${row.name}-${index}`} className="hover:bg-slate-50/80">
                            <td className="border border-slate-200 px-4 py-2 text-slate-800">
                                <span style={{ paddingLeft: (row.depth || 0) * 16 }}>
                                    {(row.depth || 0) > 0 ? "└ " : ""}
                                    {row.name}
                                </span>
                            </td>
                            <td className="border border-slate-200 px-4 py-2 text-center font-medium text-slate-900">
                                {row.count}
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}
