from abc import ABC, abstractmethod
from typing import Optional

class AssetProvider(ABC):
    @abstractmethod
    def get_asset_tar(self, source: str, target: str, read_only: bool = True) -> Optional[bytes]:
        """
        Fetch asset content from the provider and return it as a tar archive.
        
        Args:
            source: Relative path to the asset in the provider.
            target: Absolute path where the asset should be placed in the container.
            read_only: Whether the file should be read-only in the tar archive.
            
        Returns:
            Tar archive as bytes, or None if not found or on error.
        """
        pass
