import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.address import Address
from app.schemas.address import AddressCreate, AddressUpdate


def list_addresses(user_id: str, db: Session):
    addresses = db.query(Address).filter(Address.user_id == user_id).order_by(Address.is_default.desc(), Address.created_at.desc()).all()
    return [_format_address(a) for a in addresses]


def create_address(user_id: str, req: AddressCreate, db: Session):
    if req.is_default:
        db.query(Address).filter(Address.user_id == user_id, Address.is_default == True).update({"is_default": False})
    address = Address(
        user_id=uuid.UUID(user_id),
        full_name=req.full_name,
        phone=req.phone,
        street=req.street,
        city=req.city,
        state=req.state,
        country=(req.country or "IN").upper(),
        pincode=req.pincode,
        type=req.type,
        is_default=req.is_default,
    )
    db.add(address)
    db.commit()
    db.refresh(address)
    return _format_address(address)


def update_address(user_id: str, address_id: str, req: AddressUpdate, db: Session):
    address = db.query(Address).filter(Address.id == address_id, Address.user_id == user_id).first()
    if not address:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found")
    update_data = req.model_dump(exclude_unset=True)
    if update_data.get("country"):
        update_data["country"] = update_data["country"].upper()
    if update_data.get("is_default"):
        db.query(Address).filter(Address.user_id == user_id, Address.is_default == True, Address.id != address_id).update({"is_default": False})
    for key, value in update_data.items():
        setattr(address, key, value)
    db.commit()
    db.refresh(address)
    return _format_address(address)


def delete_address(user_id: str, address_id: str, db: Session):
    address = db.query(Address).filter(Address.id == address_id, Address.user_id == user_id).first()
    if not address:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found")
    db.delete(address)
    db.commit()
    return {"message": "Address deleted successfully"}


def _format_address(address: Address) -> dict:
    return {
        "id": str(address.id),
        "full_name": address.full_name,
        "phone": address.phone,
        "street": address.street,
        "city": address.city,
        "state": address.state,
        "country": address.country or "IN",
        "pincode": address.pincode,
        "type": address.type,
        "is_default": address.is_default,
        "created_at": address.created_at,
    }
