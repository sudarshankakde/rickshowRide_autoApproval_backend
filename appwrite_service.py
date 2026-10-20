"""
Appwrite Storage Service for AutoRide
Handles large APK file uploads to Appwrite Cloud / Self-hosted Storage Buckets.
Bypasses 10MB limits from other free hosts with native SDK chunking (50MB+ support).
"""

import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

_appwrite_client = None
_appwrite_storage = None
_appwrite_initialized = False


def init_appwrite() -> bool:
    """Initializes the Appwrite Python SDK client and Storage service."""
    global _appwrite_client, _appwrite_storage, _appwrite_initialized
    if _appwrite_initialized:
        return True

    endpoint = os.getenv("APPWRITE_ENDPOINT", "https://cloud.appwrite.io/v1").strip()
    project_id = os.getenv("APPWRITE_PROJECT_ID", "").strip()
    api_key = os.getenv("APPWRITE_API_KEY", "").strip()

    if not project_id or not api_key:
        return False

    try:
        from appwrite.client import Client
        from appwrite.services.storage import Storage

        client = Client()
        client.set_endpoint(endpoint)
        client.set_project(project_id)
        client.set_key(api_key)

        _appwrite_client = client
        _appwrite_storage = Storage(client)
        _appwrite_initialized = True
        return True
    except Exception as e:
        print(f"[Appwrite] Failed to initialize client: {e}")
        return False


def is_appwrite_configured() -> bool:
    """Returns True if Appwrite environment variables are set."""
    project_id = os.getenv("APPWRITE_PROJECT_ID", "").strip()
    api_key = os.getenv("APPWRITE_API_KEY", "").strip()
    bucket_id = os.getenv("APPWRITE_BUCKET_ID", "").strip()
    return bool(project_id and api_key and bucket_id)


def upload_apk_to_appwrite(apk_bytes: bytes, filename: str) -> Optional[str]:
    """
    Uploads an APK to Appwrite Storage with automatic chunking.
    Sets public read permissions so mobile drivers can download directly without credentials.
    Returns the public download URL.
    """
    if not is_appwrite_configured():
        return None

    if not init_appwrite():
        return None

    bucket_id = os.getenv("APPWRITE_BUCKET_ID", "").strip()
    endpoint = os.getenv("APPWRITE_ENDPOINT", "https://cloud.appwrite.io/v1").strip().rstrip("/")
    project_id = os.getenv("APPWRITE_PROJECT_ID", "").strip()

    try:
        from appwrite.id import ID
        from appwrite.input_file import InputFile
        from appwrite.permission import Permission
        from appwrite.role import Role

        input_file = InputFile.from_bytes(
            apk_bytes,
            filename=filename,
            mime_type="application/vnd.android.package-archive"
        )

        # Public read permission allows any user/device to download the APK
        permissions = [Permission.read(Role.any())]
        file_id = ID.unique()

        result = _appwrite_storage.create_file(
            bucket_id=bucket_id,
            file_id=file_id,
            file=input_file,
            permissions=permissions
        )

        # Build public download URL
        # Format: {endpoint}/storage/buckets/{bucketId}/files/{fileId}/download?project={projectId}
        res_file_id = getattr(result, "id", None) or getattr(result, "$id", None) or file_id
        download_url = f"{endpoint}/storage/buckets/{bucket_id}/files/{res_file_id}/download?project={project_id}"
        print(f"[Appwrite] APK uploaded successfully: {download_url}")
        return download_url
    except Exception as e:
        print(f"[Appwrite] APK upload to bucket '{bucket_id}' failed: {e}")
        return None
