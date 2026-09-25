import { useState, useEffect, useMemo, useRef } from "react";
import { useAuth } from "../../context/AuthContext";
import { WORK_FORMATS } from "../../config/api";

const STEPS = [
  { id: 0, title: "Основное", hint: "Должность, контакты и основание заявки" },
  { id: 1, title: "Роль", hint: "Цель позиции, задачи и ожидаемые результаты" },
  { id: 2, title: "Кандидат", hint: "Требования, навыки и компетенции" },
  { id: 3, title: "Поиск", hint: "Культура, инструменты и источники поиска" },
  { id: 4, title: "Условия", hint: "График, оплата и тестовое задание" },
];

const ERROR_STEP = {
  position: 0,
  department: 0,
  planned_start_date: 0,
  manager_name: 0,
  manager_position: 0,
  phone: 0,
  purpose: 1,
  mandatory_requirements: 2,
  schedule: 4,
  work_format: 4,
};

const URGENCY_OPTIONS = [
  { value: "Срочно", tone: "rose" },
  { value: "Средне", tone: "amber" },
  { value: "Планово", tone: "sky" },
];

function fieldClass(hasError) {
  return `w-full px-3.5 py-2.5 text-sm rounded-xl border bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/40 focus:border-[#4f46e5] transition-all ${
    hasError ? "border-rose-400" : "border-slate-200"
  }`;
}

function Label({ children, required }) {
  return (
    <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1.5">
      {children}
      {required ? <span className="text-rose-500"> *</span> : null}
    </label>
  );
}

function FieldError({ message }) {
  if (!message) return null;
  return <p className="mt-1 text-xs text-rose-600">{message}</p>;
}

function SectionCard({ title, children }) {
  return (
    <section className="rounded-2xl border border-slate-200/80 bg-white p-5 space-y-4">
      <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
      {children}
    </section>
  );
}

function ChipGroup({ value, options, onChange, error }) {
  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {options.map((opt) => {
          const selected = value === opt.value;
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => onChange(opt.value)}
              className={`px-3 py-1.5 rounded-xl text-sm font-medium border transition-colors ${
                selected
                  ? "bg-slate-900 text-white border-slate-900"
                  : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
              }`}
            >
              {opt.label || opt.value}
            </button>
          );
        })}
      </div>
      <FieldError message={error} />
    </div>
  );
}

function ToggleRow({ checked, onChange, title, hint }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className={`w-full text-left rounded-xl border px-4 py-3 transition-colors ${
        checked ? "border-[#4f46e5] bg-[#4f46e5]/10" : "border-slate-200 bg-slate-50 hover:bg-white"
      }`}
    >
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-slate-800">{title}</p>
          {hint ? <p className="text-xs text-slate-500 mt-0.5">{hint}</p> : null}
        </div>
        <span className={`relative inline-flex h-6 w-11 shrink-0 rounded-full transition-colors ${checked ? "bg-[#4f46e5]" : "bg-slate-300"}`}>
          <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${checked ? "left-[22px]" : "left-0.5"}`} />
        </span>
      </div>
    </button>
  );
}

function TaskArray({ label, field, items, setItem, add, remove, error, placeholder = "Добавить пункт" }) {
  return (
    <div>
      <Label>{label}</Label>
      <div className="space-y-2">
        {(items || []).map((v, i) => (
          <div key={i} className="flex gap-2">
            <input
              className={fieldClass(Boolean(error) && i === 0)}
              value={v}
              placeholder={placeholder}
              onChange={(e) => setItem(field, i, e.target.value)}
            />
            {(items || []).length > 1 ? (
              <button
                type="button"
                onClick={() => remove(i)}
                className="w-10 shrink-0 rounded-xl border border-slate-200 text-slate-400 hover:text-rose-600 hover:border-rose-200 hover:bg-rose-50"
                title="Удалить"
              >
                ×
              </button>
            ) : null}
          </div>
        ))}
      </div>
      <FieldError message={error} />
      <button
        type="button"
        onClick={add}
        className="mt-2 text-sm font-medium text-slate-600 hover:text-slate-900"
      >
        + Добавить
      </button>
    </div>
  );
}

export default function RequestFormModal({ onClose, onSubmit, user = {}, isLoading = false, closable = true, publicMode = false, initialData = null }) {
  const { user: authUser } = useAuth();
  const bodyRef = useRef(null);
  const [step, setStep] = useState(0);

  const todayDMY = (() => {
    const d = new Date();
    const dd = String(d.getDate()).padStart(2, "0");
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const yyyy = d.getFullYear();
    return `${dd}.${mm}.${yyyy}`;
  })();

  const resolveDepartment = (u = {}) => {
    const candidates = [
      u.department,
      u.department_name,
      u.departmentName,
      u?.profile?.department,
      u?.departments?.[0]?.department,
      u?.departments?.[0]?.name,
      u?.departments?.[0]?.code,
    ].filter(Boolean);
    return candidates.find((v) => typeof v === "string" && v.trim()) || "";
  };

  const blankArray = [""];

  const initial = {
    position: "",
    request_date: todayDMY,
    department: "",
    headcount: 1,
    planned_start_date: "",
    urgency: "",
    manager_name: "",
    manager_position: "",
    phone: "",
    backup_contact: "",
    reason: "",
    previous_employee: "",
    probation_period: "",
    purpose: "",
    features: "",
    reporting: "",
    horizontal_connections: "",
    growth_prospects: "",
    daily_tasks: [...blankArray],
    weekly_tasks: [...blankArray],
    project_tasks: [...blankArray],
    kpi_metrics: [...blankArray],
    expected_results_probation: [...blankArray],
    priorities_3months: [...blankArray],
    mandatory_requirements: [...blankArray],
    desired_requirements: [...blankArray],
    age_from: "",
    age_to: "",
    gender: "",
    total_experience_years: "",
    relevant_experience_years: "",
    required_hard_skills: [...blankArray],
    optional_hard_skills: [...blankArray],
    required_soft_skills: [...blankArray],
    unacceptable_soft_skills: [...blankArray],
    job_competencies: [...blankArray],
    corporate_competencies: [...blankArray],
    critical_values: [...blankArray],
    acceptable_behavior: [...blankArray],
    unacceptable_behavior: [...blankArray],
    fit_indicators: [...blankArray],
    misfit_indicators: [...blankArray],
    software: [...blankArray],
    tools: [...blankArray],
    languages: [...blankArray],
    appearance: "",
    keywords: [...blankArray],
    similar_positions: [...blankArray],
    stop_companies: [...blankArray],
    donor_companies: [...blankArray],
    referral_sources: [...blankArray],
    schedule: "",
    work_format: "",
    work_address: "",
    background_search: false,
    work_day_description: "",
    business_trips_required: false,
    business_trips_frequency: "",
    business_trips_locations: "",
    salary_from: "",
    salary_to: "",
    currency: "RUB",
    gross: true,
    bonus_type: "",
    bonus_amount: "",
    bonus_conditions: "",
    benefits: [...blankArray],
    test_required: false,
    test_description: "",
    test_deadline: "",
    test_is_paid: false,
    status: "создана",
  };

  const [form, setForm] = useState(() => Object.keys(initial).reduce(
    (acc, key) => ({ ...acc, [key]: initialData?.[key] ?? initial[key] }),
    {}
  ));
  const [errors, setErrors] = useState({});

  const effectiveUser = useMemo(
    () => ((user && Object.keys(user || {}).length > 0) ? user : authUser || {}),
    [user, authUser]
  );

  useEffect(() => {
    const dept = resolveDepartment(effectiveUser);
    if (dept) {
      setForm((p) => ({ ...p, department: dept }));
    }
  }, [effectiveUser]);

  useEffect(() => {
    bodyRef.current?.scrollTo({ top: 0, behavior: "smooth" });
  }, [step]);

  const setField = (k, v) => {
    setForm((p) => ({ ...p, [k]: v }));
    if (errors[k]) setErrors((e) => ({ ...e, [k]: null }));
  };

  const setArrayItem = (field, idx, value) => {
    const arr = Array.isArray(form[field]) ? [...form[field]] : [];
    arr[idx] = value;
    setField(field, arr);
  };
  const pushArrayItem = (field) => setField(field, [...(form[field] || []), ""]);
  const removeArrayItem = (field, idx) => setField(field, (form[field] || []).filter((_, i) => i !== idx));

  const validateDayMonth = (value) => {
    const digits = String(value).replace(/\D/g, "");
    if (digits.length < 4) return null;
    const day = Number(digits.slice(0, 2));
    const month = Number(digits.slice(2, 4));
    if (day < 1 || day > 31) return "День должен быть от 01 до 31";
    if (month < 1 || month > 12) return "Месяц должен быть от 01 до 12";
    return null;
  };

  const toDMY = (v) => {
    if (!v) return "";
    if (/^\d{2}\.\d{2}\.\d{4}$/.test(v)) return v;
    if (/^\d{2}\/\d{2}\/\d{4}$/.test(v)) return v.replace(/\//g, ".");
    const digits = String(v).replace(/\D/g, "");
    if (digits.length < 8) return v;
    const day = Number(digits.slice(0, 2));
    const month = Number(digits.slice(2, 4));
    if (day < 1 || day > 31 || month < 1 || month > 12) return v;
    const d = new Date(v);
    if (isNaN(d.getTime())) return v;
    const dd = String(d.getDate()).padStart(2, "0");
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const yyyy = d.getFullYear();
    return `${dd}.${mm}.${yyyy}`;
  };

  const formatDateInput = (value) => {
    const digits = String(value).replace(/\D/g, "").slice(0, 8);
    if (digits.length <= 2) return digits;
    if (digits.length <= 4) return `${digits.slice(0, 2)}.${digits.slice(2)}`;
    return `${digits.slice(0, 2)}.${digits.slice(2, 4)}.${digits.slice(4)}`;
  };

  const handlePlannedDateChange = (value) => {
    setField("planned_start_date", formatDateInput(value));
  };

  const handlePlannedDateBlur = (value) => {
    setField("planned_start_date", toDMY(formatDateInput(value)));
  };

  const collectErrors = () => {
    const e = {};
    if (!form.position.trim()) e.position = "Введите должность";
    if (!form.manager_name.trim()) e.manager_name = "Введите ФИО руководителя";
    if (!form.manager_position.trim()) e.manager_position = "Введите должность руководителя";
    if (!form.phone.trim()) e.phone = "Введите телефон / telegram";
    if (!form.purpose.trim()) e.purpose = "Опишите цель должности";
    if (!form.schedule.trim()) e.schedule = "Введите график";
    if (!form.work_format.trim()) e.work_format = "Укажите формат работы";
    if (!form.department?.trim()) e.department = "Подразделение не определено для пользователя";
    const plannedDateErr = validateDayMonth(form.planned_start_date);
    if (plannedDateErr) e.planned_start_date = plannedDateErr;
    if (!Array.isArray(form.mandatory_requirements) || form.mandatory_requirements.filter((x) => x.trim()).length === 0) {
      e.mandatory_requirements = "Добавьте минимум одно обязательное требование";
    }
    return e;
  };

  const goToFirstError = (e) => {
    const first = Object.keys(e)[0];
    setStep(ERROR_STEP[first] ?? 0);
    bodyRef.current?.scrollTo({ top: 0, behavior: "smooth" });
  };

  const cleanArrays = (payload) => {
    const out = { ...payload };
    Object.keys(out).forEach((k) => {
      if (Array.isArray(out[k])) {
        out[k] = out[k].map((v) => (typeof v === "string" ? v.trim() : v)).filter(Boolean);
      }
    });
    return out;
  };

  const handleSubmit = (ev) => {
    ev.preventDefault();
    const e = collectErrors();
    setErrors(e);
    if (Object.keys(e).length > 0) {
      goToFirstError(e);
      return;
    }

    let payload = { ...form };
    if (!payload.department) {
      const dept = resolveDepartment(effectiveUser);
      if (dept) payload.department = dept;
    }
    if (payload.planned_start_date) payload.planned_start_date = toDMY(payload.planned_start_date);
    if (payload.request_date) {
      const maybeISO = payload.request_date;
      if (/^\d{4}-\d{2}-\d{2}$/.test(maybeISO)) payload.request_date = toDMY(maybeISO);
    }
    payload.headcount = Number(payload.headcount || 0);
    if (payload.salary_from !== "") payload.salary_from = Number(payload.salary_from);
    if (payload.salary_to !== "") payload.salary_to = Number(payload.salary_to);
    if (payload.probation_period !== "") payload.probation_period = Number(payload.probation_period);
    if (payload.age_from !== "") payload.age_from = Number(payload.age_from);
    if (payload.age_to !== "") payload.age_to = Number(payload.age_to);
    if (payload.total_experience_years !== "") payload.total_experience_years = Number(payload.total_experience_years);
    if (payload.relevant_experience_years !== "") payload.relevant_experience_years = Number(payload.relevant_experience_years);
    payload = cleanArrays(payload);
    Object.keys(payload).forEach((k) => {
      if (payload[k] === "" || (Array.isArray(payload[k]) && payload[k].length === 0)) delete payload[k];
    });
    onSubmit(payload);
  };

  const progress = ((step + 1) / STEPS.length) * 100;
  const current = STEPS[step];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm" onClick={() => (closable && !isLoading ? onClose?.() : null)} />
      <div className="relative z-10 w-full max-w-5xl max-h-[92vh] bg-white rounded-3xl shadow-2xl ring-1 ring-slate-900/5 flex flex-col overflow-hidden">
        <header className="px-6 pt-5 pb-4 border-b border-slate-100 bg-gradient-to-br from-slate-50 to-white">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Заявка на подбор</p>
              <h2 className="mt-1 text-xl font-bold text-slate-900">{initialData ? "Уточнение заявки" : "Новая заявка"}</h2>
              <p className="mt-1 text-sm text-slate-500">{current.hint}</p>
            </div>
            {closable ? (
              <button
                type="button"
                onClick={onClose}
                disabled={isLoading}
                className="w-10 h-10 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-500 flex items-center justify-center"
                aria-label="Закрыть"
              >
                ×
              </button>
            ) : null}
          </div>
          <div className="mt-4 h-1.5 rounded-full bg-slate-100 overflow-hidden">
            <div className="h-full rounded-full bg-[#4f46e5] transition-all" style={{ width: `${progress}%` }} />
          </div>
          <nav className="mt-4 flex gap-1.5 overflow-x-auto pb-1">
            {STEPS.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setStep(item.id)}
                className={`shrink-0 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  step === item.id
                    ? "bg-slate-900 text-white"
                    : step > item.id
                      ? "bg-[#4f46e5]/15 text-slate-800"
                      : "bg-slate-100 text-slate-500 hover:bg-slate-200"
                }`}
              >
                {item.id + 1}. {item.title}
              </button>
            ))}
          </nav>
        </header>

        <form onSubmit={handleSubmit} className="flex flex-col min-h-0 flex-1">
          <div ref={bodyRef} className="flex-1 overflow-y-auto p-6 space-y-4 bg-slate-50/60">
            {errors.department ? (
              <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                {errors.department}
              </div>
            ) : null}

            {step === 0 && (
              <>
                <SectionCard title="Общая информация">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {publicMode && (
                      <div>
                        <label htmlFor="public-request-department">Подразделение *</label>
                        <input id="public-request-department" value={form.department} onChange={(e) => setField("department", e.target.value)} className={fieldClass(errors.department)} placeholder="Укажите ваш отдел" />
                        <FieldError message={errors.department} />
                      </div>
                    )}
                    <div className="md:col-span-2">
                      <Label required>Должность</Label>
                      <input value={form.position} onChange={(e) => setField("position", e.target.value)} className={fieldClass(errors.position)} placeholder="Например, логист" />
                      <FieldError message={errors.position} />
                    </div>
                    <div>
                      <Label>Количество сотрудников</Label>
                      <input type="number" min="1" value={form.headcount} onChange={(e) => setField("headcount", e.target.value)} className={fieldClass(false)} />
                    </div>
                    <div>
                      <Label>Планируемая дата выхода</Label>
                      <input
                        type="text"
                        placeholder="дд.мм.гггг"
                        inputMode="numeric"
                        value={form.planned_start_date}
                        onChange={(e) => handlePlannedDateChange(e.target.value)}
                        onBlur={(e) => handlePlannedDateBlur(e.target.value)}
                        className={fieldClass(errors.planned_start_date)}
                      />
                      <FieldError message={errors.planned_start_date} />
                    </div>
                    <div className="md:col-span-2">
                      <Label>Срочность</Label>
                      <ChipGroup
                        value={form.urgency}
                        onChange={(v) => setField("urgency", v)}
                        options={URGENCY_OPTIONS}
                      />
                    </div>
                  </div>
                </SectionCard>

                <SectionCard title="Контакты руководителя">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <Label required>ФИО руководителя</Label>
                      <input value={form.manager_name} onChange={(e) => setField("manager_name", e.target.value)} className={fieldClass(errors.manager_name)} />
                      <FieldError message={errors.manager_name} />
                    </div>
                    <div>
                      <Label required>Должность руководителя</Label>
                      <input value={form.manager_position} onChange={(e) => setField("manager_position", e.target.value)} className={fieldClass(errors.manager_position)} />
                      <FieldError message={errors.manager_position} />
                    </div>
                    <div>
                      <Label required>Телефон / Telegram</Label>
                      <input value={form.phone} onChange={(e) => setField("phone", e.target.value)} className={fieldClass(errors.phone)} placeholder="+7… или @username" />
                      <FieldError message={errors.phone} />
                    </div>
                    <div>
                      <Label>Замещающий контакт</Label>
                      <input value={form.backup_contact} onChange={(e) => setField("backup_contact", e.target.value)} className={fieldClass(false)} />
                    </div>
                  </div>
                </SectionCard>

                <SectionCard title="Основание открытия">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <Label>Причина открытия</Label>
                      <input value={form.reason} onChange={(e) => setField("reason", e.target.value)} className={fieldClass(false)} placeholder="Замена, расширение…" />
                    </div>
                    <div>
                      <Label>Предыдущий сотрудник</Label>
                      <input value={form.previous_employee} onChange={(e) => setField("previous_employee", e.target.value)} className={fieldClass(false)} />
                    </div>
                    <div>
                      <Label>Испытательный срок, мес.</Label>
                      <input type="number" min="0" value={form.probation_period} onChange={(e) => setField("probation_period", e.target.value)} className={fieldClass(false)} />
                    </div>
                  </div>
                </SectionCard>
              </>
            )}

            {step === 1 && (
              <>
                <SectionCard title="Описание должности">
                  <div>
                    <Label required>Цель должности</Label>
                    <textarea rows={4} value={form.purpose} onChange={(e) => setField("purpose", e.target.value)} className={fieldClass(errors.purpose)} placeholder="Зачем нужна эта роль в команде" />
                    <FieldError message={errors.purpose} />
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <Label>Особенности позиции</Label>
                      <input value={form.features} onChange={(e) => setField("features", e.target.value)} className={fieldClass(false)} />
                    </div>
                    <div>
                      <Label>Подчинение</Label>
                      <input value={form.reporting} onChange={(e) => setField("reporting", e.target.value)} className={fieldClass(false)} />
                    </div>
                    <div>
                      <Label>Горизонтальные связи</Label>
                      <input value={form.horizontal_connections} onChange={(e) => setField("horizontal_connections", e.target.value)} className={fieldClass(false)} />
                    </div>
                    <div>
                      <Label>Перспективы роста</Label>
                      <input value={form.growth_prospects} onChange={(e) => setField("growth_prospects", e.target.value)} className={fieldClass(false)} />
                    </div>
                  </div>
                </SectionCard>
                <SectionCard title="Основные задачи">
                  <TaskArray label="Ежедневные" field="daily_tasks" items={form.daily_tasks} setItem={setArrayItem} add={() => pushArrayItem("daily_tasks")} remove={(i) => removeArrayItem("daily_tasks", i)} />
                  <TaskArray label="Еженедельные" field="weekly_tasks" items={form.weekly_tasks} setItem={setArrayItem} add={() => pushArrayItem("weekly_tasks")} remove={(i) => removeArrayItem("weekly_tasks", i)} />
                  <TaskArray label="Проектные" field="project_tasks" items={form.project_tasks} setItem={setArrayItem} add={() => pushArrayItem("project_tasks")} remove={(i) => removeArrayItem("project_tasks", i)} />
                </SectionCard>
                <SectionCard title="KPI и результаты">
                  <TaskArray label="KPI должности" field="kpi_metrics" items={form.kpi_metrics} setItem={setArrayItem} add={() => pushArrayItem("kpi_metrics")} remove={(i) => removeArrayItem("kpi_metrics", i)} />
                  <TaskArray label="Результаты после испытательного срока" field="expected_results_probation" items={form.expected_results_probation} setItem={setArrayItem} add={() => pushArrayItem("expected_results_probation")} remove={(i) => removeArrayItem("expected_results_probation", i)} />
                  <TaskArray label="Приоритеты на 3 месяца" field="priorities_3months" items={form.priorities_3months} setItem={setArrayItem} add={() => pushArrayItem("priorities_3months")} remove={(i) => removeArrayItem("priorities_3months", i)} />
                </SectionCard>
              </>
            )}

            {step === 2 && (
              <>
                <SectionCard title="Требования к кандидату">
                  <TaskArray label="Обязательные требования *" field="mandatory_requirements" items={form.mandatory_requirements} setItem={setArrayItem} add={() => pushArrayItem("mandatory_requirements")} remove={(i) => removeArrayItem("mandatory_requirements", i)} error={errors.mandatory_requirements} />
                  <TaskArray label="Желательные требования" field="desired_requirements" items={form.desired_requirements} setItem={setArrayItem} add={() => pushArrayItem("desired_requirements")} remove={(i) => removeArrayItem("desired_requirements", i)} />
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
                    <div>
                      <Label>Возраст от</Label>
                      <input type="number" min="0" value={form.age_from} onChange={(e) => setField("age_from", e.target.value)} className={fieldClass(false)} />
                    </div>
                    <div>
                      <Label>Возраст до</Label>
                      <input type="number" min="0" value={form.age_to} onChange={(e) => setField("age_to", e.target.value)} className={fieldClass(false)} />
                    </div>
                    <div>
                      <Label>Пол</Label>
                      <select value={form.gender} onChange={(e) => setField("gender", e.target.value)} className={fieldClass(false)}>
                        <option value="">Не указан</option>
                        <option value="мужчина">Мужчина</option>
                        <option value="женщина">Женщина</option>
                      </select>
                    </div>
                    <div>
                      <Label>Общий опыт, лет</Label>
                      <input type="number" min="0" value={form.total_experience_years} onChange={(e) => setField("total_experience_years", e.target.value)} className={fieldClass(false)} />
                    </div>
                    <div>
                      <Label>Релевантный опыт, лет</Label>
                      <input type="number" min="0" value={form.relevant_experience_years} onChange={(e) => setField("relevant_experience_years", e.target.value)} className={fieldClass(false)} />
                    </div>
                  </div>
                </SectionCard>
                <SectionCard title="Навыки">
                  <TaskArray label="Профессиональные навыки" field="required_hard_skills" items={form.required_hard_skills} setItem={setArrayItem} add={() => pushArrayItem("required_hard_skills")} remove={(i) => removeArrayItem("required_hard_skills", i)} placeholder="Навык / уровень" />
                  <TaskArray label="Дополнительные навыки" field="optional_hard_skills" items={form.optional_hard_skills} setItem={setArrayItem} add={() => pushArrayItem("optional_hard_skills")} remove={(i) => removeArrayItem("optional_hard_skills", i)} />
                  <TaskArray label="Необходимые качества" field="required_soft_skills" items={form.required_soft_skills} setItem={setArrayItem} add={() => pushArrayItem("required_soft_skills")} remove={(i) => removeArrayItem("required_soft_skills", i)} />
                  <TaskArray label="Неприемлемые качества" field="unacceptable_soft_skills" items={form.unacceptable_soft_skills} setItem={setArrayItem} add={() => pushArrayItem("unacceptable_soft_skills")} remove={(i) => removeArrayItem("unacceptable_soft_skills", i)} />
                </SectionCard>
                <SectionCard title="Компетенции">
                  <TaskArray label="Должностные" field="job_competencies" items={form.job_competencies} setItem={setArrayItem} add={() => pushArrayItem("job_competencies")} remove={(i) => removeArrayItem("job_competencies", i)} />
                  <TaskArray label="Корпоративные" field="corporate_competencies" items={form.corporate_competencies} setItem={setArrayItem} add={() => pushArrayItem("corporate_competencies")} remove={(i) => removeArrayItem("corporate_competencies", i)} />
                </SectionCard>
              </>
            )}

            {step === 3 && (
              <>
                <SectionCard title="Ценности и культура">
                  <TaskArray label="Критичные ценности" field="critical_values" items={form.critical_values} setItem={setArrayItem} add={() => pushArrayItem("critical_values")} remove={(i) => removeArrayItem("critical_values", i)} />
                  <TaskArray label="Приемлемое поведение" field="acceptable_behavior" items={form.acceptable_behavior} setItem={setArrayItem} add={() => pushArrayItem("acceptable_behavior")} remove={(i) => removeArrayItem("acceptable_behavior", i)} />
                  <TaskArray label="Неприемлемое поведение" field="unacceptable_behavior" items={form.unacceptable_behavior} setItem={setArrayItem} add={() => pushArrayItem("unacceptable_behavior")} remove={(i) => removeArrayItem("unacceptable_behavior", i)} />
                  <TaskArray label="Индикаторы соответствия" field="fit_indicators" items={form.fit_indicators} setItem={setArrayItem} add={() => pushArrayItem("fit_indicators")} remove={(i) => removeArrayItem("fit_indicators", i)} />
                  <TaskArray label="Индикаторы несоответствия" field="misfit_indicators" items={form.misfit_indicators} setItem={setArrayItem} add={() => pushArrayItem("misfit_indicators")} remove={(i) => removeArrayItem("misfit_indicators", i)} />
                </SectionCard>
                <SectionCard title="Технические требования">
                  <TaskArray label="Программы" field="software" items={form.software} setItem={setArrayItem} add={() => pushArrayItem("software")} remove={(i) => removeArrayItem("software", i)} />
                  <TaskArray label="Инструменты" field="tools" items={form.tools} setItem={setArrayItem} add={() => pushArrayItem("tools")} remove={(i) => removeArrayItem("tools", i)} />
                  <TaskArray label="Языки" field="languages" items={form.languages} setItem={setArrayItem} add={() => pushArrayItem("languages")} remove={(i) => removeArrayItem("languages", i)} />
                  <div>
                    <Label>Внешний вид</Label>
                    <input value={form.appearance} onChange={(e) => setField("appearance", e.target.value)} className={fieldClass(false)} />
                  </div>
                </SectionCard>
                <SectionCard title="Стратегия поиска">
                  <TaskArray label="Ключевые слова" field="keywords" items={form.keywords} setItem={setArrayItem} add={() => pushArrayItem("keywords")} remove={(i) => removeArrayItem("keywords", i)} />
                  <TaskArray label="Похожие названия" field="similar_positions" items={form.similar_positions} setItem={setArrayItem} add={() => pushArrayItem("similar_positions")} remove={(i) => removeArrayItem("similar_positions", i)} />
                  <TaskArray label="Стоп-компании" field="stop_companies" items={form.stop_companies} setItem={setArrayItem} add={() => pushArrayItem("stop_companies")} remove={(i) => removeArrayItem("stop_companies", i)} />
                  <TaskArray label="Компании-доноры" field="donor_companies" items={form.donor_companies} setItem={setArrayItem} add={() => pushArrayItem("donor_companies")} remove={(i) => removeArrayItem("donor_companies", i)} />
                  <TaskArray label="Источники рекомендаций" field="referral_sources" items={form.referral_sources} setItem={setArrayItem} add={() => pushArrayItem("referral_sources")} remove={(i) => removeArrayItem("referral_sources", i)} />
                </SectionCard>
              </>
            )}

            {step === 4 && (
              <>
                <SectionCard title="Условия труда">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <Label required>График</Label>
                      <input value={form.schedule} onChange={(e) => setField("schedule", e.target.value)} className={fieldClass(errors.schedule)} placeholder="5/2, 9:00–18:00" />
                      <FieldError message={errors.schedule} />
                    </div>
                    <div>
                      <Label required>Формат работы</Label>
                      <ChipGroup
                        value={form.work_format}
                        error={errors.work_format}
                        onChange={(v) => setField("work_format", v)}
                        options={WORK_FORMATS.map((w) => ({ value: w }))}
                      />
                    </div>
                    <div className="md:col-span-2">
                      <Label>Адрес рабочего места</Label>
                      <input value={form.work_address} onChange={(e) => setField("work_address", e.target.value)} className={fieldClass(false)} placeholder="Город, улица, дом, офис" />
                    </div>
                    <div className="md:col-span-2">
                      <ToggleRow
                        checked={form.background_search}
                        onChange={(v) => setField("background_search", v)}
                        title="Фоновый подбор"
                        hint="Продолжать поиск кандидатов сверх текущей подтверждённой потребности"
                      />
                    </div>
                    <div className="md:col-span-2">
                      <Label>Рабочий день</Label>
                      <textarea rows={2} value={form.work_day_description} onChange={(e) => setField("work_day_description", e.target.value)} className={fieldClass(false)} />
                    </div>
                    <div className="md:col-span-2">
                      <ToggleRow
                        checked={form.business_trips_required}
                        onChange={(v) => setField("business_trips_required", v)}
                        title="Командировки"
                        hint="Нужны ли поездки по работе"
                      />
                    </div>
                    {form.business_trips_required ? (
                      <>
                        <div>
                          <Label>Частота командировок</Label>
                          <input value={form.business_trips_frequency} onChange={(e) => setField("business_trips_frequency", e.target.value)} className={fieldClass(false)} />
                        </div>
                        <div>
                          <Label>Направления</Label>
                          <input value={form.business_trips_locations} onChange={(e) => setField("business_trips_locations", e.target.value)} className={fieldClass(false)} />
                        </div>
                      </>
                    ) : null}
                    <div>
                      <Label>Оклад от</Label>
                      <input type="number" min="0" value={form.salary_from} onChange={(e) => setField("salary_from", e.target.value)} className={fieldClass(false)} />
                    </div>
                    <div>
                      <Label>Оклад до</Label>
                      <input type="number" min="0" value={form.salary_to} onChange={(e) => setField("salary_to", e.target.value)} className={fieldClass(false)} />
                    </div>
                    <div>
                      <Label>Тип премии</Label>
                      <input value={form.bonus_type} onChange={(e) => setField("bonus_type", e.target.value)} className={fieldClass(false)} />
                    </div>
                    <div>
                      <Label>Премия</Label>
                      <input value={form.bonus_amount} onChange={(e) => setField("bonus_amount", e.target.value)} className={fieldClass(false)} />
                    </div>
                    <div className="md:col-span-2">
                      <TaskArray label="Соцпакет" field="benefits" items={form.benefits} setItem={setArrayItem} add={() => pushArrayItem("benefits")} remove={(i) => removeArrayItem("benefits", i)} placeholder="ДМС, питание…" />
                    </div>
                  </div>
                </SectionCard>
                <SectionCard title="Тестовое задание">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <ToggleRow
                      checked={form.test_required}
                      onChange={(v) => setField("test_required", v)}
                      title="Нужно тестовое"
                    />
                    <ToggleRow
                      checked={form.test_is_paid}
                      onChange={(v) => setField("test_is_paid", v)}
                      title="Тест оплачивается"
                    />
                  </div>
                  {form.test_required ? (
                    <div className="grid grid-cols-1 gap-4 pt-2">
                      <div>
                        <Label>Описание теста</Label>
                        <textarea rows={3} value={form.test_description} onChange={(e) => setField("test_description", e.target.value)} className={fieldClass(false)} />
                      </div>
                      <div>
                        <Label>Срок выполнения</Label>
                        <input value={form.test_deadline} onChange={(e) => setField("test_deadline", e.target.value)} className={fieldClass(false)} placeholder="Например, 5 рабочих дней" />
                      </div>
                    </div>
                  ) : null}
                </SectionCard>
              </>
            )}
          </div>

          <footer className="px-6 py-4 border-t border-slate-100 bg-white flex flex-wrap items-center justify-between gap-3">
            {closable ? (
              <button
                type="button"
                onClick={onClose}
                disabled={isLoading}
                className="px-4 py-2.5 rounded-xl text-sm font-medium text-slate-600 hover:bg-slate-100"
              >
                Отмена
              </button>
            ) : <span />}
            <div className="flex gap-2">
              {step > 0 ? (
                <button
                  type="button"
                  onClick={() => setStep((s) => s - 1)}
                  className="px-4 py-2.5 rounded-xl border border-slate-200 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Назад
                </button>
              ) : null}
              {step < STEPS.length - 1 ? (
                <button
                  type="button"
                  onClick={() => setStep((s) => s + 1)}
                  className="px-5 py-2.5 rounded-xl bg-slate-900 text-white text-sm font-medium hover:bg-slate-800"
                >
                  Далее
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={isLoading}
                  className="px-5 py-2.5 rounded-xl bg-[#4f46e5] text-white text-sm font-semibold hover:bg-[#4338ca] disabled:opacity-60"
                >
                  {isLoading ? "Создание…" : "Создать заявку"}
                </button>
              )}
            </div>
          </footer>
        </form>
      </div>
    </div>
  );
}
