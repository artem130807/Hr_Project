import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { defaultPathForRole } from "../config/navConfig";

export default function ProtectedRoute({ children, roles }) {
    const { user, loading } = useAuth();
    const location = useLocation();

    if (loading) return null;
    if (!user) return <Navigate to="/" replace />;

    if (roles && Array.isArray(roles) && roles.length > 0) {
        if (!user.role || !roles.includes(user.role)) {
            const home = defaultPathForRole(user.role);
            if (home && home !== location.pathname && home !== "/unauthorized") {
                return <Navigate to={home} replace />;
            }
            return <Navigate to="/unauthorized" replace />;
        }
    }

    return children;
}