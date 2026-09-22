from pydantic import BaseModel, Field, model_validator
from typing import Optional


class CompanyCandidateImageBase(BaseModel):
    soft_skills: Optional[str] = Field(None, description="Soft skills of the candidate", examples=["Team player, good communication"])
    red_flags: Optional[str] = Field(None, description="Red flags of the candidate", examples=["Frequent job changes"])
    common_requirements: Optional[str] = Field(None, description="Common requirements for the candidate", examples=["Willingness to relocate"])


class CompanyCandidateImageCreate(CompanyCandidateImageBase):
    pass


class CompanyCandidateImageRead(CompanyCandidateImageBase):
    id: int


class CompanyCandidateImageUpdate(BaseModel):
    soft_skills: Optional[str] = Field(None, description="Soft skills of the candidate", examples=["Team player, good communication"])
    red_flags: Optional[str] = Field(None, description="Red flags of the candidate", examples=["Frequent job changes"])
    common_requirements: Optional[str] = Field(None, description="Common requirements for the candidate", examples=["Willingness to relocate"])


class DepartmentCandidateImageBase(BaseModel):
    hard_skills: Optional[str] = Field(None, description="Hard skills of the candidate", examples=["Python, SQL, Docker"])
    expirience: Optional[str] = Field(None, description="Experience of the candidate", examples=["3 years in backend development"])
    common_requirements: Optional[str] = Field(None, description="Common requirements for the candidate", examples=["Experience with microservices"])
    lead_id: Optional[str] = Field(None, description="ERP UUID of the lead associated with this department candidate image")
    department: Optional[str] = Field(None, description="Department used to filter candidate images")


class DepartmentCandidateImageCreate(DepartmentCandidateImageBase):
    department: str = Field(..., min_length=1, description="Department this candidate image belongs to")
    experience: Optional[str] = Field(None, description="Alias for expirience", examples=["3 years in backend development"])

    @model_validator(mode="before")
    @classmethod
    def map_experience_alias(cls, data):
        if isinstance(data, dict):
            if data.get("experience") and not data.get("expirience"):
                data = {**data, "expirience": data["experience"]}
        return data

    def to_orm_dict(self):
        return self.model_dump(exclude={"experience"})


class DepartmentCandidateImageRead(DepartmentCandidateImageBase):
    id: int


class DepartmentCandidateImageUpdate(BaseModel):
    hard_skills: Optional[str] = Field(None, description="Hard skills of the candidate", examples=["Python, SQL, Docker"])
    expirience: Optional[str] = Field(None, description="Experience of the candidate", examples=["3 years in backend development"])
    experience: Optional[str] = Field(None, description="Alias for expirience", examples=["3 years in backend development"])
    common_requirements: Optional[str] = Field(None, description="Common requirements for the candidate", examples=["Experience with microservices"])

    @model_validator(mode="before")
    @classmethod
    def map_experience_alias(cls, data):
        if isinstance(data, dict):
            if data.get("experience") and not data.get("expirience"):
                data = {**data, "expirience": data["experience"]}
        return data

    def to_orm_dict(self, exclude_unset: bool = True):
        return self.model_dump(exclude_unset=exclude_unset, exclude={"experience"})


class DepartmentFilter(BaseModel):
    department: str = Field(..., description="Name of the department to filter by", examples=["hr"])
