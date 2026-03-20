"""Pydantic schemas for request/response models."""

from .email import EmailMessage, EmailWebhookPayload

__all__ = ["EmailMessage", "EmailWebhookPayload"]
