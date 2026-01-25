from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ReplyAction:
    action: str
    result_id: int


ACTION_REGEX = re.compile(r"^\s*(deeper|details|draft|pivot)\s+(\d+)\s*$", re.I)


def parse_actions(body: str) -> list[ReplyAction]:
    actions: list[ReplyAction] = []
    for line in body.splitlines():
        match = ACTION_REGEX.match(line)
        if match:
            actions.append(
                ReplyAction(action=match.group(1).lower(), result_id=int(match.group(2)))
            )
    return actions
