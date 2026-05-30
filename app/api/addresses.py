from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.address import CreateAddressRequest, UpdateAddressRequest
from app.services import address_service

router = APIRouter(prefix="/api/addresses", tags=["Addresses"])


@router.get("")
def list_addresses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    addresses = address_service.get_addresses(db, current_user.id)
    return {"addresses": addresses}


@router.post("")
def create_address(
    req: CreateAddressRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return address_service.create_address(
        db, current_user.id, req.fullName, req.phone, req.street,
        req.city, req.state, req.pincode, req.isDefault, req.type,
    )


@router.put("/{address_id}")
def update_address(
    address_id: str,
    req: UpdateAddressRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    updates = req.model_dump(exclude_none=True)
    return address_service.update_address(db, current_user.id, address_id, updates)


@router.delete("/{address_id}")
def delete_address(
    address_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return address_service.delete_address(db, current_user.id, address_id)
