import { Routes, Route, Link } from "react-router-dom";
import ProtectedRoute from "../rotes/ProtectedRoute";
import Login from "../pages/Login";
import Dashboard from "../pages/Dashboard";
import PortraitPage from "../pages/PortraitPage";
import CandidatesPage from "../pages/CandidatesPage";
import CandidateDocumentsPage from "../pages/CandidateDocumentsPage";
import CandidateDocumentsUploadPage from "../pages/CandidateDocumentsUploadPage";
import EmployeePage from "../pages/EmployeePage";
import EmployeeDetailPage from "../pages/EmployeeDetailPage";
import OrganizationPage from "../pages/OrganizationPage";
import DepartmentDetailPage from "../pages/DepartmentDetailPage";
import VacanciesPage from "../pages/VacanciesPage";
import EventsPlannerPage from "../pages/EventsPlannerPage";
import AnalyticsPage from "../pages/AnalyticsPage";
import TestsPage from "../pages/TestsPage";
import PsychResultsPage from "../pages/PsychResultsPage";
import PsychTakePage from "../pages/PsychTakePage";
import ProfessionalTakePage from "../pages/ProfessionalTakePage";
import DepartmentProfilesPage from "../pages/DepartamentProfilesPage";
import Unauthorized from "../pages/Unauthorized";
import CalendarPage from "../pages/CalendarPage";
import BlacklistPage from "../pages/BlacklistPage";
import ArchiveCandidatesPage from "../pages/ArchiveCandidatesPage";
import RequestsPage from "../pages/RequestsPage";
import HiringRequestPublicPage from "../pages/HiringRequestPublicPage";
import ProfilePage from "../pages/ProfilePage";
import ContactsPage from "../pages/ContactsPage";
import CallsPage from "../pages/CallsPage";
import AdaptationPage from "../pages/AdaptationPage";
import AdaptationDetailPage from "../pages/AdaptationDetailPage";
import AdaptationCasePage from "../pages/AdaptationCasePage";
import AdaptationPublicFormPage from "../pages/AdaptationPublicFormPage";
import LogsPage from "../pages/LogsPage";
import NotificationsPage from "../pages/NotificationsPage";
import { rolesForPath, defaultPathForRole } from "../config/navConfig";
import { useAuth } from "../context/AuthContext";

function NotFound() {
    const { user } = useAuth();
    const home = defaultPathForRole(user?.role);
    return (
        <div className="min-h-screen flex flex-col items-center justify-center bg-yellow-50 p-6">
            <h1 className="text-3xl font-bold mb-2">404</h1>
            <p className="text-gray-600 mb-4">Страница не найдена</p>
            <Link to={home} className="px-4 py-2 bg-[#e0bb48] text-black rounded font-medium">
                На главную
            </Link>
        </div>
    );
}

export default function AppRoutes() {
    return (
        <Routes>
            <Route path="/" element={<Login />} />
            <Route path="/take/test/:testId" element={<ProfessionalTakePage />} />
            <Route path="/take/:instrumentId" element={<PsychTakePage />} />
            <Route path="/adaptation/forms/:token" element={<AdaptationPublicFormPage />} />
            <Route path="/candidate-documents/:token" element={<CandidateDocumentsUploadPage />} />
            <Route path="/hiring-request/:token" element={<HiringRequestPublicPage />} />

            <Route
                path="/dashboard"
                element={
                    <ProtectedRoute roles={rolesForPath("/dashboard")}>
                        <Dashboard />
                    </ProtectedRoute>
                }
            />

            <Route
                path="/candidate-portrait"
                element={
                    <ProtectedRoute roles={rolesForPath("/candidate-portrait")}>
                        <PortraitPage />
                    </ProtectedRoute>
                }
            />

            <Route
                path="/candidates"
                element={
                    <ProtectedRoute roles={rolesForPath("/candidates")}>
                        <CandidatesPage />
                    </ProtectedRoute>
                }
            />

            <Route
                path="/employees"
                element={
                    <ProtectedRoute roles={rolesForPath("/employees")}>
                        <EmployeePage />
                    </ProtectedRoute>
                }
            />

            <Route
                path="/vacancies"
                element={
                    <ProtectedRoute roles={rolesForPath("/vacancies")}>
                        <VacanciesPage />
                    </ProtectedRoute>
                }
            />

            <Route
                path="/events"
                element={
                    <ProtectedRoute roles={rolesForPath("/events")}>
                        <EventsPlannerPage />
                    </ProtectedRoute>
                }
            />

            <Route
                path="/calls"
                element={
                    <ProtectedRoute roles={rolesForPath("/calls")}>
                        <CallsPage />
                    </ProtectedRoute>
                }
            />

            <Route
                path="/analytics"
                element={
                    <ProtectedRoute roles={rolesForPath("/analytics")}>
                        <AnalyticsPage />
                    </ProtectedRoute>
                }
            />

            <Route
                path="/tests"
                element={
                    <ProtectedRoute roles={rolesForPath("/tests")}>
                        <TestsPage />
                    </ProtectedRoute>
                }
            />

            <Route
                path="/tests/results"
                element={
                    <ProtectedRoute roles={rolesForPath("/tests/results")}>
                        <PsychResultsPage />
                    </ProtectedRoute>
                }
            />

            <Route
                path="/tests/adaptation"
                element={
                    <ProtectedRoute roles={rolesForPath("/tests/adaptation")}>
                        <AdaptationPage />
                    </ProtectedRoute>
                }
            />

            <Route
                path="/tests/adaptation/case/:enrollmentId"
                element={
                    <ProtectedRoute roles={rolesForPath("/tests/adaptation")}>
                        <AdaptationCasePage />
                    </ProtectedRoute>
                }
            />

            <Route
                path="/tests/adaptation/:checkpointId"
                element={
                    <ProtectedRoute roles={rolesForPath("/tests/adaptation")}>
                        <AdaptationDetailPage />
                    </ProtectedRoute>
                }
            />

            <Route
                path="/departments"
                element={
                    <ProtectedRoute roles={rolesForPath("/departments")}>
                        <DepartmentProfilesPage />
                    </ProtectedRoute>
                }
            />

            <Route
                path="/calendar"
                element={
                    <ProtectedRoute roles={rolesForPath("/calendar")}>
                        <CalendarPage />
                    </ProtectedRoute>
                }
            />

            <Route
                path="/blacklist"
                element={
                    <ProtectedRoute roles={rolesForPath("/blacklist")}>
                        <BlacklistPage />
                    </ProtectedRoute>
                }
            />

            <Route
                path="/archive"
                element={
                    <ProtectedRoute roles={rolesForPath("/archive")}>
                        <ArchiveCandidatesPage />
                    </ProtectedRoute>
                }
            />

            <Route
                path="/requests"
                element={
                    <ProtectedRoute roles={rolesForPath("/requests")}>
                        <RequestsPage />
                    </ProtectedRoute>
                }
            />

            <Route
                path="/contacts"
                element={
                    <ProtectedRoute roles={rolesForPath("/contacts")}>
                        <ContactsPage />
                    </ProtectedRoute>
                }
            />

            <Route
                path="/logs"
                element={
                    <ProtectedRoute roles={rolesForPath("/logs")}>
                        <LogsPage />
                    </ProtectedRoute>
                }
            />

            <Route
                path="/notifications"
                element={
                    <ProtectedRoute roles={rolesForPath("/notifications")}>
                        <NotificationsPage />
                    </ProtectedRoute>
                }
            />

            <Route
                path="/candidate-documents"
                element={
                    <ProtectedRoute roles={rolesForPath("/candidate-documents")}>
                        <CandidateDocumentsPage />
                    </ProtectedRoute>
                }
            />
            <Route path="/employees/:employeeId" element={<ProtectedRoute roles={rolesForPath("/employees")}><EmployeeDetailPage /></ProtectedRoute>} />
            <Route path="/organization" element={<ProtectedRoute roles={rolesForPath("/organization")}><OrganizationPage /></ProtectedRoute>} />
            <Route path="/organization/departments/:departmentId" element={<ProtectedRoute roles={rolesForPath("/organization")}><DepartmentDetailPage /></ProtectedRoute>} />

            <Route
                path="/profile"
                element={
                    <ProtectedRoute roles={rolesForPath("/profile")}>
                        <ProfilePage />
                    </ProtectedRoute>
                }
            />

            <Route path="/unauthorized" element={<Unauthorized />} />
            <Route path="*" element={<NotFound />} />
        </Routes>
    );
}
