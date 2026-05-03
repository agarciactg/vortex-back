"""
ai_tools.py

Defines the tools in Gemini format (google.generativeai.types.FunctionDeclaration)
and the execute_tool() function that executes them using the existing services of the project.

Imports from the real project:
  - app.services.ticket_service  →  list_tickets, get_ticket_by_id, create_ticket,
                                    change_status, reassign_ticket, get_user_by_id
  - app.services.user_service    →  get_all_users, get_user_by_id
  - app.services.comment_service →  create_comment
  - app.schemas.ticket           →  TicketCreate, TicketOut
  - app.schemas.user             →  UserSummary
"""
from typing import Any

import google.generativeai as genai

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ticket import TicketStatus, TicketPriority
from app.models.user import User
from app.services import ticket_service, user_service
from app.services.comment_service import create_comment
from app.schemas.ticket import TicketCreate, TicketOut
from app.schemas.user import UserSummary


list_tickets_tool = genai.protos.FunctionDeclaration(
    name="list_tickets",
    description=(
        "List tickets in the system with optional filters. "
        "Use it when the user asks to see, show or search tickets. "
        "Example: 'show me my open high priority tickets'"
    ),
    parameters=genai.protos.Schema(
        type=genai.protos.Type.OBJECT,
        properties={
            "status": genai.protos.Schema(
                type=genai.protos.Type.STRING,
                enum=["open", "in_progress", "in_review", "closed"],
                description="Filter by ticket status",
            ),
            "priority": genai.protos.Schema(
                type=genai.protos.Type.STRING,
                enum=["low", "medium", "high", "critical"],
                description="Filter by priority",
            ),
            "assignee_id": genai.protos.Schema(
                type=genai.protos.Type.STRING,
                description="ID of the user assigned to the ticket",
            ),
            "search": genai.protos.Schema(
                type=genai.protos.Type.STRING,
                description="Search by ticket title",
            ),
            "limit": genai.protos.Schema(
                type=genai.protos.Type.INTEGER,
                description="Maximum number of tickets to return (default: 10)",
            ),
        },
    ),
)

get_ticket_tool = genai.protos.FunctionDeclaration(
    name="get_ticket",
    description="Get the complete details of a ticket by its ID.",
    parameters=genai.protos.Schema(
        type=genai.protos.Type.OBJECT,
        properties={
            "ticket_id": genai.protos.Schema(
                type=genai.protos.Type.STRING,
                description="ID of the ticket",
            ),
        },
        required=["ticket_id"],
    ),
)

create_ticket_tool = genai.protos.FunctionDeclaration(
    name="create_ticket",
    description=(
        "Create a new ticket from the user's description. "
        "Example: 'create a ticket to fix the login'"
    ),
    parameters=genai.protos.Schema(
        type=genai.protos.Type.OBJECT,
        properties={
            "title": genai.protos.Schema(
                type=genai.protos.Type.STRING,
                description="Title of the ticket",
            ),
            "description": genai.protos.Schema(
                type=genai.protos.Type.STRING,
                description="Detailed description of the ticket",
            ),
            "priority": genai.protos.Schema(
                type=genai.protos.Type.STRING,
                enum=["low", "medium", "high", "critical"],
                description="Priority of the ticket (default: medium)",
            ),
            "assignee_id": genai.protos.Schema(
                type=genai.protos.Type.STRING,
                description="ID of the user to assign (optional)",
            ),
        },
        required=["title"],
    ),
)

change_ticket_status_tool = genai.protos.FunctionDeclaration(
    name="change_ticket_status",
    description=(
        "Change the status of a ticket. "
        "Example: 'close ticket #42', 'mark ticket as in progress'"
    ),
    parameters=genai.protos.Schema(
        type=genai.protos.Type.OBJECT,
        properties={
            "ticket_id": genai.protos.Schema(
                type=genai.protos.Type.STRING,
                description="ID of the ticket",
            ),
            "status": genai.protos.Schema(
                type=genai.protos.Type.STRING,
                enum=["open", "in_progress", "in_review", "closed"],
                description="New status of the ticket",
            ),
        },
        required=["ticket_id", "status"],
    ),
)

assign_ticket_tool = genai.protos.FunctionDeclaration(
    name="assign_ticket",
    description=(
        "Reassign a ticket to another user in the system. "
        "If you don't have the user's ID, use list_users first to find it."
    ),
    parameters=genai.protos.Schema(
        type=genai.protos.Type.OBJECT,
        properties={
            "ticket_id": genai.protos.Schema(
                type=genai.protos.Type.STRING,
                description="ID of the ticket to reassign",
            ),
            "assignee_id": genai.protos.Schema(
                type=genai.protos.Type.STRING,
                description="ID of the user to assign the ticket to",
            ),
        },
        required=["ticket_id", "assignee_id"],
    ),
)

add_comment_tool = genai.protos.FunctionDeclaration(
    name="add_comment",
    description=(
        "Add a comment to a ticket. "
        "Example: 'comment on #17 that it is already deployed in staging'"
    ),
    parameters=genai.protos.Schema(
        type=genai.protos.Type.OBJECT,
        properties={
            "ticket_id": genai.protos.Schema(
                type=genai.protos.Type.STRING,
                description="ID of the ticket",
            ),
            "content": genai.protos.Schema(
                type=genai.protos.Type.STRING,
                description="Text of the comment to add",
            ),
        },
        required=["ticket_id", "content"],
    ),
)

list_users_tool = genai.protos.FunctionDeclaration(
    name="list_users",
    description=(
        "List users registered in the system. "
        "Use it to resolve a name to an ID before assigning a ticket."
    ),
    parameters=genai.protos.Schema(
        type=genai.protos.Type.OBJECT,
        properties={
            "search": genai.protos.Schema(
                type=genai.protos.Type.STRING,
                description="Search user by name or email",
            ),
        },
    ),
)

GEMINI_TOOLS = genai.protos.Tool(
    function_declarations=[
        list_tickets_tool,
        get_ticket_tool,
        create_ticket_tool,
        change_ticket_status_tool,
        assign_ticket_tool,
        add_comment_tool,
        list_users_tool,
    ]
)


async def execute_tool(
    name: str,
    arguments: dict[str, Any],
    db: AsyncSession,
    current_user: User,
) -> dict:
    """
    Executes the indicated tool and returns a dict with the result.
    Gemini expects a dict, not a string, in the function_response.
    The current_user guarantees that the same permissions as the API REST are respected.
    """
    try:
        if name == "list_tickets":
            status_val = arguments.get("status")
            priority_val = arguments.get("priority")
            tickets, total = await ticket_service.get_tickets(
                db=db,
                status=TicketStatus(status_val) if status_val else None,
                priority=TicketPriority(priority_val) if priority_val else None,
                assignee_id=arguments.get("assignee_id"),
                search=arguments.get("search"),
                limit=int(arguments.get("limit", 10)),
            )
            items = [TicketOut.model_validate(t).model_dump(mode="json") for t in tickets]
            return {"tickets": items, "total": total}

        elif name == "get_ticket":
            ticket = await ticket_service.get_ticket_by_id(db, arguments["ticket_id"])
            if not ticket:
                return {"error": f"Ticket '{arguments['ticket_id']}' no encontrado"}
            return TicketOut.model_validate(ticket).model_dump(mode="json")

        elif name == "create_ticket":
            data = TicketCreate(
                title=arguments["title"],
                description=arguments.get("description"),
                priority=arguments.get("priority", "medium"),
                assignee_id=arguments.get("assignee_id"),
            )
            ticket = await ticket_service.create_ticket(
                db=db, data=data, author_id=current_user.id
            )
            return {
                "success": True,
                "ticket": TicketOut.model_validate(ticket).model_dump(mode="json"),
            }

        elif name == "change_ticket_status":
            ticket = await ticket_service.get_ticket_by_id(db, arguments["ticket_id"])
            if not ticket:
                return {"error": "Ticket no encontrado"}
            ticket = await ticket_service.change_ticket_status(db, ticket, TicketStatus(arguments["status"]))
            return {
                "success": True,
                "ticket_id": ticket.id,
                "new_status": ticket.status.value,
            }

        elif name == "assign_ticket":
            ticket = await ticket_service.get_ticket_by_id(db, arguments["ticket_id"])
            if not ticket:
                return {"error": "Ticket no encontrado"}
            assignee = await user_service.get_user_by_id(db, arguments["assignee_id"])
            if not assignee:
                return {"error": "Usuario no encontrado"}
            ticket = await ticket_service.assign_ticket(db, ticket, arguments["assignee_id"])
            return {
                "success": True,
                "ticket_id": ticket.id,
                "assignee_name": assignee.name,
            }

        elif name == "add_comment":
            ticket = await ticket_service.get_ticket_by_id(db, arguments["ticket_id"])
            if not ticket:
                return {"error": "Ticket no encontrado"}
            comment = await create_comment(
                db=db,
                ticket_id=arguments["ticket_id"],
                content=arguments["content"],
                author_id=current_user.id,
            )
            return {"success": True, "comment_id": comment.id}

        elif name == "list_users":
            users, total = await user_service.get_all_users(
                db=db, search=arguments.get("search"), limit=50
            )
            items = [UserSummary.model_validate(u).model_dump(mode="json") for u in users]
            return {"users": items, "total": total}

        else:
            return {"error": f"Tool '{name}' no reconocido"}

    except Exception as exc:
        return {"error": str(exc)}
