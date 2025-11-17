# update-workflows

Run this tool to update `.github/workflows/*.yml` files based on a comment on the first line:

```bash
python -m update_workflows
```
If a workflow file starts with a comment like this:

```yaml
# simonw/python-test
...
```
The command will fetch the latest version of that workflow from the [simonw/actions-workflows](https://github.com/simonw/actions-workflows) repository and update the file accordingly.
