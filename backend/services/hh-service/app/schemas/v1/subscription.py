from pydantic import BaseModel, Field
from typing import Literal


class PostSubscriptionResponse(BaseModel):
    status: Literal["subscribed", "unsubscribed"] = Field(..., examples=["subscribed", "unsubscribed"])


class GetSubscriptionStatusResponse(BaseModel):
    has_subscription: bool