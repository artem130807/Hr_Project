from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from app.loader import client, redis_client
from app.api.endpoints import Endpoints
from app.app_logging import logger


class IsUser(BaseFilter):
    def __init__(self, 
                 is_candidate: bool | None = None,
                 is_admin: bool | None = None,
                 is_hr: bool | None = None,
                 is_art: bool | None = None,
                 is_lead: bool | None = None,
                 is_owner: bool | None = None,
                 is_employee: bool | None = None,
                 new_user: bool | None = None):
        self.is_candidate = bool(is_candidate) 
        self.is_admin = bool(is_admin)
        self.is_hr = bool(is_hr)
        self.is_art = bool(is_art)
        self.is_lead = bool(is_lead)
        self.is_owner = bool(is_owner) 
        self.is_employee = bool(is_employee)
        
        self.new_user = new_user

        self.role_filter = any([self.is_employee, self.is_admin, self.is_art, self.is_candidate, self.is_hr, self.is_lead, self.is_owner])

        self.allowed_groups = {'candidate': self.is_candidate,
                               'hr': self.is_hr or self.is_admin,
                               'art': self.is_art or self.is_admin,
                               'lead': self.is_lead or self.is_admin,
                               'owner': self.is_owner or self.is_admin,
                               'employee': self.is_employee}
        

    async def __call__(self, update: Message | CallbackQuery) -> bool:
        id = str(update.from_user.id)
        user = {}
        role = await redis_client.get(id)
        if role:
            user['role'] = role
        else:
            user = await client.get(Endpoints.get_user_by_telegram_id, telegram_id=id)
            if user:
                await redis_client.set(id, user['role'], expires=300)
                role = user['role']
            else:
                if self.new_user:
                    return True
        if user:
            if self.role_filter:
                if not self.allowed_groups[role]:
                    logger.info(f'role filter not passed:\ncurrent role {role}\nrole allowed {self.allowed_groups[role]}')
                    return False
            return True
        return False
