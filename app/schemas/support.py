from pydantic import BaseModel
from enum import Enum


class IssueType(str, Enum):
    technical = "technical"
    course    = "course"
    account   = "account"
    general   = "general"


class ContactRequest(BaseModel):
    issue_type: IssueType
    subject:    str
    message:    str
