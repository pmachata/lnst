from lnst.Controller.Task import ctl
from TestLib import TestLib
from ptp_common import PtpTest

# The topology used is:
#
#  +-----------------------+
#  | m1 (Master)           |
#  |                       |
#  | + m1_if1.111          |
#  | | 192.0.2.1/28        |
#  | | 2001:db8:1::1/64    |
#  | |                     |
#  | + m1_if1              |
#  +-|---------------------+
#    |
#  +-|-----------------------------------------------+
#  | + sw_if1                            switch (BC) |
#  | |                                               |
#  | + sw_if1.111                                    |
#  |   192.0.2.2/28                                  |
#  |   2001:db8:1::2/64                              |
#  |                                                 |
#  | + sw_if2.222              + sw_if3              |
#  | | 192.0.2.17/28           | 192.0.2.33/28       |
#  | | 2001:db8:2::1/64        | 2001:db8:3::1/64    |
#  | |                         |                     |
#  | + sw_if2                  |                     |
#  +-|-------------------------|---------------------+
#    |                         |
#  +-|-------------------------|---------------------+
#  | + m2_if1                  + m2_if2           m2 |
#  | |                           192.0.2.34/28       |
#  | + m2_if1.222                2001:db8:3::2/64    |
#  |   192.0.2.18/28                                 |
#  |   2001:db8:2::2/64                              |
#  |                                                 |
#  | Slave1                    Slave2                |
#  +-------------------------------------------------+

def do_task(ctl, hosts, ifaces, aliases):
    m1, m2, sw = hosts
    m1_if1, m2_if1, m2_if2, sw_if1, sw_if2, sw_if3 = ifaces

    sw_if1_111 = sw.create_vlan(sw_if1, 111)
    m1_if1_111 = m1.create_vlan(m1_if1, 111)

    sw_if2_222 = sw.create_vlan(sw_if2, 222)
    m2_if1_222 = m2.create_vlan(m2_if1, 222)

    tl = TestLib(ctl, aliases)
    tl.wait_for_if(ifaces)

    pt = PtpTest(tl, hosts, ifaces = [m1_if1_111, m2_if1_222, m2_if2,
            sw_if1_111, sw_if2_222, sw_if3])
    pt.run_tests()


do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("machine2").get_interface("if1"),
         ctl.get_host("machine2").get_interface("if2"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2"),
         ctl.get_host("switch").get_interface("if3")],
         ctl.get_aliases())
