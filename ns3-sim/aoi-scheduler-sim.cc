/*
 * AoI DRL Scheduler -- NS-3 review simulation.
 *
 * Models the exact 1-AP + 4-STA star topology of the real ESP32 + Raspberry
 * Pi testbed, using the SAME application-layer centralized grant-reply
 * protocol as the real firmware (see common/contracts/packets.py): the AP
 * (gateway) sends a UDP GRANT to exactly one node per slot; that node
 * replies with a UDP DATA packet carrying the generation-time age of its
 * buffered sample. AoI accounting and the safety shield reproduce the
 * frozen math in common/contracts/aoi.py and config/system.yaml exactly,
 * so ns3-sim/analysis/validate_against_contracts.py can cross-check the
 * two implementations bit-for-bit.
 *
 * Baseline schedulers: Round Robin, Fixed Priority, Max-Weight,
 * Channel-Aware Greedy, Random -- all wrapped by a deterministic safety
 * shield that force-grants any node breaching its AoI ceiling.
 */

#include "aoi-timestamp-tag.h"

#include "ns3/core-module.h"
#include "ns3/flow-monitor-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/netanim-module.h"
#include "ns3/network-module.h"
#include "ns3/wifi-module.h"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <memory>
#include <string>
#include <vector>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("AoiSchedulerSim");

// ─────────────────────────────────────────────────────────────────────────
// Global constants (mirrors config/system.yaml -- keep the two in sync)
// ─────────────────────────────────────────────────────────────────────────

static const uint32_t N_NODES = 4;
static const uint16_t PORT_GRANT = 5006; // AP -> STA
static const uint16_t PORT_DATA = 5005;  // STA -> AP
static const uint16_t PORT_HB = 5007;    // STA -> AP (heartbeat)

// system.node_classes: ["urgent", "urgent", "important", "routine"]
static const std::string NODE_CLASSES[N_NODES] = {"urgent", "urgent", "important", "routine"};

// scheduler.weights: urgent=10, important=3, routine=1
static const double WEIGHTS[N_NODES] = {10.0, 10.0, 3.0, 1.0};

// scheduler.shield_ceilings_s: urgent=2.0, important=6.0, routine=20.0
static const double SHIELD_CEILING[N_NODES] = {2.0, 2.0, 6.0, 20.0};

// Channel-Aware Greedy logistic delivery-probability model
static const double R50_DBM = -82.0; // RSSI at 50% delivery probability
static const double BETA_LOG = 4.0;  // logistic slope width (dB)

// Node positions in metres, AP at the origin (radial placement for
// unambiguous, easy-to-read NetAnim layout). Distances from the AP are
// 5m/8m/12m/18m respectively, giving clear RSSI diversity across classes.
static const double NODE_X[N_NODES] = {5.0, 0.0, -12.0, 0.0};
static const double NODE_Y[N_NODES] = {0.0, 8.0, 0.0, -18.0};

// ─────────────────────────────────────────────────────────────────────────
// Scheduler selection
// ─────────────────────────────────────────────────────────────────────────

enum SchedulerType
{
    SCHED_RR,
    SCHED_FPQ,
    SCHED_MAXWEIGHT,
    SCHED_CAG,
    SCHED_RANDOM
};

static SchedulerType
ParseSchedulerType(const std::string& s)
{
    if (s == "rr")
    {
        return SCHED_RR;
    }
    if (s == "fpq")
    {
        return SCHED_FPQ;
    }
    if (s == "maxweight")
    {
        return SCHED_MAXWEIGHT;
    }
    if (s == "cag")
    {
        return SCHED_CAG;
    }
    if (s == "random")
    {
        return SCHED_RANDOM;
    }
    NS_FATAL_ERROR("Unknown --scheduler value: " << s
                                                  << " (expected rr|fpq|maxweight|cag|random)");
}

static std::string
SchedulerName(SchedulerType t)
{
    switch (t)
    {
    case SCHED_RR:
        return "rr";
    case SCHED_FPQ:
        return "fpq";
    case SCHED_MAXWEIGHT:
        return "maxweight";
    case SCHED_CAG:
        return "cag";
    case SCHED_RANDOM:
        return "random";
    }
    return "unknown";
}

// Urgent=2, Important=1, Routine=0 -- used by the Fixed Priority scheduler.
static int
ClassPriority(uint32_t nodeId)
{
    const std::string& cls = NODE_CLASSES[nodeId];
    if (cls == "urgent")
    {
        return 2;
    }
    if (cls == "important")
    {
        return 1;
    }
    return 0;
}

// ─────────────────────────────────────────────────────────────────────────
// IoTSensorApp -- installed on each STA. Generates a 10 Hz sensor sample
// into a single-slot LCFS buffer, replies to GRANTs, and sends periodic
// unsolicited HEARTBEATs so the gateway can keep an RSSI estimate warm.
// ─────────────────────────────────────────────────────────────────────────

class IoTSensorApp : public Application
{
  public:
    static TypeId GetTypeId()
    {
        static TypeId tid =
            TypeId("ns3::IoTSensorApp").SetParent<Application>().SetGroupName("AoiScheduler");
        return tid;
    }

    IoTSensorApp(uint32_t nodeId,
                 Ipv4Address gatewayAddr,
                 double sampleIntervalS,
                 double heartbeatPeriodS)
        : m_nodeId(nodeId),
          m_gwAddr(gatewayAddr),
          m_sampleIntervalS(sampleIntervalS),
          m_heartbeatPeriodS(heartbeatPeriodS)
    {
        m_jitter = CreateObject<UniformRandomVariable>();
        m_jitter->SetAttribute("Min", DoubleValue(-0.2));
        m_jitter->SetAttribute("Max", DoubleValue(0.2));
    }

  private:
    void StartApplication() override
    {
        m_grantSocket = Socket::CreateSocket(GetNode(), UdpSocketFactory::GetTypeId());
        m_grantSocket->Bind(InetSocketAddress(Ipv4Address::GetAny(), PORT_GRANT));
        m_grantSocket->SetRecvCallback(MakeCallback(&IoTSensorApp::HandleGrant, this));

        m_dataSocket = Socket::CreateSocket(GetNode(), UdpSocketFactory::GetTypeId());
        m_dataSocket->Bind();

        m_hbSocket = Socket::CreateSocket(GetNode(), UdpSocketFactory::GetTypeId());
        m_hbSocket->Bind();

        m_sampleEvent = Simulator::ScheduleNow(&IoTSensorApp::GenerateSample, this);
        m_hbEvent = Simulator::Schedule(Seconds(m_jitter->GetValue() + m_heartbeatPeriodS),
                                         &IoTSensorApp::SendHeartbeat,
                                         this);
    }

    void StopApplication() override
    {
        Simulator::Cancel(m_sampleEvent);
        Simulator::Cancel(m_hbEvent);
        if (m_grantSocket)
        {
            m_grantSocket->Close();
        }
        if (m_dataSocket)
        {
            m_dataSocket->Close();
        }
        if (m_hbSocket)
        {
            m_hbSocket->Close();
        }
    }

    void GenerateSample()
    {
        m_latestSampleTimeUs = Simulator::Now().GetMicroSeconds();
        m_queueOccupied = true; // LCFS-1: overwrite, never grows a queue
        m_sampleEvent =
            Simulator::Schedule(Seconds(m_sampleIntervalS), &IoTSensorApp::GenerateSample, this);
    }

    void HandleGrant(Ptr<Socket> socket)
    {
        Address from;
        socket->RecvFrom(from);

        if (!m_queueOccupied)
        {
            return; // empty queue: grant wasted, nothing to send
        }

        Ptr<Packet> packet = Create<Packet>(25);
        AoITimestampTag tag;
        tag.SetData(m_nodeId, m_latestSampleTimeUs);
        packet->AddPacketTag(tag);

        m_dataSocket->SendTo(packet, 0, InetSocketAddress(m_gwAddr, PORT_DATA));
        m_queueOccupied = false;
        m_seqNum++;
    }

    void SendHeartbeat()
    {
        Ptr<Packet> packet = Create<Packet>(8);
        AoITimestampTag tag;
        tag.SetData(m_nodeId, 0); // genTime=0 marks a heartbeat, not sensor data
        packet->AddPacketTag(tag);
        m_hbSocket->SendTo(packet, 0, InetSocketAddress(m_gwAddr, PORT_HB));

        double nextPeriod = std::max(0.1, m_heartbeatPeriodS + m_jitter->GetValue());
        m_hbEvent = Simulator::Schedule(Seconds(nextPeriod), &IoTSensorApp::SendHeartbeat, this);
    }

    uint32_t m_nodeId;
    Ipv4Address m_gwAddr;
    double m_sampleIntervalS;
    double m_heartbeatPeriodS;

    Ptr<Socket> m_grantSocket;
    Ptr<Socket> m_dataSocket;
    Ptr<Socket> m_hbSocket;
    Ptr<UniformRandomVariable> m_jitter;

    uint64_t m_latestSampleTimeUs{0};
    bool m_queueOccupied{false};
    uint32_t m_seqNum{0};

    EventId m_sampleEvent;
    EventId m_hbEvent;
};

// ─────────────────────────────────────────────────────────────────────────
// MasterSchedulerApp -- installed on the AP. Runs the slot timer, tracks
// per-node AoI/RSSI/queue state, applies the safety shield, invokes the
// selected baseline scheduler, and logs one row per slot to CSV.
// ─────────────────────────────────────────────────────────────────────────

class MasterSchedulerApp : public Application
{
  public:
    static TypeId GetTypeId()
    {
        static TypeId tid =
            TypeId("ns3::MasterSchedulerApp").SetParent<Application>().SetGroupName("AoiScheduler");
        return tid;
    }

    MasterSchedulerApp(std::vector<Ipv4Address> staAddrs,
                        Time slotDuration,
                        SchedulerType schedulerType,
                        std::string csvOutputPath)
        : m_staAddrs(std::move(staAddrs)),
          m_slotDuration(slotDuration),
          m_schedulerType(schedulerType),
          m_csvOutputPath(std::move(csvOutputPath))
    {
        m_randomPick = CreateObject<UniformRandomVariable>();
        m_randomPick->SetAttribute("Min", DoubleValue(0));
        m_randomPick->SetAttribute("Max", DoubleValue(N_NODES - 1 + 0.999999));
        for (uint32_t i = 0; i < N_NODES; ++i)
        {
            m_aoi[i] = 0.0;
            m_rssi[i] = -60.0;
            m_rssiAge[i] = 0.0;
            m_deliveredThisSlot[i] = false;
            m_pendingDeliveredAgeS[i] = 0.0;
        }
        g_instance = this;
    }

    // Invoked from the PHY MonitorSnifferRx trace callback (see main()) to
    // keep a live RSSI estimate per node, independent of application data.
    void UpdateRssiEstimate(uint32_t nodeId, double rssiDbm)
    {
        if (nodeId < N_NODES)
        {
            m_rssi[nodeId] = rssiDbm;
            m_rssiAge[nodeId] = 0.0;
        }
    }

    static MasterSchedulerApp* GetInstance()
    {
        return g_instance;
    }

  private:
    void StartApplication() override
    {
        m_csvFile.open(m_csvOutputPath);
        NS_ASSERT_MSG(m_csvFile.is_open(), "Failed to open CSV output: " << m_csvOutputPath);
        m_csvFile << "slot_id,timestamp_pi,policy_id,action_granted_node,shield_fired,"
                     "uplink_received,delivered_node,delivered_age_us,rssi_at_rx,queue_status,"
                     "energy_proxy_cost,malformed_dropped,stale_dropped,"
                     "aoi_n1,aoi_n2,aoi_n3,aoi_n4,rssi_n1,rssi_n2,rssi_n3,rssi_n4\n";

        m_dataSocket = Socket::CreateSocket(GetNode(), UdpSocketFactory::GetTypeId());
        m_dataSocket->Bind(InetSocketAddress(Ipv4Address::GetAny(), PORT_DATA));
        m_dataSocket->SetRecvCallback(MakeCallback(&MasterSchedulerApp::HandleDataReply, this));

        m_hbSocket = Socket::CreateSocket(GetNode(), UdpSocketFactory::GetTypeId());
        m_hbSocket->Bind(InetSocketAddress(Ipv4Address::GetAny(), PORT_HB));
        m_hbSocket->SetRecvCallback(MakeCallback(&MasterSchedulerApp::HandleHeartbeat, this));

        m_grantSocket = Socket::CreateSocket(GetNode(), UdpSocketFactory::GetTypeId());
        m_grantSocket->Bind();

        Simulator::Schedule(m_slotDuration, &MasterSchedulerApp::SlotTick, this);
    }

    void StopApplication() override
    {
        // Flush the outcome of the last grant sent, if it hasn't been
        // closed out by a following SlotTick yet.
        if (m_pendingGrantedNode >= 0 && m_csvFile.is_open())
        {
            bool anyDelivered = false;
            int deliveredNode = -1;
            double deliveredAgeS = 0.0;
            for (uint32_t i = 0; i < N_NODES; ++i)
            {
                if (m_deliveredThisSlot[i])
                {
                    anyDelivered = true;
                    deliveredNode = static_cast<int>(i);
                    deliveredAgeS = m_pendingDeliveredAgeS[i];
                }
            }
            WriteCsvRow(m_pendingGrantedNode,
                        m_pendingShieldFired,
                        anyDelivered,
                        deliveredNode,
                        deliveredAgeS);
            m_pendingGrantedNode = -1;
        }

        std::cout << "=== Simulation Complete (" << SchedulerName(m_schedulerType)
                  << ") ===" << std::endl;
        std::cout << "Total slots:         " << m_totalSlots << std::endl;
        std::cout << "Packets received:    " << m_packetsReceived << std::endl;
        double shieldPct = m_totalSlots > 0 ? (100.0 * m_shieldActivations / m_totalSlots) : 0.0;
        std::cout << "Shield activations:  " << m_shieldActivations << " (" << shieldPct
                  << "%)" << std::endl;
        std::cout << "Empty grants:        " << m_emptyGrants << std::endl;
        if (m_csvFile.is_open())
        {
            m_csvFile.close();
        }
        g_instance = nullptr;
    }

    // Each tick does two things, in order:
    //   1. Closes out the PREVIOUS slot: applies AoI aging/resets for the
    //      period since the last tick, then logs one CSV row pairing that
    //      previous grant (m_pendingGrantedNode) with its own outcome.
    //   2. Decides and sends the GRANT for the slot that is now starting,
    //      remembering it as m_pendingGrantedNode so the *next* tick can
    //      close it out the same way.
    // Keeping "which node was granted" and "what happened to that grant"
    // in the same CSV row (rather than a grant and an unrelated in-flight
    // reply) is what lets validate_against_contracts.py replay AoI with
    // common/contracts/aoi.py::update_aoi_for_slot and match bit-for-bit.
    void SlotTick()
    {
        m_currentSlot++;
        m_totalSlots++;

        bool anyDelivered = false;
        int deliveredNode = -1;
        double deliveredAgeS = 0.0;
        for (uint32_t i = 0; i < N_NODES; ++i)
        {
            if (m_deliveredThisSlot[i])
            {
                anyDelivered = true;
                deliveredNode = static_cast<int>(i);
                deliveredAgeS = m_pendingDeliveredAgeS[i];
                m_deliveredThisSlot[i] = false;
            }
            else
            {
                m_aoi[i] += m_slotDuration.GetSeconds();
            }
            m_rssiAge[i] += m_slotDuration.GetSeconds();
        }

        if (m_pendingGrantedNode >= 0)
        {
            WriteCsvRow(m_pendingGrantedNode,
                        m_pendingShieldFired,
                        anyDelivered,
                        deliveredNode,
                        deliveredAgeS);
        }

        // Safety shield: force-grant the highest-urgency ceiling violator.
        bool shieldFired = false;
        int shieldNode = -1;
        double maxUrgency = -1.0;
        for (uint32_t i = 0; i < N_NODES; ++i)
        {
            if (m_aoi[i] >= SHIELD_CEILING[i])
            {
                double urgency = WEIGHTS[i] * m_aoi[i];
                if (urgency > maxUrgency)
                {
                    maxUrgency = urgency;
                    shieldNode = static_cast<int>(i);
                    shieldFired = true;
                }
            }
        }

        int chosenNode;
        if (shieldFired)
        {
            chosenNode = shieldNode;
            m_shieldActivations++;
        }
        else
        {
            chosenNode = RunScheduler();
        }

        Ptr<Packet> grantPkt = Create<Packet>(16);
        m_grantSocket->SendTo(grantPkt,
                               0,
                               InetSocketAddress(m_staAddrs[chosenNode], PORT_GRANT));

        m_pendingGrantedNode = chosenNode;
        m_pendingShieldFired = shieldFired;

        Simulator::Schedule(m_slotDuration, &MasterSchedulerApp::SlotTick, this);
    }

    int RunScheduler()
    {
        switch (m_schedulerType)
        {
        case SCHED_RR:
            return static_cast<int>(m_currentSlot % N_NODES);

        case SCHED_FPQ: {
            uint32_t best = 0;
            for (uint32_t i = 1; i < N_NODES; ++i)
            {
                if (ClassPriority(i) > ClassPriority(best) ||
                    (ClassPriority(i) == ClassPriority(best) && m_aoi[i] > m_aoi[best]))
                {
                    best = i;
                }
            }
            return static_cast<int>(best);
        }

        case SCHED_MAXWEIGHT: {
            uint32_t best = 0;
            for (uint32_t i = 1; i < N_NODES; ++i)
            {
                if (WEIGHTS[i] * m_aoi[i] > WEIGHTS[best] * m_aoi[best])
                {
                    best = i;
                }
            }
            return static_cast<int>(best);
        }

        case SCHED_CAG: {
            uint32_t best = 0;
            double bestScore = -1.0;
            for (uint32_t i = 0; i < N_NODES; ++i)
            {
                double ps = 1.0 / (1.0 + std::exp(-(m_rssi[i] - R50_DBM) / BETA_LOG));
                double score = WEIGHTS[i] * m_aoi[i] * ps;
                if (score > bestScore)
                {
                    bestScore = score;
                    best = i;
                }
            }
            return static_cast<int>(best);
        }

        case SCHED_RANDOM:
            return static_cast<int>(std::lround(m_randomPick->GetValue())) % N_NODES;
        }
        return 0;
    }

    void HandleDataReply(Ptr<Socket> socket)
    {
        Address from;
        Ptr<Packet> pkt = socket->RecvFrom(from);
        AoITimestampTag tag;
        if (!pkt->PeekPacketTag(tag))
        {
            return;
        }
        uint32_t srcId = tag.GetNodeId();
        if (srcId >= N_NODES)
        {
            return;
        }
        uint64_t genTimeUs = tag.GetGenTimeUs();
        uint64_t nowUs = Simulator::Now().GetMicroSeconds();

        double deliveredAgeS = static_cast<double>(nowUs - genTimeUs) / 1e6;
        m_aoi[srcId] = deliveredAgeS; // generation-time AoI reset (D0.1)
        m_deliveredThisSlot[srcId] = true;
        m_pendingDeliveredAgeS[srcId] = deliveredAgeS;
        m_lastRssiAtRx = m_rssi[srcId];
        m_packetsReceived++;
        m_rssiAge[srcId] = 0.0;
    }

    void HandleHeartbeat(Ptr<Socket> socket)
    {
        Address from;
        Ptr<Packet> pkt = socket->RecvFrom(from);
        AoITimestampTag tag;
        if (!pkt->PeekPacketTag(tag))
        {
            return;
        }
        uint32_t srcId = tag.GetNodeId();
        if (srcId < N_NODES)
        {
            m_rssiAge[srcId] = 0.0; // heartbeats refresh liveness, not AoI
        }
    }

    void WriteCsvRow(int grantedNode,
                      bool shieldFired,
                      bool uplinkReceived,
                      int deliveredNode,
                      double deliveredAgeS)
    {
        uint64_t deliveredAgeUs = uplinkReceived
                                       ? static_cast<uint64_t>(deliveredAgeS * 1e6)
                                       : 0;
        double rssiAtRx = uplinkReceived ? m_lastRssiAtRx : -999.0;
        // Queue occupancy is not directly observable by the gateway (as on
        // the real hardware, which has no explicit "queue empty" signal);
        // it is inferred from whether the granted node actually replied.
        int queueStatus = uplinkReceived ? 1 : 0;
        // WifiPsMode is forced to NONE (D1.3): radios never sleep, so the
        // per-slot TX-energy proxy cost is constant regardless of who is
        // granted.
        const double energyProxyCost = 1.0;
        if (!uplinkReceived)
        {
            m_emptyGrants++;
        }

        m_csvFile << m_currentSlot << "," << Simulator::Now().GetSeconds() << ","
                  << SchedulerName(m_schedulerType) << "," << grantedNode << ","
                  << (shieldFired ? 1 : 0) << "," << (uplinkReceived ? 1 : 0) << ","
                  << deliveredNode << "," << deliveredAgeUs << "," << rssiAtRx << ","
                  << queueStatus << "," << energyProxyCost << ",0,0," << m_aoi[0] << ","
                  << m_aoi[1] << "," << m_aoi[2] << "," << m_aoi[3] << "," << m_rssi[0] << ","
                  << m_rssi[1] << "," << m_rssi[2] << "," << m_rssi[3] << "\n";
    }

    std::vector<Ipv4Address> m_staAddrs;
    Time m_slotDuration;
    SchedulerType m_schedulerType;
    std::string m_csvOutputPath;

    Ptr<Socket> m_grantSocket;
    Ptr<Socket> m_dataSocket;
    Ptr<Socket> m_hbSocket;
    Ptr<UniformRandomVariable> m_randomPick;

    double m_aoi[N_NODES];
    double m_rssi[N_NODES];
    double m_rssiAge[N_NODES];
    bool m_deliveredThisSlot[N_NODES];
    double m_pendingDeliveredAgeS[N_NODES];
    double m_lastRssiAtRx{-60.0};

    uint32_t m_currentSlot{0};
    std::ofstream m_csvFile;

    uint32_t m_shieldActivations{0};
    uint32_t m_totalSlots{0};
    uint32_t m_packetsReceived{0};
    uint32_t m_emptyGrants{0};

    // The most recently sent grant, awaiting its outcome to be logged by
    // the next SlotTick (see SlotTick's comment). -1 means "none yet".
    int m_pendingGrantedNode{-1};
    bool m_pendingShieldFired{false};

    static MasterSchedulerApp* g_instance;
};

MasterSchedulerApp* MasterSchedulerApp::g_instance = nullptr;

// ─────────────────────────────────────────────────────────────────────────
// RSSI monitoring: tap the WifiPhy MonitorSnifferRx trace at the AP so the
// scheduler has a live channel-quality estimate per node (used by CAG).
// ─────────────────────────────────────────────────────────────────────────

static void
RssiMonitorCallback(Ptr<const Packet> packet,
                     uint16_t /*channelFreqMhz*/,
                     WifiTxVector /*txVector*/,
                     MpduInfo /*aMpdu*/,
                     SignalNoiseDbm signalNoise,
                     uint16_t /*staId*/)
{
    AoITimestampTag tag;
    if (packet->PeekPacketTag(tag) && MasterSchedulerApp::GetInstance())
    {
        MasterSchedulerApp::GetInstance()->UpdateRssiEstimate(tag.GetNodeId(), signalNoise.signal);
    }
}

// ─────────────────────────────────────────────────────────────────────────
// main()
// ─────────────────────────────────────────────────────────────────────────

int
main(int argc, char* argv[])
{
    std::string schedulerStr = "rr";
    double slotDurationS = 0.1;
    double simTimeS = 300.0;
    uint32_t seed = 1;
    bool enableNetAnim = true;
    std::string csvOutput = "results/output.csv";

    CommandLine cmd(__FILE__);
    cmd.AddValue("scheduler", "rr|fpq|maxweight|cag|random", schedulerStr);
    cmd.AddValue("slotDuration", "Slot duration in seconds", slotDurationS);
    cmd.AddValue("simTime", "Simulation duration in seconds", simTimeS);
    cmd.AddValue("seed", "RNG seed", seed);
    cmd.AddValue("enableNetAnim", "Enable NetAnim XML output", enableNetAnim);
    cmd.AddValue("csvOutput", "Path for CSV telemetry output", csvOutput);
    cmd.Parse(argc, argv);

    RngSeedManager::SetSeed(seed);
    SchedulerType schedType = ParseSchedulerType(schedulerStr);

    // NetAnim/FlowMonitor outputs are colocated with the CSV so a campaign
    // that points --csvOutput at a per-run directory keeps all three
    // artifacts together.
    std::string resultsDir = ".";
    {
        auto slashPos = csvOutput.find_last_of('/');
        if (slashPos != std::string::npos)
        {
            resultsDir = csvOutput.substr(0, slashPos);
        }
    }
    std::string netanimPath = resultsDir + "/topology.xml";
    std::string flowmonPath = resultsDir + "/flowmon-results.xml";

    // ── Nodes ──
    NodeContainer apNode;
    apNode.Create(1);
    NodeContainer staNodes;
    staNodes.Create(N_NODES);
    NodeContainer allNodes(apNode, staNodes);

    // ── Wi-Fi channel: LogDistance chained with Nakagami fading ──
    Ptr<LogDistancePropagationLossModel> logDist = CreateObject<LogDistancePropagationLossModel>();
    logDist->SetAttribute("Exponent", DoubleValue(2.8));
    logDist->SetAttribute("ReferenceDistance", DoubleValue(1.0));
    logDist->SetAttribute("ReferenceLoss", DoubleValue(40.046)); // free-space loss @1m, 2.4GHz

    Ptr<NakagamiPropagationLossModel> nakagami = CreateObject<NakagamiPropagationLossModel>();
    nakagami->SetAttribute("m0", DoubleValue(1.5));  // near-field, d < 80m
    nakagami->SetAttribute("m1", DoubleValue(1.0));  // Rayleigh, mid-range
    nakagami->SetAttribute("m2", DoubleValue(0.75)); // severe fading, far-field
    logDist->SetNext(nakagami);

    Ptr<YansWifiChannel> channel = CreateObject<YansWifiChannel>();
    channel->SetPropagationLossModel(logDist);
    channel->SetPropagationDelayModel(CreateObject<ConstantSpeedPropagationDelayModel>());

    YansWifiPhyHelper phy;
    phy.SetChannel(channel);
    // HT20 on channel 1, 2.4GHz -- the exact band/width the ESP32 uses.
    phy.Set("ChannelSettings", StringValue("{1, 20, BAND_2_4GHZ, 0}"));

    // ── Wi-Fi MAC: 802.11n 2.4GHz, matching the ESP32 hardware ──
    WifiHelper wifi;
    wifi.SetStandard(WIFI_STANDARD_80211n);
    wifi.SetRemoteStationManager("ns3::ConstantRateWifiManager",
                                 "DataMode",
                                 StringValue("HtMcs0"),
                                 "ControlMode",
                                 StringValue("HtMcs0"));

    WifiMacHelper mac;
    Ssid ssid = Ssid("aoi-iot-net");

    mac.SetType("ns3::StaWifiMac", "Ssid", SsidValue(ssid), "ActiveProbing", BooleanValue(false));
    NetDeviceContainer staDevs = wifi.Install(phy, mac, staNodes);

    mac.SetType("ns3::ApWifiMac", "Ssid", SsidValue(ssid));
    NetDeviceContainer apDev = wifi.Install(phy, mac, apNode);

    // ── Mobility: static radial placement, RSSI diversity by distance ──
    MobilityHelper mobility;
    Ptr<ListPositionAllocator> posAlloc = CreateObject<ListPositionAllocator>();
    posAlloc->Add(Vector(0.0, 0.0, 1.5)); // AP at the centre
    for (uint32_t i = 0; i < N_NODES; ++i)
    {
        posAlloc->Add(Vector(NODE_X[i], NODE_Y[i], 1.0));
    }
    mobility.SetPositionAllocator(posAlloc);
    mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mobility.Install(allNodes);

    // ── Internet stack + addressing ──
    InternetStackHelper internet;
    internet.Install(allNodes);
    Ipv4AddressHelper ipv4;
    ipv4.SetBase("192.168.1.0", "255.255.255.0");
    Ipv4InterfaceContainer apIf = ipv4.Assign(apDev);
    Ipv4InterfaceContainer staIf = ipv4.Assign(staDevs);

    // ── Applications ──
    std::vector<Ipv4Address> staAddrs;
    for (uint32_t i = 0; i < N_NODES; ++i)
    {
        staAddrs.push_back(staIf.GetAddress(i));
        Ptr<IoTSensorApp> sensorApp = CreateObject<IoTSensorApp>(i, apIf.GetAddress(0), 0.1, 2.0);
        staNodes.Get(i)->AddApplication(sensorApp);
        sensorApp->SetStartTime(Seconds(0.5));
        sensorApp->SetStopTime(Seconds(simTimeS));
    }

    Ptr<MasterSchedulerApp> masterApp =
        CreateObject<MasterSchedulerApp>(staAddrs, Seconds(slotDurationS), schedType, csvOutput);
    apNode.Get(0)->AddApplication(masterApp);
    masterApp->SetStartTime(Seconds(1.0)); // start after Wi-Fi association settles
    masterApp->SetStopTime(Seconds(simTimeS));

    // ── RSSI monitoring via the AP's PHY sniffer trace ──
    Config::ConnectWithoutContext(
        "/NodeList/" + std::to_string(apNode.Get(0)->GetId()) +
            "/DeviceList/*/$ns3::WifiNetDevice/Phy/MonitorSnifferRx",
        MakeCallback(&RssiMonitorCallback));

    // ── FlowMonitor ──
    FlowMonitorHelper flowmonHelper;
    Ptr<FlowMonitor> monitor = flowmonHelper.InstallAll();

    // ── NetAnim (AnimationInterface is not an ns3::Object, so it is owned
    // by a plain unique_ptr rather than Ptr<>) ──
    std::unique_ptr<AnimationInterface> anim;
    if (enableNetAnim)
    {
        anim = std::make_unique<AnimationInterface>(netanimPath);
        anim->SetMaxPktsPerTraceFile(500000);

        uint32_t apId = apNode.Get(0)->GetId();
        anim->UpdateNodeDescription(apId, "Gateway-AP");
        anim->UpdateNodeColor(apId, 220, 20, 20);
        anim->UpdateNodeSize(apId, 3.0, 3.0);

        static const std::string labels[N_NODES] = {"STA-1 (Urgent w=10)",
                                                      "STA-2 (Urgent w=10)",
                                                      "STA-3 (Important w=3)",
                                                      "STA-4 (Routine w=1)"};
        static const uint8_t colorR[N_NODES] = {255, 255, 255, 0};
        static const uint8_t colorG[N_NODES] = {140, 140, 200, 180};
        static const uint8_t colorB[N_NODES] = {0, 0, 0, 255};
        for (uint32_t i = 0; i < N_NODES; ++i)
        {
            uint32_t staId = staNodes.Get(i)->GetId();
            anim->UpdateNodeDescription(staId, labels[i]);
            anim->UpdateNodeColor(staId, colorR[i], colorG[i], colorB[i]);
        }
    }

    // ── Run ──
    Simulator::Stop(Seconds(simTimeS));
    Simulator::Run();

    monitor->CheckForLostPackets();
    monitor->SerializeToXmlFile(flowmonPath, true, true);

    Simulator::Destroy();
    return 0;
}
