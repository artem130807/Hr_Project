const STORAGE_KEY = "candidates"

export const loadCandidates = () => {
    try {
        const data = localStorage.getItem(STORAGE_KEY)
        return data ? JSON.parse(data) : []
    } catch (err) {
        console.log(err)
        return []
    }
}

export const saveCandidates = candidate => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(candidate))
}