from nef_pipelines.lib.util import exit_error


def _exit_if_no_frames_selected(frames):
    if len(frames) == 0:
        exit_error("no shift frames selected")


def _filter_shifts_by_chain(shifts, chain):
    return [shift for shift in shifts if shift.atom.residue.chain_code == chain]


def _exit_no_chain_selected(chains_codes):
    if len(chains_codes) == 0:
        exit_error("no chain was selected, please specify a chain with -c")


def _select_target_chain_from_sequence_if_not_defined(target_chain, shift_chains):
    if target_chain is None:
        num_shift_chains = len(shift_chains)
        if num_shift_chains == 1:
            target_chain = shift_chains[0]
        elif num_shift_chains != 0:
            _exit_no_chain_selected(shift_chains)
    return target_chain
