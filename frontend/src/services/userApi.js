import {http} from "../utils/http";

export const getUsers = (role = null) => {
    const params = role ? `?role=${role}` : ''
    return http.get(`/admin/users${params}`)
}

export const getAdminRoles = () => http.get("/admin/roles")

export const createUser = async (data) => {
    const payload = {
        role: data.role,
        user_id: data.user_id || null,
        username: data.username,
        full_name: data.full_name || data.name || null,
        plain_password: data.password || null,
        department: data.department === "it" ? "IT" : data.department,
        date_hired: data.date_hired || null,
    };

    const result = await http.post("/admin/user", payload);
    // ERP proxy returns { user, password? }; keep flat user for callers.
    if (result && result.user) {
        return { ...result.user, generated_password: result.password || null };
    }
    return result;
}
export const updateUser = (id, data) => {
    const payload = {};

    if (data.role) {
        payload.role = data.role;
    }

    if (data.username) {
        payload.username = data.username;
    }

    if (data.full_name !== undefined || data.name !== undefined) {
        payload.full_name = data.full_name ?? data.name ?? null;
    }

    if (data.user_id && typeof data.user_id === 'number') {
        payload.user_id = data.user_id;
    }

    if (data.department !== undefined) {
        payload.department = data.department === "it" ? "IT" : data.department;
    }

    if (data.date_hired !== undefined) {
        payload.date_hired = data.date_hired || null;
    }

    if (data.plain_password) {
        payload.plain_password = data.plain_password;
    }

    return http.patch(`/admin/user/${id}`, payload);
}

export const resetUserPassword = (id) =>
    http.post(`/admin/user/${id}/reset-password`, {});

export const deleteUser = (id) => http.del(`/admin/user/${id}`)
export const getInviteUrl = (id, role) => http.post("/invite_url", { id, role });
