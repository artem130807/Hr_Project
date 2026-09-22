/**
 * Single source of truth: menu items + route roles (TZ navigation).
 * Keep Sidebar and AppRoutes in sync via this config.
 *
 * ERP «Руководитель» / «Руководитель отдела» (leader, dept_leader) see only
 * hiring requests, employees, candidate portrait, department profiles, and
 * their personal profile — not the rest of the HR workspace.
 */

/** @typedef {{ to: string, label: string, roles: string[], icon?: string, hidden?: boolean }} NavLeaf */
/** @typedef {{ label: string, icon?: string, roles: string[], children: NavLeaf[], hidden?: boolean }} NavGroup */
/** @typedef {NavLeaf | NavGroup} NavItem */

/** ERP roles that use the HR panel like HR staff (not department heads). */
const ERP_STAFF_ROLES = ["superadmin", "admin", "manager", "senior_manager"];

/** ERP display names «Руководитель» and «Руководитель отдела». */
export const LEADER_ROLES = ["leader", "dept_leader"];

const uniq = (...lists) => Array.from(new Set(lists.flat()));

const withErpStaff = (roles) => uniq(roles, ERP_STAFF_ROLES);

const withLeaders = (roles) => uniq(roles, LEADER_ROLES);

/** Any signed-in panel role may open the personal profile (hidden from the main menu). */
const withAllPanelRoles = (roles) => uniq(roles, ERP_STAFF_ROLES, LEADER_ROLES);

export function isLeaderRole(role) {
    return LEADER_ROLES.includes(String(role || "").trim());
}

/** @type {NavItem[]} */
export const NAV_ITEMS = [
    { to: "/dashboard", label: "Главная", icon: "DashboardIcon", roles: withErpStaff(["owner", "lead", "hr", "dev", "art"]) },
    { to: "/requests", label: "Заявки", icon: "InboxIcon", roles: withLeaders(withErpStaff(["lead", "hr", "dev", "owner"])) },
    { to: "/vacancies", label: "Вакансии", icon: "BriefcaseIcon", roles: withErpStaff(["hr", "owner", "dev", "lead"]) },
    { to: "/candidates", label: "Кандидаты", icon: "UsersIcon", roles: withErpStaff(["hr", "dev", "owner"]) },
    { to: "/candidate-documents", label: "Документы кандидатов", icon: "FileTextIcon", roles: withErpStaff(["hr", "dev", "owner"]) },
    { to: "/employees", label: "Сотрудники", icon: "CheckCircleIcon", roles: withLeaders(withErpStaff(["hr", "owner", "dev"])) },
    { to: "/contacts", label: "Контакты HH", icon: "UsersIcon", roles: withErpStaff(["hr", "owner", "dev"]) },
    {
        label: "Тесты",
        icon: "ClipboardIcon",
        roles: withErpStaff(["hr", "owner", "dev"]),
        children: [
            { to: "/tests", label: "Создание тестов", roles: withErpStaff(["hr", "owner", "dev"]) },
            { to: "/tests/results", label: "Результаты тестов", roles: withErpStaff(["hr", "owner", "dev"]) },
            { to: "/tests/adaptation", label: "Адаптация", roles: withLeaders(withErpStaff(["hr", "owner", "dev"])) },
        ],
    },
    { to: "/calendar", label: "Календарь", icon: "CalendarIcon", roles: withErpStaff(["hr", "owner", "dev"]) },
    { to: "/analytics", label: "Статистика кандидатов", icon: "BarChartIcon", roles: withErpStaff(["owner", "dev", "hr"]) },
    { to: "/events", label: "События", icon: "CalendarIcon", roles: withErpStaff(["hr", "dev", "owner"]) },
    { to: "/calls", label: "Звонки", icon: "PhoneIcon", roles: withErpStaff(["hr", "dev", "owner"]) },
    {
        to: "/notifications",
        label: "Уведомления",
        icon: "InboxIcon",
        roles: withAllPanelRoles(["owner", "hr", "dev", "lead", "art"]),
        hidden: true,
    },
    // Hidden from sidebar; route/page kept for possible future use
    { to: "/logs", label: "Журнал", icon: "FileTextIcon", roles: withErpStaff(["owner", "hr", "dev"]), hidden: true },
    { to: "/candidate-portrait", label: "Портрет кандидатов", icon: "FileTextIcon", roles: withLeaders(withErpStaff(["owner", "lead", "dev"])) },
    { to: "/departments", label: "Профили отделов", icon: "BuildingIcon", roles: withLeaders(withErpStaff(["owner", "lead", "dev", "hr"])) },
    { to: "/organization", label: "Структура компании", icon: "BuildingIcon", roles: withLeaders(withErpStaff(["owner", "lead", "dev", "hr"])) },
    { to: "/blacklist", label: "Черный список", icon: "BanIcon", roles: withErpStaff(["owner", "hr", "dev"]) },
    { to: "/archive", label: "Архив кандидатов", icon: "ArchiveIcon", roles: withErpStaff(["hr", "owner", "dev"]) },
    // Personal page — any logged-in panel role (incl. ERP). Hidden from main menu; opened from sidebar avatar.
    {
        to: "/profile",
        label: "Профиль",
        icon: "UsersIcon",
        roles: withAllPanelRoles(["owner", "hr", "dev", "lead", "art"]),
        hidden: true,
    },
];

/** Preferred menu order for TZ IA (others follow after). */
const MENU_ORDER = [
    "/dashboard",
    "/requests",
    "/vacancies",
    "/candidates",
    "/candidate-documents",
    "/employees",
    "/contacts",
    "/analytics",
    "/calendar",
    "/tests",
    "/events",
    "/calls",
    "/logs",
    "/candidate-portrait",
    "/departments",
    "/organization",
    "/blacklist",
    "/archive",
];

export function isNavGroup(item) {
    return Boolean(item && Array.isArray(item.children));
}

export function menuItemsForRole(role) {
    const items = NAV_ITEMS.filter((item) => !item.hidden && item.roles.includes(role)).map((item) => {
        if (!isNavGroup(item)) return item;
        return {
            ...item,
            children: item.children.filter((c) => !c.hidden && c.roles.includes(role)),
        };
    }).filter((item) => !isNavGroup(item) || item.children.length > 0);

    return items.sort((a, b) => {
        const aKey = isNavGroup(a) ? (a.children[0]?.to || a.label) : a.to;
        const bKey = isNavGroup(b) ? (b.children[0]?.to || b.label) : b.to;
        const ai = MENU_ORDER.indexOf(aKey.startsWith("/tests") ? "/tests" : aKey);
        const bi = MENU_ORDER.indexOf(bKey.startsWith("/tests") ? "/tests" : bKey);
        // Groups ordered by parent key /tests
        const aOrder = isNavGroup(a) ? MENU_ORDER.indexOf("/tests") : ai;
        const bOrder = isNavGroup(b) ? MENU_ORDER.indexOf("/tests") : bi;
        return (aOrder === -1 ? 999 : aOrder) - (bOrder === -1 ? 999 : bOrder);
    });
}

export function rolesForPath(path) {
    for (const item of NAV_ITEMS) {
        if (isNavGroup(item)) {
            const child = item.children.find((c) => c.to === path);
            if (child) return child.roles;
            continue;
        }
        if (item.to === path) return item.roles;
    }
    // Nested detail paths under /tests/results/:id inherit results roles
    if (path.startsWith("/tests/results")) {
        return rolesForPath("/tests/results");
    }
    if (path.startsWith("/tests/adaptation")) {
        return rolesForPath("/tests/adaptation");
    }
    return [];
}

/** First allowed workspace page for this role (profile if the menu is empty). */
export function defaultPathForRole(role) {
    const items = menuItemsForRole(role);
    for (const item of items) {
        if (isNavGroup(item)) {
            const child = item.children.find((c) => c.to);
            if (child?.to) return child.to;
            continue;
        }
        if (item.to) return item.to;
    }
    const profileRoles = rolesForPath("/profile");
    if (!role || profileRoles.includes(role)) return "/profile";
    return "/unauthorized";
}

export function psychPublicTakePath(instrumentId) {
    return `/take/${encodeURIComponent(instrumentId)}`;
}

export function professionalPublicTakePath(testId) {
    return `/take/test/${encodeURIComponent(testId)}`;
}
