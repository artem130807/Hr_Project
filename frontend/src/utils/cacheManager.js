const CACHE_PREFIX = "hh_dict_"
const CACHE_TTL = 24 * 60 * 60 * 1000

export const cacheManager = {
    set(key, data) {
        const cacheData = {
            data,
            timestamp: Date.now()
        }
        localStorage.setItem(CACHE_PREFIX + key, JSON.stringify(cacheData))
    },

    get(key) {
        const cached = localStorage.getItem(CACHE_PREFIX + key)
        if (!cached) return null

        try {
            const {data, timestamp} = JSON.parse(cached)
            const now = Date.now()

            if(now - timestamp > CACHE_TTL) {
                this.remove(key)
                return null
            }
            return data
        } catch (e) {
            console.error("Error parsing cached data:", e)
            return null
        }
    },

    remove(key) {
        localStorage.removeItem(CACHE_PREFIX + key)
    },

    clearAll() {
        Object.keys(localStorage).forEach(key => {
            if(key.startsWith(CACHE_PREFIX)) {
                localStorage.removeItem(key)
            }
        })
    }
}