"""Controller-owned public test execution; no model or hidden verifier access."""

from .docker import DockerTestRunner, PublicTestCommand, TestExecution
from .pipeline import validate_candidate
from .regression import RegressionTest
from .reports import ReportError, ReportFormat, TestReport, parse_report
from .reproduction import ReproductionSpec, python_reproduction_command

__all__ = [
    "DockerTestRunner",
    "PublicTestCommand",
    "RegressionTest",
    "ReportError",
    "ReportFormat",
    "ReproductionSpec",
    "TestExecution",
    "TestReport",
    "parse_report",
    "python_reproduction_command",
    "validate_candidate",
]
