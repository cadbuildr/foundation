import hashlib
import json
from typing import Dict


def compute_hash(content: Dict) -> str:
    """Compute SHA-256 hash of content."""
    content_bytes = json.dumps(content, sort_keys=True).encode("utf-8")
    return hashlib.sha256(content_bytes).hexdigest()


def _truncate_dag_hashes(dag: dict, root_hash: str, initial_length: int = 4) -> tuple[dict, str]:
    """
    Post-process DAG to use shorter unique hash IDs.
    
    Args:
        dag: Original DAG with full 64-char hash IDs
        root_hash: Full hash of root node
        initial_length: Initial truncation length (default 4)
        
    Returns:
        Tuple of (truncated_dag, truncated_root_id)
    """
    def common_prefix_length(a: str, b: str) -> int:
        """Calculate common prefix length between two strings."""
        min_len = min(len(a), len(b))
        i = 0
        while i < min_len and a[i] == b[i]:
            i += 1
        return i
    
    def get_min_unique_prefixes(sorted_hashes: list[str], initial_length: int) -> dict[str, int]:
        """Determine minimal unique prefix length for each hash."""
        prefixes = {}
        n = len(sorted_hashes)
        for i in range(n):
            current_hash = sorted_hashes[i]
            prefix_length = initial_length
            
            # Compare with previous hash
            if i > 0:
                prev_hash = sorted_hashes[i - 1]
                common_prev = common_prefix_length(current_hash, prev_hash)
                prefix_length = max(prefix_length, common_prev + 1)
            
            # Compare with next hash
            if i < n - 1:
                next_hash = sorted_hashes[i + 1]
                common_next = common_prefix_length(current_hash, next_hash)
                prefix_length = max(prefix_length, common_next + 1)
            
            prefix_length = min(prefix_length, len(current_hash))
            prefixes[current_hash] = prefix_length
        
        return prefixes
    
    def build_truncated_ids(sorted_hashes: list[str], prefixes: dict[str, int]) -> dict[str, str]:
        """Assign truncated IDs based on minimal unique prefixes."""
        truncated_ids = {}
        seen_truncated_ids = set()
        
        for hash_str in sorted_hashes:
            prefix_length = prefixes[hash_str]
            truncated_id = hash_str[:prefix_length]
            
            # Handle collisions by incrementing prefix length
            while truncated_id in seen_truncated_ids and truncated_id != hash_str:
                prefix_length += 1
                if prefix_length > len(hash_str):
                    raise ValueError(f"Cannot truncate hash {hash_str} to a unique ID.")
                truncated_id = hash_str[:prefix_length]
            
            truncated_ids[hash_str] = truncated_id
            seen_truncated_ids.add(truncated_id)
        
        return truncated_ids
    
    # Step 1: Sort all hashes
    sorted_hashes = sorted(dag.keys())
    
    # Step 2: Determine minimal unique prefix lengths
    prefixes = get_min_unique_prefixes(sorted_hashes, initial_length)
    
    # Step 3: Assign truncated IDs
    id_map = build_truncated_ids(sorted_hashes, prefixes)
    
    # Step 4: Replace IDs in the DAG
    truncated_dag = {}
    for full_hash, node in dag.items():
        truncated_id = id_map[full_hash]
        updated_node = {
            "type": node["type"],
            "params": node["params"],
            "deps": {},
        }
        
        for dep_key, dep_value in node.get("deps", {}).items():
            if isinstance(dep_value, list):
                updated_node["deps"][dep_key] = [
                    id_map.get(dep, dep) for dep in dep_value
                ]
            else:
                updated_node["deps"][dep_key] = id_map.get(dep_value, dep_value)
        
        truncated_dag[truncated_id] = updated_node
    
    # Return truncated DAG and truncated root ID
    return truncated_dag, id_map[root_hash]

