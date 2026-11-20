"""Custom exception hierarchy. Every RegistryError carries a message that is safe
to show to the user, so the web layer can turn any of them into a friendly flash."""


class RegistryError(Exception):
    """Base class for every error this application raises on purpose."""
    category = "error"      


class ValidationError(RegistryError):
    """User input is missing, malformed or out of range."""


class DuplicateError(RegistryError):
    """A unique value (username, email, community name) is already taken."""


class NotFoundError(RegistryError):
    """The requested record does not exist."""


class AuthError(RegistryError):
    """Wrong credentials."""


class PrivateProfileError(RegistryError):
    """The profile exists but its owner made it private."""
    category = "warning"


class DatabaseError(RegistryError):
    """The database failed. The original error is chained (__cause__), the user
    only sees a friendly message."""
