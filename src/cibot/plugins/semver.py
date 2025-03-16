


from typing import override
from src.cibot.plugins.base import VersionBumpPlugin


class SemVerPlugin(VersionBumpPlugin):
	
	@override
	def next_version(self, bump_type: ReleaseType) -> str:
		return super().next_version(bump_type)