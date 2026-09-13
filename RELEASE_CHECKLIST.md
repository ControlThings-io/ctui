# Release checklist

Run this checklist from a clean checkout of the commit intended for release.
Replace `1.0.0` in the commands when preparing a later version.

## Prepare

- [ ] Confirm `pyproject.toml` contains the intended version.
- [ ] Confirm `CHANGELOG.md` describes that version and uses the release date.
- [ ] Confirm `uv.lock` is current with `uv lock --check`.
- [ ] Confirm `git status --short` is empty.
- [ ] Review the comparison with the previous release tag.
- [ ] Confirm the `pypi` GitHub environment and PyPI trusted publisher target
      this repository and `.github/workflows/publish.yml`.

## Verify source

```bash
uv sync --locked --python 3.11
uv run --python 3.11 black --check src tests examples
uv run --python 3.11 isort --check-only src tests examples
uv run --python 3.11 python -m unittest discover -s tests -v
```

The GitHub Actions test workflow must also pass on every supported Python and
operating-system combination.

## Verify distributions

Remove or move any previous `dist/` directory, then run:

```bash
uv build
uv run --isolated --no-project --with dist/*.whl tests/smoke_test.py
uv run --isolated --no-project --with dist/*.tar.gz tests/smoke_test.py
```

Inspect both archives. They should contain the license; the source archive
should contain `README.md`, and the wheel metadata should contain its rendered
project description. Both metadata files should report the intended name,
version, Python requirement, dependencies, and project URLs.

## Release

- [ ] Commit all release preparation changes and obtain a passing branch build.
- [ ] Create and push an annotated tag matching the package version:

```bash
git tag -a v1.0.0 -m "ctui 1.0.0"
git push origin v1.0.0
```

- [ ] Watch the **Publish release to PyPI** workflow through verification,
      artifact smoke tests, attestation, publication, and GitHub release
      creation.
- [ ] Do not reuse a failed or incorrect release version; fix the problem and
      increment the version according to semantic versioning.

## Verify publication

- [ ] Confirm the PyPI project displays the README and correct metadata.
- [ ] Confirm PyPI provides both the wheel and source distribution plus their
      attestations.
- [ ] Confirm the generated GitHub release is attached to the correct tag.
- [ ] Install from PyPI in a new environment and run an import check:

```bash
uv run --isolated --no-project --with ctui==1.0.0 python -c \
  "import ctui; print(ctui.__version__)"
```

- [ ] Run at least one tutorial against the published package or a minimal
      external application before announcing the release.
