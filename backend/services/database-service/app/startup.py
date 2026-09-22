from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.v1.models import ServiceClient
from app.utils.utils import get_hash
from app.config import SERVICE_CLIENTS
from app.app_logging import logger


async def ensure_superuser_and_services(db: AsyncSession):
    """Panel users live in ERP; only seed service-to-service clients here."""
    for client in SERVICE_CLIENTS:
        query = select(ServiceClient).where(ServiceClient.client_id == client["id"])
        result = await db.execute(query)
        service = result.scalar_one_or_none()

        if not service:
            new_service = ServiceClient(
                client_id=client["id"],
                client_secret_hash=get_hash(client["secret"]),
                name=client["id"],
                description="",
            )
            db.add(new_service)
            await db.commit()
            logger.info(f"[INIT] Service client '{client['id']}' created")
