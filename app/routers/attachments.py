import os

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.attachment import AttachmentOut, AttachmentListOut
from app.services import attachment_service, ticket_service

router = APIRouter()


@router.get(
    "/{ticket_id}/attachments",
    response_model=AttachmentListOut,
    summary="List attachments",
    description="Returns all attachments of a ticket.",
)
async def list_attachments(
    ticket_id: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    ticket = await ticket_service.get_ticket_by_id(db=db, ticket_id=ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")

    attachments, total = await attachment_service.get_attachments_by_ticket(
        db=db, ticket_id=ticket_id, skip=skip, limit=limit
    )
    return AttachmentListOut(
        items=[AttachmentOut.model_validate(a) for a in attachments],
        total=total,
    )


@router.post(
    "/{ticket_id}/attachments",
    response_model=AttachmentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload attachment",
    description=(
        f"Uploads a file and attaches it to a ticket. "
        f"Max size: {settings.MAX_FILE_SIZE_MB} MB. "
        f"Accepts multipart/form-data."
    ),
)
async def upload_attachment(
    ticket_id: str,
    file: UploadFile = File(..., description="File to upload"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = await ticket_service.get_ticket_by_id(db=db, ticket_id=ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")

    try:
        attachment = await attachment_service.save_upload(
            db=db,
            file=file,
            ticket_id=ticket_id,
            uploaded_by=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(e))

    await db.commit()
    return AttachmentOut.model_validate(attachment)


@router.get(
    "/{ticket_id}/attachments/{att_id}/download",
    summary="Download attachment",
    description="Returns the file with Content-Disposition: attachment so the browser downloads it.",
)
async def download_attachment(
    ticket_id: str,
    att_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    ticket = await ticket_service.get_ticket_by_id(db=db, ticket_id=ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")

    attachment = await attachment_service.get_attachment_by_id(db=db, attachment_id=att_id)
    if not attachment or attachment.ticket_id != ticket_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found.")

    file_path = os.path.join(settings.UPLOAD_DIR, attachment.filename)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk.")

    return FileResponse(
        path=file_path,
        media_type=attachment.content_type,
        filename=attachment.original_filename,
        headers={"Content-Disposition": f'attachment; filename="{attachment.original_filename}"'},
    )


@router.delete(
    "/{ticket_id}/attachments/{att_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete attachment",
    description="Deletes an attachment. Only the uploader or the ticket author can delete it.",
)
async def delete_attachment(
    ticket_id: str,
    att_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = await ticket_service.get_ticket_by_id(db=db, ticket_id=ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")

    attachment = await attachment_service.get_attachment_by_id(db=db, attachment_id=att_id)
    if not attachment or attachment.ticket_id != ticket_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found.")

    is_uploader = attachment.uploaded_by == current_user.id
    is_ticket_author = ticket.author_id == current_user.id
    if not (is_uploader or is_ticket_author):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the uploader or the ticket author can delete this attachment.",
        )

    await attachment_service.delete_attachment(db=db, attachment=attachment)
    await db.commit()
