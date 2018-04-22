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
import logging

BAND_TO_PRIOMAP = {1:"0 0 1 1 1 1 1 1", 2:"1 1 0 0 0 0 0 0 0 0 0"}

def change_band(red_test, band_number):
    logging.info("Remap PRIO so the traffic will go via band %d" % band_number)
    red_test.set_prio(priomap=BAND_TO_PRIOMAP[band_number], change=True)
    red_test.choose_parent(band_number)
    sleep(30)

def run_actual_test(red_test):
    red_test.set_red(1500000, 1500001, parent=1)
    red_test.set_red(1000000, 1000001, parent=2)

    change_band(red_test, 1)
    logging.info("Check low rate on the first band")
    low_red_res = red_test.tune_low_rate(backlog_threshold = 0.9)
    red_test.check_red_low(low_red_res)

    change_band(red_test, 2)
    logging.info("Check low rate on the second band")
    low_red_res = red_test.tune_low_rate(backlog_threshold = 0.9)
    red_test.check_red_low(low_red_res)

    change_band(red_test, 1)
    logging.info("Check high rate on the first band")
    high_red_res1 = red_test.tune_high_rate(backlog_threshold = 0.9)
    red_test.check_red_high(high_red_res1)

    change_band(red_test, 2)
    logging.info("Check high rate on the second band")
    high_red_res2 = red_test.tune_high_rate(backlog_threshold = 0.9)
    red_test.check_red_high(high_red_res2)

    change_band(red_test, 1)
    logging.info("Disable RED on the first band")
    red_test.set_no_red(1)
    logging.info("Check that the first band have no RED")
    no_red_res = red_test.send_traffic(is_red = False)
    red_test.check_no_red(no_red_res, high_red_res2)

    change_band(red_test, 2)
    logging.info("Check that the second band still have RED")
    high_red_res2 = red_test.tune_high_rate(backlog_threshold = 0.9)
    red_test.check_red_high(high_red_res2)
    logging.info("Disable RED on the second band")
    red_test.set_no_red(2)
    logging.info("Check that the second band have no RED")
    no_red_res = red_test.send_traffic(is_red = False)
    red_test.check_no_red(no_red_res, high_red_res2)

def do_task(ctl, hosts, ifaces, aliases):
    m1, m2, sw = hosts
    m1_if1, m2_if1, sw_if1, sw_if2 = ifaces

    tl = TestLib(ctl, aliases)
    red_test = RedTestLib(tl, sw, {sw_if1:m1_if1, sw_if2:m2_if1}, router=True)
    red_test.create_bottleneck(aliases)
    red_test.set_prio()
    sleep(60)

    try:
        run_actual_test(red_test)
    except Exception as e:
        logging.error("Test run failed")
        tl.custom(sw, "Basic RED test", "Failed because of %s" % e)


do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("machine2").get_interface("if1"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2")],
        ctl.get_aliases())
