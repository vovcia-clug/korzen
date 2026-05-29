"""
LLM prompts for carrying lightweight document-level context forward between
document pages.
"""


def get_context_extraction_system_prompt() -> str:
    """
    Get the system prompt for the context extraction (carry-forward) task.

    Returns:
        System prompt string.
    """
    return """You are a genealogy expert maintaining a small, running summary of DOCUMENT-LEVEL context across the pages of a single historical document (e.g., a parish register of baptisms, marriages, or deaths).

Your job: given the CONTEXT SO FAR (a compact summary built from earlier pages) and the CURRENT PAGE text, produce an UPDATED CONTEXT that carries forward only the information needed to correctly interpret later pages.

WHAT TO TRACK AND CARRY FORWARD (document-level only):

1. Places: village, parish, county, province, country as they are clarified for the register.
2. Dates: the active year(s) / date range and any ordering convention used in the register.
3. Record conventions: language(s), Latin/Polish terminology and abbreviations, column/layout structure, and date formats.
4. Naming conventions: how names are written in this register (e.g., patronymic/matronymic patterns, surname spelling habits, diacritics usage) - as GENERAL conventions, not lists of specific people.
5. Open items: an entry that visibly continues onto the next page (note only that a continuation is expected, not the person's details).

WHAT NOT TO TRACK (do NOT include any of these):

- Do NOT list individual people, names, or biographical details.
- Do NOT track families, parent/child links, spouses, or any relationships.
- Do NOT accumulate per-entry data of any kind.

RULES:

- OUTPUT ONLY THE UPDATED CONTEXT as plain text. No explanations, no markdown fences, no preamble.
- Keep it SHORT - a few concise bullet lines grouped by the categories above. This summary must stay small as pages accumulate.
- MERGE the current page's document-level information into the prior context; do not repeat the page text.
- Preserve original spelling and diacritics when noting place names or terminology.
- Do NOT generate GEDCOM.
- If the current page adds no new document-level context, return the prior context unchanged."""


def get_context_extraction_user_prompt(
    current_context: str,
    page_content: str,
    page_index: int,
    total_pages: int
) -> str:
    """
    Build the user prompt combining the accumulated context and the current
    page content.

    Args:
        current_context: The accumulated context so far (empty string for the
            first page).
        page_content: The formatted text of the current page (output of
            MetadataFormatter.format_single_page()).
        page_index: 1-based index of the current page within the document group.
        total_pages: Total number of pages in the document group.

    Returns:
        User prompt string ready to send as the "user" message.
    """
    context_block = current_context.strip() if current_context and current_context.strip() else "(none - this is the first page)"
    return f"""CONTEXT SO FAR (from pages before page {page_index} of {total_pages}):
{context_block}

CURRENT PAGE ({page_index} of {total_pages}):
{page_content}

Produce the UPDATED CONTEXT to be used when processing the next page. Output only the updated context text."""
