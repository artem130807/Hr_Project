import {http} from "../../utils/http";
import * as XLSX from "xlsx";
import { useRef } from "react";
import {useAlertContext} from "../../context/AlertContext";
import { documentFilename } from "../../utils/documentFilename";

export default function EmployeeImportExport({ onImportFinish }) {
    const fileRef = useRef();
    const { showAlert } = useAlertContext();
    const parseChildren = (str) => {
        if (!str) return [];
        return str.split(";").map((entry) => {
            const [name, date] = entry.split(":").map((s) => s.trim());
            return { name, birthdate: date };
        });
    };

    const stringifyChildren = (arr) => {
        if (!arr || !arr.length) return "";
        return arr.map((child) => `${child.name}:${child.birthdate}`).join("; ");
    };

    const handleImport = async (e) => {
       const file = e.target.files[0];
       if (!file) return;

       const data = await file.arrayBuffer();
       const workbook = XLSX.read(data);
       const worksheet = workbook.Sheets[workbook.SheetNames[0]];
       const json = XLSX.utils.sheet_to_json(worksheet);

       const parsed = json.map((row) => ({
           full_name: row["ФИО"] || "",
           position: row["Должность"] || "",
           department: row["Отдел"] || "",
           birthdate: row["Дата рождения"] ? new Date(row[""]).toISOString() : null,
           hire_date: row["Дата приема"] ? new Date(row[""]).toISOString() : null,
           hobbies: row["Хобби"] || "",
           children: parseChildren(row["Дети"]),
       }))

        try {
           for(const item of parsed) {
               await http.post("/employees", item)
           }
           onImportFinish?.()
        } catch (e) {
           showAlert("Ошибка импорта сотрудника", "error")
        } finally {
            fileRef.current.value = "";
        }
    };

    const handleExport = async () => {
        try {
            const data = await http.get("/employees")
            const safe = Array.isArray(data) ? data : []
            const formatted = safe.map((emp) => ({
                "ФИО": emp.full_name,
                "Должность": emp.position,
                "Отдел": emp.department,
                "Дата рождения": emp.birthdate,
                "Дата приема": emp.hire_date,
                "Дети": stringifyChildren(emp.children),
                "Хобби": emp.hobbies,
            }))

            const worksheet = XLSX.utils.json_to_sheet(formatted);
            const workbook = XLSX.utils.book_new()
            XLSX.utils.book_append_sheet(workbook, worksheet, "Сотрудники")
            XLSX.writeFile(workbook, documentFilename({ type: "Сотрудники HR", date: new Date(), extension: "xlsx" }))
        } catch (e) {
            showAlert("Ошибка экспорта сотрудника", "error")
        }
    };

    return (
        <div className="flex items-center gap-4 my-4">
            <input
                type="file"
                ref={fileRef}
                accept=".xlsx,.xls,.csv"
                onChange={handleImport}
                className="hidden"
            />
            <button
                onClick={() => fileRef.current?.click()}
                className="bg-green-600 text-white px-4 py-2 rounded"
            >
                Импорт из Excel
            </button>
            <button
                onClick={handleExport}
                className="bg-gray-700 text-white px-4 py-2 rounded"
            >
                Экспорт в Excel
            </button>
        </div>
    );
}
