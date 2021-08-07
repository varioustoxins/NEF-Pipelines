
from textwrap import dedent

import pytest
from freezegun import freeze_time
from typer.testing import CliRunner

from lib.test_lib import assert_lines_match

runner = CliRunner()

@pytest.fixture
def using_header():
    # register the module under test
    import tools.header


EXPECTED_TEMPLATE = '''
    data_%(name)s

    save_nef_nmr_meta_data
       _nef_nmr_meta_data.sf_category      nef_nmr_meta_data
       _nef_nmr_meta_data.sf_framecode     nef_nmr_meta_data
       _nef_nmr_meta_data.format_name      nmr_exchange_format
       _nef_nmr_meta_data.format_version   1.1
       _nef_nmr_meta_data.program_name     NEFPipelines
       _nef_nmr_meta_data.script_name      header.py
       _nef_nmr_meta_data.program_version  0.0.1
       _nef_nmr_meta_data.creation_date    2012-01-14T12:00:01.123456
       _nef_nmr_meta_data.uuid             NEFPipelines-2012-01-14T12:00:01.123456-1043321819

       loop_
          _nef_run_history.run_number
          _nef_run_history.program_name
          _nef_run_history.program_version
          _nef_run_history.script_name


       stop_

    save_'''


def get_expected(name):
    expected = EXPECTED_TEMPLATE % {'name': name}
    expected = dedent('\n'.join(expected.split('\n')[1:]))
    return expected


# noinspection PyUnusedLocal
@freeze_time("2012-01-14 12:00:01.123456")
def test_nef_default_header(typer_app, using_header, fixed_seed):

    result = runner.invoke(typer_app, ['header'])

    assert result.exit_code == 0

    assert_lines_match(get_expected('nef'), result.stdout)


# noinspection PyUnusedLocal
@freeze_time("2012-01-14 12:00:01.123456")
def test_nef_named_header(typer_app, using_header, fixed_seed):

    result = runner.invoke(typer_app, ['header', 'test'])
    assert result.exit_code == 0

    assert_lines_match(get_expected('test'), result.stdout)


if __name__ == '__main__':
    pytest.main([__file__, '-vv'])
