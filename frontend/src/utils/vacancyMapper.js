const GENDER_MAP = {
    "мужчина": "male",
    "женщина": "female"
}

const DEPARTMENT_MAP = {
    "it": "IT",
    "development": "развитие",
}

const EXPERIENCE_MAP = {
    "0-1 год": "noExperience",
    "1-3 года": "between1And3",
    "3-6 лет": "between3And6",
    "6+ лет": "moreThan6"
};

export function mapVacancyToBackend(data) {
    const mapped = {
        ...data,
        gender: GENDER_MAP[data.gender] || data.gender,
        department: DEPARTMENT_MAP[data.department] || data.department,
        total_work_expirience: EXPERIENCE_MAP[data.total_work_expirience] || data.total_work_expirience,
        employment_id: data.employment_id || data.employment_type || null,
        schedule_id: data.schedule_id || data.work_format || null,
    };

    delete mapped.employment_type;
    delete mapped.work_format;

    if (data.professional_role_id !== null && data.professional_role_id !== undefined && data.professional_role_id !== "") {
        mapped.professional_roles_id = [String(data.professional_role_id)];
        delete mapped.professional_role_id;
    }

    return mapped;
}

export function mapVacancyFromBackend(data) {
    const reverseGender = {
        "male": "мужчина",
        "female": "женщина"
    }

    const mapped = {
        ...data,
        gender: reverseGender[data.gender] || data.gender,
        // Keep HH ids — form selects bind to dictionary item.id
        total_work_expirience: data.total_work_expirience || "",
        employment_type: data.employment_id || data.employment_type || "",
        employment_id: data.employment_id || "",
        work_format: data.schedule_id || data.work_format || "",
        schedule_id: data.schedule_id || "",
    };

    if (Array.isArray(data.professional_roles_id) && data.professional_roles_id.length > 0) {
        mapped.professional_role_id = Number(data.professional_roles_id[0]);
        delete mapped.professional_roles_id;
    }

    return mapped;
}
