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
from random import randint
from time import sleep
from RedTestLib import RedTestLib
from PrioTestLib import PrioTestLib
import logging

def do_task(ctl, hosts, ifaces, aliases):
    m1, m2, sw = hosts
    m1_if1, m2_if1, sw_if1, sw_if2 = ifaces

    tl = TestLib(ctl, aliases)
    prio_test = PrioTestLib(tl, sw, {sw_if1: m1_if1, sw_if2: m2_if1})
    prio_test.create_bottleneck(aliases)
    prio_test.set_prio(bands=8, priomap="0 0 7 7 7 7 7 7")

    red_test = RedTestLib(tl, sw, {sw_if1:m1_if1, sw_if2:m2_if1}, router=True,
                          no_init=True)
    red_test.choose_bottleneck(prio_test.ingress_port, prio_test.egress_port)
    logging.info("Set traffic to be with priority 6 - which is band 7")
    red_test.set_traffic_tos(PrioTestLib.PRIORITY_TO_TOS[6] >> 2)
    sleep(30)

    logging.info("Set RED on band 7")
    red_test.set_red(1500000, 1500001, parent=8)
    logging.info("Check that it affect the traffic")
    high_red_res = red_test.tune_high_rate(backlog_threshold = 0.9)
    red_test.check_red_high(high_red_res)

    logging.info("Change prio to have only 4 bands")
    prio_test.set_prio(bands=4, priomap="0 0 3 3 3 3 3 3")
    sleep(30)
    logging.info("See that the traffic is not affected by RED")
    no_red_res = red_test.send_traffic(is_red = False)
    red_test.check_no_red(no_red_res, high_red_res)

    logging.info("Change prio to have 8 bands - traffic is on band 7")
    prio_test.set_prio(bands=8, priomap="0 0 7 7 7 7 7 7")
    sleep(30)
    logging.info("See that the traffic is still not affected by RED")
    no_red_res = red_test.send_traffic(is_red = False)
    red_test.check_no_red(no_red_res, high_red_res)

    logging.info("Set RED again on band 7. See that the counters are not"
                 "affected by the past")
    red_test.set_red(1500000, 1500001, parent=8)
    high_red_res = red_test.tune_high_rate(backlog_threshold = 0.9)
    red_test.check_red_high(high_red_res)

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("machine2").get_interface("if1"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2")],
        ctl.get_aliases())
