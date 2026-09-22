import React from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { defaultPathForRole } from "../config/navConfig";

export default function Unauthorized() {
    const { user } = useAuth();
    const home = defaultPathForRole(user?.role);

    return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50 p-8">
            <div className="bg-white rounded-2xl shadow p-8 max-w-md text-center">
                <h1 className="text-2xl font-semibold mb-2">Нет доступа</h1>
                <p className="text-gray-600 mb-6">У вас нет прав для просмотра этой страницы.</p>
                <Link to={home} className="underline">На главную</Link>
            </div>
        </div>
    );
}