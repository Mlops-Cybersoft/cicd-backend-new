from sqlalchemy import and_, exists, or_, select

from app.models import (
    Document,
    DocumentPermission,
    DocumentVisibility,
    PermissionLevel,
    User,
    UserRole,
)


def document_access_filter(user: User):
    if user.role == UserRole.ADMIN.value:
        return True

    shared_permission = exists(
        select(DocumentPermission.id).where(
            DocumentPermission.document_id == Document.id,
            DocumentPermission.permission.in_(
                [PermissionLevel.READ.value, PermissionLevel.MANAGE.value]
            ),
            or_(
                and_(
                    DocumentPermission.grantee_type == "user",
                    DocumentPermission.grantee_id == user.id,
                ),
                and_(
                    DocumentPermission.grantee_type == "department",
                    DocumentPermission.grantee_id == user.department_id,
                ),
            ),
        )
    )

    common_access = [
        Document.owner_id == user.id,
        Document.visibility == DocumentVisibility.COMPANY.value,
        and_(
            Document.department_id == user.department_id,
            Document.visibility.in_(
                [
                    DocumentVisibility.DEPARTMENT.value,
                    DocumentVisibility.SHARED.value,
                ]
            ),
        ),
        shared_permission,
    ]
    if user.role == UserRole.MANAGER.value and user.department_id is not None:
        common_access.append(Document.department_id == user.department_id)
    return or_(*common_access)


def can_manage_document(user: User, document: Document) -> bool:
    if user.role == UserRole.ADMIN.value or document.owner_id == user.id:
        return True
    if (
        user.role == UserRole.MANAGER.value
        and user.department_id is not None
        and document.department_id == user.department_id
    ):
        return True
    return any(
        permission.permission == PermissionLevel.MANAGE.value
        and (
            (
                permission.grantee_type == "user"
                and permission.grantee_id == user.id
            )
            or (
                permission.grantee_type == "department"
                and permission.grantee_id == user.department_id
            )
        )
        for permission in document.permissions
    )
