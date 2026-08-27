from datetime import datetime
from pydantic import BaseModel, Field

class LoginRequest(BaseModel): email: str; password: str
class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=12, max_length=128)
class DeviceCodeRequest(BaseModel): label: str = Field(default="Child browser", max_length=100)
class DeviceLinkRequest(BaseModel): code: str; label: str = Field(default="Child browser", max_length=100)
class AnalyzeRequest(BaseModel):
    device_id: str
    source: str = Field(pattern="^(search|web_message)$")
    text: str = Field(min_length=1, max_length=1000)
class AcknowledgeRequest(BaseModel): acknowledged: bool = True
class AlertOut(BaseModel):
    id: str; source: str; category: str; severity: str; score: int; confidence: float
    trigger_text: str; context: list[str]; rationale: str; acknowledged: bool; created_at: datetime
