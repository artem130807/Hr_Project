import {useSortable} from "@dnd-kit/sortable";
import {CSS} from "@dnd-kit/utilities";

function SortableRow({employee, onEdit, onDelete, onStats}) {
    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        transition
    } = useSortable({id: employee.id})

    const style = {
        transform: CSS.Transform.toString(transform),
        transition
    }

    const getRoleColor = (role) => {
        switch (role) {
            case 'owner': return 'bg-purple-50 text-purple-700 border-purple-200';
            case 'hr': return 'bg-blue-50 text-blue-700 border-blue-200';
            case 'lead': return 'bg-emerald-50 text-emerald-700 border-emerald-200';
            case 'dev': return 'bg-slate-100 text-slate-700 border-slate-200';
            default: return 'bg-gray-50 text-gray-700 border-gray-200';
        }
    };

    return (
        <tr ref={setNodeRef} style={style} className="border-b border-slate-100 hover:bg-slate-50/80 transition-colors group">
            <td className="px-6 py-4 cursor-grab active:cursor-grabbing text-slate-300 hover:text-slate-500 w-12" {...attributes} {...listeners}>
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8h16M4 16h16" /></svg>
            </td>
            <td className="px-6 py-4">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center text-slate-600 font-bold text-sm border border-slate-200 shrink-0">
                        {(employee.full_name || employee.name || employee.username || "U").charAt(0).toUpperCase()}
                    </div>
                    <div>
                        <div className="font-bold text-slate-900 leading-snug">
                            {employee.full_name || employee.name || employee.username}
                            {employee.erp_user_id ? (
                                <span
                                    className="ml-2 inline-flex align-middle text-[10px] font-semibold uppercase tracking-wide text-teal-700 bg-teal-50 border border-teal-200 px-1.5 py-0.5 rounded"
                                    title={`ERP id: ${employee.erp_user_id}`}
                                >
                                    ERP
                                </span>
                            ) : null}
                        </div>
                        <div className="text-xs text-slate-500 font-medium">ID: {employee.id}</div>
                    </div>
                </div>
            </td>
            <td className="px-6 py-4">
                <div className="flex items-center gap-2 text-sm text-slate-600 font-medium bg-slate-50 border border-slate-200 w-fit px-2.5 py-1 rounded-lg">
                    <svg className="w-3.5 h-3.5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>
                    {employee.username}
                </div>
            </td>
            <td className="px-6 py-4">
                <span className={`inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-bold uppercase tracking-wider border ${getRoleColor(employee.role)}`}>
                    {employee.role}
                </span>
                {employee.department && (
                    <div className="text-xs text-slate-500 font-medium mt-1.5">{employee.department}</div>
                )}
            </td>
            <td className="px-6 py-4">
                <div className="text-sm font-medium text-slate-600">
                    {employee.created_at
                        ? new Date(employee.created_at).toLocaleDateString("ru-RU")
                        : "—"}
                </div>
            </td>
            <td className="px-6 py-4 text-right">
                <div className="flex justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button 
                        onClick={() => onStats(employee)} 
                        className="w-8 h-8 rounded-lg bg-white border border-blue-200 text-blue-500 hover:text-blue-700 hover:bg-blue-50 flex items-center justify-center transition-all shadow-sm"
                        title="Статистика"
                    >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
                    </button>
                    <button 
                        onClick={() => onEdit(employee)} 
                        className="w-8 h-8 rounded-lg bg-white border border-slate-200 text-slate-500 hover:text-slate-900 hover:bg-slate-50 hover:border-slate-300 flex items-center justify-center transition-all shadow-sm"
                        title="Редактировать"
                    >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                    </button>
                    <button 
                        onClick={() => onDelete(employee.id)} 
                        className="w-8 h-8 rounded-lg bg-white border border-red-200 text-red-500 hover:text-red-700 hover:bg-red-50 flex items-center justify-center transition-all shadow-sm"
                        title="Удалить"
                    >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                    </button>
                </div>
            </td>
        </tr>
    )
}

export default function EmployeeTable({employees, onDelete, onEdit, onStats}) {
    // Note: the original props were onEmployeeDeleted and onEmployeeEdit
    // but the caller passing them inside SortableContext might pass them as onEdit / onDelete. 
    // We will support both naming variants for safety.
    const editHandler = onEdit || arguments[0].onEmployeeEdit;
    const deleteHandler = onDelete || arguments[0].onEmployeeDeleted;
    const statsHandler = onStats || arguments[0].onEmployeeStats;

    if(!employees || employees.length === 0) {
        return null;
    }

    return (
        <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200">
                <thead className="bg-slate-50">
                    <tr>
                        <th className="px-6 py-4 text-left w-12"></th>
                        <th className="px-6 py-4 text-left text-xs font-bold text-slate-500 uppercase tracking-wider">
                            Сотрудник
                        </th>
                        <th className="px-6 py-4 text-left text-xs font-bold text-slate-500 uppercase tracking-wider">
                            Логин
                        </th>
                        <th className="px-6 py-4 text-left text-xs font-bold text-slate-500 uppercase tracking-wider">
                            Роль / Отдел
                        </th>
                        <th className="px-6 py-4 text-left text-xs font-bold text-slate-500 uppercase tracking-wider">
                            Дата создания
                        </th>
                        <th className="px-6 py-4 text-right text-xs font-bold text-slate-500 uppercase tracking-wider">
                            Действия
                        </th>
                    </tr>
                </thead>
                <tbody className="bg-white divide-y divide-slate-100">
                    {employees.map(employee => (
                        <SortableRow
                            key={employee.id}
                            employee={employee}
                            onEdit={editHandler}
                            onDelete={deleteHandler}
                            onStats={statsHandler}
                        />
                    ))}
                </tbody>
            </table>
        </div>
    )
}