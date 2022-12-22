from typing import List

from nef_pipelines.lib.structures import SequenceResidue

PSF_FILE_IDENTIFIER = "PSF"  # text  expected on the first line of a psf file
PSF_NUM_NATOM_FIELDS = 2  # number of fields on the !NATOM line
PSF_NATOM_BLOCK_KEY_WORD = "!NATOM"  # idenifier for the !NATOM block
PSF_NATOM_COUNT_INDEX = 0  # index on the !NATOM line of the number of atoms
PSF_NATOM_KEY_WORD_INDEX = 1  # index on the !NATOM line of the !NATOM keyword
XPLOR_PSF_NUM_ATOM_FIELDS = 9  # number of fields in each NATOM block line

PSF_SEGID_INDEX = 1  # index of the segid in a line of the NATOM block
PSF_RESID_INDEX = 2  # index of the resid in a line of the NATOM block
PSF_ATOM_NAME_INDEX = 3  # index of the atom name  in a line of the NATOM block


def parse_xplor_PSF(text: str, file_name: str = "unknown") -> List[SequenceResidue]:
    in_data = False
    data_count = 0
    natom = None

    residues = set()
    for line_no, line in enumerate(text.split("\n"), start=1):
        if line_no == 1:
            if line.strip() != PSF_FILE_IDENTIFIER:
                msg = f"the first line of a PSF file should be '{PSF_FILE_IDENTIFIER}' i got '{line.rstrip()}'"
                raise_parse_exception(file_name, line_no, line, msg)

        if line_no > 1 and not in_data:
            fields = line.strip().split()
            if (
                len(fields) == PSF_NUM_NATOM_FIELDS
                and fields[PSF_NATOM_KEY_WORD_INDEX] == PSF_NATOM_BLOCK_KEY_WORD
            ):
                in_data = True
                try:
                    natom = int(fields[PSF_NATOM_COUNT_INDEX])
                except ValueError:
                    msg = "can't convert natom to an int"
                    raise_parse_exception(file_name, line_no, line, msg)

            continue

        if in_data and data_count >= natom:
            in_data = False
            break

        if in_data:
            data_count += 1
            fields = line.split()

            num_fields = len(fields)

            if num_fields != XPLOR_PSF_NUM_ATOM_FIELDS:
                msg = f"there are {num_fields} fields for atom number {data_count}; \
                        i expected {XPLOR_PSF_NUM_ATOM_FIELDS}"
                raise_parse_exception(file_name, line_no, line, msg)

            chain_code = fields[PSF_SEGID_INDEX]
            try:
                sequence_code = int(fields[PSF_RESID_INDEX])
            except ValueError:
                msg = f"i couldn't convert the residue number [field {PSF_RESID_INDEX}] to an integer, \
                      value was: {fields[PSF_RESID_INDEX]}"
                raise_parse_exception(file_name, line_no, line, msg)

            residue_type = fields[PSF_ATOM_NAME_INDEX]

            residue = SequenceResidue(
                chain_code=chain_code,
                sequence_code=sequence_code,
                residue_name=residue_type,
            )
            residues.add(residue)

    if natom != data_count:
        msg = (
            f" !unexpected! expected to read {natom} atoms but got {data_count} instead"
        )
        raise_parse_exception(file_name, line_no, line, msg)

    if not residues:
        msg = "no residues found!"
        raise_parse_exception(file_name, line_no, line, msg)

    residues = list(residues)
    residues.sort()

    return tuple(residues)


class PSFParseException(Exception):
    ...


def raise_parse_exception(file_name, line_no, line, specific_message):
    msg = f"""\
            Error: {specific_message}\
                at line {line_no}
                in file {file_name}
                line was "{line}"
        """
    raise PSFParseException(msg)
