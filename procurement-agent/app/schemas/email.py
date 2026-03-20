"""Email webhook payload schemas."""

from pydantic import BaseModel, Field


class EmailMessage(BaseModel):
    message_id: str = Field(description="Unique message identifier")
    thread_id: str = Field(description="Thread ID for conversation tracking")
    inbox_id: str = Field(description="Inbox ID where the message was received")
    from_: str = Field(alias="from", description="Sender email address")
    to: list[str] = Field(default_factory=list, description="Recipient email addresses")
    subject: str = Field(default="", description="Email subject line")
    text: str | None = Field(default=None, description="Plain text content")
    html: str | None = Field(default=None, description="HTML content")

    class Config:
        populate_by_name = True


class EmailWebhookPayload(BaseModel):
    event_type: str = Field(default="message.received", description="Type of webhook event")
    event_id: str = Field(description="Unique event identifier")
    message: EmailMessage = Field(description="The email message data")
