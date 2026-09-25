import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import {AlertProvider} from "./context/AlertContext";
import AppRoutes from "./rotes/AppRoutes";
import { appBasePath } from "./utils/publicUrl";
import "./App.css";

function App() {
    return (
        <BrowserRouter basename={appBasePath()}>
            <AuthProvider>
                <AlertProvider>
                    <AppRoutes />
                </AlertProvider>
            </AuthProvider>
        </BrowserRouter>
    );
}

export default App;
