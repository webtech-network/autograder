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
        # We use a tar-compatible relative path for the tar entry name,
        # but we provide the target_path directory as the container's put_archive
        # target.
        # Actually, if we use put_archive(path='/', tar_bytes), the tar should
        # contain the full path.
        # If we use put_archive(path='/tmp', tar_bytes), the tar should contain
        # relative paths to /tmp.
        
        # Let's assume we use put_archive(path='/', ...) for simplicity.
        # Ensure the path in the tar is relative (tar doesn't like absolute paths)
        tar_name = target_path.lstrip('/')
        
        info = tarfile.TarInfo(name=tar_name)
        info.size = len(content)
        info.mtime = int(time.time())
        # Permissions: 0444 for read-only, 0644 for default
        info.mode = 0o444 if read_only else 0o644
        
        tar.addfile(info, io.BytesIO(content))
        
    return out.getvalue()
