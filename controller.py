from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib import hub
from ryu.lib.packet import packet, ethernet
import time
import csv


BLOCKED_MAC = "00:00:00:00:00:03"


class AdvancedMonitor(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(AdvancedMonitor, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.datapaths = {}
        self.prev_stats = {}
        self.monitor_thread = hub.spawn(self.monitor)

        self.file = open("traffic_log.csv", "w", newline="")
        self.writer = csv.writer(self.file)
        self.writer.writerow(["Time", "Packets", "Bytes", "Mbps"])

    # ---------------- SWITCH CONNECTION ----------------
    @set_ev_cls(ofp_event.EventOFPStateChange,
                [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def state_change_handler(self, ev):
        dp = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            self.datapaths[dp.id] = dp
            print(f"Switch {dp.id} connected")
        elif ev.state == DEAD_DISPATCHER:
            self.datapaths.pop(dp.id, None)

    # ---------------- DEFAULT RULE ----------------
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        dp = ev.msg.datapath
        parser = dp.ofproto_parser
        ofproto = dp.ofproto

        # Default: send unknown packets to controller
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                         ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(dp, 0, match, actions)

        # Pre-install drop rule for h3 before any packet arrives
        block_match = parser.OFPMatch(eth_src=BLOCKED_MAC)
        self.add_flow(dp, 100, block_match, [])  # empty actions = DROP
        print(f"🚫 Drop rule pre-installed for {BLOCKED_MAC}")

    def add_flow(self, dp, priority, match, actions):
        parser = dp.ofproto_parser
        ofproto = dp.ofproto

        inst = [parser.OFPInstructionActions(
            ofproto.OFPIT_APPLY_ACTIONS, actions)]

        mod = parser.OFPFlowMod(datapath=dp,
                               priority=priority,
                               match=match,
                               instructions=inst)
        dp.send_msg(mod)

    # ---------------- PACKET HANDLER ----------------
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        parser = dp.ofproto_parser
        ofproto = dp.ofproto

        dpid = dp.id
        self.mac_to_port.setdefault(dpid, {})

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if eth is None:
            return

        dst = eth.dst
        src = eth.src
        in_port = msg.match['in_port']

        # 🚫 Drop any h3 packet that still reaches controller
        if src == BLOCKED_MAC:
            print("🚫 BLOCKED: h3 and h4 traffic")
            return

        # ✅ Learn MAC
        self.mac_to_port[dpid][src] = in_port

        # ✅ Forwarding
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst)
            self.add_flow(dp, 1, match, actions)

        out = parser.OFPPacketOut(
            datapath=dp,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=msg.data
        )
        dp.send_msg(out)

    # ---------------- MONITOR ----------------
    def monitor(self):
        while True:
            for dp in self.datapaths.values():
                self.request_stats(dp)
            hub.sleep(5)

    def request_stats(self, dp):
        parser = dp.ofproto_parser
        req = parser.OFPFlowStatsRequest(dp)
        dp.send_msg(req)

    # ---------------- STATS ----------------
    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def stats_handler(self, ev):
        print("\n===== FLOW STATS =====")
        current_time = time.time()

        for stat in ev.msg.body:
            key = (str(stat.match), str(stat.instructions))

            prev_bytes, prev_time = self.prev_stats.get(key, (0, current_time))

            byte_diff = stat.byte_count - prev_bytes
            time_diff = current_time - prev_time if current_time != prev_time else 1

            mbps = (byte_diff * 8) / (time_diff * 1e6)

            print(f"Packets: {stat.packet_count}, Bytes: {stat.byte_count}, Mbps: {mbps:.2f}")

            self.prev_stats[key] = (stat.byte_count, current_time)

            self.writer.writerow([current_time, stat.packet_count, stat.byte_count, mbps])