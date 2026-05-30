import uuid
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.address import Address


def get_addresses(db: Session, user_id: str) -> list:
    return [a.to_dict() for a in db.query(Address).filter(Address.user_id == user_id).all()]


def create_address(
    db: Session,
    user_id: str,
    full_name: str,
    phone: str,
    street: str,
    city: str,
    state: str,
    pincode: str,
    is_default: bool = False,
    addr_type: str = "Home",
) -> dict:
    if is_default:
        db.query(Address).filter(Address.user_id == user_id, Address.is_default == True).update(
            {"is_default": False}
        )

    address = Address(
        id=str(uuid.uuid4()),
        user_id=user_id,
        full_name=full_name,
        phone=phone,
        street=street,
        city=city,
        state=state,
        pincode=pincode,
        is_default=is_default,
        type=addr_type,
    )
    db.add(address)
    db.commit()
    db.refresh(address)
    return address.to_dict()


def update_address(
    db: Session,
    user_id: str,
    address_id: str,
    updates: dict,
) -> dict:
    address = db.query(Address).filter(
        Address.id == address_id, Address.user_id == user_id
    ).first()
    if not address:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found")

    if updates.get("isDefault"):
        db.query(Address).filter(Address.user_id == user_id, Address.is_default == True).update(
            {"is_default": False}
        )

    for key, value in updates.items():
        if value is not None:
            setattr(address, key, value)

    db.commit()
    db.refresh(address)
    return address.to_dict()


def delete_address(db: Session, user_id: str, address_id: str) -> dict:
    address = db.query(Address).filter(
        Address.id == address_id, Address.user_id == user_id
    ).first()
    if not address:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found")

    db.delete(address)
    db.commit()
    return {"deleted": True}
