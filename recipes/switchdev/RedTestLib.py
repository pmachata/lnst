"""
Copyright 2017 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
nogahf@mellanox.com (Nogah Frankel)
"""

from time import sleep
import logging

# Merely a container for a run results
# Holds:
#   stats: The last red stats taken in the run, or, for none red runs, some
#   minimal data from the normal stats.
#   backlogs: A list of the backlogs sizes during the runs. Filtered so a
#   backlog won't be counted if there was no TX in the time it was taken.
class RedTestResults:
    def __init__(self, red_stats, backlogs):
        self.stats = red_stats
        self.backlogs = backlogs

class RedTestLib:
    def __init__(self, tl, switch, links):
        self.tl = tl
        self.switch = switch
        self.links = links
        self.ports = links.keys()
        self.switch.create_bridge(slaves=self.ports,
                                  options={"vlan_filtering": 1})
        self.rate = 0
        self.desc = "TC qdisc RED"
        self.threshold = 100
        self.speed_base = 1000
        self.min = 0
        self.max = 0
        self.rate = self.speed_base
        self.set_traffic_ecn_enable()

    # choose egress & ingress ports and set their speed to create bottleneck
    def create_bottleneck(self, aliases):
        self.egress_port = self.ports[0]
        self.ingress_port = self.ports[1]
        self.egress_port.set_speed(self.speed_base)
        self.ingress_port.set_speed(aliases["speed_hi"])

    def set_traffic_ecn_enable(self):
        self.tos = '01'
        logging.info("traffic will be ecn enabled")

    def set_traffic_ecn_disable(self):
        self.tos = '00'
        logging.info("traffic will be ecn disabled")

    def set_red(self, min, max, prob=None, ecn=False):
        limit = max * 4
        avpkt = 1000
        self.egress_port.set_qdisc_red(limit, avpkt, min, max, ecn=ecn)
        self.min = min
        self.max = max

    def set_no_red(self):
        self.min = 0
        self.max = 0
        self.egress_port.unset_qdisc_red()

    # Send traffic in the set rate.
    # If RED is set, collect res stats while the traffic is being sent.
    # Collect the backlog size for every time there is a traffic passing via the
    # red qdisc, indicated by change in the TX counter.
    def send_traffic(self, is_red = True):
        rx_before = self.ingress_port.link_stats()["rx_packets"]
        tx_before = self.egress_port.link_stats()["tx_packets"]
        pkt_size = self.links[self.ingress_port].get_mtu()

        if is_red: # if RED is enabled
            self.egress_port.collect_qdisc_red_stats()

        self.tl.pktgen(self.links[self.ingress_port],
                       self.links[self.egress_port], pkt_size, count=10**6,
                       rate=str(self.rate)+"M", tos=self.tos)
        sleep(3)

        rx_after = self.ingress_port.link_stats()["rx_packets"]
        tx_after = self.egress_port.link_stats()["tx_packets"]
        tx_packets = tx_after - tx_before
        rx_packets = rx_after - rx_before
        drops = rx_packets - tx_packets

        if is_red:
            backlog, stats = self.egress_port.stop_collecting_qdisc_red_stats()
            results = RedTestResults(stats, backlog)
        else:
            stats = {"drops": drops, "tx_packets": tx_packets}
            results = RedTestResults(stats, [])

        logging.info("Sent %d packets, dropped %d packets" % (tx_after, drops))
        return results

