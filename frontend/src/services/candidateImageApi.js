import { http } from "../utils/http";

export const getCompanyCandidateImage = () => http.get("/candidate-image/company");
export const createCompanyCandidateImage = (data) => http.post("/candidate-image/company", data);
export const updateCompanyCandidateImage = (arg1, arg2) => {
  const data = arg2 !== undefined ? arg2 : arg1;
  return http.patch("/candidate-image/company", data);
}

export const getDepartmentCandidateImage = (department) =>
    http.get(`/candidate-image/department?department=${encodeURIComponent(department)}`);
export async function getAllDepartmentCandidateImages(department) {
  // Owner/dev: list all department portraits. Lead: filter by own department.
  if (department == null || department === "" || department === "*") {
    return http.get("/candidate-images/department/list");
  }
  return http.get(`/candidate-image/department?department=${encodeURIComponent(department)}`);
}

export const listDepartmentCandidateImages = () =>
  http.get("/candidate-images/department/list");
export const createDepartmentCandidateImage = (data) => http.post("/candidate-image/department", data);
export const updateDepartmentCandidateImage = (arg1, arg2) => {
  let department, data;
  if (arg2 !== undefined) {
    department = arg1;
    data = arg2;
  } else {
    data = arg1;
  }
  const qs = department ? `?department=${encodeURIComponent(department)}` : '';
  return http.patch(`/candidate-image/department${qs}`, data);
};