from fastapi import APIRouter
from sqlalchemy import select

from app.dependencies import CurrentUser, DatabaseDependency
from app.models import Department
from app.schemas import DepartmentRead


router = APIRouter(prefix="/departments", tags=["Departments"])


@router.get("", response_model=list[DepartmentRead])
def list_departments(
    database: DatabaseDependency,
    _: CurrentUser,
) -> list[Department]:
    return list(database.scalars(select(Department).order_by(Department.name)).all())
