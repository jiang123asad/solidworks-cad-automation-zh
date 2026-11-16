"""Filesystem-only batch helpers; safe to import without SolidWorks/pywin32."""
from contextlib import contextmanager
from pathlib import Path
import glob
import os
import shutil
import tempfile
import warnings


def expand_inputs(patterns, suffixes=('.sldprt',)):
    paths = []
    seen = set()
    for pattern in patterns:
        hits = glob.glob(pattern) if glob.has_magic(pattern) else [pattern]
        if not hits:
            raise FileNotFoundError(pattern)
        for hit in sorted(hits):
            p = Path(hit).resolve(strict=True)
            if not p.is_file() or p.suffix.lower() not in suffixes:
                raise ValueError('Unsupported input: %s' % p)
            key = os.path.normcase(str(p))
            if key not in seen:
                seen.add(key)
                paths.append(p)
    if not paths:
        raise ValueError('No input files')
    return paths


def plan_outputs(files, outdir, extensions=None):
    outdir = Path(outdir).resolve()
    outputs, seen = [], set()
    for src in files:
        for ext in extensions or [src.suffix]:
            dst = outdir / (src.stem + ext)
            key = os.path.normcase(str(dst)).casefold()
            if key in seen:
                raise ValueError('Output name collision: %s' % dst)
            seen.add(key)
            if dst.exists():
                raise FileExistsError(dst)
            if key == os.path.normcase(str(src.resolve())).casefold():
                raise ValueError('Source and destination are identical')
            outputs.append(dst)
    return outputs


@contextmanager
def staged_file(destination, source=None):
    """Publish only on normal exit, without replacing an existing destination.

    The private directory lives beside the output, on the same filesystem.
    Windows os.rename rejects an existing destination (also closes the race
    between the preflight and publishing). This skill targets Windows only.
    """
    destination = Path(destination).resolve()
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # SW may retain an empty staging directory as its process working directory.
    # TemporaryDirectory's permission-repair recursion can mask a successful save.
    tmp = Path(tempfile.mkdtemp(prefix='.sw-stage-', dir=destination.parent)).resolve()
    try:
        staged = Path(tmp) / destination.name
        if source is not None:
            source = Path(source).resolve(strict=True)
            if source == destination:
                raise ValueError('Source and destination are identical')
            shutil.copy2(source, staged)
        yield staged
        if not staged.is_file() or staged.stat().st_size == 0:
            raise RuntimeError('No nonempty output generated: %s' % staged)
        if destination.exists():
            raise FileExistsError(destination)
        os.rename(str(staged), str(destination))
    finally:
        if tmp.parent != destination.parent or not tmp.name.startswith('.sw-stage-'):
            raise RuntimeError('Unexpected staging directory: %s' % tmp)
        shutil.rmtree(tmp, ignore_errors=True)
        if tmp.exists():
            warnings.warn('SolidWorks retained staging directory; left for later cleanup: %s' % tmp)
