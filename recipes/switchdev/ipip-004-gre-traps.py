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
                        onet1_ip, onet2_ip, unet_ip, ipv4, ipv6
from time import sleep
import logging

def do_task(ctl, hosts, ifaces, aliases):
    m1, m2, sw = hosts
    m1_if1, m2_if1, sw_if1, sw_if2 = ifaces

    m1_if1.add_nhs_route(ipv4(onet2_ip(ctl, 0)), [ipv4(onet1_ip(ctl, 1, []))])
    m2_if1.add_nhs_route("1.2.3.4/32", [ipv4(unet_ip(ctl, 1, []))])
    m2_gre3 = m2.get_interface("gre3")

    vrf_None = None
    tl = TestLib(ctl, aliases)

    # Test that non-IPIP traffic gets to slow path.
    with dummy(sw, vrf_None, ip=["1.2.3.4/32"]) as d, \
         gre(sw, None, vrf_None,
             tos="inherit",
             local_ip="1.2.3.4",
             remote_ip="1.2.3.5") as g, \
         encap_route(sw, vrf_None, 2, g, ip=ipv4):
        tl.wait_for_if(ifaces)
        ping_test(tl, m2, sw, "1.2.3.4", m2_if1, g, count=20)

    # Configure the wrong interface on M2 to test that the traffic gets trapped
    # to CPU.
    with encap_route(m2, vrf_None, 1, "gre3"):

        add_forward_route(sw, vrf_None, "1.2.3.5")

        with dummy(sw, vrf_None, ip=["1.2.3.4/32"]) as d, \
             gre(sw, None, vrf_None,
                 local_ip="1.2.3.4",
                 remote_ip="1.2.3.5") as g:
            tl.wait_for_if(ifaces)

            before_stats = sw_if2.link_stats()["rx_packets"]
            ping_test(tl, m2, sw, ipv4(onet1_ip(ctl, 33, [])), m2_gre3, g,
                      count=20, fail_expected=True)
            after_stats = sw_if2.link_stats()["rx_packets"]
            delta = after_stats - before_stats
            if delta < 15:
                tl.custom(sw, "ipip",
                        "Too few packets (%d) observed in slow path" % delta)

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("machine2").get_interface("if1"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2")],
        ctl.get_aliases())
