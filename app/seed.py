from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Department, User, UserRole
from app.security import hash_password


DEPARTMENTS = [
    {
        "code": "FINANCE",
        "name": "Phòng Tài chính",
        "description": "Quản lý ngân sách, kế toán và báo cáo tài chính.",
        "color": "#19715f",
    },
    {
        "code": "HR",
        "name": "Phòng Nhân sự",
        "description": "Quản lý nhân sự, chính sách và hồ sơ lao động.",
        "color": "#b46b35",
    },
    {
        "code": "LEGAL",
        "name": "Phòng Pháp lý",
        "description": "Quản lý hợp đồng, quy định và hồ sơ pháp lý.",
        "color": "#5f63a8",
    },
]


def seed_database(database: Session) -> None:
    departments: dict[str, Department] = {}
    for payload in DEPARTMENTS:
        department = database.scalar(
            select(Department).where(Department.code == payload["code"])
        )
        if not department:
            department = Department(**payload)
            database.add(department)
            database.flush()
        departments[payload["code"]] = department

    demo_users = [
        ("admin@documind.vn", "Quản trị hệ thống", UserRole.ADMIN.value, None),
        (
            "finance@documind.vn",
            "Nguyễn Minh Tài",
            UserRole.MANAGER.value,
            departments["FINANCE"].id,
        ),
        (
            "hr@documind.vn",
            "Trần Thu Hà",
            UserRole.MANAGER.value,
            departments["HR"].id,
        ),
        (
            "legal@documind.vn",
            "Lê Hoàng Minh",
            UserRole.MANAGER.value,
            departments["LEGAL"].id,
        ),
    ]

    for email, full_name, role, department_id in demo_users:
        if not database.scalar(select(User).where(User.email == email)):
            database.add(
                User(
                    email=email,
                    full_name=full_name,
                    role=role,
                    department_id=department_id,
                    hashed_password=hash_password(settings.demo_password),
                )
            )
    database.commit()
