import uuid
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.access import can_manage_document
from app.api.routes.admin_users import _resolve_department
from app.dependencies import require_admin
from app.models import UserRole


def make_user(role: str, department_id: uuid.UUID | None = None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        role=role,
        department_id=department_id,
    )


def make_document(
    department_id: uuid.UUID,
    owner_id: uuid.UUID | None = None,
):
    return SimpleNamespace(
        department_id=department_id,
        owner_id=owner_id or uuid.uuid4(),
        permissions=[],
    )


def test_admin_can_manage_every_document() -> None:
    admin = make_user(UserRole.ADMIN.value)
    document = make_document(uuid.uuid4())

    assert can_manage_document(admin, document)


def test_manager_can_only_manage_documents_in_own_department() -> None:
    department_id = uuid.uuid4()
    manager = make_user(UserRole.MANAGER.value, department_id)

    assert can_manage_document(manager, make_document(department_id))
    assert not can_manage_document(manager, make_document(uuid.uuid4()))


def test_employee_can_manage_document_they_own() -> None:
    employee = make_user(UserRole.EMPLOYEE.value, uuid.uuid4())
    document = make_document(employee.department_id, owner_id=employee.id)

    assert can_manage_document(employee, document)


def test_require_admin_rejects_non_admin() -> None:
    with pytest.raises(HTTPException) as exc_info:
        require_admin(make_user(UserRole.MANAGER.value))

    assert exc_info.value.status_code == 403


def test_non_admin_account_requires_department() -> None:
    database = Mock()

    with pytest.raises(HTTPException) as exc_info:
        _resolve_department(database, UserRole.EMPLOYEE.value, None)

    assert exc_info.value.status_code == 422
    database.get.assert_not_called()


def test_admin_account_is_company_wide() -> None:
    database = Mock()

    assert _resolve_department(database, UserRole.ADMIN.value, uuid.uuid4()) is None
    database.get.assert_not_called()
