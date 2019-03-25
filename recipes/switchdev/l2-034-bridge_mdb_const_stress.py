"""
Copyright 2017 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
nogahf@mellanox.com (Nogah Frankel)
"""

from lnst.Controller.Task import ctl
from TestLib import TestLib
from time import sleep
import random
import logging
import re

def test_ip(major, minor):
    return ["192.168.10%d.%d/24" % (major, minor)]

def mcgrp(i):
    l = i / 250
    i = (i % 250) + 1
    return "239.255.%d.%d" % (l, i)

def get_listeners(i, bridged):
    temp = (i % 7) + 1
    listeners = []
    if temp & 1:
        listeners.append(bridged[0])
    if temp & 2:
        listeners.append(bridged[1])
    if temp & 4:
        listeners.append(bridged[2])
    return listeners

def do_task(ctl, hosts, ifaces, bridges, aliases):
    m1, m2, sw = hosts
    m1_if, m2_if, m3_if, m4_if, sw_if1, sw_if2, sw_if3, sw_if4 = ifaces
    peers = {m1_if: sw_if1, m2_if: sw_if2, m3_if: sw_if3, m4_if: sw_if4}

    for bridge in bridges:
        bridge.set_br_mcast_snooping(False)

    # Create a bridge
    sw_ports = peers.values()
    sw_br = sw.create_bridge(slaves=sw_ports, options={"vlan_filtering":1,
                                                       "multicast_querier":1})

    sw_br.set_br_mcast_hash_max(8192)
    sw_br.set_br_mcast_hash_elasticity(16)
    m1_if.set_addresses(test_ip(1,1))
    m2_if.set_addresses(test_ip(1,2))
    m3_if.set_addresses(test_ip(1,3))
    m4_if.set_addresses(test_ip(1,4))
    for iface in [m1_if, m2_if, m3_if, m4_if]:
        iface.enable_multicast()

    tl = TestLib(ctl, aliases)
    tl.wait_for_if(ifaces)
    tl.check_cpu_traffic(sw_ports, test=False)

    used_mdb = max(8, sw_br.show_br_mdb().count("offload") + 2)
    max_mdb = int(aliases["max_mdb"]) - used_mdb
    bridged = [m2_if, m3_if, m4_if]
    logging.info("Add %d mdb entries" % max_mdb)
    for i in range(max_mdb):
        group = mcgrp(i)
        listeners = get_listeners(i, bridged)
        for l in listeners:
            sw_br.add_br_mdb(str(peers[l].get_devname()), group, permanent=True)

    mdb_str = sw_br.show_br_mdb()

    msg = ""
    logging.info("Check mdb entries are offloaded")
    pattern = "(?:dev)?\s*?%s (?:port)?\s*? (\S+)\s+(?:grp)?\s*?(\S+) \s*permanent\s* offload" % (
               str(sw_br.get_devname()))
    p = re.compile(pattern)
    mdb_pairs = p.findall(mdb_str)
    for i in range(max_mdb):
        group = mcgrp(i)
        listeners = get_listeners(i, bridged)
        for l in listeners:
            if not (str(peers[l].get_devname()), group) in mdb_pairs:
                msg = "mdb entry %d: group %s port %s was not offloaded" % (
                       i, group, str(peers[l].get_devname()))
                break
        if msg:
            break

    tl.custom(sw, "Check mdb was offloaded", msg)

    for _ in range(5):
        logging.info("Check random group %s" % group)
        i = random.randint(0, max_mdb - 1)
        group = mcgrp(i)
        listeners = get_listeners(i, bridged)
        res = tl.iperf_mc(m1_if, bridged, group)
        expected = [i in listeners for i in bridged]
        tl.mc_ipref_compare_result(bridged, res, expected)

    logging.info("Del mdb entries")
    for i in range(max_mdb):
        group = mcgrp(i)
        listeners = get_listeners(i, bridged)
        for l in listeners:
            sw_br.del_br_mdb(str(peers[l].get_devname()), group, permanent=True)

    for _ in range(5):
        i = random.randint(0, max_mdb - 1)
        group = mcgrp(i)
        logging.info("Check random group %s" % group)
        res = tl.iperf_mc(m1_if, bridged, group)
        expected = [False for i in bridged]
        tl.mc_ipref_compare_result(bridged, res, expected)

    for iface in [m1_if, m2_if, m3_if, m4_if]:
        iface.disable_multicast()
    tl.check_cpu_traffic(sw_ports)

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("veth1"),
         ctl.get_host("machine1").get_interface("veth3"),
         ctl.get_host("machine2").get_interface("veth1"),
         ctl.get_host("machine2").get_interface("veth3"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2"),
         ctl.get_host("switch").get_interface("if3"),
         ctl.get_host("switch").get_interface("if4")],
        [ctl.get_host("machine1").get_interface("brif1"),
         ctl.get_host("machine1").get_interface("brif2"),
         ctl.get_host("machine2").get_interface("brif1"),
         ctl.get_host("machine2").get_interface("brif2")],
        ctl.get_aliases())
