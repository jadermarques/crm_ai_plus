from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from src.core.config import get_settings

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)
settings = get_settings()

CHATWOOT_RESPONSE_MESSAGE = "Recebi sua mensagem!"


async def send_message_to_chatwoot(
    *,
    account_id: int,
    conversation_id: int,
    message: str,
) -> tuple[bool, str]:
    base_url = settings.CHATWOOT_BASE_URL.rstrip("/")
    token = settings.chatwoot_token
    if not token:
        return False, "CHATWOOT_API_ACCESS_TOKEN ausente"

    url = (
        f"{base_url}/api/v1/accounts/"
        f"{account_id}/conversations/{conversation_id}/messages"
    )

    headers = {
        "api_access_token": token,
        "Content-Type": "application/json",
    }
    payload = {
        "content": message,
        "message_type": "outgoing",
        "private": False,
        "content_type": "text",
        "content_attributes": {},
    }

    timeout = httpx.Timeout(connect=5.0, read=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            body_preview = response.text[:200]
            if response.is_success:
                logger.info(
                    "Chatwoot reply sent: status=%s conversation_id=%s body=%s",
                    response.status_code,
                    conversation_id,
                    body_preview,
                )
                return True, body_preview
            logger.warning(
                "Chatwoot reply failed: status=%s conversation_id=%s body=%s",
                response.status_code,
                conversation_id,
                body_preview,
            )
            return False, body_preview
        except httpx.HTTPError as exc:
            logger.exception(
                "HTTP error sending Chatwoot reply conversation_id=%s", conversation_id
            )
            return False, str(exc)


@router.post("/chatwoot", status_code=status.HTTP_200_OK)
async def chatwoot_webhook(request: Request) -> JSONResponse:
    try:
        payload: dict[str, Any] = await request.json()
    except Exception:
        logger.exception("Payload inválido (JSON) recebido de Chatwoot")
        return JSONResponse(
            {"status": "ignored", "reason": "invalid_json"},
            status_code=status.HTTP_200_OK,
        )

    event_type = payload.get("event")
    if event_type != "message_created":
        logger.info("Ignorado evento não suportado: %s", event_type)
        return JSONResponse(
            {"status": "ignored", "reason": "event_type"}, status_code=status.HTTP_200_OK
        )

    sender = payload.get("sender") or {}
    sender_type = sender.get("type")
    message_type = payload.get("message_type")
    is_private = bool(payload.get("private"))
    if sender_type != "contact" or message_type != "incoming" or is_private:
        logger.info(
            "Ignorado por prevenção de loop: sender_type=%s message_type=%s private=%s",
            sender_type,
            message_type,
            is_private,
        )
        return JSONResponse(
            {"status": "ignored", "reason": "sender_direction_or_private"},
            status_code=status.HTTP_200_OK,
        )

    conversation = payload.get("conversation") or {}
    account = payload.get("account") or {}
    conversation_id = conversation.get("id") or payload.get("conversation_id")
    account_id = account.get("id") or settings.CHATWOOT_ACCOUNT_ID
    user_content = payload.get("content") or ""

    if not conversation_id:
        logger.error("Webhook sem conversation_id; payload incompleto")
        return JSONResponse(
            {"status": "error", "reason": "missing_conversation_id"},
            status_code=status.HTTP_200_OK,
        )

    if not account_id:
        logger.error("Webhook sem account_id e sem fallback em configuração")
        return JSONResponse(
            {"status": "error", "reason": "missing_account_id"},
            status_code=status.HTTP_200_OK,
        )

    logger.info(
        "Mensagem recebida do cliente: conversation_id=%s account_id=%s content=%s",
        conversation_id,
        account_id,
        user_content,
    )

    success, detail = await send_message_to_chatwoot(
        account_id=account_id,
        conversation_id=conversation_id,
        message=CHATWOOT_RESPONSE_MESSAGE,
    )

    if not success:
        logger.error(
            "Falha ao responder conversa %s: %s", conversation_id, detail
        )
        return JSONResponse(
            {"status": "error", "reason": "send_failed", "detail": detail},
            status_code=status.HTTP_200_OK,
        )

    return JSONResponse(
        {"status": "ok", "conversation_id": conversation_id},
        status_code=status.HTTP_200_OK,
    )
