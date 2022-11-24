import json
import os
from pathlib import Path

import pytest

from lib.translation.chem_comp import ChemComp

@pytest.fixture
def test_data_file():
    path_1 = Path.cwd() / '..' / '..' / 'data' / 'chem_comp'/ 'protein+Ala+msd_ccpnRef_2007-12-11-10-20-09_00022.json'
    path_2 = Path.cwd() / 'data' / 'chem_comp'/ 'protein+Ala+msd_ccpnRef_2007-12-11-10-20-09_00022.json'

    if path_1.exists():
        result=path_1
    elif path_2.exists():
        result = path_2
    else:
        msg = """\
            can't find the test chemcomp file, tried the following paths
            {path_1}
            {path_2}
        """
        Exception(msg)

    return result

def test_read_chemcomp_ala(test_data_file):

    with open(test_data_file, "r") as f:

        chemcomp_data = json.load(f)
        ChemComp(**chemcomp_data)

    assert True


def test_link_and_unlink_checm_com_ala(test_data_file):

    with open(test_data_file, "r") as f:

        loaded_json = f.read()
        chemcomp_data = json.loads(loaded_json)
        chem_comp = ChemComp(**chemcomp_data)

        # to normalise the spacing
        output_json = json.dumps(json.loads(chem_comp.json()),indent=4)

        assert loaded_json == output_json


