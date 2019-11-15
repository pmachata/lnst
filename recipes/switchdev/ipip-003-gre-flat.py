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
    m1_if1.add_nhs_route(ipv6(onet2_ip(ctl, 0)), [ipv6(onet1_ip(ctl, 1, []))])
    m2_if1.add_nhs_route("1.2.3.4/32", [ipv4(unet_ip(ctl, 1, []))])

    vrf_None = None
    tl = TestLib(ctl, aliases)

    logging.info("=== Flat configuration in non-default VRF")
    with encap_route(m2, vrf_None, 1, "gre1", ip=ipv4), \
         encap_route(m2, vrf_None, 1, "gre1", ip=ipv6), \
         vrf(sw) as vrf1, \
         dummy(sw, vrf_None, ip=["1.2.3.4/32"]) as d, \
         gre(sw, None, vrf1,
             tos="inherit",
             local_ip="1.2.3.4",
             remote_ip="1.2.3.5") as g, \
         encap_route(sw, vrf1, 2, g, ip=ipv4), \
         encap_route(sw, vrf1, 2, g, ip=ipv6):

	sw.run("ip l set dev %s master %s" % (sw_if1.get_devname(), vrf1))
        sw_if1.reset()
        add_forward_route(sw, vrf_None, "1.2.3.5")
        tl.wait_for_if(ifaces)

        ping_test(tl, m1, sw, ipv6(onet2_ip(ctl, 33, [])), m1_if1, g,
                  ipv6=True)
        ping_test(tl, m1, sw, ipv4(onet2_ip(ctl, 33, [])), m1_if1, g)

    logging.info("=== Flat configuration in default VRF")
    with encap_route(m2, vrf_None, 1, "gre1", ip=ipv4), \
         encap_route(m2, vrf_None, 1, "gre1", ip=ipv6):

        sw_if1.reset()
        sw_if2.reset()
        add_forward_route(sw, vrf_None, "1.2.3.5")

        # - Set up encap route before decap route.
        # - Tear down encap route before decap route.
        logging.info("--- Eup, Dup, Edown, Ddown")
        with dummy(sw, vrf_None) as d, \
             gre(sw, None, vrf_None,
                 tos="inherit",
                 local_ip="1.2.3.4",
                 remote_ip="1.2.3.5") as g, \
             encap_route(sw, vrf_None, 2, g, ip=ipv4), \
             encap_route(sw, vrf_None, 2, g, ip=ipv6):

            sleep(5)
            d.set_addresses(["1.2.3.4/32"])
            tl.wait_for_if(ifaces)
            ping_test(tl, m1, sw, ipv6(onet2_ip(ctl, 33, [])), m1_if1, g,
                      ipv6=True)
            ping_test(tl, m1, sw, ipv4(onet2_ip(ctl, 33, [])), m1_if1, g)

        # - Set up decap route before encap route.
        # - Tear down decap route before encap route.
        logging.info("--- Dup, Eup, Ddown, Edown")
        with dummy(sw, vrf_None, ip=["1.2.3.4/32"]) as d, \
             gre(sw, None, vrf_None,
                 tos="inherit",
                 local_ip="1.2.3.4",
                 remote_ip="1.2.3.5") as g:

            with encap_route(sw, vrf_None, 2, g, ip=ipv4), \
                 encap_route(sw, vrf_None, 2, g, ip=ipv6):
                sleep(30)
                ping_test(tl, m1, sw, ipv6(onet2_ip(ctl, 33, [])), m1_if1, g,
                          ipv6=True)
                ping_test(tl, m1, sw, ipv4(onet2_ip(ctl, 33, [])), m1_if1, g)

            d.set_addresses([])
            g.set_addresses([])

        logging.info("--- Bound device in flat config")
        with dummy(sw, vrf_None, ip=["1.2.3.4/32"]) as d, \
             gre(sw, d, vrf_None,
                 tos="inherit",
                 local_ip="1.2.3.4",
                 remote_ip="1.2.3.5") as g, \
             encap_route(sw, vrf_None, 2, g, ip=ipv4), \
             encap_route(sw, vrf_None, 2, g, ip=ipv6):
                sleep(30)
                ping_test(tl, m1, sw, ipv6(onet2_ip(ctl, 33, [])), m1_if1, g,
                          ipv6=True)
                ping_test(tl, m1, sw, ipv4(onet2_ip(ctl, 33, [])), m1_if1, g)

        logging.info("--- No dummy")
        with gre(sw, None, vrf_None,
                 tos="inherit",
                 local_ip="1.2.3.4",
                 remote_ip="1.2.3.5",
                 ip=["1.2.3.4/32"]) as g, \
             encap_route(sw, vrf_None, 2, g, ip=ipv4), \
             encap_route(sw, vrf_None, 2, g, ip=ipv6):

            sleep(30)
            ping_test(tl, m1, sw, ipv6(onet2_ip(ctl, 33, [])), m1_if1, g,
                      ipv6=True)
            ping_test(tl, m1, sw, ipv4(onet2_ip(ctl, 33, [])), m1_if1, g)


do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("machine2").get_interface("if1"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2")],
        ctl.get_aliases())
