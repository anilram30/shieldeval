"""shieldeval - shield transfer impedance and screening attenuation evaluation (legacy-exact + modern)."""
__version__ = "4.0.0"
__author__ = "Sreeram Anil"
from .core import Evaluation, Settings, evaluate
from .fixtures import list_fixtures, load_fixture
from .io import read_measurement
from .legacy import legacy_evaluate

__all__ = ["Settings", "Evaluation", "evaluate", "load_fixture", "list_fixtures", "read_measurement", "legacy_evaluate", "__version__"]
