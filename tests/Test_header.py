from io import StringIO
from itertools import zip_longest
from textwrap import dedent
import pytest

from freezegun import freeze_time
from argparse import Namespace
from random import seed

@pytest.fixture
def app():
    import nef_app

    import typer
    app = typer.Typer()
    nef_app.app = app


@freeze_time("2012-01-14 12:00:01.123456")
def test_nef_header(app, capsys):
    from tools import header

    expected = '''
    data_test

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

    seed(42)
    expected = dedent('\n'.join(expected.split('\n')[1:]))
    header.header(name='test')
    test_header_entry, _ = capsys.readouterr()

    zip_lines = zip_longest(expected.split('\n'), test_header_entry.split('\n'), fillvalue='')

    for expected_line, header_line in zip_lines:
        assert expected_line == header_line


if __name__ == '__main__':
    pytest.main([__file__])
