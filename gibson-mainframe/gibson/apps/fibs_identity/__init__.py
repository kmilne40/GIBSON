"""Local FIBS BANK OAuth/OIDC/JWT training simulator.

This is a bounded local simulator for Gibson labs.  It does not contact an
external identity provider and it does not provide production identity security.
"""
from .oauth_server import discovery, jwks, authorize, token, introspect, revoke, lab_jwt_forge, lab_oauth_authorize, lab_oauth_token, lab_oauth_refresh
