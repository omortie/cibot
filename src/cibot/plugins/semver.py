import re
from pathlib import Path
from typing import override

from packaging.version import Version

from cibot.plugins.base import BumpType, VersionBumpPlugin

SEMVER_REGEX = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def bumped_version(bump_type: BumpType, version_raw: str) -> str:
	current_version = Version(version_raw)

	def semver_to_str(major: int, minor: int, patch: int) -> str:
		return f"{major}.{minor}.{patch}"

	match bump_type:
		case BumpType.MAJOR:
			new_version = semver_to_str(current_version.major + 1, 0, 0)
		case BumpType.MINOR:
			new_version = semver_to_str(current_version.major, current_version.minor + 1, 0)
		case BumpType.PATCH:
			new_version = semver_to_str(
				current_version.major, current_version.minor, current_version.micro + 1
			)
		case _:
			raise ValueError(f"Invalid bump type: {bump_type}")
	return new_version


class SemverPlugin(VersionBumpPlugin):
	@override
	def plugin_name(self) -> str:
		return "semver"

	@override
	def supported_backends(self) -> tuple[str, ...]:
		return ("*",)

	@override
	def next_version(self, bump_type: BumpType) -> str:
		current_version = self._current_version_from_pyproject()
		new_version = bumped_version(bump_type, current_version)
		self._pr_comment = f"Bumping version to {new_version}. Bump type: {bump_type.value}."
		return new_version

	@override
	def prepare_release(self, release_type: BumpType, next_version: str) -> list[Path]:
		content = self._pyproject.read_text()
		new_content = re.sub(SEMVER_REGEX, next_version, content)
		self._pyproject.write_text(new_content)
		return [self._pyproject]

	@property
	def _pyproject(self) -> Path:
		return Path.cwd() / "pyproject.toml"

	def _current_version_from_pyproject(self) -> str:
		content = self._pyproject.read_text()
		if matched := SEMVER_REGEX.search(content):
			return f"{matched.group(0)}.{matched.group(1)}.{matched.group(2)}"
		raise ValueError("Invalid version format in pyproject.toml")
