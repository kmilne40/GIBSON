"""EZRecon - reconnaissance & assessment toolkit as an ISPF panel application.

Reached from the ISPF Management menu (option M.5).  Presents EZRecon's toolset
(github.com/kmilne40/EZRecon: nmap, hydra, shodan, google-dork, geolocation,
dangling-DNS, subdomains, report) as a professional full-screen 3270 panel,
driving Gibson's existing offline recon fixtures so it stays self-contained.
"""
from gibson.apps.ezrecon3270.ezrecon_session import EzRecon3270Session
__all__ = ["EzRecon3270Session"]
