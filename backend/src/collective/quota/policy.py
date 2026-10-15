"""Over-limit policies.

Phase 3 defines the policy tokens only; phase 4 adds the evaluation logic.
"""

BLOCK_ALL = "block_all"
BLOCK_FILES = "block_files"
LIMIT_FILE_SIZE = "limit_file_size"
ALLOW = "allow"

POLICIES = (BLOCK_ALL, BLOCK_FILES, LIMIT_FILE_SIZE, ALLOW)
