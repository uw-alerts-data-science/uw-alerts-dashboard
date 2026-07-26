MARK_NO_UPDATE_SCHEMA = {
    "name": "mark_no_update",
    "description": "Call when scraped content is already in DB. Ends the agent run.",
    "input_schema": {
        "type": "object",
        "properties": {"reason": {"type": "string"}},
        "required": ["reason"],
    },
}
