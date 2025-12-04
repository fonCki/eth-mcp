#!/usr/bin/env python3
"""
Custom MCP Server for ETH VVZ Course Catalog.

Wraps mcp-server-sqlite functionality and adds LLM-specific resources
with schema documentation and data format instructions.
"""

import json
import sqlite3
from pathlib import Path
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, TextContent, Tool

DB_PATH = Path("/data/vvz.db")

# LLM Instructions Resource
LLM_INSTRUCTIONS = """# ETH VVZ Database - LLM Instructions

## Data Format Reference

### Weekday Encoding (0-indexed, Monday = 0)
| Value | Day |
|-------|-----|
| 0 | Monday |
| 1 | Tuesday |
| 2 | Wednesday |
| 3 | Thursday |
| 4 | Friday |
| 5 | Saturday |

### Timeslot JSON Structure
The `timeslots` field in the `course` table contains a JSON array:
```json
{
  "weekday": 3,           // Thursday (0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri)
  "start_time": "14:15",  // 24-hour format
  "end_time": "16:00",
  "building": "HG",       // Building code
  "floor": "E",           // Floor
  "room": "7",            // Room number
  "biweekly": false,      // Every week or every 2 weeks
  "first_half_semester": false,
  "second_half_semester": false
}
```

### Course Type Codes
| Code | Meaning |
|------|---------|
| V | Vorlesung (Lecture) |
| U | Übung (Exercise session) |
| P | Praktikum (Lab/Practical) |
| G | Guided self-study |
| K | Kolloquium (Colloquium) |
| S | Seminar |

### Semester Format
`YYYYS` or `YYYYW` (e.g., "2026S" = Spring 2026, "2025W" = Winter 2025)

## Important Guidelines

1. **Show complete data**: When users ask for course information, display ALL fields without summarizing. Include full `objective`, `content`, and `abstract` fields.

2. **Decode weekdays**: Always convert weekday numbers to day names (0=Monday, etc.)

3. **Format schedules clearly**: Present timeslots in a readable table format with day names.

4. **Join tables for complete info**:
   - Courses → Lecturers: `learningunit` JOIN `unitlecturerlink` JOIN `lecturer`
   - Courses → Schedule: `learningunit` JOIN `course` (via unit_id)

## Database Schema

### Main Tables
- `learningunit` - Core course data (title, credits, department, abstract, content, objective)
- `course` - Course schedule and timing information
- `lecturer` - Instructor information (surname, name)
- `section` - Hierarchical department/program structure
- `unitlecturerlink` - Links courses to lecturers
- `unitsectionlink` - Links courses to sections

### Key Fields in `learningunit`
- `id`, `number` - Course identifiers (e.g., "252-0211-00L")
- `title`, `title_english` - Course names
- `credits` - ECTS credits
- `department` - Department code
- `objective` - Learning objectives (what students will master)
- `content` - Full course content and topics
- `abstract` - Short course description
- `exam_type`, `exam_mode` - Examination details
- `language` - Language of instruction
- `levels` - JSON array of levels (e.g., ["BSC", "MSC"])
- `competencies` - JSON object with assessed competencies

### Key Fields in `course`
- `unit_id` - Links to `learningunit.id`
- `type` - Course type code (V, U, P, etc.)
- `hours` - Weekly hours
- `timeslots` - JSON array with schedule details

### Key Fields in `lecturer`
- `id` - Lecturer ID
- `surname` - Last name
- `name` - First name

## Example Queries

### Get course with lecturers
```sql
SELECT l.*, lec.surname, lec.name
FROM learningunit l
JOIN unitlecturerlink ull ON l.id = ull.unit_id
JOIN lecturer lec ON ull.lecturer_id = lec.id
WHERE l.number = '252-0211-00L'
```

### Get course schedule
```sql
SELECT c.* FROM course c
JOIN learningunit l ON c.unit_id = l.id
WHERE l.number = '252-0211-00L'
```

### Find courses by lecturer surname
```sql
SELECT l.number, l.title, l.credits
FROM learningunit l
JOIN unitlecturerlink ull ON l.id = ull.unit_id
JOIN lecturer lec ON ull.lecturer_id = lec.id
WHERE lec.surname = 'Basin'
```
"""

server = Server("eth-vvz")


def get_db_connection():
    """Get database connection."""
    return sqlite3.connect(str(DB_PATH))


@server.list_resources()
async def list_resources():
    """List available resources."""
    return [
        Resource(
            uri="eth-vvz://instructions",
            name="LLM Instructions",
            description="Data format reference and query guidelines for the ETH VVZ database",
            mimeType="text/markdown"
        )
    ]


@server.read_resource()
async def read_resource(uri: str):
    """Read a resource by URI."""
    if str(uri) == "eth-vvz://instructions":
        return LLM_INSTRUCTIONS
    raise ValueError(f"Unknown resource: {uri}")


@server.list_tools()
async def list_tools():
    """List available tools."""
    return [
        Tool(
            name="read_query",
            description="Execute a SELECT query on the ETH VVZ SQLite database. Use this to search courses, lecturers, and schedules.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SELECT SQL query to execute"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="list_tables",
            description="List all tables in the ETH VVZ database",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="describe_table",
            description="Get the schema information for a specific table",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Name of the table to describe"
                    }
                },
                "required": ["table_name"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Execute a tool call."""

    if name == "read_query":
        query = arguments.get("query", "")
        if not query.strip().upper().startswith("SELECT"):
            return [TextContent(type="text", text="Error: Only SELECT queries are allowed")]

        try:
            conn = get_db_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            conn.close()

            result = [dict(row) for row in rows]
            return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    elif name == "list_tables":
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            return [TextContent(type="text", text=json.dumps(tables, indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    elif name == "describe_table":
        table_name = arguments.get("table_name", "")
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            conn.close()

            result = [
                {"cid": c[0], "name": c[1], "type": c[2], "notnull": c[3], "default": c[4], "pk": c[5]}
                for c in columns
            ]
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
