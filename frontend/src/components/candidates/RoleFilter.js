import React, {useEffect, useState, useRef} from "react";
import { getProfessionalRoles } from "../../services/vacancyApi";



export default function RoleFilter({value, onChange, required = false}) {
    const [roles, setRoles] = useState([]);
    const [search, setSearch] = useState("");
    // eslint-disable-next-line no-unused-vars
    const [selectedRole, setSelectedRole] = useState(null);
    const [loading, setLoading] = useState(true);
    const [isOpen, setIsOpen] = useState(false);
    const wrapperRef = useRef(null);

    const normalizeRoles = (d) => {
        const mapRole = (r) => ({
            id: r?.id ?? r?.value ?? r?.code,
            name: r?.name ?? r?.title ?? r?.label ?? ''
        });

        if (Array.isArray(d)) return d.map(mapRole);
        if (Array.isArray(d?.items)) return d.items.map(mapRole);
        if (Array.isArray(d?.data)) return d.data.map(mapRole);


        if (Array.isArray(d?.categories)) {
            return d.categories.flatMap(cat => {
                const roles = cat?.roles ?? cat?.specializations ?? [];
                return Array.isArray(roles) ? roles.map(mapRole) : [];
            });
        }

        return [];
    };

    useEffect(() => {
        const loadRoles = async () => {
            try {
                setLoading(true);
                const data = await getProfessionalRoles("");
                const normalized = normalizeRoles(data);
                setRoles(normalized);
            } catch (e) {
                console.error("Ошибка загрузки ролей:", e);
                setRoles([]);
            } finally {
                setLoading(false);
            }
        };
        loadRoles();
    }, []);


    useEffect(() => {
        if (value && roles.length > 0) {
            const role = roles.find(r => String(r.id) === String(value));
            if (role) {
                setSelectedRole(role);
                setSearch(role.name);
            }
        }
    }, [value, roles]);


    useEffect(() => {
        const handleClickOutside = (event) => {
            if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
                setIsOpen(false);
            }
        };
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    const handleRoleSelect = (role) => {
        setSelectedRole(role);
        setSearch(role.name);
        onChange(role.id);
        setIsOpen(false);
    };

    const handleSearchChange = (e) => {
        setSearch(e.target.value);
        setIsOpen(true);
        if (!e.target.value) {
            setSelectedRole(null);
            onChange(null);
        }
    };

    const handleFocus = () => {
        setIsOpen(true);
    };

    const filteredRoles = roles.filter(r =>
        r.name.toLowerCase().includes(search.toLowerCase())
    );

    if (loading) {
        return <div className="text-sm text-gray-500">Загрузка ролей...</div>;
    }

    return (
        <div className="relative" ref={wrapperRef}>
            <input
                type="text"
                value={search}
                onChange={handleSearchChange}
                onFocus={handleFocus}
                placeholder="Выберите или начните вводить роль..."
                className="w-full border rounded p-2"
                required={required}
            />

            {isOpen && filteredRoles.length > 0 && (
                <div className="absolute z-10 w-full mt-1 bg-white border rounded shadow-lg max-h-60 overflow-y-auto">
                    {filteredRoles.map((role, index) => (
                        <div
                            key={`${role.id}-${index}`}
                            onClick={() => handleRoleSelect(role)}
                            className="p-2 hover:bg-blue-100 cursor-pointer"
                        >
                            {role.name}
                        </div>
                    ))}
                </div>
            )}

            {isOpen && filteredRoles.length === 0 && (
                <div className="absolute z-10 w-full mt-1 bg-white border rounded shadow-lg p-2 text-gray-500 text-sm">
                    Роли не найдены
                </div>
            )}
        </div>
    );
}