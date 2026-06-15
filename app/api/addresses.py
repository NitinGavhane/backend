from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.address import AddressCreate, AddressResponse, AddressUpdate
from app.services import address_service

router = APIRouter(prefix="/api/v1/addresses", tags=["Addresses"])


@router.get("", response_model=list[AddressResponse])
def list_addresses(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return address_service.list_addresses(str(user.id), db)


@router.post("", response_model=AddressResponse, status_code=201)
def create_address(req: AddressCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return address_service.create_address(str(user.id), req, db)


@router.put("/{address_id}", response_model=AddressResponse)
def update_address(address_id: str, req: AddressUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return address_service.update_address(str(user.id), address_id, req, db)


@router.delete("/{address_id}")
def delete_address(address_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return address_service.delete_address(str(user.id), address_id, db)
