import React, {createContext, useContext} from "react";
import {useAlert} from "../hooks/useAlert";
import CustomAlert from "../components/common/CustomAlert";

const AlertContext = createContext(null)

export function AlertProvider({children}){
    const {alerts, showAlert, closeAlert} = useAlert()

    return (
        <AlertContext.Provider value={{showAlert}}>
            {children}
            <div className="fixed top-16 right-4 z-[80] space-y-2 pointer-events-none">
                {alerts.map(alert => (
                    <div key={alert.id} className="pointer-events-auto">
                        <CustomAlert message={alert.message} type={alert.type} onClose={() => closeAlert(alert.id)}/>
                    </div>
                ))}
            </div>
        </AlertContext.Provider>
    )
}

export function useAlertContext(){
    return useContext(AlertContext)
}