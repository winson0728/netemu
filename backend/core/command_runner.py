from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from typing import Iterable, Sequence

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CommandResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        return self.returncode == 0

    def command_text(self) -> str:
        return " ".join(self.argv)


class CommandRunner:
    def run(
        self,
        argv: Sequence[str],
        *,
        ok_returncodes: Iterable[int] = (0,),
        timeout_s: float = 10,
    ) -> CommandResult:
        argv_list = list(argv)
        logger.debug("RUN %s", " ".join(argv_list))
        try:
            completed = subprocess.run(
                argv_list,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired:
            logger.error("Command timed out after %ss: %s", timeout_s, " ".join(argv_list))
            return CommandResult(
                argv=argv_list,
                returncode=-1,
                stdout="",
                stderr=f"command timed out after {timeout_s}s",
            )
        result = CommandResult(
            argv=argv_list,
            returncode=completed.returncode,
            stdout=(completed.stdout or "").strip(),
            stderr=(completed.stderr or "").strip(),
        )
        if result.returncode not in set(ok_returncodes):
            logger.debug("Command failed rc=%s stderr=%s", result.returncode, result.stderr)
        return result
