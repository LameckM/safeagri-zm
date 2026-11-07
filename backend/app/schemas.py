from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field

class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    farm_name: str = Field(min_length=2, max_length=120)
    location: str | None = Field(default=None, max_length=160)
    setup_key: str | None = Field(default=None, max_length=256)

class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

class FieldUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=80)
    crop: str | None = Field(default=None, min_length=1, max_length=40)

class ReadingIn(BaseModel):
    """One sensor reading, exactly as the ESP32 will send it later."""
    node_id: str = Field(min_length=1, max_length=32)
    soil_moisture: float = Field(allow_inf_nan=False)
    temperature: float = Field(allow_inf_nan=False)
    humidity: float = Field(allow_inf_nan=False)
    timestamp: datetime | None = None

class ReadingOut(BaseModel):
    id: int
    field_id: int
    valid: bool
    flag: str | None = None


class DemoFaultIn(BaseModel):
    field_id: int
    metric: Literal["humidity", "temperature", "soil_moisture"]
    scenario: Literal["low", "high", "flatline"] = "high"

class DemoFaultClearIn(BaseModel):
    field_id: int
