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
from PrioTestLib import PrioTestLib
from time import sleep
import logging

def do_task(ctl, hosts, ifaces, aliases):
    m1, m2, sw = hosts
    m1_if1, m2_if1, sw_if1, sw_if2 = ifaces

    tl = TestLib(ctl, aliases)
    prio_test = PrioTestLib(tl, sw, {sw_if1:m1_if1, sw_if2:m2_if1})
    prio_test.create_bottleneck(aliases)
    prio_test.set_prio(bands=3, priomap="2 2 0 0 1 1 1")
    sleep(30)

    logging.info("Start traffic in band 1")
    prio_test.send_bg_traffic(6)
    sleep(60)

    logging.info("Send traffic in band 0 (should pass)")
    prio_test.check_traffic_passes(2, True)

    logging.info("Send traffic in band 2 (shouldn't pass)")
    prio_test.check_traffic_passes(0, False)

    prio_test.stop_bg_traffic()

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("machine2").get_interface("if1"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2")],
        ctl.get_aliases())
