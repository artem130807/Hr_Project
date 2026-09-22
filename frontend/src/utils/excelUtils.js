import * as XLSX from 'xlsx'
import { documentFilename } from './documentFilename'

export const exportEmployeesToExcel = (employees) => {
    const data = employees.map(employee => ({
        "ID": employee.id,
        "Имя": employee.full_name || employee.name || '',
        "Логин": employee.username,
        "Пароль": "",
        "Роль": employee.role,
        "Дата создания": employee.created_at ? new Date(employee.created_at).toLocaleDateString() : ""
    }))

    const worksheet = XLSX.utils.json_to_sheet(data)
    const workbook = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(workbook, worksheet, "Сотрудники")

    XLSX.writeFile(workbook, documentFilename({ type: 'Сотрудники', date: new Date(), extension: 'xlsx' }))
}

export const importEmployeesFromExcel = (file) => {
    return new Promise((resolve, reject) => {
        const reader = new FileReader()

        reader.onload = (e) => {
            try {
                const data = new Uint8Array(e.target.result)
                const workbook = XLSX.read(data, {type: 'array'})

                const worksheet = workbook.Sheets[workbook.SheetNames[0]]
                const jsonData = XLSX.utils.sheet_to_json(worksheet)

                const employees =  jsonData.map(row => ({
                    username: row['Логин'] || row['Username'],
                    password: row['Пароль'] || row['password'],
                    name: row["Имя"] || row["Name"],
                    role: row["Роль"] || row["role"] || row['hr']
                }))

                resolve(employees)
            } catch (err) {
                reject(err)
            }
        }
        reader.onerror = (error) => {
            reject(error)
        }
        reader.readAsArrayBuffer(file)
    })
}
