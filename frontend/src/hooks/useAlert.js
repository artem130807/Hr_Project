import {useState, useCallback} from "react";

let alertIdCounter = 0;

export function useAlert() {
    const [alerts, setAlerts] = useState([])

    const showAlert = useCallback((message, type = 'info') => {
        const id = ++alertIdCounter;
        setAlerts(prev => [...prev, {id, message, type}])
    }, [])

    const closeAlert = useCallback((id) => {
        setAlerts(prev => prev.filter(alert => alert.id !== id))
    }, [])

    return {alerts, showAlert, closeAlert}
}