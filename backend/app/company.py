from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Company, User
from app.services.schemas import CompanyProfile

router = APIRouter(prefix="/api/company", tags=["company"])


class CompanyInfoOut(CompanyProfile):
    model_config = ConfigDict(from_attributes=True)
    locked_at: datetime | None = None


@router.get("/info", response_model=CompanyInfoOut)
def get_info(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    company = db.get(Company, user.company_id)
    if company.status != "LOCKED":
        raise HTTPException(status.HTTP_409_CONFLICT, "Onboarding non termine")
    return CompanyInfoOut.model_validate(company)