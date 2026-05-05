from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.postgres import get_db
from app.collector.keenetic_client import KeeneticClient
from app.config import get_settings
from app.models import (
    ClientRead,
    ClientMetric,
    ClientMetricRead,
    CurrentClient,
    Router,
    RouterCreate,
    RouterRead,
    RouterStatus,
    RouterUpdate,
    StatusRead,
    decrypt_secret,
    encrypt_secret,
)

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/routers", response_model=list[RouterRead])
def list_routers(db: Session = Depends(get_db)) -> list[Router]:
    return list(db.scalars(select(Router).order_by(Router.created_at.desc())))


@router.post("/routers", response_model=RouterRead, status_code=status.HTTP_201_CREATED)
def create_router(payload: RouterCreate, db: Session = Depends(get_db)) -> Router:
    item = Router(
        name=payload.name,
        site=payload.site,
        host=payload.host,
        port=payload.port,
        username=payload.username,
        password_encrypted=encrypt_secret(payload.password),
        access_method=payload.access_method.value,
        enabled=payload.enabled,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/routers/{router_id}", response_model=RouterRead)
def update_router(router_id: str, payload: RouterUpdate, db: Session = Depends(get_db)) -> Router:
    item = db.get(Router, router_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Router not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "password":
            item.password_encrypted = encrypt_secret(value)
        elif field == "access_method" and value is not None:
            item.access_method = value.value
        else:
            setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/routers/{router_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_router(router_id: str, db: Session = Depends(get_db)) -> None:
    item = db.get(Router, router_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Router not found")
    db.execute(delete(CurrentClient).where(CurrentClient.router_id == router_id))
    status_row = db.get(RouterStatus, router_id)
    if status_row is not None:
        db.delete(status_row)
    db.delete(item)
    db.commit()


@router.get("/routers/{router_id}/clients", response_model=list[ClientRead])
def router_clients(router_id: str, db: Session = Depends(get_db)) -> list[CurrentClient]:
    return list(db.scalars(select(CurrentClient).where(CurrentClient.router_id == router_id).order_by(CurrentClient.hostname)))


@router.get("/routers/{router_id}/client-metrics", response_model=list[ClientMetricRead])
def router_client_metrics(
    router_id: str,
    limit: int = Query(default=300, ge=1, le=2000),
    db: Session = Depends(get_db),
) -> list[ClientMetric]:
    rows = list(
        db.scalars(
            select(ClientMetric)
            .where(ClientMetric.router_id == router_id)
            .order_by(ClientMetric.time.desc())
            .limit(limit)
        )
    )
    return list(reversed(rows))


@router.get("/routers/{router_id}/status", response_model=StatusRead)
def router_status(router_id: str, db: Session = Depends(get_db)) -> RouterStatus:
    item = db.get(RouterStatus, router_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Router status not found")
    return item


@router.post("/routers/{router_id}/test")
def test_router(router_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    item = db.get(Router, router_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Router not found")
    password = decrypt_secret(item.password_encrypted)
    if password is None:
        raise HTTPException(status_code=400, detail="Router password is not configured")
    try:
        with KeeneticClient(
            item.host,
            item.port,
            item.username,
            password,
            raw_response_dir=get_settings().raw_response_dir,
            router_id=item.id,
        ) as client:
            client.login()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Router RCI test failed: {exc}") from exc
    return {"status": "ok"}
