from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class HRUserIn(BaseModel):
    employee_id: str = Field(..., alias="employee_id")
    first_name: str
    last_name: str
    preferred_name: Optional[str] = None
    email: EmailStr
    title: Optional[str] = None
    department: Optional[str] = None
    manager_email: Optional[EmailStr] = None
    location: Optional[str] = None
    office: Optional[str] = None
    employment_type: Optional[str] = None
    employment_status: Optional[str] = None
    start_date: Optional[str] = None
    termination_date: Optional[str] = None
    cost_center: Optional[str] = None
    employee_type: Optional[str] = None
    work_phone: Optional[str] = None
    mobile_phone: Optional[str] = None
    country: Optional[str] = None
    time_zone: Optional[str] = None
    legal_entity: Optional[str] = None
    division: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class OktaProfile(BaseModel):
    login: EmailStr
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    email: EmailStr
    employeeNumber: Optional[str] = None


class OktaUser(BaseModel):
    profile: OktaProfile
    groups: List[str] = []
    applications: List[str] = []


class EnrichedUser(BaseModel):
    id: str
    name: str
    email: EmailStr
    title: Optional[str] = None
    department: Optional[str] = None
    startDate: Optional[str] = None
    groups: List[str] = []
    applications: List[str] = []
    onboarded: bool = True

    @classmethod
    def from_sources(cls, hr: HRUserIn, okta: OktaUser) -> "EnrichedUser":
        name = f"{hr.first_name} {hr.last_name}".strip()
        start_date = hr.start_date
        return cls(
            id=hr.employee_id,
            name=name,
            email=hr.email,
            title=hr.title,
            department=hr.department,
            startDate=start_date,
            groups=okta.groups or [],
            applications=okta.applications or [],
            onboarded=True,
        )


class WebhookAcceptedResponse(BaseModel):
    """Response model for accepted webhook with background processing."""
    status: str = "accepted"
    message: str
    employee_id: str
    email: EmailStr
    correlation_id: Optional[str] = None
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "accepted",
                "message": "User enrichment queued for background processing",
                "employee_id": "12345",
                "email": "jane.doe@example.com"
            }
        }
    )


