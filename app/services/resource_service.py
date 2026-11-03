from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import MovementType, NotificationCategory, Role
from app.domain.errors import AppError
from app.domain.permissions import Permission
from app.domain.rules import stock_after
from app.models.identity import User
from app.models.inventory import Resource, ResourceTransaction
from app.models.projects import Project
from app.repositories.common import apply_sort, get_for_update, get_or_404, paginate
from app.schemas.operations import MovementCreate, ResourceCreate, ResourceRead, ResourceUpdate
from app.services.access import audit, authorize, notify, touch, users_with_roles


def present(row: Resource) -> ResourceRead:
    data = ResourceRead.model_validate(row)
    return data.model_copy(update={"is_low_stock": row.quantity_on_hand <= row.reorder_level})


def create_resource(db: Session, actor: User, payload: ResourceCreate) -> Resource:
    authorize(actor, Permission.MANAGE_RESOURCES)
    resource = Resource(
        name=payload.name,
        category=payload.category.value if hasattr(payload.category, "value") else payload.category,
        unit=payload.unit,
        quantity_on_hand=0,
        reorder_level=payload.reorder_level,
        description=payload.description,
    )
    db.add(resource)
    db.flush()
    if payload.quantity_on_hand > 0:
        apply_movement(
            db,
            actor,
            resource.id,
            MovementType.STOCK_IN.value,
            payload.quantity_on_hand,
            None,
            "Opening stock",
            check_permission=False,
        )
    audit(db, actor.id, "resource.created", "resource", resource.id, {"name": resource.name, "category": resource.category})
    db.flush()
    return resource


def update_resource(db: Session, actor: User, resource_id: int, payload: ResourceUpdate) -> Resource:
    authorize(actor, Permission.MANAGE_RESOURCES)
    resource = get_or_404(db, Resource, resource_id, "Resource")
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(resource, key, value)
    touch(resource)
    if resource.quantity_on_hand <= resource.reorder_level:
        _alert_low_stock(db, resource)
    audit(db, actor.id, "resource.updated", "resource", resource.id, {"fields": list(changes)})
    db.flush()
    return resource


def apply_movement(
    db: Session,
    actor: User,
    resource_id: int,
    movement_type: str,
    quantity: int,
    project_id: int | None,
    notes: str | None,
    *,
    check_permission: bool = True,
) -> ResourceTransaction:
    if check_permission:
        authorize(actor, Permission.MANAGE_RESOURCES)
    movement_type = movement_type.value if hasattr(movement_type, "value") else movement_type
    if movement_type == MovementType.ALLOCATION.value and project_id is None:
        raise AppError("Allocating stock requires a project", 422, "project_required")
    if project_id is not None:
        get_or_404(db, Project, project_id, "Project")
    resource = get_for_update(db, Resource, resource_id, "Resource")
    inbound = movement_type == MovementType.STOCK_IN.value
    resource.quantity_on_hand = stock_after(resource.quantity_on_hand, quantity, inbound)
    touch(resource)
    movement = ResourceTransaction(
        resource_id=resource.id,
        project_id=project_id,
        movement_type=movement_type,
        quantity=quantity,
        balance_after=resource.quantity_on_hand,
        notes=notes,
        actor_id=actor.id,
    )
    db.add(movement)
    db.flush()
    if resource.quantity_on_hand <= resource.reorder_level:
        _alert_low_stock(db, resource)
    audit(
        db,
        actor.id,
        "resource.movement",
        "resource",
        resource.id,
        {
            "movement_type": movement_type,
            "quantity": quantity,
            "balance_after": resource.quantity_on_hand,
            "project_id": project_id,
        },
    )
    return movement


def move(db: Session, actor: User, resource_id: int, payload: MovementCreate) -> ResourceTransaction:
    return apply_movement(
        db,
        actor,
        resource_id,
        payload.movement_type,
        payload.quantity,
        payload.project_id,
        payload.notes,
    )


def _alert_low_stock(db: Session, resource: Resource) -> None:
    notify(
        db,
        users_with_roles(db, {Role.SUPER_ADMIN.value, Role.NGO_MANAGER.value, Role.VOLUNTEER_COORDINATOR.value}),
        title="Low resource stock",
        message=f"{resource.name} has {resource.quantity_on_hand} {resource.unit} left (reorder at {resource.reorder_level}).",
        category=NotificationCategory.LOW_STOCK.value,
        entity_type="resource",
        entity_id=resource.id,
    )


def get_resource(db: Session, actor: User, resource_id: int) -> Resource:
    authorize(actor, Permission.READ_RESOURCES)
    return get_or_404(db, Resource, resource_id, "Resource")


def list_resources(db, actor, *, page, page_size, sort_by, sort_dir, q, category, low_stock):
    authorize(actor, Permission.READ_RESOURCES)
    stmt = select(Resource)
    if q:
        stmt = stmt.where(Resource.name.ilike(f"%{q}%"))
    if category:
        stmt = stmt.where(Resource.category == category)
    if low_stock:
        stmt = stmt.where(Resource.quantity_on_hand <= Resource.reorder_level)
    stmt = apply_sort(stmt, sort_by, sort_dir, {"id": Resource.id, "name": Resource.name, "quantity_on_hand": Resource.quantity_on_hand})
    rows, total = paginate(db, stmt, page, page_size)
    return [present(row) for row in rows], total


def list_movements(db: Session, actor: User, resource_id: int):
    authorize(actor, Permission.READ_RESOURCES)
    get_or_404(db, Resource, resource_id, "Resource")
    return list(
        db.scalars(
            select(ResourceTransaction)
            .where(ResourceTransaction.resource_id == resource_id)
            .order_by(ResourceTransaction.id.desc())
        ).all()
    )
