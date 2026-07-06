from gibson.net.service_profiles import FTP_ZOS, HTTP_DASHBOARD, TN3270E, VTAM_TELNET


def test_service_profiles_no_longer_spoof_ibm_runtime_identities():
    assert FTP_ZOS.nmap_service == "ftp"
    assert "Gibson" in FTP_ZOS.nmap_version
    assert "Gibson" in TN3270E.nmap_version
    assert "Gibson" in VTAM_TELNET.nmap_version
    assert "Server" not in HTTP_DASHBOARD.headers


def test_removed_rest_profile_is_not_exported():
    import gibson.net.service_profiles as profiles
    assert not hasattr(profiles, "REST_GATEWAY")
