import { http } from "../utils/http";

export const getT2OAuthTokens = () => http.get("/t2-oauth/tokens");

export const putT2OAuthTokens = (payload) => http.put("/t2-oauth/tokens", payload);

export const deleteT2OAuthTokens = () => http.del("/t2-oauth/tokens");

export function isT2AtsConnected(response) {
    const payload = response?.payload;
    if (!payload || typeof payload !== "object") return false;
    return Boolean(String(payload.access_token || "").trim() && String(payload.refresh_token || "").trim());
}
