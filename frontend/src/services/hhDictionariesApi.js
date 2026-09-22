import { http } from "../utils/http";

const asItems = async (path) => {
  const data = await http.get(path);
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.items)) return data.items;
  return [];
};

export const getAreas = () => asItems("/areas");
export const getAreasDict = getAreas;
export const getProfessionalRolesDict = () => asItems("/professional_roles");
export const getVacancyTypes = () => asItems("/vacancy_type");
export const getWorkFormats = () => asItems("/work_format");
export const getExperience = () => asItems("/experience");
export const getExperienceDict = getExperience;
export const getEmploymentTypes = () => asItems("/employment");
export const getEmploymentDict = getEmploymentTypes;
export const getSchedules = () => asItems("/schedule");
export const getScheduleDict = getSchedules;
