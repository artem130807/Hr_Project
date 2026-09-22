export default function ChildrenField({children, setChildren}) {
    const update = (index, key, value) => {
        const copy = [...children]
        copy[index][key] = value
        setChildren(copy)
    }

    const add = () => setChildren([...children, {name: "", birthdate: ""}])
    const remove = (i) => setChildren(children.filter((_, idx) => idx !== i))

    return (
        <div>
            <h3 className="font-semibold mb-2">Дети</h3>
            {children.map((child, i) => (
                <div key={i} className="felx gap-2 mb-2">
                    <input placeholder="Имя" className="border p-2 w-1/2" value={child.name} onChange={e => update(i, "name", e.target.value)}/>
                    <input type="date" className="border p-2 rounded w-1/2" value={child.birthdate} onChange={e => update(i, "birthdate", e.target.value)}/>
                    <button onClick={() => remove(i)} type="button" className="text-red-500">x</button>
                </div>
            ))}
            <button type="button" onClick={add} className="text-blue-600 mt-1">+ Добавить ребенка</button>
        </div>
    )
}