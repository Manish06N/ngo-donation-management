from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import Listing, as_page, get_current_user, get_db
from app.models.identity import User
from app.schemas.operations import MovementCreate, MovementRead, ResourceCreate, ResourceRead, ResourceUpdate
from app.services import resource_service

router = APIRouter(prefix="/resources", tags=["Resources"])


@router.post("", response_model=ResourceRead, status_code=status.HTTP_201_CREATED)
def create_resource(payload: ResourceCreate, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Register a resource. Opening quantity is stored as a stock-in movement."""
    return resource_service.present(resource_service.create_resource(db, actor, payload))


@router.get("", response_model=dict)
def list_resources(
    listing: Listing = Depends(),
    q: str | None = None,
    category: str | None = None,
    low_stock: bool = False,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows, total = resource_service.list_resources(
        db, actor, page=listing.page, page_size=listing.page_size, sort_by=listing.sort_by, sort_dir=listing.sort_dir, q=q, category=category, low_stock=low_stock
    )
    return as_page(rows, total, listing)


@router.get("/{resource_id}", response_model=ResourceRead)
def get_resource(resource_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return resource_service.present(resource_service.get_resource(db, actor, resource_id))


@router.patch("/{resource_id}", response_model=ResourceRead)
def update_resource(resource_id: int, payload: ResourceUpdate, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return resource_service.present(resource_service.update_resource(db, actor, resource_id, payload))


@router.post("/{resource_id}/movements", response_model=MovementRead, status_code=status.HTTP_201_CREATED)
def move(resource_id: int, payload: MovementCreate, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Stock in, stock out, or allocate to a project. The balance cannot go below zero."""
    return resource_service.move(db, actor, resource_id, payload)


@router.get("/{resource_id}/movements", response_model=list[MovementRead])
def movements(resource_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return resource_service.list_movements(db, actor, resource_id)
