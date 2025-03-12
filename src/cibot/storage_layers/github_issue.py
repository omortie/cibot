import json

import msgspec
from github.IssueComment import IssueComment

from cibot.storage_layers.base import BaseStorage


class GithubIssueStorage(BaseStorage):
    def __init__(self, comment: IssueComment) -> None:
        self.comment = comment

    def get_json_part_from_comment(self) -> dict[str, bytes] | None:
        body = self.comment.body
        try:
            return json.loads(body.split("```json")[1].split("```")[0].strip())
        except IndexError:
            return None

    def get[T](self, key: str, type_: type[T]) -> T:
        raw = self.get_json_part_from_comment()
        if raw is None:
            raise ValueError("No JSON part found in comment")

        return msgspec.json.decode(raw[key], type=type_)

    def set(self, key: str, value: msgspec.Struct) -> None:
        raw = msgspec.json.encode(value)
        comment_base = """
        ### CIBot Storage Layer
        ### Do not edit this comment
        ```json
        {}
        ```
        """
        if exists := self.get_json_part_from_comment():
            exists[key] = raw
            new_comment = comment_base.format(json.dumps(exists))
        else:
            new_comment = comment_base.format(json.dumps({key: raw}))
        self.comment.edit(new_comment)
