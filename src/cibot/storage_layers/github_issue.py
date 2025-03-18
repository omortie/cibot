import json
import textwrap
from typing import override

import msgspec
from github.Repository import Repository
from loguru import logger
from pydantic_settings import BaseSettings

from cibot.storage_layers.base import BaseStorage


class Settings(BaseSettings):
	model_config = {
		"env_prefix": "CIBOT_STORAGE_GH_ISSUE_",
	}
	number: int | None = None


class Bucket(msgspec.Struct):
	plugin_srorage: dict[str, str]


COMMENT_BASE = """
### CIBot Storage Layer
### Do not edit this comment

```json
{}
```
"""


class GithubIssueStorage(BaseStorage):
	def __init__(self, repo: Repository) -> None:
		settings = Settings()
		if not settings.number:
			raise ValueError("missing STORAGE_ISSUE_NUMBER")
		issue = repo.get_issue(settings.number)
		logger.info(f"Found issue {issue.title}")
		self.issue = issue

	def get_json_part_from_comment(self) -> Bucket | None:
		if body := self.issue.body:
			body = body.split("```json")[1].split("```")[0].strip()
			return msgspec.json.decode(body, type=Bucket)

	def get[T](self, key: str, type_: type[T]) -> T | None:
		logger.info(f"Getting key {key}")
		if bucket := self.get_json_part_from_comment():
			if exists := bucket.plugin_srorage.get(key, None):
				return msgspec.json.decode(exists, type=type_)
		return None

	def set(self, key: str, value: msgspec.Struct) -> None:
		raw = msgspec.json.encode(value).decode()

		if bucket := self.get_json_part_from_comment():
			logger.info(f"Updating key {key} with value {raw}")
			bucket.plugin_srorage[key] = raw
			new_comment = COMMENT_BASE.format(json.dumps(msgspec.to_builtins(bucket), indent=2))
		else:
			logger.info(f"Creating new bucket with key {key} with value {raw}")
			new_comment = COMMENT_BASE.format(
				json.dumps(msgspec.to_builtins(Bucket(plugin_srorage={key: raw})), indent=2)
			)
		self.issue.edit(body=textwrap.dedent(new_comment))

	@override
	def delete(self, key: str) -> None:
		if bucket := self.get_json_part_from_comment():
			logger.info(f"Deleting key {key}")
			del bucket.plugin_srorage[key]
			new_comment = COMMENT_BASE.format(json.dumps(msgspec.to_builtins(bucket), indent=2))
			self.issue.edit(body=textwrap.dedent(new_comment))
