"""
Dreamina Auto Register - Models Module
"""
from app.models.account import Account
from app.models.task_record import TaskRecord
from app.models.email_domain import EmailDomain
from app.models.proxy_node import ProxyNode
from app.models.outlook_mailbox import OutlookMailbox
from app.models.content_generation_job import ContentGenerationJob
from app.models.insmind_account import InsMindAccount
from app.models.photogpt_account import PhotoGPTAccount
from app.models.photogpt_job import PhotoGPTJob

__all__ = [
    "Account",
    "TaskRecord",
    "EmailDomain",
    "ProxyNode",
    "OutlookMailbox",
    "ContentGenerationJob",
    "InsMindAccount",
    "PhotoGPTAccount",
]
