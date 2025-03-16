


from pathlib import Path
import re
from typing import override
from src.cibot.plugins.base import BumpType, VersionBumpPlugin
from packaging.version import Version

SEMVER_REGEX = re.compile(r"(\d+)\.(\d+)\.(\d+)")
def bump_version(bump_type: BumpType, version_raw: str) -> str:
	current_version = Version(version_raw)
	
	def semver_to_str(major: int, minor: int, patch: int) -> str:
		return f"{major}.{minor}.{patch}"

	match bump_type:
		case BumpType.MAJOR:
			new_version = semver_to_str(current_version.major + 1, 0, 0)
		case BumpType.MINOR:
			new_version = semver_to_str(current_version.major, current_version.minor + 1, 0)
		case BumpType.PATCH:
			new_version = semver_to_str(current_version.major, current_version.minor, current_version.micro + 1)
		case _:
			raise ValueError(f"Invalid bump type: {bump_type}")
	return new_version
	
class SemVerPlugin(VersionBumpPlugin):
	

	@override
	def plugin_name(self) -> str:
		return "semver"

	@property
	def pyproject(self) -> Path:
		return Path.cwd() / "pyproject.toml"

	def current_version_from_pyproject(self) -> str:
		content = self.pyproject.read_text()
		for line in content.split("\n"):
			version_match = SEMVER_REGEX.match(line)
			if version_match:
				return version_match.group(0)
		raise ValueError("Invalid version format in pyproject.toml")
	
	def bump_pyproject(self, new_version: str) -> None:
		content = self.pyproject.read_text()
		new_content = re.sub(SEMVER_REGEX, new_version, content)
		self.pyproject.write_text(new_content)

	@override
	def next_version(self, bump_type: BumpType) -> str:
		return bump_version(bump_type, self.current_version_from_pyproject())
	
	
	@override
	def prepare_release(self, release_type: BumpType, next_version: str) -> list[Path]:
		self.bump_pyproject(next_version)
		return [self.pyproject]
