# Plan: `nef plot bar` — bar chart from a loop column

## Context

New command that reads a numeric column from any NEF loop and renders it as a bar chart
saved to a file. Primary use case: visualise RCI values along sequence, but generic enough
for any numeric loop column (relaxation rates, peak intensities, etc.).

Modelled on the existing (awaiting) `correlations.py` and `relaxation.py` tools already in
`src/nef_pipelines/tools/plot/`.

---

## Command

```
nefl plot bar [FRAME_SELECTORS]... --column COLUMN [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `-i / --in` | stdin | NEF input |
| `--column` | required | Column name to use as bar heights (e.g. `rci_value`) |
| `--loop` | auto | Loop category; required only if frame has >1 loop |
| `--label-column` | auto | Column for x-axis labels; defaults to `sequence_code` if present, else row index |
| `--title` | column name | Chart title |
| `--x-label` | label column name | X-axis label |
| `--y-label` | column name | Y-axis label |
| `-o / --out` | `bar_{column}.{format}` | Output file path |
| `-f / --format` | `pdf` | Output format; validated against `FILE_FORMATS` from `plot_lib` |
| `--paper-size` | `a4` | Paper size; from `PAPER_SIZES` in `plot_lib` |
| `--orientation` | `portrait` | `portrait` or `landscape` |
| `--colour` | `steelblue` | Bar fill colour (British spelling) |

The command **passes the NEF stream through unchanged** (prints entry to stdout) and writes
the chart to `--out`, consistent with the pipeline model.

---

## Implementation

### New file
`src/nef_pipelines/tools/plot/bar.py`

### Activate `plot_lib`
Rename `plot_lib.py.awaiting` → `plot_lib.py` so `FILE_FORMATS` and `PAPER_SIZES`
are importable. (Both `correlations.py` and `relaxation.py` already import from it.)

### Registration
Add to `src/nef_pipelines/tools/plot/__init__.py` inside the existing
`try: import matplotlib` block:
```python
import nef_pipelines.tools.plot.bar  # noqa: F401
```

### Matplotlib backend (top of `bar.py`, matching `correlations.py`)
```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
```

### Core structure (`bar.py`)

```python
@plot_app.command()
def bar(
    frame_selectors: List[str] = typer.Argument(None, ...),
    in_path: Path = typer.Option(STDIN, "-i", "--in", ...),
    column: str = typer.Option(..., "--column", ...),
    loop_category: Optional[str] = typer.Option(None, "--loop", ...),
    label_column: Optional[str] = typer.Option(None, "--label-column", ...),
    title: Optional[str] = typer.Option(None, "--title", ...),
    x_label: Optional[str] = typer.Option(None, "--x-label", ...),
    y_label: Optional[str] = typer.Option(None, "--y-label", ...),
    output: str = typer.Option("bar_{column}.{format}", "-o", "--out", ...),
    plot_format: str = typer.Option("pdf", "-f", "--format", ...),
    paper_size: str = typer.Option("a4", "--paper-size", ...),
    orientation: str = typer.Option("portrait", "--orientation", ...),
    colour: str = typer.Option("steelblue", "--colour", ...),
):
```

Worker function `_bar(frames, column, loop_category, label_column, title, x_label,
y_label, output, plot_format, paper_size, orientation, colour)`:

1. Validate `plot_format` against `FILE_FORMATS`; `exit_error` if unknown
2. Validate `paper_size` against `PAPER_SIZES`; `exit_error` if unknown
3. Resolve output filename (expand `{column}` and `{format}` placeholders)
4. For each matching frame, find target loop:
   - If `--loop` given: `frame.get_loop(loop_category)`
   - Else: auto-detect single loop; `exit_error` if frame has >1 loop and `--loop` omitted
5. Iterate rows with `loop_row_namespace_iter(loop)`; collect `(label, float(value))` pairs,
   skipping rows where value is `"."` / blank
6. `exit_error` if no numeric values found
7. Compute figure size from `PAPER_SIZES[paper_size]`, swap w/h if `orientation == "landscape"`
8. Build chart: `plt.bar(labels, values, color=colour)`
9. Apply title / axis labels
10. Save:
    - PDF → `with PdfPages(output) as pdf: pdf.savefig(fig, dpi=300)`
    - Other → `plt.savefig(output, dpi=300, bbox_inches="tight")`
11. `plt.close(fig)`

Then print entry unchanged to stdout.

---

## Key reuse

| What | Where |
|---|---|
| `loop_row_namespace_iter()` | `src/nef_pipelines/lib/nef_lib.py` |
| `read_entry_from_file_or_stdin_or_exit_error()` | `src/nef_pipelines/lib/nef_lib.py` |
| `select_frames()` + `SelectionType` | `src/nef_pipelines/lib/nef_lib.py` |
| `exit_error()`, `STDIN` | `src/nef_pipelines/lib/util.py` |
| `FILE_FORMATS`, `PAPER_SIZES` | `src/nef_pipelines/tools/plot/plot_lib.py` (activate from `.awaiting`) |
| `plot_app` | `src/nef_pipelines/tools/plot/__init__.py` |
| matplotlib already a dep | `setup.cfg` |

---

## Example usage

```bash
# RCI bar chart piped directly from calculate
nefl rci calculate --in PyJCScorr_seq.nef \
  | nefl plot bar nefpls_rci_list --column rci_value -o rci.pdf

# PNG output, custom labels
nefl plot bar nef_chemical_shift_list --column value \
  --label-column atom_name --format png --in shifts.nef -o shifts.png
```

---

## Tests

File: `src/nef_pipelines/tests/tools/plot/test_bar.py`
Test data: `src/nef_pipelines/tests/tools/plot/test_data/rci_output.nef`
(small NEF with a `nefpls_rci_list` frame — generate once from `nefl rci calculate`)

| Test | What it checks |
|---|---|
| `test_bar_produces_pdf` | exit_code=0, output file exists, non-empty |
| `test_bar_passes_through_nef` | stdout is a valid NEF entry (unchanged) |
| `test_bar_missing_column_exits_error` | `--column nonexistent` → non-zero exit |
| `test_bar_ambiguous_loop_exits_error` | frame with 2 loops, no `--loop` → non-zero exit |
| `test_bar_invalid_format_exits_error` | `--format xyz` → non-zero exit |

All tests use `run_and_report()`, `path_in_test_data()`, never bare asserts on NEF content.
