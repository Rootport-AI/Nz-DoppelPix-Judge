import unittest

from nz_doppelpix_judge.network_access import NetworkAccessControl, client_is_allowed


class NetworkAccessTests(unittest.TestCase):
    def test_disabled_allows_loopback_and_local_machine_addresses(self) -> None:
        local_addresses = {"192.168.1.10"}

        self.assertTrue(client_is_allowed("127.0.0.1", False, local_addresses))
        self.assertTrue(client_is_allowed("::1", False, local_addresses))
        self.assertTrue(client_is_allowed("::ffff:127.0.0.1", False, local_addresses))
        self.assertTrue(client_is_allowed("192.168.1.10", False, local_addresses))

    def test_disabled_blocks_other_network_clients(self) -> None:
        self.assertFalse(client_is_allowed("192.168.1.20", False, {"192.168.1.10"}))

    def test_enabled_allows_other_network_clients(self) -> None:
        self.assertTrue(client_is_allowed("192.168.1.20", True, {"192.168.1.10"}))

    def test_access_control_state_can_be_toggled(self) -> None:
        access_control = NetworkAccessControl(local_network_enabled=False)

        self.assertFalse(access_control.is_local_network_enabled())
        access_control.set_local_network_enabled(True)
        self.assertTrue(access_control.is_local_network_enabled())


if __name__ == "__main__":
    unittest.main()
