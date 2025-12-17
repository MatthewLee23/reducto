from pathlib import Path
from reducto import AsyncReducto


async def upload_pdf(client: AsyncReducto, pdf_path: Path) -> str:
    """
    Upload a PDF file to Reducto's server and return the remote input reference.

    Args:
        client: AsyncReducto client instance
        pdf_path: Path to the PDF file to upload

    Returns:
        Remote input reference (url, id, document_id, or file_id)

    Raises:
        ValueError: If no server reference can be found in the upload response
    """
    # Upload the PDF file to Reducto's server (@Reducto Python SDK)
    upload_response = await client.upload(file=pdf_path)

    # Extract a server-side reference (prefer url, fallback to id-like fields)
    if hasattr(upload_response, "model_dump"):
        upload_data = upload_response.model_dump()
    else:
        # Last resort fallback if model_dump is unavailable
        upload_data = getattr(upload_response, "__dict__", {})

    remote_input = (
        upload_data.get("url")
        or upload_data.get("id")
        or upload_data.get("document_id")
        or upload_data.get("file_id")
    )

    if not remote_input:
        raise ValueError(
            f"Could not find server reference in upload response keys: {list(upload_data.keys())}"
        )

    return remote_input
