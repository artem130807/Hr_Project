import { http } from "../utils/http";

export const getCallConversations = (params = {}) => {
    const search = new URLSearchParams();
    if (params.limit != null) search.set("limit", String(params.limit));
    if (params.offset != null) search.set("offset", String(params.offset));
    if (params.status) search.set("status", String(params.status));
    const qs = search.toString();
    return http.get(`/call-conversations${qs ? `?${qs}` : ""}`);
};

export const getCallConversation = (id) => http.get(`/call-conversations/${id}`);
