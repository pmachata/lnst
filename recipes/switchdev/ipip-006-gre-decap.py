"""
Copyright 2017 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
petrm@mellanox.com (Petr Machata)
"""

from lnst.Controller.Task import ctl
from TestLib import TestLib, vrf, dummy, gre
from ipip_common import ping_test, encap_route, \
                        add_forward_route, connect_host_ifaces, \
                        onet1_ip, onet2_ip, unet_ip, ipv4, ipv6, refresh_addrs
from time import sleep
import logging

def do_task(ctl, hosts, ifaces, aliases):
    m1, m2, sw = hosts
    (m1_if1_10, m1_if1_20,
     m2_if1_10, m2_if1_20,
     sw_if1_10, sw_if1_20,
     sw_if2_10, sw_if2_20) = ifaces

    m2_if1_10.add_nhs_route("1.2.3.4/32", [ipv4(unet_ip(ctl, 1, []))])
    m2_gre1 = m2.get_interface("gre1")

    vrf_None = None
    tl = TestLib(ctl, aliases)

    logging.info("=== Decap-only flow tests")
    logging.info("--- default VRF")
    with encap_route(m2, vrf_None, 1, "gre1",
                     ip=ipv4, src=ipv4(onet2_ip(ctl, 33, []))), \
         encap_route(m2, vrf_None, 1, "gre1", ip=ipv6), \
         gre(sw, None, vrf_None,
             tos="inherit",
             local_ip="1.2.3.4",
             remote_ip="1.2.3.5") as g:

        with dummy(sw, vrf_None, ip=["1.2.3.4/32"]) as d:
            add_forward_route(sw, vrf_None, "1.2.3.5")
            sleep(30)

            ping_test(tl, m2, sw, ipv6(onet1_ip(ctl, 33, [])), m2_gre1, g,
                      ipv6=True)
            ping_test(tl, m2, sw, ipv4(onet1_ip(ctl, 33, [])), m2_gre1, g)

            # Make sure that downing a tunnel makes the decap flow stop working.
            logging.info("--- set a tunnel down")
            g.set_link_down()
            sleep(5)

            ping_test(tl, m2, sw, ipv6(onet1_ip(ctl, 33, [])), m2_gre1, g,
                      count=25, fail_expected=True, ipv6=True)
            ping_test(tl, m2, sw, ipv4(onet1_ip(ctl, 33, [])), m2_gre1, g,
                      count=25, fail_expected=True)

        # `g' is now down, and no local decap route exists, because `d' went
        # away. Test adding an address directly to `g' and make sure that it
        # isn't offloaded.
        logging.info("--- add decap route to a down tunnel")
        g.set_addresses(["1.2.3.4/32"])
        sleep(5)

        ping_test(tl, m2, sw, ipv6(onet1_ip(ctl, 33, [])), m2_gre1, g,
                  count=25, fail_expected=True, ipv6=True)
        ping_test(tl, m2, sw, ipv4(onet1_ip(ctl, 33, [])), m2_gre1, g,
                  count=25, fail_expected=True)

        # Now set the tunnel back up and test that it again all works.
        g.set_link_up()
        sleep(5)

        ping_test(tl, m2, sw, ipv6(onet1_ip(ctl, 33, [])), m2_gre1, g,
                  ipv6=True)
        ping_test(tl, m2, sw, ipv4(onet1_ip(ctl, 33, [])), m2_gre1, g)

    with vrf(sw) as vrf_u, \
         vrf(sw) as vrf_o, \
         dummy(sw, vrf_u, ip=["1.2.3.4/32"]) as d, \
         encap_route(m2, vrf_None, 1, "gre1",
                     ip=ipv4, src=ipv4(onet2_ip(ctl, 33, []))), \
         encap_route(m2, vrf_None, 1, "gre1", ip=ipv6):

        connect_host_ifaces(sw, sw_if1_10, vrf_o, sw_if2_10, vrf_u)
        refresh_addrs(sw, sw_if1_10)
        add_forward_route(sw, vrf_u, "1.2.3.5")

        with gre(sw, d, vrf_o,
                 tos="inherit",
                 local_ip="1.2.3.4",
                 remote_ip="1.2.3.5") as g:

            logging.info("--- hierarchical configuration")
            sleep(30)

            ping_test(tl, m2, sw, ipv6(onet1_ip(ctl, 33, [])), m2_gre1, g,
                      ipv6=True)
            ping_test(tl, m2, sw, ipv4(onet1_ip(ctl, 33, [])), m2_gre1, g)

            # Make sure that downing an underlay device doesn't make the decap
            # flow stop working. There is a complementary test in ipip-010 to
            # test that encap stops working.
            logging.info("--- set an underlay down")
            d.set_link_down()
            sleep(5)

            ping_test(tl, m2, sw, ipv6(onet1_ip(ctl, 33, [])), m2_gre1, g,
                      ipv6=True)
            ping_test(tl, m2, sw, ipv4(onet1_ip(ctl, 33, [])), m2_gre1, g)

        # Make sure that when a newly-created tunnel has a down underlay, decap
        # still works. There's a complementary test in ipip-010 to test that
        # encap doesn't work in that scenario.
        logging.info("--- create tunnel with a down underlay")
        d.set_link_down() # Should be down already, but make this robust against
                          # later coding changes.
        with gre(sw, d, vrf_o,
                 tos="inherit",
                 local_ip="1.2.3.4",
                 remote_ip="1.2.3.5") as g:

            ping_test(tl, m2, sw, ipv6(onet1_ip(ctl, 33, [])), m2_gre1, g,
                      ipv6=True)
            ping_test(tl, m2, sw, ipv4(onet1_ip(ctl, 33, [])), m2_gre1, g)

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1.10"),
         ctl.get_host("machine1").get_interface("if1.20"),
         ctl.get_host("machine2").get_interface("if1.10"),
         ctl.get_host("machine2").get_interface("if1.20"),
         ctl.get_host("switch").get_interface("if1.10"),
         ctl.get_host("switch").get_interface("if1.20"),
         ctl.get_host("switch").get_interface("if2.10"),
         ctl.get_host("switch").get_interface("if2.20")],
        ctl.get_aliases())
