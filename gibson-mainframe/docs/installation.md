# Gibson v17 Installation Notes

The installer now checks whether the selected Python interpreter can create virtual environments. If `python -m venv` support is missing, the installer detects the Python major/minor version and, on Debian/Ubuntu-style systems, attempts the version-specific package first, such as `python3.12-venv`, then falls back to `python3-venv`.

Automatic installation only runs when a supported package manager is detected and root or `sudo` is available. `--skip-deps` and offline workflows are preserved: in those modes the installer prints the required package and exits cleanly instead of running package-manager commands.

Typical manual commands are:

```bash
sudo apt-get update
sudo apt-get install -y python3.12-venv
# or
sudo apt-get install -y python3-venv
```
