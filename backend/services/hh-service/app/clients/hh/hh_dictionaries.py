import os
import time
from typing import Any, Dict, List, Optional
import json

import httpx

# Все эндпоинты справочников hh.ru
DICTS_URLS = {
    "areas": "https://api.hh.ru/areas",
    "dictionaries": "https://api.hh.ru/dictionaries",
    "professional_roles": "https://api.hh.ru/professional_roles",
    "languages": "https://api.hh.ru/languages",
    "skills": "https://api.hh.ru/skills"
}

CACHE_PATH = os.path.join(os.path.dirname(__file__), "hh_dictionaries_cache.json")
CACHE_TTL = 86400  # 1 день


class HHDictionaries:
    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._load_cache()
        if self._cache_expired():
            self.update_all()

    def _load_cache(self):
        if os.path.exists(CACHE_PATH):
            try:
                with open(CACHE_PATH, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
            except Exception:
                self._cache = {"timestamp": 0}
        else:
            self._cache = {"timestamp": 0}

    def _save_cache(self):
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, ensure_ascii=False, indent=2)

    def _cache_expired(self) -> bool:
        return time.time() - self._cache.get("timestamp", 0) > CACHE_TTL

    def update_all(self):
        for key, url in DICTS_URLS.items():
            try:
                resp = httpx.get(url, timeout=10)
                resp.raise_for_status()
                self._cache[key] = resp.json()
            except Exception as e:
                print(f"Failed to update {key}: {e}")
        self._cache["timestamp"] = time.time()
        self._save_cache()

    # === Методы для отдачи справочников "как есть" ===

    def get_areas(self) -> List[Dict]:
        return self._cache["areas"]

    def get_professional_roles(self) -> List[Dict]:
        return self._cache["professional_roles"]

    def get_languages(self) -> List[Dict]:
        return self._cache["languages"]

    def get_currency(self) -> List[Dict]:
        return self._cache["dictionaries"]["currency"]
    
    def get_skills(self) -> List[Dict]:
        return self._cache["skills"]

    # === Справочники из /dictionaries ===
    def get_resume_access_type(self) -> List[Dict]:
        return self._cache["dictionaries"]["resume_access_type"]

    def get_billing_type(self) -> List[Dict]:
        return self._cache["dictionaries"]["vacancy_billing_type"]

    def get_vacancy_search_order(self) -> List[Dict]:
        return self._cache["dictionaries"]["vacancy_search_order"]

    def get_vacancy_search_fields(self) -> List[Dict]:
        return self._cache["dictionaries"]["vacancy_search_fields"]

    def get_gender(self) -> List[Dict]:
        return self._cache["dictionaries"]["gender"]

    def get_preferred_contact_type(self) -> List[Dict]:
        return self._cache["dictionaries"]["preferred_contact_type"]

    def get_travel_time(self) -> List[Dict]:
        return self._cache["dictionaries"]["travel_time"]

    def get_relocation_type(self) -> List[Dict]:
        return self._cache["dictionaries"]["relocation_type"]

    def get_business_trip_readiness(self) -> List[Dict]:
        return self._cache["dictionaries"]["business_trip_readiness"]

    def get_experience(self) -> List[Dict]:
        return self._cache["dictionaries"]["experience"]

    def get_employment(self) -> List[Dict]:
        return self._cache["dictionaries"]["employment"]

    def get_schedule(self) -> List[Dict]:
        return self._cache["dictionaries"]["schedule"]

    def get_education_level(self) -> List[Dict]:
        return self._cache["dictionaries"]["education_level"]

    def get_language_level(self) -> List[Dict]:
        return self._cache["dictionaries"]["language_level"]

    def get_driver_license_types(self) -> List[Dict]:
        return self._cache["dictionaries"]["driver_license_types"]

    def get_working_days(self) -> List[Dict]:
        return self._cache["dictionaries"]["working_days"]

    def get_working_time_intervals(self) -> List[Dict]:
        return self._cache["dictionaries"]["working_time_intervals"]

    def get_working_time_modes(self) -> List[Dict]:
        return self._cache["dictionaries"]["working_time_modes"]

    def get_work_schedule_by_days(self) -> List[Dict]:
        return self._cache["dictionaries"]["work_schedule_by_days"]

    def get_working_hours(self) -> List[Dict]:
        return self._cache["dictionaries"]["working_hours"]

    def get_salary_range_mode(self) -> List[Dict]:
        return self._cache["dictionaries"]["salary_range_mode"]

    def get_salary_range_frequency(self) -> List[Dict]:
        return self._cache["dictionaries"]["salary_range_frequency"]

    def get_age_restriction(self) -> List[Dict]:
        return self._cache["dictionaries"]["age_restriction"]

    def get_fly_in_fly_out_duration(self) -> List[Dict]:
        return self._cache["dictionaries"]["fly_in_fly_out_duration"]

    def get_employment_form(self) -> List[Dict]:
        return self._cache["dictionaries"]["employment_form"]

    def get_work_format(self) -> List[Dict]:
        return self._cache["dictionaries"]["work_format"]

    def get_vacancy_type(self) -> List[Dict]:
        return self._cache["dictionaries"]["vacancy_type"]

    # Дополнительные (менее часто используемые, но доступные)
    def get_resume_status(self) -> List[Dict]:
        return self._cache["dictionaries"]["resume_status"]

    def get_messaging_status(self) -> List[Dict]:
        return self._cache["dictionaries"]["messaging_status"]

    def get_vacancy_relation(self) -> List[Dict]:
        return self._cache["dictionaries"]["vacancy_relation"]

    def get_resume_hidden_fields(self) -> List[Dict]:
        return self._cache["dictionaries"]["resume_hidden_fields"]

    def get_vacancy_label(self) -> List[Dict]:
        return self._cache["dictionaries"]["vacancy_label"]

    def get_employer_type(self) -> List[Dict]:
        return self._cache["dictionaries"]["employer_type"]

    def get_resume_contacts_site_type(self) -> List[Dict]:
        return self._cache["dictionaries"]["resume_contacts_site_type"]

    def get_job_search_statuses_applicant(self) -> List[Dict]:
        return self._cache["dictionaries"]["job_search_statuses_applicant"]

    def get_job_search_statuses_employer(self) -> List[Dict]:
        return self._cache["dictionaries"]["job_search_statuses_employer"]
    
    # --- UNIVERSAL SEARCH BY ID ---
    def _find_in_list(self, items: List[Dict], target_id: str) -> Optional[str]:
        """
        Рекурсивно ищет элемент по id в списке словарей hh (включая вложенные).
        Возвращает name или None, если не найден.
        """
        for item in items:
            if str(item.get("id")) == str(target_id):
                return item.get("name")
            # HH структуры часто вложенные (areas, roles)
            for key in ("areas", "roles", "items"):
                if key in item and isinstance(item[key], list):
                    found = self._find_in_list(item[key], target_id)
                    if found:
                        return found
        return None

    # --- SHORTCUT HELPERS FOR EACH DICTIONARY ---
    def get_area_name(self, area_id: str) -> Optional[str]:
        return self._find_in_list(self.get_areas(), area_id)

    def get_professional_role_name(self, role_id: str) -> Optional[str]:
        """
        Возвращает название профессиональной роли по её ID
        из структуры hh.ru /professional_roles.
        """
        data = self._cache.get("professional_roles")
        if not data or "categories" not in data:
            return None

        for category in data["categories"]:
            roles = category.get("roles", [])
            for role in roles:
                if str(role.get("id")) == str(role_id):
                    return role.get("name")
        return None

    def get_language_name(self, lang_id: str) -> Optional[str]:
        return self._find_in_list(self.get_languages(), lang_id)

    def get_currency_name(self, curr_id: str) -> Optional[str]:
        for item in self.get_currency():
            if str(item.get("id")) == str(curr_id):
                return item.get("name")
            # HH структуры часто вложенные (areas, roles)
            for key in ("areas", "roles", "items"):
                if key in item and isinstance(item[key], list):
                    found = self._find_in_list(item[key], curr_id)
                    if found:
                        return found
        return None
        return self._find_in_list(self.get_currency(), curr_id)

    def get_skill_name(self, skill_id: str) -> Optional[str]:
        return self._find_in_list(self.get_skills(), skill_id)

    # универсальные для словарей внутри "dictionaries"
    def get_dict_item_name(self, dict_name: str, item_id: str) -> Optional[str]:
        """Поиск name по id в любом справочнике из /dictionaries"""
        dict_data = self._cache["dictionaries"].get(dict_name)
        if not dict_data:
            return None
        return self._find_in_list(dict_data, item_id)
    
     # --- Примеры конкретных мапперов ---

    def get_experience_name(self, exp_id: str) -> str | None:
        return self._find_in_list(self.get_experience(), exp_id)

    def get_employment_name(self, emp_id: str) -> str | None:
        return self._find_in_list(self.get_employment(), emp_id)

    def get_schedule_name(self, sched_id: str) -> str | None:
        return self._find_in_list(self.get_schedule(), sched_id)

    def get_work_format_name(self, wf_id: str) -> str | None:
        return self._find_in_list(self.get_work_format(), wf_id)

    def get_vacancy_type_name(self, vt_id: str) -> str | None:
        return self._find_in_list(self.get_vacancy_type(), vt_id)

    def get_billing_type_name(self, bt_id: str) -> str | None:
        return self._find_in_list(self.get_billing_type(), bt_id)

    def get_gender_name(self, gender_id: str) -> str | None:
        return self._find_in_list(self.get_gender(), gender_id)

    def get_education_level_name(self, edu_id: str) -> str | None:
        return self._find_in_list(self.get_education_level(), edu_id)