# update-workflows

Run this tool to update `.github/workflows/*.yml` files based on a configuration file.

## Usage

```bash
python -m update_workflows
```

This reads `.github/workflows.yml` which contains references to workflow templates:

```yaml
- simonw/python-test
- simonw/python-publish
```

Or with custom filenames:

```yaml
test: simonw/python-test
publish: simonw/python-publish
```

The command will fetch the latest version of each workflow from the [simonw/actions-workflows](https://github.com/simonw/actions-workflows) repository and update the corresponding files in `.github/workflows/`.

### List Format

When using the list format, the workflow filename is derived from the template name:

```yaml
- simonw/python-test
```

This creates/updates `.github/workflows/python-test.yml`

### Dict Format

When using the dict format, you specify custom filenames:

```yaml
test: simonw/python-test
publish: simonw/python-publish
```

This creates/updates:
- `.github/workflows/test.yml`
- `.github/workflows/publish.yml`

## CLI Options

```bash
# Dry-run mode (shows what would be updated)
python -m update_workflows --dry-run

# Custom workflows directory
python -m update_workflows --workflows-dir custom/path
```
