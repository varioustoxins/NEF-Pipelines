
from itertools import zip_longest
from textwrap import dedent
from random import seed

import pytest
from freezegun import freeze_time
from typer.testing import CliRunner

runner = CliRunner()

@pytest.fixture
def header_app():
    import typer

    import nef_app
    if not nef_app.app:
        nef_app.app = typer.Typer()

        # if only one command is registered it is ignored on the command line...
        dummy_app = typer.Typer()
        nef_app.app.add_typer(dummy_app, name='dummy')

    return nef_app.app

@pytest.fixture
def using_header():
    # register the module under test
    import tools.header

@pytest.fixture
def seed_42():
    seed(42)


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


def check_lines_match(expected, result):
    zip_lines = zip_longest(expected.split('\n'), result.stdout.split('\n'), fillvalue='')
    for expected_line, header_line in zip_lines:
        assert expected_line == header_line


# noinspection PyUnusedLocal
@freeze_time("2012-01-14 12:00:01.123456")
def test_nef_default_header(header_app, using_header, seed_42):

    result = runner.invoke(header_app, ['header'])
    assert result.exit_code == 0

    check_lines_match(get_expected('nef'), result)


# noinspection PyUnusedLocal
@freeze_time("2012-01-14 12:00:01.123456")
def test_nef_named_header(header_app, using_header, seed_42):

    result = runner.invoke(header_app, ['header', 'test'])
    assert result.exit_code == 0

    check_lines_match(get_expected('test'), result)


if __name__ == '__main__':
    pytest.main([__file__, '-vv'])
