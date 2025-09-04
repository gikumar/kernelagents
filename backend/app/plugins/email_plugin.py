from .base_plugin import BasePlugin
#from semantic_kernel.plugin import kernel_function
from semantic_kernel.functions import kernel_function
import logging

logger = logging.getLogger(__name__)

class EmailPlugin(BasePlugin):
    def __init__(self, kernel):
        super().__init__(kernel, "EmailPlugin")
    
    async def initialize(self):
        logger.info("Initializing EmailPlugin")
    
    @kernel_function(
        name="send_email",
        description="Send an email (simulated)"
    )
    async def send_email(self, to: str, subject: str, body: str) -> str:
        """Send an email (simulated)"""
        logger.info(f"💥 Sending email to: {to}, subject: {subject}")
        print(f"\nTo: {to}")
        print(f"Subject: {subject}")
        print(f"Body: {body}\n")
        return f"Email sent successfully to {to} with subject '{subject}'"
    