import os
import uuid
import aiofiles

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.attachment import Attachment


MAX_FILE_SIZE_BYTES = settings.MAX_FILE_SIZE_MB * 1024 * 1024


def _base_query():
    """Base query with eager-loaded uploader."""
    return select(Attachment).options(selectinload(Attachment.uploader))


async def get_attachments_by_ticket(
    db: AsyncSession,
    ticket_id: str,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[Attachment], int]:
    query = (
        _base_query()
        .where(Attachment.ticket_id == ticket_id)
        .order_by(Attachment.created_at.asc())
    )
    count_query = (
        select(func.count())
        .select_from(Attachment)
        .where(Attachment.ticket_id == ticket_id)
    )

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(query.offset(skip).limit(limit))
    return list(result.scalars().all()), total


async def get_attachment_by_id(db: AsyncSession, attachment_id: str) -> Attachment | None:
    result = await db.execute(_base_query().where(Attachment.id == attachment_id))
    return result.scalar_one_or_none()


async def save_upload(
    db: AsyncSession,
    file: UploadFile,
    ticket_id: str,
    uploaded_by: str,
) -> Attachment:
    """Writes the file to disk and creates the DB record."""
    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"File exceeds the maximum allowed size of {settings.MAX_FILE_SIZE_MB} MB.")

    ext = os.path.splitext(file.filename or "file")[1]
    unique_name = f"{uuid.uuid4().hex}{ext}"
    dest_path = os.path.join(settings.UPLOAD_DIR, unique_name)

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    async with aiofiles.open(dest_path, "wb") as f:
        await f.write(content)

    attachment = Attachment(
        filename=unique_name,
        original_filename=file.filename or unique_name,
        file_size=len(content),
        content_type=file.content_type or "application/octet-stream",
        ticket_id=ticket_id,
        uploaded_by=uploaded_by,
    )
    db.add(attachment)
    await db.flush()
    await db.refresh(attachment)
    return await get_attachment_by_id(db, attachment.id)


async def delete_attachment(db: AsyncSession, attachment: Attachment) -> None:
    """Deletes the DB record and the file from disk."""
    file_path = os.path.join(settings.UPLOAD_DIR, attachment.filename)
    await db.delete(attachment)
    await db.flush()

    try:
        os.remove(file_path)
    except FileNotFoundError:
        pass
