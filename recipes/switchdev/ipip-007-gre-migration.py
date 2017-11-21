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

            sleep(30)
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
                sleep(30)
                ping_test(tl, m1, sw, ipv6(onet2_ip(ctl, 33, [])), m1_if1, g,
                          ipv6=True)
                ping_test(tl, m1, sw, ipv4(onet2_ip(ctl, 33, [])), m1_if1, g)

    # IPv4 should go through g4, IPv6 through g6, but g4 starts out in the
    # wrong VRF. Thus there's no conflict and both g4 and g6 are offloaded.
    # When the configuration of g4 is fixed, both tunnels are forced to slow
    # path, but now they both work.
    # There's a similar test in ipip-010 for local address change.
    logging.info("--- That causes local conflict")
    with vrf(sw) as vrf1, \
         \
         encap_route(m2, vrf_None, 1, "gre1", ip=ipv4), \
         gre(sw, None, vrf1,
             tos="inherit",
             local_ip="1.2.3.4",
             remote_ip="1.2.3.5",
             ip=["1.2.3.4/32"]) as g4, \
         \
         encap_route(m2, vrf_None, 1, "gre2", ip=ipv6), \
         gre(sw, None, vrf_None,
             tos="inherit",
             local_ip="1.2.3.4",
             remote_ip="1.2.3.5",
             ikey=2222, okey=1111,
             ip=["1.2.3.4/32"]) as g6, \
         encap_route(sw, vrf_None, 2, g6, ip=ipv6):

        route = encap_route(sw, vrf_None, 2, g4, ip=ipv4)
        route.do("add")

        sleep(60)
        ping_test(tl, m1, sw, ipv6(onet2_ip(ctl, 33, [])), m1_if1, g6,
                  count=25, ipv6=True)
        ping_test(tl, m1, sw, ipv4(onet2_ip(ctl, 33, [])), m1_if1, g4,
                  count=25, fail_expected=True)

        sw.run("ip link set dev %s nomaster" % g4.get_devname())

        # The VRF motion drops the encap route, so re-add it.
        route.do("add")

        sleep(5)
        ping_test(tl, m1, sw, ipv6(onet2_ip(ctl, 33, [])), m1_if1, g6,
                  ipv6=True, require_fastpath=False, require_slowpath=True)
        ping_test(tl, m1, sw, ipv4(onet2_ip(ctl, 33, [])), m1_if1, g4,
                  require_fastpath=False, require_slowpath=True)

        route.do("del")


do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("machine2").get_interface("if1"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2")],
        ctl.get_aliases())
