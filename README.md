# ETH VVZ MCP Server

[![Docker](https://img.shields.io/badge/docker-ready-blue)](https://hub.docker.com/r/alfonsoridao/eth-mcp)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Unofficial MCP (Model Context Protocol) server for ETH Zurich course catalog.**

A community-built tool to query 2500+ courses from ETH Zurich using natural language with your AI assistant.

> **Note**: This is an unofficial project and is not affiliated with or endorsed by ETH Zurich. Course data is scraped from the publicly available [ETH VVZ](https://www.vvz.ethz.ch/) website.

## Features

- **Pre-loaded Database**: Ships with complete Spring 2026 course data - no waiting!
- **Auto-Update**: Automatically detects and scrapes new semesters
- **Full Course Data**: Abstracts, schedules, lecturers, credits, competencies
- **MCP Compatible**: Works with Claude Desktop, Claude Code, and any MCP client
- **Persistent Storage**: Uses Docker volumes for data persistence

## Quick Start

### Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "eth-courses": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-v", "eth-mcp-data:/data",
        "alfonsoridao/eth-mcp:latest"
      ]
    }
  }
}
```

### Claude Code

```bash
claude mcp add eth-courses -- docker run --rm -i -v eth-mcp-data:/data alfonsoridao/eth-mcp:latest
```

### Manual Testing

```bash
# Pull and run (first time uses embedded database)
docker run --rm -it -v eth-mcp-data:/data alfonsoridao/eth-mcp:latest
```

## Available MCP Tools

Once connected, your AI has access to:

| Tool | Description |
|------|-------------|
| `read_query` | Execute SELECT queries on the course database |
| `list_tables` | Show all available tables |
| `describe_table` | Show table schema and columns |

## Example Queries

Ask your AI:

- *"Show me all Computer Science courses for Spring 2026"*
- *"Find courses with less than 4 credits on Tuesdays"*
- *"What are the prerequisites for Machine Learning?"*
- *"List all courses taught by Professor X"*
- *"Find courses that don't overlap with my current schedule"*

## Database Schema

### Main Tables

| Table | Description |
|-------|-------------|
| `learningunit` | Core course data (title, credits, department, abstract, content) |
| `course` | Course schedule and timing information |
| `lecturer` | Instructor information |
| `section` | Hierarchical department/program structure |
| `unitlecturerlink` | Links courses to lecturers |
| `unitsectionlink` | Links courses to sections |

### Key Fields in `learningunit`

- `id`, `number` - Course identifiers (e.g., "252-0211-00L")
- `title`, `title_english` - Course names
- `credits` - ECTS credits
- `department` - Department code
- `objective`, `content`, `abstract` - Course descriptions
- `exam_type`, `exam_mode` - Examination details
- `language` - Language of instruction

### Key Fields in `course` (Schedule)

- `unit_id` - Links to `learningunit.id`
- `type` - "V" (Lecture), "U" (Exercise), "P" (Lab)
- `timeslots` - JSON array with schedule details

### Key Fields in `lecturer`

- `surname`, `name` - Lecturer names

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ETH_SEMESTER` | Auto | Force specific semester (e.g., "2026S") |
| `FORCE_REFRESH` | 0 | Set to "1" to force re-scrape |
| `SCRAPE_UPCOMING` | 1 | Also scrape upcoming semester |

## Examples

### Force refresh for a specific semester

```bash
docker run --rm -i -v eth-mcp-data:/data \
  -e ETH_SEMESTER=2026S \
  -e FORCE_REFRESH=1 \
  alfonsoridao/eth-mcp:latest
```

### Query the database directly (debugging)

```bash
docker run --rm -it -v eth-mcp-data:/data --entrypoint sqlite3 \
  alfonsoridao/eth-mcp:latest /data/vvz.db \
  "SELECT title, credits FROM learningunit LIMIT 10"
```

## How It Works

1. **First Run**: Uses embedded database (no scraping needed!)
2. **Subsequent Runs**: Checks if new semester data is available
3. **Auto-Update**: Scrapes only when semester changes (Feb/Aug typically)
4. **MCP Server**: Starts on stdio for AI communication

## Data Source

Course data is scraped from the official [ETH Zurich VVZ](https://www.vvz.ethz.ch/) using the excellent [vvzapi](https://github.com/markbeep/vvzapi) project.

## Performance

- **First run**: Instant (uses embedded database)
- **Semester refresh**: 30-60 minutes (rate-limited to be polite)
- **Query response**: <100ms

## Troubleshooting

### Container exits immediately
The MCP server runs on stdio. For testing, use `-it` flag or connect via MCP client.

### Data seems outdated
```bash
docker run --rm -i -v eth-mcp-data:/data -e FORCE_REFRESH=1 alfonsoridao/eth-mcp:latest
```

### Check database contents
```bash
docker run --rm -v eth-mcp-data:/data alpine cat /data/.metadata.json
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Credits

- [vvzapi](https://github.com/markbeep/vvzapi) - ETH VVZ scraper
- [mcp-server-sqlite](https://pypi.org/project/mcp-server-sqlite/) - MCP SQLite server
- [Model Context Protocol](https://modelcontextprotocol.io/) - MCP specification

## Author

Alfonso Ridao - [@alfonsoridao](https://github.com/alfonsoridao)

---

**Made with AI assistance for the ETH community**
