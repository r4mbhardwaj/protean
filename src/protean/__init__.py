"""Primary Module to define version and expose packages"""

__version__ = "0.5.8"

from protean.utils import get_version

from .domain import Domain

__all__ = ("Domain", "get_version")
