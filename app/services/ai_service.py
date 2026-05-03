"""
ai_service.py — Gemini AI implementation

Uses google-generativeai with function calling to manage tickets
in natural language.

Tool calling loop flow:

1. The conversation history is built from PostgreSQL.
2. Gemini is called with the available tools.
3. If Gemini returns `function_call`, the tool is executed (`execute_tool`).
4. The result is forwarded to Gemini as a `function_response`.
5. This process is repeated until Gemini returns plain text (without a `function_call`).
6. All messages are persisted in `ai_messages`.
"""
import json

import google.generativeai as genai
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.config import settings
from app.models.ai_conversation import AIConversation, AIMessage, MessageRole
from app.models.user import User
from app.schemas.ai import ToolCallOut
from app.services.ai_tools import GEMINI_TOOLS, execute_tool

genai.configure(api_key=settings.GEMINI_API_KEY)

SYSTEM_PROMPT = """You are a ticketing assistant for the Orbidi system.

Your job is to help users manage their tickets using natural language.

You can:
- View tickets by applying filters for status, priority, or assigned status
- Change the status of a ticket
- ​​Create new tickets from a description
- Add comments to tickets
- Reassign tickets to other users

When you perform an action, always clearly confirm what you did.

If you need a user's ID to assign it, use `list_users` first.
Always respond in the same language as the user."""


async def get_or_create_conversation(
    db: AsyncSession,
    user_id: str,
    conversation_id: str | None,
) -> AIConversation:
    if conversation_id:
        result = await db.execute(
            select(AIConversation).where(
                AIConversation.id == conversation_id,
                AIConversation.user_id == user_id,
            )
        )
        conv = result.scalar_one_or_none()
        if conv:
            return conv

    conv = AIConversation(user_id=user_id)
    db.add(conv)
    await db.flush()
    return conv


async def _load_history(db: AsyncSession, conversation_id: str) -> list[dict]:
    """
    Reconstruct the history in the format Gemini expects:
    [
      {"role": "user",  "parts": [{"text": "..."}]},
      {"role": "model", "parts": [{"text": "..."}]},
      {"role": "user",  "parts": [{"function_response": {...}}]},
      ...
    ]
    """
    result = await db.execute(
        select(AIMessage)
        .where(AIMessage.conversation_id == conversation_id)
        .order_by(AIMessage.created_at)
    )
    messages = result.scalars().all()

    history = []
    for m in messages:
        if m.role == MessageRole.USER:
            history.append({"role": "user", "parts": [{"text": m.content}]})

        elif m.role == MessageRole.ASSISTANT:
            parts = []
            if m.content:
                parts.append({"text": m.content})
            if m.tool_calls:
                for fc in json.loads(m.tool_calls):
                    parts.append({"function_call": fc})
            if parts:
                history.append({"role": "model", "parts": parts})

        elif m.role == MessageRole.TOOL:
            history.append({
                "role": "user",
                "parts": [{
                    "function_response": {
                        "name":     m.tool_name,
                        "response": json.loads(m.content) if m.content else {},
                    }
                }],
            })

    return history


async def _save_message(
    db: AsyncSession,
    conversation_id: str,
    role: MessageRole,
    content: str | None = None,
    tool_calls_raw: str | None = None,
    tool_call_id: str | None = None,
    tool_name: str | None = None,
) -> None:
    msg = AIMessage(
        conversation_id=conversation_id,
        role=role,
        content=content,
        tool_calls=tool_calls_raw,
        tool_call_id=tool_call_id,
        tool_name=tool_name,
    )
    db.add(msg)
    await db.flush()


async def chat(
    db: AsyncSession,
    current_user: User,
    message: str,
    conversation_id: str | None,
) -> tuple[str, str, list[ToolCallOut]]:
    """
    Returns (reply_text, conversation_id, actions_executed).
    """
    conv = await get_or_create_conversation(db, current_user.id, conversation_id)
    history = await _load_history(db, conv.id)

    await _save_message(db, conv.id, MessageRole.USER, content=message)

    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=SYSTEM_PROMPT,
        tools=[GEMINI_TOOLS],
    )

    gemini_chat = model.start_chat(history=history)

    actions: list[ToolCallOut] = []
    current_message = message

    while True:
        response = await gemini_chat.send_message_async(current_message)
        candidate = response.candidates[0]
        parts = candidate.content.parts

        function_calls = [p for p in parts if hasattr(p, "function_call") and p.function_call.name]

        if not function_calls:
            reply = "".join(p.text for p in parts if hasattr(p, "text") and p.text)
            await _save_message(db, conv.id, MessageRole.ASSISTANT, content=reply)
            return reply, conv.id, actions

        text_content = next(
            (p.text for p in parts if hasattr(p, "text") and p.text), None
        )
        tool_calls_raw = json.dumps([
            {
                "name": fc.function_call.name,
                "args": dict(fc.function_call.args),
            }
            for fc in function_calls
        ])
        await _save_message(
            db, conv.id, MessageRole.ASSISTANT,
            content=text_content,
            tool_calls_raw=tool_calls_raw,
        )

        function_responses = []
        for part in function_calls:
            fc = part.function_call
            name = fc.name
            args = dict(fc.args)

            result = await execute_tool(name, args, db, current_user)

            actions.append(ToolCallOut(
                tool_name=name,
                input=args,
                result=json.dumps(result),
            ))

            await _save_message(
                db, conv.id, MessageRole.TOOL,
                content=json.dumps(result),
                tool_name=name,
            )

            function_responses.append(
                genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=name,
                        response=result,
                    )
                )
            )

        current_message = function_responses


async def get_history(
    db: AsyncSession,
    user_id: str,
    conversation_id: str,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[AIMessage], int]:
    base = (
        select(AIMessage)
        .join(AIConversation)
        .where(
            AIConversation.id == conversation_id,
            AIConversation.user_id == user_id,
        )
        .order_by(AIMessage.created_at)
    )
    count_q = (
        select(func.count())
        .select_from(AIMessage)
        .join(AIConversation)
        .where(
            AIConversation.id == conversation_id,
            AIConversation.user_id == user_id,
        )
    )
    total = (await db.execute(count_q)).scalar_one()
    items = list((await db.execute(base.offset(skip).limit(limit))).scalars().all())
    return items, total
