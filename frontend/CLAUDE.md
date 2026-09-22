# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HR/Recruitment management SPA (React 19, CRA, React Router 7) for managing candidates, vacancies, tests, analytics, and HH.ru integration. All UI text is in Russian (no i18n).

## Commands

- `npm start` — dev server (port 3000, proxies API to `https://db.istendlay.ru`)
- `npm run build` — production build
- `npm test` — run Jest tests (react-scripts test, watch mode)
- `npm test -- --watchAll=false` — run tests once
- `npm test -- --testPathPattern=<pattern>` — run a single test file
- No separate lint command; ESLint runs via `react-scripts` (config in package.json extends `react-app`)

## Architecture

### App Structure & Auth

- **Provider nesting:** `App.js` → `BrowserRouter` → `AuthProvider` → `AlertProvider` → `AppRoutes`
- **Routes:** `src/rotes/AppRoutes.js` (note: directory is misspelled as `rotes`)
- **Auth flow:** `AuthContext` → login via `/token/user` (URLSearchParams body) → JWT stored in localStorage as `token`, user object as `user` → `ProtectedRoute` wrapper checks `user.role` against allowed roles
- **Roles:** owner, lead, hr, dev, art, manager — Sidebar menu items and routes render conditionally by role via `ProtectedRoute`
- **Layout:** `src/layout/MainLayout.js` wraps all authenticated pages (flex layout: Sidebar + main content with `bg-yellow-100`)

### Data Flow

- **State management:** React Context (AuthContext, AlertContext) + local useState in page components. No Redux.
- **API layer:** `utils/http.js` — custom fetch wrapper (`http.get/post/put/patch/del`) that injects Bearer token, auto-logouts on 401, detects content type (FormData, URLSearchParams, JSON). All services in `services/` call through this.
- **Alerts:** `useAlertContext()` hook provides `showAlert()` — renders fixed-position notifications (top-right, z-50)
- **Data mapping:** `utils/candidateMapper.js` and `utils/vacancyMapper.js` transform between frontend display values and backend enums.
- **Custom hooks:** `src/hooks/` — `useAlert()` (alert state lifecycle), `useHHDictionaries()` (fetch + cache HH.ru dictionaries)

### Key Patterns

- **Page components** (`pages/`) are stateful containers that fetch data, manage filters/pagination, and render child components from `components/`
- **Infinite scroll:** `CandidateList` uses IntersectionObserver on last element ref, loads 20 items/page, debounced search (500ms)
- **Caching:** `utils/cacheManager.js` — localStorage-based with 24h TTL, used for HH.ru dictionaries
- **Modals:** Fixed-position overlays with backdrop click handling (stopPropagation on content)

### Services Layer

15 service files in `src/services/` — all use `http` wrapper:
- **Core:** candidateApi, vacancyApi, testApi, userApi, analyticsApi
- **Features:** adminApi, aiApi, autosearchApi, blacklistApi, candidateImageApi, hiringRequestsApi, sheduleApi
- **HH.ru integration:** hhAuthApi, hhDictionariesApi, hhSubscriptionApi

### Notable Libraries

- **Recharts** — analytics charts
- **react-big-calendar** — calendar view
- **@dnd-kit + @hello-pangea/dnd** — drag-and-drop (both installed)
- **dayjs/moment** — date handling (both used)
- **xlsx** — Excel export

### Styling

Tailwind CSS 3 with utility classes inline. Brand colors are hardcoded in components (not in tailwind.config.js): gold `#e0bb48` (primary), gray `#666666` (secondary), background `#f5f5f5`.

### External Integrations

- **HH.ru:** OAuth flow, vacancy posting, auto-negotiations, professional roles — services in `hhAuthApi`, `hhDictionariesApi`, `hhSubscriptionApi`. Uses separate API base URL: `https://hh.istendlay.ru` (not the main API)
- **Supabase:** initialized in `supabaseClient.js`, used minimally

### API Configuration

Base URL hardcoded in `src/config/api.js` (`API_URL = "https://db.istendlay.ru"`, `API_PREFIX = "/v1"`). Backend enum constants (departments, work formats, employment types, genders, test types, etc.) also live in `config/api.js`.

## Conventions

- Services return promises; error handling is try-catch at the page component level
- Filter/search changes reset pagination back to page 1 (page 0 internally)
- The `config/api.js` file contains shared constants (departments list, work format options, status values) used across components
- Existing tests: `utils/http.test.js`, `utils/localStorageHelper.test.js`
- Some directories/files have typos — preserve these spellings when importing: `rotes/` (routes), `employess/` (employees), `sheduleApi` (schedule), `DepartamentProfilesPage.js` (Department)