"""
Input validation and sanitization utilities.

Provides:
- Input sanitization to prevent injection attacks
- Validation helpers for common patterns
- File upload validation
"""
import html
import re
from pathlib import Path

from fastapi import HTTPException, UploadFile

# Patterns for validation
SAFE_STRING_PATTERN = re.compile(r'^[\w\s\-.,@#&()\'\"!?:;/\[\]{}+=*%$€£¥]+$', re.UNICODE)
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
UUID_PATTERN = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
OBJECT_ID_PATTERN = re.compile(r'^[0-9a-fA-F]{24}$')

# Dangerous patterns to detect potential attacks
SQL_INJECTION_PATTERNS = [
    re.compile(r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|TRUNCATE)\b)", re.IGNORECASE),
    re.compile(r"(--|;|/\*|\*/|@@|@)", re.IGNORECASE),
    re.compile(r"(\bOR\b.*=.*\bOR\b)", re.IGNORECASE),
]

NOSQL_INJECTION_PATTERNS = [
    re.compile(r'(\$where|\$gt|\$lt|\$ne|\$regex|\$or|\$and|\$not|\$nor|\$exists|\$type)', re.IGNORECASE),
    re.compile(r'(\{.*\$.*\})', re.IGNORECASE),
]

XSS_PATTERNS = [
    re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL),
    re.compile(r'javascript:', re.IGNORECASE),
    re.compile(r'on\w+\s*=', re.IGNORECASE),
    re.compile(r'<\s*img[^>]+src\s*=', re.IGNORECASE),
    re.compile(r'<\s*iframe', re.IGNORECASE),
]

PATH_TRAVERSAL_PATTERNS = [
    re.compile(r'\.\./', re.IGNORECASE),
    re.compile(r'\.\.\\', re.IGNORECASE),
    re.compile(r'%2e%2e%2f', re.IGNORECASE),
    re.compile(r'%2e%2e/', re.IGNORECASE),
]


class InputValidationError(Exception):
    """Exception raised when input validation fails."""

    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"Validation failed for '{field}': {message}")


def sanitize_string(value: str, max_length: int = 10000) -> str:
    """
    Sanitize a string input.

    Args:
        value: Input string to sanitize.
        max_length: Maximum allowed length.

    Returns:
        Sanitized string.

    Raises:
        InputValidationError: If input exceeds max length.
    """
    if not value:
        return value

    # Check length
    if len(value) > max_length:
        raise InputValidationError("input", f"Input exceeds maximum length of {max_length}")

    # HTML encode to prevent XSS
    sanitized = html.escape(value)

    # Remove null bytes
    sanitized = sanitized.replace('\x00', '')

    return sanitized


def sanitize_html(value: str, max_length: int = 50000) -> str:
    """
    Sanitize HTML content (more aggressive sanitization).

    Args:
        value: Input HTML string.
        max_length: Maximum allowed length.

    Returns:
        Sanitized string with HTML tags removed.
    """
    if not value:
        return value

    # Check length
    if len(value) > max_length:
        raise InputValidationError("input", f"Input exceeds maximum length of {max_length}")

    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', '', value)

    # HTML encode remaining content
    clean = html.escape(clean)

    # Remove null bytes
    clean = clean.replace('\x00', '')

    return clean


def detect_injection(value: str) -> str | None:
    """
    Detect potential injection attacks in input.

    Args:
        value: Input string to check.

    Returns:
        Type of injection detected, or None if clean.
    """
    if not value:
        return None

    # Check for SQL injection
    for pattern in SQL_INJECTION_PATTERNS:
        if pattern.search(value):
            return "sql_injection"

    # Check for NoSQL injection
    for pattern in NOSQL_INJECTION_PATTERNS:
        if pattern.search(value):
            return "nosql_injection"

    # Check for XSS
    for pattern in XSS_PATTERNS:
        if pattern.search(value):
            return "xss"

    # Check for path traversal
    for pattern in PATH_TRAVERSAL_PATTERNS:
        if pattern.search(value):
            return "path_traversal"

    return None


def validate_and_sanitize(
    value: str,
    field_name: str,
    max_length: int = 10000,
    allow_html: bool = False,
    check_injection: bool = True
) -> str:
    """
    Validate and sanitize input with comprehensive checks.

    Args:
        value: Input string.
        field_name: Name of the field (for error messages).
        max_length: Maximum allowed length.
        allow_html: Whether to allow HTML (will still be escaped).
        check_injection: Whether to check for injection patterns.

    Returns:
        Sanitized string.

    Raises:
        InputValidationError: If validation fails.
    """
    if not value:
        return value

    # Check for injection patterns
    if check_injection:
        injection_type = detect_injection(value)
        if injection_type:
            raise InputValidationError(
                field_name,
                f"Potential {injection_type} attack detected"
            )

    # Sanitize based on type
    if allow_html:
        return sanitize_html(value, max_length)
    else:
        return sanitize_string(value, max_length)


def validate_email(email: str) -> bool:
    """
    Validate email format.

    Args:
        email: Email address to validate.

    Returns:
        True if valid, False otherwise.
    """
    if not email or len(email) > 254:
        return False
    return bool(EMAIL_PATTERN.match(email))


def validate_uuid(value: str) -> bool:
    """
    Validate UUID format.

    Args:
        value: String to validate.

    Returns:
        True if valid UUID, False otherwise.
    """
    if not value:
        return False
    return bool(UUID_PATTERN.match(value))


def validate_object_id(value: str) -> bool:
    """
    Validate MongoDB ObjectId format.

    Args:
        value: String to validate.

    Returns:
        True if valid ObjectId, False otherwise.
    """
    if not value:
        return False
    return bool(OBJECT_ID_PATTERN.match(value))


def validate_file_upload(
    file: UploadFile,
    allowed_types: list[str],
    max_size_mb: float = 10.0
) -> None:
    """
    Validate uploaded file.

    Args:
        file: Uploaded file to validate.
        allowed_types: List of allowed MIME types.
        max_size_mb: Maximum file size in megabytes.

    Raises:
        HTTPException: If validation fails.
    """
    # Check content type
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(allowed_types)}"
        )

    # Check filename for path traversal
    if file.filename:
        if detect_injection(file.filename):
            raise HTTPException(
                status_code=400,
                detail="Invalid filename"
            )

        # Check for dangerous extensions
        dangerous_extensions = {'.exe', '.bat', '.cmd', '.sh', '.ps1', '.vbs', '.js'}
        file_ext = Path(file.filename).suffix.lower()
        if file_ext in dangerous_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"File type not allowed: {file_ext}"
            )


async def validate_file_size(file: UploadFile, max_size_mb: float = 10.0) -> bytes:
    """
    Read and validate file size.

    Args:
        file: Uploaded file.
        max_size_mb: Maximum size in megabytes.

    Returns:
        File contents as bytes.

    Raises:
        HTTPException: If file is too large.
    """
    max_size_bytes = int(max_size_mb * 1024 * 1024)

    # Read file in chunks to avoid memory issues
    contents = b""
    while True:
        chunk = await file.read(8192)  # 8KB chunks
        if not chunk:
            break
        contents += chunk
        if len(contents) > max_size_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size: {max_size_mb}MB"
            )

    # Reset file position
    await file.seek(0)

    return contents


def validate_pagination_params(
    limit: int,
    max_limit: int = 100,
    min_limit: int = 1
) -> int:
    """
    Validate pagination limit parameter.

    Args:
        limit: Requested limit.
        max_limit: Maximum allowed limit.
        min_limit: Minimum allowed limit.

    Returns:
        Validated limit value.
    """
    if limit < min_limit:
        return min_limit
    if limit > max_limit:
        return max_limit
    return limit


def sanitize_mongodb_query(query: dict) -> dict:
    """
    Sanitize a MongoDB query to prevent NoSQL injection.

    Args:
        query: MongoDB query dictionary.

    Returns:
        Sanitized query.

    Raises:
        InputValidationError: If dangerous operators are detected.
    """
    dangerous_operators = {'$where', '$expr', '$function'}

    def check_dict(d: dict, path: str = "") -> dict:
        result = {}
        for key, value in d.items():
            current_path = f"{path}.{key}" if path else key

            # Check for dangerous operators
            if key in dangerous_operators:
                raise InputValidationError(
                    current_path,
                    f"Operator '{key}' is not allowed"
                )

            # Recursively check nested dicts
            if isinstance(value, dict):
                result[key] = check_dict(value, current_path)
            elif isinstance(value, list):
                result[key] = [
                    check_dict(item, f"{current_path}[]") if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                result[key] = value

        return result

    return check_dict(query)
