import {http} from "../utils/http";

export const getAdminUsers = (role = null) => {
    const params = role ? `?role=${role}` : ''
    return http.get(`/admin/users${params}`)
}

export const getAdminUser = (id) => http.get(`/admin/user/${id}`)
export const createAdminUser = async (data) => {
    const result = await http.post("/admin/user", data);
    // ERP proxy returns { user, password? }
    if (result && result.user) {
        return { ...result.user, generated_password: result.password || null };
    }
    return result;
}
export const updateAdminUser = (id, data) => http.patch(`/admin/user/${id}`, data)
export const deleteAdminUser = (id) => http.del(`/admin/user/${id}`)