/**
 * CRA dev server: proxy /v1 to the API so the browser stays same-origin
 * (no CORS). Only used when REACT_APP_API_URL is empty.
 */
const { createProxyMiddleware } = require("http-proxy-middleware");

const target =
    process.env.CRA_PROXY_TARGET || "https://hr-platform.alt-cargo.tw1.ru";

module.exports = function setupProxy(app) {
    app.use(
        "/v1",
        createProxyMiddleware({
            target,
            changeOrigin: true,
            secure: true,
            logLevel: "warn",
            onError(err, req, res) {
                // Surface proxy/TLS failures as HTTP 502 instead of a blank browser fetch.
                console.error("[setupProxy]", err.message);
                if (!res.headersSent) {
                    res.writeHead(502, { "Content-Type": "application/json" });
                }
                res.end(JSON.stringify({ detail: `Dev proxy failed: ${err.message}` }));
            },
        })
    );
};
