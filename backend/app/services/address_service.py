from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.address import Address
from app.schemas.address import AddressCreate, AddressUpdate


def list_addresses(user_id: str, db: Session) -> list[dict]:
    addresses = db.query(Address).filter(Address.user_id == user_id).order_by(Address.is_default.desc(), Address.created_at.desc()).all()
    return [_address_to_dict(a) for a in addresses]


def create_address(user_id: str, req: AddressCreate, db: Session) -> dict:
    if req.is_default:
        db.query(Address).filter(Address.user_id == user_id, Address.is_default == True).update({"is_default": False})
    address = Address(user_id=user_id, **req.model_dump())
    db.add(address)
    db.commit()
    db.refresh(address)
    return _address_to_dict(address)


def get_address(user_id: str, address_id: str, db: Session) -> dict:
    address = db.query(Address).filter(Address.id == address_id, Address.user_id == user_id).first()
    if not address:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found")
    return _address_to_dict(address)


def update_address(user_id: str, address_id: str, req: AddressUpdate, db: Session) -> dict:
    address = db.query(Address).filter(Address.id == address_id, Address.user_id == user_id).first()
    if not address:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found")
    update_data = req.model_dump(exclude_unset=True)
    if update_data.get("is_default"):
        db.query(Address).filter(Address.user_id == user_id, Address.is_default == True, Address.id != address_id).update({"is_default": False})
    for key, value in update_data.items():
        setattr(address, key, value)
    db.commit()
    db.refresh(address)
    return _address_to_dict(address)


def delete_address(user_id: str, address_id: str, db: Session) -> None:
    address = db.query(Address).filter(Address.id == address_id, Address.user_id == user_id).first()
    if not address:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found")
    db.delete(address)
    db.commit()


def _address_to_dict(address: Address) -> dict:
    return {
        "id": str(address.id),
        "user_id": str(address.user_id),
        "full_name": address.full_name,
        "phone": address.phone,
        "street": address.street,
        "city": address.city,
        "state": address.state,
        "zip_code": address.zip_code,
        "country": address.country,
        "is_default": address.is_default,
        "created_at": address.created_at,
    }
