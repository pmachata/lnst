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
import logging

def test_ip(major, minor, prefix=24):
    return "192.168.10%d.%d%s" % (major, minor,
        "/" + str(prefix) if prefix > 0 else "")

class PrioTestLib:
    PRIORITY_TO_TOS = {0:96, 6:16, 2:40, 4:90}

    def __init__(self, tl, switch, links):
        self.tl = tl
        self.switch = switch
        ports = links.keys()
        self.egress_port = ports[0]
        self.ingress_port = ports[1]
        self.recieving_agent = links[ports[0]]
        self.sending_agent = links[ports[1]]
        self.ping_count = 100
        for port in [self.egress_port, self.ingress_port, self.sending_agent,
                    self.recieving_agent]:
            port.reset()
        self.recieving_agent.set_addresses([test_ip(2,1)])
        self.sending_agent.set_addresses([test_ip(1,1)])
        self.egress_port.set_addresses([test_ip(2,2)])
        self.ingress_port.set_addresses([test_ip(1,2)])

        self.recieving_agent.add_nhs_route(test_ip(1,0),
                                           [test_ip(2,2,0)])
        self.sending_agent.add_nhs_route(test_ip(2,0),
                                           [test_ip(1,2,0)])
        self.prio_exists = False

    def ping(self, tos=None):
        options = {"count" : self.ping_count, "limit_rate" : 0,
                   "ipv4_only": True}
        if tos:
            options["tos"] = tos

        self.tl.ping_simple(self.sending_agent, self.recieving_agent,
                            **options)

    def create_bottleneck(self, aliases):
        self.egress_port.set_speed(1000)
        self.ingress_port.set_speed(aliases["speed_hi"])

    def set_prio(self, bands = None, priomap = None, change = False):
        if self.prio_exists:
            change = True
        self.egress_port.set_qdisc_prio(bands, priomap, change)
        self.prio_exists = True

    def send_bg_traffic(self, pkt_priority):
        tos = "%02x" % self.PRIORITY_TO_TOS[pkt_priority]
        options = {"pkt_size": 1400, "count": 0, "tos": tos, "rate": "1200M",
                   "bg": True, "dst": test_ip(2,1,0),
                   "dst_mac": self.ingress_port.get_hwaddr()}
        self.pktgen_proc = self.tl.pktgen(self.sending_agent,
                                          self.recieving_agent, **options)
        sleep(1)

    def stop_bg_traffic(self):
        self.pktgen_proc.kill()

    def check_traffic_passes(self, priority, should_pass):
        tos = self.PRIORITY_TO_TOS[priority]
        min = int(0.9 * self.ping_count if should_pass else 0)
        max = int(self.ping_count if should_pass else 0.1 * self.ping_count)
        proc = self.start_collect_packets(tos, min, max)
        self.ping(tos=tos)
        sleep(1)
        proc.intr()

    def start_collect_packets(self, tos, min, max):
        filter_str = "icmp && (ip[1] == %d) && dst %s" % (tos, test_ip(2,1,0))
        packet_assert_options = {"min": min, "max": max, "promiscuous" : True,
                                 "filter" : filter_str,
                                 "interface": self.recieving_agent.get_devname()}

        packet_assert_mod = ctl.get_module("PacketAssert",
                                           options = packet_assert_options)
        host = self.recieving_agent.get_host()
        return host.run(packet_assert_mod, bg=True)
