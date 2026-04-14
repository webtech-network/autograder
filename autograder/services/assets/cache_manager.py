import os
import shutil
import logging
from typing import Optional, Dict
import collections

logger = logging.getLogger("AssetCacheManager")

class AssetCacheManager:
    def __init__(self, in_memory_limit: int = 0, disk_cache_dir: str = "/tmp/autograder_assets_cache"):
        """
        Initialize the asset cache manager.
        
        Args:
            in_memory_limit: Maximum number of assets to keep in memory. If 0, in-memory cache is disabled.
            disk_cache_dir: Directory to use for disk caching.
        """
        self.in_memory_limit = in_memory_limit
        self.disk_cache_dir = disk_cache_dir
        
        # LRU cache for in-memory assets (filename -> bytes)
        self.in_memory_cache: Dict[str, bytes] = collections.OrderedDict()
        
        # Ensure disk cache directory exists
        if not os.path.exists(self.disk_cache_dir):
            os.makedirs(self.disk_cache_dir, exist_ok=True)
            
    def get(self, asset_key: str) -> Optional[bytes]:
        """Get an asset from cache (memory first, then disk)."""
        # Try in-memory cache first
        if self.in_memory_limit > 0 and asset_key in self.in_memory_cache:
            logger.debug("In-memory cache hit for %s", asset_key)
            # Move to end to mark as recently used
            content = self.in_memory_cache.pop(asset_key)
            self.in_memory_cache[asset_key] = content
            return content
            
        # Try disk cache
        disk_path = self._get_disk_path(asset_key)
        if os.path.exists(disk_path):
            logger.debug("Disk cache hit for %s", asset_key)
            try:
                with open(disk_path, "rb") as f:
                    content = f.read()
                    
                # Store in in-memory cache if enabled
                if self.in_memory_limit > 0:
                    self._add_to_memory_cache(asset_key, content)
                    
                return content
            except Exception as e:
                logger.error("Failed to read asset from disk cache: %s", str(e))
                
        return None
        
    def put(self, asset_key: str, content: bytes) -> None:
        """Store an asset in both memory and disk caches."""
        # Save to disk
        disk_path = self._get_disk_path(asset_key)
        try:
            # Create subdirectories if needed (e.g., if asset_key contains '/')
            os.makedirs(os.path.dirname(disk_path), exist_ok=True)
            with open(disk_path, "wb") as f:
                f.write(content)
            logger.debug("Stored asset %s in disk cache", asset_key)
        except Exception as e:
            logger.error("Failed to write asset to disk cache: %s", str(e))
            
        # Save to memory if enabled
        if self.in_memory_limit > 0:
            self._add_to_memory_cache(asset_key, content)
            
    def _add_to_memory_cache(self, asset_key: str, content: bytes) -> None:
        """Helper to add an asset to the LRU memory cache."""
        if asset_key in self.in_memory_cache:
            self.in_memory_cache.pop(asset_key)
        elif len(self.in_memory_cache) >= self.in_memory_limit:
            # Remove oldest item (first item in OrderedDict)
            self.in_memory_cache.popitem(last=False)
            
        self.in_memory_cache[asset_key] = content
        
    def _get_disk_path(self, asset_key: str) -> str:
        """Resolve the absolute disk path for an asset key."""
        # Sanitize asset_key to prevent directory traversal
        # asset_key is expected to be a hash or a safe relative path
        safe_key = os.path.normpath(asset_key).lstrip('/')
        return os.path.join(self.disk_cache_dir, safe_key)

    def clear(self) -> None:
        """Clear all caches."""
        self.in_memory_cache.clear()
        if os.path.exists(self.disk_cache_dir):
            shutil.rmtree(self.disk_cache_dir)
            os.makedirs(self.disk_cache_dir, exist_ok=True)
