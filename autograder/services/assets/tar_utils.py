import io
import tarfile
import os
import time

def create_tar_archive(filename: str, content: bytes, target_path: str, read_only: bool = True) -> bytes:
    """
    Create an in-memory tar archive for a single file.
    
    Args:
        filename: Base name of the file.
        content: Raw file contents as bytes.
        target_path: Full absolute path in the container.
        read_only: Whether to set permissions to 0444.
        
    Returns:
        Tar archive as bytes.
    """
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode='w') as tar:
        # Let's use put_archive(path='/', ...) for simplicity.
        # Ensure the path in the tar is relative (tar doesn't like absolute paths)
        tar_name = target_path.lstrip('/')
        
        info = tarfile.TarInfo(name=tar_name)
        info.size = len(content)
        info.mtime = int(time.time())
        # Permissions: 0444 for read-only, 0644 for default
        info.mode = 0o444 if read_only else 0o644
        
        tar.addfile(info, io.BytesIO(content))
        
    return out.getvalue()
