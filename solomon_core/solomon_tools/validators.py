# solomon_tools/validators.py — Enhanced validation with detailed feedback
import os
from werkzeug.utils import secure_filename
from solomon_core.solomon_tools.errors import ValidationError
from solomon_core.solomon_tools.fileops import detect_mime_type, UPLOADS_DIR

# ---------------------------------------------------
# Intent-to-allowed-file-type mapping
# ---------------------------------------------------
INTENT_ALLOWED_TYPES = {
    "count_lines": ["text/plain", "text/csv"],
    "sum_column": [
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/csv"
    ],
    "merge_files": ["text/plain"],
    "first_lines": ["text/plain", "text/csv"],
    "parse_file": [
        "application/json",
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain"
    ]
}


# ---------------------------------------------------
# Validation Logic
# ---------------------------------------------------
def validate_task(intent: str, entities: dict):
    """
    Validate extracted entities and file compatibility for a given intent.
    Ensures files exist, types match, and required parameters are present.
    Produces human-readable diagnostic messages for UI feedback.
    """

    filenames = []
    if "filename" in entities:
        filenames.append(entities["filename"])
    if "file2" in entities:
        filenames.append(entities["file2"])

    # --- Check for missing file entity ---
    if not filenames:
        raise ValidationError("No file was provided. A filename is required for this task.")

    for fname in filenames:
        if not isinstance(fname, str) or fname.strip() == "":
            raise ValidationError("Invalid filename format (must be a non-empty string).")

        if ".." in fname or fname.startswith("/"):
            raise ValidationError(f"Potentially unsafe or invalid filename: {fname}")

        # ✅ Normalize the filename (handles spaces & special chars from uploads)
        normalized_fname = secure_filename(fname)
        path = os.path.join(UPLOADS_DIR, normalized_fname)

        # ✅ Graceful fallback: try replacing spaces with underscores if still missing
        if not os.path.exists(path):
            alt_path = os.path.join(UPLOADS_DIR, fname.replace(" ", "_"))
            if os.path.exists(alt_path):
                path = alt_path
            else:
                raise ValidationError(f"File not found in uploads directory: {fname}")

        mime = detect_mime_type(path)
        allowed_types = INTENT_ALLOWED_TYPES.get(intent, [])

        # --- MIME validation with clearer reasoning ---
        if allowed_types and mime not in allowed_types:
            if intent == "sum_column":
                raise ValidationError(
                    f"Cannot sum a column in a {mime.split('/')[-1].upper()} file "
                    f"('{fname}'). This operation requires an Excel or CSV file."
                )
            elif intent == "merge_files":
                raise ValidationError(
                    f"Cannot merge {mime.split('/')[-1].upper()} files. "
                    f"Only plain text files can be merged."
                )
            elif intent == "count_lines":
                raise ValidationError(
                    f"Cannot count lines in a {mime.split('/')[-1].upper()} file. "
                    f"Only text or CSV files support line counting."
                )
            else:
                raise ValidationError(
                    f"Intent '{intent}' is not compatible with file type {mime} ({fname})."
                )

    # --- Entity-specific checks ---
    if intent in ["sum_column", "total_column"]:
        if "column" not in entities:
            raise ValidationError("Missing required entity: column (e.g., 'column B').")
        if not isinstance(entities["column"], str):
            raise ValidationError("Column name must be a string (e.g., 'B' or 'Revenue').")

    if intent in ["first_lines", "head"]:
        if "n" in entities:
            try:
                n_val = int(entities["n"])
                if n_val <= 0:
                    raise ValidationError("Parameter 'n' must be a positive number.")
            except ValueError:
                raise ValidationError("Parameter 'n' must be a valid integer.")

    return True
