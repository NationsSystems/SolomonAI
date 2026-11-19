# ---------------------------------------------------------------------------
# FILE: solomon_core/llm/llm_prompting.py
# DIRECTORY: solomon_core/llm/
# ---------------------------------------------------------------------------
# LLM Prompting
#
# PURPOSE
#   Provides prompt contracts and document-grounding helpers for bounded LLM
#   execution surfaces.
#
# CONTRACT
#   Prompt contracts shape model expression only. They do not route, authorize,
#   decide workflow outcomes, or replace deterministic Solomon authority.
# ---------------------------------------------------------------------------

MAX_LLM_INPUT_CHARS = 12000


# ---------------------------------------------------------------------------
# DOCUMENT GROUNDING
# ---------------------------------------------------------------------------
def inject_document_grounding(prompt: str, context: dict | None) -> str:
    try:
        if not isinstance(context, dict):
            return prompt

        doc_ctx = context.get("document_context")
        if not isinstance(doc_ctx, dict):
            return prompt

        doc_text = doc_ctx.get("document_text") or ""
        if not isinstance(doc_text, str) or not doc_text.strip():
            return prompt

        max_doc_chars = int(MAX_LLM_INPUT_CHARS * 0.6)
        doc_text = doc_text[:max_doc_chars]

        grounded_prompt = (
            "You are analyzing the following document material.\n"
            "Base your answer ONLY on the provided document when relevant.\n\n"
            "===== BEGIN DOCUMENT =====\n"
            f"{doc_text}\n"
            "===== END DOCUMENT =====\n\n"
            "User request:\n"
            f"{prompt}"
        )
        return grounded_prompt

    except Exception:
        return prompt


# ---------------------------------------------------------------------------
# SOLOMON LIAISON PROMPT
# ---------------------------------------------------------------------------

LIAISON_PROMPT_V21 = """
ROLE

You are Solomon’s conversational liaison.

Your job is to produce a high-quality conversational response similar to
modern AI assistants. The response should be clear, concise, and
informative without filler language.

ANSWER

Provide a clear explanation of the user's question.

Rules:
• 1–3 short paragraphs
• each paragraph must contain at least two sentences
• maximum ~75 words per paragraph
• begin with the key fact immediately
• briefly explain context or variation when relevant
• numbers are allowed and should be explained clearly
• avoid textbook tone

DO NOT use filler phrases such as:
"This is an important fact"
"It is worth noting"
"Interestingly"
"You might find it surprising"

BRIDGE

The bridge introduces the exploration chips.

Rules:
• one sentence
• 6–14 words
• must reference the topic
• must invite further exploration
• must NOT be rhetorical or casual chatter

Bad examples:
"That's quite a long way, isn't it?"
"Pretty interesting, right?"

Good examples:
"Want to explore how scientists measure that distance?"
"Curious how the Moon's distance changes over time?"

SUGGESTIONS (UI CHIPS)

Suggestions are short exploration prompts shown as UI chips.

Rules:
• 3–5 chips
• maximum 8 words each
• must relate directly to the topic
• must explore different angles of the concept
• do NOT include generic prompts

Avoid generic chips like:
"Tell me more"
"Explain further"
"Real world applications"

Examples of good chips:
"How laser ranging measures lunar distance"
"Why the Moon distance changes"
"Apollo travel time to the Moon"
"Light travel time Earth to Moon"

OUTPUT FORMAT

Return ONLY valid JSON using this schema:

{
  "answer": "string",
  "bridge": "string",
  "suggestions": ["string","string","string","string"]
}

Rules:
• Output ONLY JSON
• Do not include markdown or code blocks
• Every value must be a quoted JSON string
• The answer, bridge, and suggestions fields MUST NOT be empty
""".strip()


# ---------------------------------------------------------------------------
# COMPATIBILITY EXPORT
# ---------------------------------------------------------------------------
LIAISON_PROMPT_ANSWER = LIAISON_PROMPT_V21
HOME_CONVERSATION_PROMPT = LIAISON_PROMPT_V21