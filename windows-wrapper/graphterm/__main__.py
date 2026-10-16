# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Allow ``python -m graphterm`` to start the GraphTerm shell."""

import sys

from graphterm.shell import main

if __name__ == "__main__":
    sys.exit(main())
