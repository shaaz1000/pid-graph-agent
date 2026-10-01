"""Exception types raised by the application (never by normal tool usage)."""


class PidAgentError(Exception):
    """Base class for all application errors."""


class ConfigError(PidAgentError):
    """Configuration is missing or invalid."""


class DataFileNotFoundError(PidAgentError):
    """The DEXPI/Proteus XML file does not exist."""


class DexpiParseError(PidAgentError):
    """The XML file exists but could not be parsed into a DEXPI model."""


class GraphNormalizationError(PidAgentError):
    """The pyDEXPI graphs do not have the structure the normalizer relies on."""
