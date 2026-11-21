# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Desktop-app entry point: launches graphterm.launcher with this folder on sys.path."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from graphterm.launcher import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
