import importlib

from eyconf.validation import ConfigurationError, MultiConfigurationError

__all__ = [
    "ConfigurationError",
    "MultiConfigurationError",
    "NotFoundError",
]


class NotFoundError(Exception):
    def __init__(self, message="Resource not found", resource=None):
        self.message = message
        self.resource = resource
        super().__init__(self.message)

    def __str__(self):
        if self.resource:
            return f"{self.message}: {self.resource}"
        return self.message


class DependencyError(ImportError):
    """Custom error for missing service dependencies."""

    def __init__(
        self,
        service: str,
        missing_packages: list[str],
        extra_name: str | None = None,
    ):
        self.service = service
        self.missing_packages = missing_packages
        self.extra_name = extra_name or service

        if len(missing_packages) == 1:
            packages_str = missing_packages[0]
        else:
            packages_str = ", ".join(f"{pkg}" for pkg in missing_packages)

        msg = (
            f"Service '{service}' requires package '{packages_str}'.\n"
            f"Install extra with: pip install 'plistsync[{self.extra_name}]'"
        )
        super().__init__(msg)


class AuthenticationError(Exception):
    pass


def check_imports(
    service: str,
    required_packages: list[str],
    extra_name: str | None = None,
) -> None:
    """
    Check if required packages are importable.

    Raises
    ------
        DependencyError: If packages are missing
    """
    missing = []

    for package in required_packages:
        # Handle extras like 'eyconf[cli]' by extracting base package
        base_package = (
            package.split("[")[0].split("<")[0].split(">")[0].split("=")[0].strip()
        )

        try:
            importlib.import_module(base_package)
        except ImportError:
            missing.append(package)

    if missing:
        raise DependencyError(
            service=service, missing_packages=missing, extra_name=extra_name
        )


# ----------------------------- Playlist specific ---------------------------- #


class PlaylistAssociationError(Exception):
    """Raised when a playlist's association state is wrong for the operation."""

    already_associated: bool

    def __init__(self, *, already_associated: bool) -> None:
        if already_associated:
            super().__init__("Playlist is already associated with a remote.")
        else:
            super().__init__("Playlist must be associated with a remote.")

        self.already_associated = already_associated
