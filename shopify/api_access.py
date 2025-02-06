import re
import sys


def get_basestring_type():
    """
    Returns the appropriate string type based on the Python version.
    For Python 2.x, returns basestring; for Python 3.x, returns str.
    """
    return basestring if sys.version_info[0] < 3 else str


class ApiAccessError(Exception):
    """Custom exception raised for API access errors."""
    pass


class ApiAccess:
    SCOPE_DELIMITER = ","
    SCOPE_RE = re.compile(r"\A(?P<unauthenticated>unauthenticated_)?(write|read)_(?P<resource>.*)\Z")
    IMPLIED_SCOPE_RE = re.compile(r"\A(?P<unauthenticated>unauthenticated_)?write_(?P<resource>.*)\Z")

    def __init__(self, scopes):
        """
        Initializes ApiAccess with the provided scopes. If a single string is passed,
        it splits it by the delimiter into a list of scopes.
        """
        if isinstance(scopes, get_basestring_type()):
            scopes = scopes.split(self.SCOPE_DELIMITER)

        self._store_scopes(scopes)

    def covers(self, api_access):
        """
        Checks if the current access covers the provided API access.
        """
        return api_access._compressed_scopes <= self._expanded_scopes

    def __str__(self):
        """Returns a string representation of the compressed scopes."""
        return self.SCOPE_DELIMITER.join(self._compressed_scopes)

    def __iter__(self):
        """Returns an iterator over the compressed scopes."""
        return iter(self._compressed_scopes)

    def __eq__(self, other):
        """Compares two ApiAccess instances for equality."""
        return isinstance(other, ApiAccess) and self._compressed_scopes == other._compressed_scopes

    def _store_scopes(self, scopes):
        """
        Processes and stores the provided scopes, separating implied and regular scopes.
        """
        sanitized_scopes = frozenset(filter(None, (scope.strip() for scope in scopes)))
        self._validate_scopes(sanitized_scopes)
        implied_scopes = frozenset(self._get_implied_scope(scope) for scope in sanitized_scopes)
        self._compressed_scopes = sanitized_scopes - implied_scopes
        self._expanded_scopes = sanitized_scopes.union(implied_scopes)

    def _validate_scopes(self, scopes):
        """
        Validates that each scope matches the expected pattern.
        """
        for scope in scopes:
            if not self.SCOPE_RE.match(scope):
                raise ApiAccessError(f"'{scope}' is not a valid access scope")

    def _get_implied_scope(self, scope):
        """
        Returns the implied scope for a given scope, if applicable.
        """
        match = self.IMPLIED_SCOPE_RE.match(scope)
        if match:
            return f"{match.group('unauthenticated') or ''}read_{match.group('resource')}"
        return None
