from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


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


class WaterUsageIn(BaseModel):
    """A simulated/real flow-meter volume for one sensor node interval."""
    node_id: str = Field(min_length=1, max_length=32)
    liters: float = Field(ge=0, le=100000, allow_inf_nan=False)
    timestamp: datetime | None = None
    source: str = Field(default="simulated", pattern="^(simulated|meter)$")
