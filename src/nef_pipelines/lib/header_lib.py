import datetime
from random import randint

from pynmrstar import Loop, Saveframe

from nef_pipelines.lib.constants import NEF_PIPELINES, NEF_VERSION


def get_creation_time():
    return datetime.datetime.now().isoformat()


def get_uuid(name, creation_time):
    random_value = "".join(["{}".format(randint(0, 9)) for _ in range(10)])
    return f"{name}-{creation_time}-{random_value}"


def create_header_frame(program_name, program_version, script_name):
    frame = Saveframe.from_scratch("nef_nmr_meta_data", "nef_nmr_meta_data")

    frame.add_tag("sf_category", "nef_nmr_meta_data")
    frame.add_tag("sf_framecode", "nef_nmr_meta_data")
    frame.add_tag("format_name", "nmr_exchange_format")
    frame.add_tag("nef_nmr_meta_data.format_version", NEF_VERSION)
    frame.add_tag("program_name", program_name)
    frame.add_tag("script_name", script_name)
    frame.add_tag("program_version", program_version)

    creation_date = get_creation_time()
    uuid = get_uuid(NEF_PIPELINES, creation_date)
    frame.add_tag("creation_date", creation_date)
    frame.add_tag("uuid", uuid)

    loop = Loop.from_scratch("nef_run_history")
    frame.add_loop(loop)

    history_tags = "run_number", "program_name", "program_version", "script_name"
    loop.add_tag(history_tags)

    return frame
