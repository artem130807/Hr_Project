import { HIRING_REQUEST_STATUS } from "../../services/hiringRequestsApi";
import { useAuth } from "../../context/AuthContext";
import { formatDateRu } from "../../utils/dateFormat";

/**
 * Модальное окно просмотра заявки на подбор персонала
 */

const formatSalary = (from, to) => {
    if (!from && !to) return "Не указана";
    if (from && to) return `${from.toLocaleString()} - ${to.toLocaleString()} руб.`;
    if (from) return `от ${from.toLocaleString()} руб.`;
    return `до ${to.toLocaleString()} руб.`;
};

const formatDate = (dateString) => {
    if (!dateString) return "—";
    return new Date(dateString).toLocaleDateString("ru-RU", {
        day: "numeric",
        month: "long",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit"
    });
};

const getStatusColor = (status) => {
    switch (status) {
        case "создана":
            return "bg-blue-100 text-blue-800";
        case "завершена":
        case "закрыта":
            return "bg-green-100 text-green-800";
        case "возвращена на уточнение":
            return "bg-amber-100 text-amber-800";
        case "отменена":
            return "bg-red-100 text-red-800";
        default:
            return "bg-gray-100 text-gray-800";
    }
};

const InfoRow = ({ label, value }) => (
  <div>
    <p className="text-sm text-gray-500">{label}</p>
    <p className="font-medium whitespace-pre-wrap">{value || "—"}</p>
  </div>
);

const ListBlock = ({ label, items }) => {
  if (!items || items.length === 0) return null;
  return (
    <div>
      <p className="text-sm text-gray-500 mb-1">{label}</p>
      <ul className="list-disc list-inside space-y-0.5 text-gray-700">
        {items.map((item, idx) => (
          <li key={idx}>{item}</li>
        ))}
      </ul>
    </div>
  );
};

export default function RequestViewModal({
  request,
  onClose,
  onStatusChange,
  onEdit,
  onCreateVacancy,
  onPublishHH,
  isUpdating = false,
  isCreatingVacancy = false,
  isPublishingHH = false,
}) {
  const { user } = useAuth();
  if (!request) return null;

  const statusLabel = HIRING_REQUEST_STATUS[request.status] || request.status;
  const isHr = user?.role === "hr" || user?.role === "owner" || user?.role === "dev";
  const canCreateVacancy =
    isHr &&
    !request.linked_vacancy_id &&
    !["закрыта", "завершена", "отменена", "возвращена на уточнение"].includes(request.status);
  const canPublishHH =
    isHr &&
    Boolean(request.linked_vacancy_id) &&
    !["закрыта", "завершена", "отменена", "возвращена на уточнение"].includes(request.status);

  const changeWithPrompt = (status, promptText, field) => {
    const value = window.prompt(promptText, "");
    if (value === null) return;
    if (!value.trim()) {
      window.alert("Комментарий обязателен");
      return;
    }
    onStatusChange(request.id, status, { [field]: value.trim() });
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-3xl mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white flex justify-between items-center px-6 py-4 border-b z-10">
          <div>
            <h2 className="text-xl font-semibold">Заявка #{request.id}</h2>
            <span className={`inline-block mt-1 px-2 py-0.5 text-xs font-medium rounded ${getStatusColor(request.status)}`}>
              {statusLabel}
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
          >
            &times;
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Основная информация */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-3 uppercase tracking-wide">Основная информация</h3>
            <div className="grid grid-cols-2 gap-4">
              <InfoRow label="Должность" value={request.position} />
              <InfoRow label="Отдел" value={request.department} />
              <InfoRow label="Количество" value={request.headcount ? `${request.headcount} чел.` : null} />
              <InfoRow label="Дата выхода" value={formatDateRu(request.planned_start_date)} />
              <InfoRow label="Срочность" value={request.urgency} />
              <InfoRow label="Зарплата" value={formatSalary(request.salary_from, request.salary_to)} />
            </div>
          </div>

          {/* Контактное лицо */}
          <div className="pt-4 border-t">
            <h3 className="text-sm font-semibold text-gray-900 mb-3 uppercase tracking-wide">Контактное лицо</h3>
            <div className="grid grid-cols-2 gap-4">
              <InfoRow label="ФИО руководителя" value={request.manager_name} />
              <InfoRow label="Должность руководителя" value={request.manager_position} />
              <InfoRow label="Телефон" value={request.phone} />
              <InfoRow label="Замещающий контакт" value={request.backup_contact} />
              <InfoRow label="Ответственный HR" value={request.assigned_hr_name} />
            </div>
          </div>

          {/* Основание */}
          <div className="pt-4 border-t">
            <h3 className="text-sm font-semibold text-gray-900 mb-3 uppercase tracking-wide">Основание</h3>
            <div className="grid grid-cols-2 gap-4">
              <InfoRow label="Причина открытия" value={request.reason} />
              <InfoRow label="Предыдущий сотрудник" value={request.previous_employee} />
              <InfoRow label="Испытательный срок (мес)" value={request.probation_period} />
            </div>
          </div>

          {/* Описание должности */}
          <div className="pt-4 border-t">
            <h3 className="text-sm font-semibold text-gray-900 mb-3 uppercase tracking-wide">Описание должности</h3>
            <div className="grid grid-cols-2 gap-4">
              <InfoRow label="Цель должности" value={request.purpose} />
              <InfoRow label="Особенности" value={request.features} />
              <InfoRow label="Подчинение" value={request.reporting} />
              <InfoRow label="Горизонтальные связи" value={request.horizontal_connections} />
              <InfoRow label="Перспективы роста" value={request.growth_prospects} />
            </div>
          </div>

          {/* Задачи */}
          <div className="pt-4 border-t">
            <h3 className="text-sm font-semibold text-gray-900 mb-3 uppercase tracking-wide">Задачи</h3>
            <div className="space-y-3">
              <ListBlock label="Ежедневные задачи" items={request.daily_tasks} />
              <ListBlock label="Еженедельные задачи" items={request.weekly_tasks} />
              <ListBlock label="Проектные задачи" items={request.project_tasks} />
            </div>
          </div>

          {/* KPI */}
          <div className="pt-4 border-t">
            <h3 className="text-sm font-semibold text-gray-900 mb-3 uppercase tracking-wide">KPI и результаты</h3>
            <div className="space-y-3">
              <ListBlock label="KPI" items={request.kpi_metrics} />
              <ListBlock label="Результаты после ИС" items={request.expected_results_probation} />
              <ListBlock label="Приоритеты 3 месяца" items={request.priorities_3months} />
            </div>
          </div>

          {/* Требования */}
          <div className="pt-4 border-t">
            <h3 className="text-sm font-semibold text-gray-900 mb-3 uppercase tracking-wide">Требования</h3>
            <div className="space-y-3">
              <ListBlock label="Обязательные требования" items={request.mandatory_requirements} />
              <ListBlock label="Желаемые требования" items={request.desired_requirements} />
              <div className="grid grid-cols-2 gap-4">
                {request.age_from && <InfoRow label="Возраст от" value={`${request.age_from} лет`} />}
                {request.age_to && <InfoRow label="Возраст до" value={`${request.age_to} лет`} />}
                {request.gender && <InfoRow label="Пол" value={request.gender} />}
                {request.total_experience_years && <InfoRow label="Общий опыт" value={`${request.total_experience_years} лет`} />}
                {request.relevant_experience_years && <InfoRow label="Релевантный опыт" value={`${request.relevant_experience_years} лет`} />}
              </div>
            </div>
          </div>

          {/* Hard / Soft Skills */}
          <div className="pt-4 border-t">
            <h3 className="text-sm font-semibold text-gray-900 mb-3 uppercase tracking-wide">Навыки</h3>
            <div className="space-y-3">
              <ListBlock label="Обязательные профессиональные навыки" items={request.required_hard_skills} />
              <ListBlock label="Дополнительные профессиональные навыки" items={request.optional_hard_skills} />
              <ListBlock label="Гибкие навыки" items={request.required_soft_skills} />
              <ListBlock label="Неприемлемые качества" items={request.unacceptable_soft_skills} />
            </div>
          </div>

          {/* Компетенции и ценности */}
          <div className="pt-4 border-t">
            <h3 className="text-sm font-semibold text-gray-900 mb-3 uppercase tracking-wide">Компетенции и ценности</h3>
            <div className="space-y-3">
              <ListBlock label="Должностные компетенции" items={request.job_competencies} />
              <ListBlock label="Корпоративные компетенции" items={request.corporate_competencies} />
              <ListBlock label="Критичные ценности" items={request.critical_values} />
              <ListBlock label="Приемлемое поведение" items={request.acceptable_behavior} />
              <ListBlock label="Неприемлемое поведение" items={request.unacceptable_behavior} />
              <ListBlock label="Индикаторы соответствия" items={request.fit_indicators} />
              <ListBlock label="Индикаторы несоответствия" items={request.misfit_indicators} />
            </div>
          </div>

          {/* Технические требования */}
          <div className="pt-4 border-t">
            <h3 className="text-sm font-semibold text-gray-900 mb-3 uppercase tracking-wide">Технические требования</h3>
            <div className="space-y-3">
              <ListBlock label="Программы" items={request.software} />
              <ListBlock label="Инструменты" items={request.tools} />
              <ListBlock label="Языки" items={request.languages} />
              <InfoRow label="Внешний вид" value={request.appearance} />
            </div>
          </div>

          {/* Стратегия поиска */}
          <div className="pt-4 border-t">
            <h3 className="text-sm font-semibold text-gray-900 mb-3 uppercase tracking-wide">Стратегия поиска</h3>
            <div className="space-y-3">
              <ListBlock label="Ключевые слова" items={request.keywords} />
              <ListBlock label="Похожие названия" items={request.similar_positions} />
              <ListBlock label="Стоп-компании" items={request.stop_companies} />
              <ListBlock label="Компании-доноры" items={request.donor_companies} />
              <ListBlock label="Источники рекомендаций" items={request.referral_sources} />
            </div>
          </div>

          {/* Условия труда */}
          <div className="pt-4 border-t">
            <h3 className="text-sm font-semibold text-gray-900 mb-3 uppercase tracking-wide">Условия труда</h3>
            <div className="grid grid-cols-2 gap-4">
              <InfoRow label="График" value={request.schedule} />
              <InfoRow label="Формат работы" value={request.work_format} />
              <InfoRow label="Адрес рабочего места" value={request.work_address} />
              <InfoRow label="Фоновый подбор" value={request.background_search ? "Включён" : "Выключен"} />
              <InfoRow label="Рабочий день" value={request.work_day_description} />
              <InfoRow label="Командировки требуются" value={request.business_trips_required ? "Да" : "Нет"} />
              <InfoRow label="Частота командировок" value={request.business_trips_frequency} />
              <InfoRow label="Направления командировок" value={request.business_trips_locations} />
              <InfoRow label="Оклад" value={formatSalary(request.salary_from, request.salary_to)} />
              <InfoRow label="Валюта" value={request.currency} />
              <InfoRow label="Оклад gross" value={request.gross ? "Да" : "Нет"} />
              <InfoRow label="Премия (тип)" value={request.bonus_type} />
              <InfoRow label="Премия (сумма/описание)" value={request.bonus_amount} />
              <InfoRow label="Условия премии" value={request.bonus_conditions} />
              <ListBlock label="Бенефиты" items={request.benefits} />
            </div>
          </div>

          {/* Тестовое */}
          <div className="pt-4 border-t">
            <h3 className="text-sm font-semibold text-gray-900 mb-3 uppercase tracking-wide">Тестовое задание</h3>
            <div className="grid grid-cols-2 gap-4">
              <InfoRow label="Требуется тестовое" value={request.test_required ? "Да" : "Нет"} />
              <InfoRow label="Тест оплачивается" value={request.test_is_paid ? "Да" : "Нет"} />
              <InfoRow label="Описание теста" value={request.test_description} />
              <InfoRow label="Дедлайн теста" value={formatDateRu(request.test_deadline, request.test_deadline || "—")} />
            </div>
          </div>

          {/* Даты и статус */}
          <div className="pt-4 border-t">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <InfoRow label="Комментарий к уточнению" value={request.return_comment} />
              <InfoRow label="Основание закрытия" value={request.close_reason} />
              <InfoRow label="Основание отмены" value={request.cancel_reason} />
              <div>
                <p className="text-gray-500">Создана</p>
                <p>{formatDate(request.created_at)}</p>
              </div>
              <div>
                <p className="text-gray-500">Связанная вакансия</p>
                <p>
                  {request.linked_vacancy_id ? (
                    <a
                      href={`/vacancies`}
                      className="text-[#cda834] hover:underline font-medium"
                      onClick={(e) => {
                        e.preventDefault();
                        window.location.assign(`/vacancies`);
                      }}
                    >
                      #{request.linked_vacancy_id} — открыть список вакансий
                    </a>
                  ) : (
                    "—"
                  )}
                </p>
                {request.linked_vacancy_id && (
                  <p className="text-xs text-amber-700 mt-1">
                    Перед публикацией на HH укажите в вакансии профессиональную роль и город.
                  </p>
                )}
              </div>
              {request.status === "завершена" && (
                <div>
                  <p className="text-gray-500">Завершена</p>
                  <p>{formatDate(request.updated_at)}</p>
                </div>
              )}
            </div>
          </div>

          {/* Workflow: vacancy + HH */}
          {(canCreateVacancy || canPublishHH || onStatusChange) && (
            <div className="pt-4 border-t flex flex-wrap gap-2">
              {canCreateVacancy && onCreateVacancy && (
                <button
                  type="button"
                  onClick={() => onCreateVacancy(request.id)}
                  disabled={isCreatingVacancy}
                  className="px-4 py-2 text-sm bg-slate-900 text-white rounded-lg hover:bg-slate-800 disabled:opacity-50"
                >
                  {isCreatingVacancy ? "Создание..." : "Создать вакансию"}
                </button>
              )}
              {canPublishHH && onPublishHH && (
                <button
                  type="button"
                  onClick={() => onPublishHH(request.id)}
                  disabled={isPublishingHH}
                  className="px-4 py-2 text-sm bg-[#e0bb48] text-black rounded-lg hover:bg-[#d4af3a] disabled:opacity-50 font-medium"
                >
                  {isPublishingHH ? "Публикация..." : "Опубликовать на HH.ru"}
                </button>
              )}
              {onStatusChange && ["создана", "на анализе"].includes(request.status) && isHr && (
                <button
                  type="button"
                  onClick={() => onStatusChange(request.id, "утверждена")}
                  disabled={isUpdating}
                  className="px-4 py-2 text-sm bg-green-100 text-green-800 rounded-lg hover:bg-green-200 disabled:opacity-50"
                >
                  {isUpdating ? "..." : "Утвердить"}
                </button>
              )}
              {onStatusChange && ["создана", "на анализе", "утверждена"].includes(request.status) && isHr && (
                <button
                  type="button"
                  onClick={() => changeWithPrompt("возвращена на уточнение", "Что необходимо уточнить руководителю?", "comment")}
                  disabled={isUpdating}
                  className="px-4 py-2 text-sm bg-amber-100 text-amber-800 rounded-lg hover:bg-amber-200 disabled:opacity-50"
                >
                  Возвратить на уточнение
                </button>
              )}
              {onStatusChange && request.status === "возвращена на уточнение" && (
                <button type="button" onClick={() => onStatusChange(request.id, "на анализе")} disabled={isUpdating} className="px-4 py-2 text-sm bg-blue-100 text-blue-800 rounded-lg hover:bg-blue-200 disabled:opacity-50">Отправить повторно</button>
              )}
              {onEdit && request.status === "возвращена на уточнение" && (
                <button type="button" onClick={() => onEdit(request)} className="px-4 py-2 text-sm bg-slate-900 text-white rounded-lg hover:bg-slate-800">Редактировать условия</button>
              )}
              {onStatusChange && ["утверждена", "опубликована"].includes(request.status) && isHr && (
                <button type="button" onClick={() => changeWithPrompt("закрыта", "Укажите основание закрытия", "reason")} disabled={isUpdating} className="px-4 py-2 text-sm bg-slate-100 text-slate-700 rounded-lg">Закрыть заявку</button>
              )}
              {onStatusChange && !["закрыта", "завершена", "отменена"].includes(request.status) && isHr && (
                <button type="button" onClick={() => changeWithPrompt("отменена", "Укажите основание отмены", "reason")} disabled={isUpdating} className="px-4 py-2 text-sm bg-red-50 text-red-700 rounded-lg">Отменить заявку</button>
              )}
            </div>
          )}

          {Array.isArray(request.history) && request.history.length > 0 && (
            <div className="pt-4 border-t">
              <h3 className="text-sm font-semibold text-gray-900 mb-3 uppercase tracking-wide">История заявки</h3>
              <div className="space-y-3">
                {request.history.map(item => (
                  <div key={item.id} className="rounded-lg border border-slate-200 p-3 text-sm">
                    <div className="flex justify-between gap-3"><b>{item.event_type === "conditions_updated" ? "Изменены условия" : "Изменён статус"}</b><span className="text-slate-500">{formatDate(item.created_at)}</span></div>
                    {item.from_status && <p className="text-slate-600">{item.from_status} → {item.to_status}</p>}
                    {item.comment && <p className="mt-1">{item.comment}</p>}
                    {item.changes && Object.entries(item.changes).map(([field, values]) => <p key={field} className="text-slate-600">{field}: {String(values?.from ?? "—")} → {String(values?.to ?? "—")}</p>)}
                    <p className="text-xs text-slate-400 mt-1">{item.actor_name || "Система"}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-between px-6 py-4 border-t bg-gray-50 rounded-b-lg">
          <div />
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-100"
          >
            Закрыть
          </button>
        </div>
      </div>
    </div>
  );
}
