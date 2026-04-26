from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from nef_pipelines.lib.test_lib import assert_lines_match, run_and_report
from nef_pipelines.tools.namespace.defined import defined_namespaces

runner = CliRunner()
app = typer.Typer()
app.command()(defined_namespaces)

_MOCK_NAMESPACES = {
    "nef": ("NEF Standard", "Data Exchange"),
    "ccpn": ("CcpNmr Analysis", "NMR data analysis"),
}

EXPECTED_SIMPLE = """\
Namespace    Programme        Use
-----------  ---------------  -----------------
nef          NEF Standard     Data Exchange
ccpn         CcpNmr Analysis  NMR data analysis
"""

EXPECTED_PRETTY = """\
+-----------+-----------------+-------------------+
| Namespace |    Programme    |        Use        |
+-----------+-----------------+-------------------+
|    nef    |  NEF Standard   |   Data Exchange   |
|   ccpn    | CcpNmr Analysis | NMR data analysis |
+-----------+-----------------+-------------------+
"""

EXPECTED_MARKDOWN = """\
| Namespace   | Programme       | Use               |
|:------------|:----------------|:------------------|
| nef         | NEF Standard    | Data Exchange     |
| ccpn        | CcpNmr Analysis | NMR data analysis |
"""

EXPECTED_HTML = """\
<table>
<thead>
<tr><th>Namespace  </th><th>Programme      </th><th>Use              </th></tr>
</thead>
<tbody>
<tr><td>nef        </td><td>NEF Standard   </td><td>Data Exchange    </td></tr>
<tr><td>ccpn       </td><td>CcpNmr Analysis</td><td>NMR data analysis</td></tr>
</tbody>
</table>
"""


@pytest.mark.parametrize(
    "format_option, expected",
    [
        ([], EXPECTED_SIMPLE),
        (["--format", "simple"], EXPECTED_SIMPLE),
        (["--format", "pretty"], EXPECTED_PRETTY),
        (["--format", "markdown"], EXPECTED_MARKDOWN),
        (["--format", "ai"], EXPECTED_MARKDOWN),
        (["--format", "html"], EXPECTED_HTML),
    ],
    ids=["default", "simple", "pretty", "markdown", "ai", "html"],
)
def test_defined_namespaces(format_option, expected):
    """Test that defined_namespaces formats a mocked namespace table correctly."""

    with patch(
        "nef_pipelines.tools.namespace.defined.get_registered_namespaces",
        return_value=_MOCK_NAMESPACES,
    ):
        result = run_and_report(app, format_option)

    assert_lines_match(expected, result.stdout)
