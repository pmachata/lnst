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

    logging.info("=== UL migration")
    # - Test underlay migration: create a dummy in one VRF, then offload a
    #   tunnel and move the dummy to another VRF.
    logging.info("--- Simple")
    with vrf(sw) as vrf_u, \
         vrf(sw) as vrf_o:
        connect_host_ifaces(sw, sw_if1, vrf_o, sw_if2, vrf_u)
        sw_if1.reset()
        sw_if2.reset()
        add_forward_route(sw, vrf_u, "1.2.3.5")

        with encap_route(m2, vrf_None, 1, "gre1", ip=ipv4), \
             encap_route(m2, vrf_None, 1, "gre1", ip=ipv6), \
             dummy(sw, vrf_o, ip=["1.2.3.4/32"]) as d, \
             gre(sw, d, vrf_o,
                 tos="inherit",
                 local_ip="1.2.3.4",
                 remote_ip="1.2.3.5") as g, \
             encap_route(sw, vrf_o, 2, g, ip=ipv4), \
             encap_route(sw, vrf_o, 2, g, ip=ipv6):

            sw.run("ip l set dev %s master %s" % (d.get_devname(), vrf_u))

            tl.wait_for_if(ifaces)
            ping_test(tl, m1, sw, ipv6(onet2_ip(ctl, 33, [])), m1_if1, g,
                    ipv6=True)
            ping_test(tl, m1, sw, ipv4(onet2_ip(ctl, 33, [])), m1_if1, g)

    logging.info("=== OL migration")
    with encap_route(m2, vrf_None, 1, "gre1", ip=ipv4), \
         encap_route(m2, vrf_None, 1, "gre1", ip=ipv6):

        sw_if1.reset()
        sw_if2.reset()
        add_forward_route(sw, vrf_None, "1.2.3.5")

        # N.B. overlay migration to non-default is tested implicitly by many,
        # many tests as the device is first created in default VRF, and only
        # then moved to the right VRF. So just test migration back outside.
        logging.info("--- To default")
        with vrf(sw) as vrf1, \
             gre(sw, None, vrf1,
                 tos="inherit",
                 local_ip="1.2.3.4",
                 remote_ip="1.2.3.5",
                 ip=["1.2.3.4/32"]) as g:

            sleep(5)
            sw.run("ip link set dev %s nomaster" % g.get_devname())

            with encap_route(sw, vrf_None, 2, g, ip=ipv4), \
                 encap_route(sw, vrf_None, 2, g, ip=ipv6):
                tl.wait_for_if(ifaces)
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
