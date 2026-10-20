/*
 * AoI DRL Scheduler -- NS-3 simulation and evaluation engine.
 *
 * Models the 1-AP + 4-STA star topology of the ESP32 + Raspberry Pi testbed,
 * using the application-layer centralized grant-reply protocol matching
 * common/contracts/packets.py and config/system.yaml.
 *
 * Schedulers supported:
 *   - Round Robin (rr)
 *   - Fixed Priority (fpq)
 *   - Max-Weight (maxweight)
 *   - Channel-Aware Greedy (cag)
 *   - Random (random)
 *   - Deep Q-Network (dqn) via dqn-policy.h C++ inference (N1.2, N2.1)
 *
 * Includes:
 *   - Deterministic safety shield (bounds AoI violator urgency)
 *   - Liveness tracking (OK -> DEGRADED (3 misses) -> UNREACHABLE (5 misses))
 *   - Liveness masking (excludes unreachable nodes from shield and argmax)
 *   - Sidecar events logging (events.jsonl)
 *   - Live UDP telemetry streaming for real-time demo dashboard (N2.6)
 *   - Realistic channel & scenario controls: TxPower, PathLoss, Distance,
 *     Co-channel / Hidden Interferer, Waypoint Mobility, Fault Injection.
 */

#include "aoi-timestamp-tag.h"
#include "dqn-policy.h"

#include "ns3/core-module.h"
#include "ns3/flow-monitor-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/netanim-module.h"
#include "ns3/network-module.h"
#include "ns3/wifi-module.h"
#include "ns3/applications-module.h"
#include "ns3/arp-cache.h"
#include "ns3/ipv4-interface.h"

#include <arpa/inet.h>
#include <sys/socket.h>
#include <unistd.h>

#include <algorithm>
#include <cmath>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <memory>
#include <sstream>
#include <string>
#include <vector>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("AoiSchedulerSim");

// ─────────────────────────────────────────────────────────────────────────
// Global constants (mirrors config/system.yaml -- keep in sync)
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
static const double BETA_LOG = 4.0;
static const double ASSOC_END_S = 0.9; // all STAs associate before this; scheduler starts at 1.0 s
static const uint32_t PROBE_INTERVAL_SLOTS = 20; // re-probe UNREACHABLE nodes every 2 s at 0.1 s slots  // logistic slope width (dB)

// Node base positions in metres (AP at origin)
static const double BASE_NODE_X[N_NODES] = {5.0, 0.0, -12.0, 0.0};
static const double BASE_NODE_Y[N_NODES] = {0.0, 8.0, 0.0, -18.0};

// Liveness thresholds (from config/system.yaml)
static const uint32_t N_DEGRADED_THRESHOLD = 3;
static const uint32_t N_FAIL_THRESHOLD = 5;

// ─────────────────────────────────────────────────────────────────────────
// Scheduler Types
// ─────────────────────────────────────────────────────────────────────────

enum SchedulerType
{
    AOI_SCHED_RR,
    AOI_SCHED_FPQ,
    AOI_SCHED_MAXWEIGHT,
    AOI_SCHED_CAG,
    AOI_SCHED_RANDOM,
    AOI_SCHED_DQN
};

static SchedulerType
ParseSchedulerType(const std::string& s)
{
    if (s == "rr") return AOI_SCHED_RR;
    if (s == "fpq") return AOI_SCHED_FPQ;
    if (s == "maxweight") return AOI_SCHED_MAXWEIGHT;
    if (s == "cag") return AOI_SCHED_CAG;
    if (s == "random") return AOI_SCHED_RANDOM;
    if (s == "dqn") return AOI_SCHED_DQN;
    NS_FATAL_ERROR("Unknown --scheduler value: " << s
                   << " (expected rr|fpq|maxweight|cag|random|dqn)");
}

static std::string
SchedulerName(SchedulerType t)
{
    switch (t)
    {
    case AOI_SCHED_RR: return "rr";
    case AOI_SCHED_FPQ: return "fpq";
    case AOI_SCHED_MAXWEIGHT: return "maxweight";
    case AOI_SCHED_CAG: return "cag";
    case AOI_SCHED_RANDOM: return "random";
    case AOI_SCHED_DQN: return "dqn";
    }
    return "unknown";
}

static int
ClassPriority(uint32_t nodeId)
{
    const std::string& cls = NODE_CLASSES[nodeId];
    if (cls == "urgent") return 2;
    if (cls == "important") return 1;
    return 0;
}

enum LivenessState
{
    NODE_OK = 0,
    NODE_DEGRADED = 1,
    NODE_UNREACHABLE = 2
};

static std::string
LivenessName(LivenessState s)
{
    switch (s)
    {
    case NODE_OK: return "OK";
    case NODE_DEGRADED: return "DEGRADED";
    case NODE_UNREACHABLE: return "UNREACHABLE";
    }
    return "UNKNOWN";
}

// ─────────────────────────────────────────────────────────────────────────
// IoTSensorApp: Installed on each STA
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

    void SetFailed(bool failed)
    {
        m_failed = failed;
    }

    bool IsFailed() const
    {
        return m_failed;
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
        if (m_grantSocket) m_grantSocket->Close();
        if (m_dataSocket) m_dataSocket->Close();
        if (m_hbSocket) m_hbSocket->Close();
    }

    void GenerateSample()
    {
        if (!m_failed)
        {
            m_latestSampleTimeUs = Simulator::Now().GetMicroSeconds();
            m_queueOccupied = true; // LCFS-1: overwrite sample
        }
        m_sampleEvent =
            Simulator::Schedule(Seconds(m_sampleIntervalS), &IoTSensorApp::GenerateSample, this);
    }

    void HandleGrant(Ptr<Socket> socket)
    {
        Address from;
        socket->RecvFrom(from);

        if (m_failed || !m_queueOccupied)
        {
            return; // In fault state or empty queue: grant wasted
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
        if (!m_failed)
        {
            Ptr<Packet> packet = Create<Packet>(8);
            AoITimestampTag tag;
            tag.SetData(m_nodeId, 0); // genTime=0 marks a heartbeat
            packet->AddPacketTag(tag);
            m_hbSocket->SendTo(packet, 0, InetSocketAddress(m_gwAddr, PORT_HB));
        }

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
    bool m_failed{false};
    uint32_t m_seqNum{0};

    EventId m_sampleEvent;
    EventId m_hbEvent;
};

// ─────────────────────────────────────────────────────────────────────────
// MasterSchedulerApp: Installed on AP (Gateway)
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
                       std::string csvOutputPath,
                       std::string eventsOutputPath,
                       std::string policyFile,
                       std::string policyId,
                       uint16_t liveUdpPort)
        : m_staAddrs(std::move(staAddrs)),
          m_slotDuration(slotDuration),
          m_schedulerType(schedulerType),
          m_csvOutputPath(std::move(csvOutputPath)),
          m_eventsOutputPath(std::move(eventsOutputPath)),
          m_policyFile(std::move(policyFile)),
          m_policyId(std::move(policyId)),
          m_liveUdpPort(liveUdpPort)
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
            m_consecutiveMisses[i] = 0;
            m_liveness[i] = NODE_OK;
            m_queueEstimate[i] = true;
        }

        if (m_schedulerType == AOI_SCHED_DQN)
        {
            NS_ASSERT_MSG(!m_policyFile.empty(), "DQN scheduler requires --policyFile");
            std::cout << "[MasterSchedulerApp] Loading DQN policy from " << m_policyFile << "..." << std::endl;
            m_dqnPolicy.Load(m_policyFile);
            std::cout << "[MasterSchedulerApp] Loaded DQN policy (hash: "
                      << m_dqnPolicy.GetSchemaHash() << ")" << std::endl;
        }

        g_instance = this;
    }

    // Delivery-loss model mirroring the training channel (sim/channel.py): a logistic
    // success curve in RSSI layered with a Gilbert-Elliott burst chain, plus an optional
    // extra loss on one node during the interferer window (scenario S2). It is applied to
    // DATA frames the AP receives, on top of whatever the 802.11 PHY already drops.
    struct LossConfig
    {
        bool enabled{true};
        double r50{-82.0};
        double slope{4.0};
        double pGoodToBad{0.02};
        double pBadToGood{0.3};
        double badMult{0.3};
        int intfNode{-1};
        double intfLoss{0.0};
        double intfStart{0.0};
        double intfStop{0.0};
    };

    void ConfigureLoss(const LossConfig& cfg)
    {
        m_loss = cfg;
        m_lossRng = CreateObject<UniformRandomVariable>();
        for (uint32_t i = 0; i < N_NODES; ++i)
        {
            m_geBad[i] = false;
        }
    }

    void UpdateRssiEstimate(uint32_t nodeId, double rssiDbm)
    {
        if (nodeId < N_NODES)
        {
            m_rssi[nodeId] = rssiDbm;
            m_rssiAge[nodeId] = 0.0;
        }
    }

    void LogEvent(const std::string& eventType, int nodeId, const std::string& desc = "")
    {
        if (m_eventsFile.is_open())
        {
            m_eventsFile << "{\"time_s\":" << Simulator::Now().GetSeconds()
                         << ",\"event\":\"" << eventType << "\""
                         << ",\"node_id\":" << nodeId
                         << ",\"description\":\"" << desc << "\"}\n";
            m_eventsFile.flush();
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

        if (!m_eventsOutputPath.empty())
        {
            m_eventsFile.open(m_eventsOutputPath);
            NS_ASSERT_MSG(m_eventsFile.is_open(), "Failed to open events output: " << m_eventsOutputPath);
            LogEvent("SIM_START", -1, "Simulation started");
        }

        m_dataSocket = Socket::CreateSocket(GetNode(), UdpSocketFactory::GetTypeId());
        m_dataSocket->Bind(InetSocketAddress(Ipv4Address::GetAny(), PORT_DATA));
        m_dataSocket->SetRecvCallback(MakeCallback(&MasterSchedulerApp::HandleDataReply, this));

        m_hbSocket = Socket::CreateSocket(GetNode(), UdpSocketFactory::GetTypeId());
        m_hbSocket->Bind(InetSocketAddress(Ipv4Address::GetAny(), PORT_HB));
        m_hbSocket->SetRecvCallback(MakeCallback(&MasterSchedulerApp::HandleHeartbeat, this));

        m_grantSocket = Socket::CreateSocket(GetNode(), UdpSocketFactory::GetTypeId());
        m_grantSocket->Bind();

        if (m_liveUdpPort > 0)
        {
            // A real host UDP socket: ns-3's own sockets stay inside the simulated
            // network and would never reach the dashboard server.
            m_liveFd = ::socket(AF_INET, SOCK_DGRAM, 0);
            std::memset(&m_liveAddr, 0, sizeof(m_liveAddr));
            m_liveAddr.sin_family = AF_INET;
            m_liveAddr.sin_port = htons(m_liveUdpPort);
            ::inet_pton(AF_INET, "127.0.0.1", &m_liveAddr.sin_addr);
            std::cout << "[MasterSchedulerApp] Streaming live UDP telemetry to 127.0.0.1:"
                      << m_liveUdpPort << std::endl;
        }

        Simulator::Schedule(m_slotDuration, &MasterSchedulerApp::SlotTick, this);
    }

    void StopApplication() override
    {
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

        LogEvent("SIM_END", -1, "Simulation complete");

        std::string effectivePolicy = m_policyId.empty() ? SchedulerName(m_schedulerType) : m_policyId;
        std::cout << "=== Simulation Complete (" << effectivePolicy << ") ===" << std::endl;
        std::cout << "Total slots:         " << m_totalSlots << std::endl;
        std::cout << "Packets received:    " << m_packetsReceived << std::endl;
        double shieldPct = m_totalSlots > 0 ? (100.0 * m_shieldActivations / m_totalSlots) : 0.0;
        std::cout << "Shield activations:  " << m_shieldActivations << " (" << shieldPct << "%)" << std::endl;
        std::cout << "Empty grants:        " << m_emptyGrants << std::endl;
        std::cout << "Loss-model drops:    " << m_lossDropped << std::endl;

        if (m_csvFile.is_open()) m_csvFile.close();
        if (m_eventsFile.is_open()) m_eventsFile.close();
        if (m_liveFd >= 0) ::close(m_liveFd);
        g_instance = nullptr;
    }

    void StepGilbertElliott()
    {
        if (!m_loss.enabled) return;
        for (uint32_t i = 0; i < N_NODES; ++i)
        {
            double u = m_lossRng->GetValue();
            if (!m_geBad[i])
            {
                if (u < m_loss.pGoodToBad) m_geBad[i] = true;
            }
            else if (u < m_loss.pBadToGood)
            {
                m_geBad[i] = false;
            }
        }
    }

    // True if the DATA frame from `node` survives the modelled channel.
    bool DeliveryOk(uint32_t node)
    {
        if (!m_loss.enabled) return true;
        double p = 1.0 / (1.0 + std::exp(-(m_rssi[node] - m_loss.r50) / m_loss.slope));
        if (m_geBad[node]) p *= m_loss.badMult;
        double t = Simulator::Now().GetSeconds();
        if (static_cast<int>(node) == m_loss.intfNode && t >= m_loss.intfStart && t < m_loss.intfStop)
        {
            p *= (1.0 - m_loss.intfLoss);
        }
        return m_lossRng->GetValue() < p;
    }

    void SlotTick()
    {
        m_currentSlot++;
        m_totalSlots++;
        StepGilbertElliott();

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

                // Liveness update: recovered on delivery
                if (m_liveness[i] != NODE_OK)
                {
                    m_liveness[i] = NODE_OK;
                    LogEvent("NODE_RECOVERED", i, "Received DATA reply, status restored to OK");
                }
                m_consecutiveMisses[i] = 0;
                m_queueEstimate[i] = false;
            }
            else
            {
                m_aoi[i] += m_slotDuration.GetSeconds();
                // 10 Hz sampling: a new sample arrives in each 0.1s slot
                m_queueEstimate[i] = true;
            }
            m_rssiAge[i] += m_slotDuration.GetSeconds();
        }

        // Liveness tracking for the node that was granted last slot
        if (m_pendingGrantedNode >= 0)
        {
            if (!anyDelivered)
            {
                m_consecutiveMisses[m_pendingGrantedNode]++;
                if (m_consecutiveMisses[m_pendingGrantedNode] == N_DEGRADED_THRESHOLD)
                {
                    m_liveness[m_pendingGrantedNode] = NODE_DEGRADED;
                    LogEvent("NODE_DEGRADED", m_pendingGrantedNode, "3 consecutive missed grants");
                }
                else if (m_consecutiveMisses[m_pendingGrantedNode] == N_FAIL_THRESHOLD)
                {
                    m_liveness[m_pendingGrantedNode] = NODE_UNREACHABLE;
                    LogEvent("NODE_UNREACHABLE", m_pendingGrantedNode, "5 consecutive missed grants, masking node");
                }
            }

            WriteCsvRow(m_pendingGrantedNode,
                        m_pendingShieldFired,
                        anyDelivered,
                        deliveredNode,
                        deliveredAgeS);
        }

        // ── Deterministic Safety Shield (N2.1, N2.3) ──
        // Force-grant the highest urgency ceiling violator AMONG REACHABLE NODES
        bool shieldFired = false;
        int shieldNode = -1;
        double maxUrgency = -1.0;
        for (uint32_t i = 0; i < N_NODES; ++i)
        {
            // Mask out unreachable nodes so dead node doesn't starve reachable nodes (N2.3)
            if (m_liveness[i] != NODE_UNREACHABLE && m_aoi[i] >= SHIELD_CEILING[i])
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

        int chosenNode = -1;
        if (shieldFired)
        {
            chosenNode = shieldNode;
            m_shieldActivations++;
            LogEvent("SHIELD_TRIGGERED", chosenNode, "Shield force-grant (urgency=" + std::to_string(maxUrgency) + ")");
        }
        else
        {
            // Recovery probe: a node masked as UNREACHABLE is re-granted every
            // PROBE_INTERVAL_SLOTS so one bad stretch cannot starve it forever.
            for (uint32_t i = 0; i < N_NODES; ++i)
            {
                if (m_liveness[i] == NODE_UNREACHABLE &&
                    m_currentSlot - m_lastProbeSlot[i] >= PROBE_INTERVAL_SLOTS)
                {
                    chosenNode = static_cast<int>(i);
                    m_lastProbeSlot[i] = m_currentSlot;
                    break;
                }
            }
            if (chosenNode < 0) chosenNode = RunScheduler();
        }

        // Send grant to chosen node
        Ptr<Packet> grantPkt = Create<Packet>(16);
        m_grantSocket->SendTo(grantPkt,
                               0,
                               InetSocketAddress(m_staAddrs[chosenNode], PORT_GRANT));

        m_pendingGrantedNode = chosenNode;
        m_pendingShieldFired = shieldFired;

        Simulator::Schedule(m_slotDuration, &MasterSchedulerApp::SlotTick, this);
    }

    void BuildObservation(float obs[16]) const
    {
        for (uint32_t i = 0; i < N_NODES; ++i)
        {
            // aoi_norm: min(aoi / 10.0, 1.0)
            obs[i * 4 + 0] = static_cast<float>(std::min(m_aoi[i] / 10.0, 1.0));
            // queue_norm: 1.0 if sample generated since last delivery, 0.0 otherwise
            obs[i * 4 + 1] = m_queueEstimate[i] ? 1.0f : 0.0f;
            // rssi_norm: clip((rssi - (-100.0)) / 70.0, 0.0, 1.0)
            double r_norm = (m_rssi[i] - (-100.0)) / 70.0;
            obs[i * 4 + 2] = static_cast<float>(std::max(0.0, std::min(1.0, r_norm)));
            // weight_norm: weight / 10.0
            obs[i * 4 + 3] = static_cast<float>(WEIGHTS[i] / 10.0);
        }
    }

    int RunScheduler()
    {
        // Reachability mask: skip UNREACHABLE nodes unless all are unreachable
        std::vector<bool> reachable(N_NODES, true);
        int reachableCount = 0;
        for (uint32_t i = 0; i < N_NODES; ++i)
        {
            if (m_liveness[i] == NODE_UNREACHABLE)
            {
                reachable[i] = false;
            }
            else
            {
                reachableCount++;
            }
        }
        if (reachableCount == 0)
        {
            std::fill(reachable.begin(), reachable.end(), true);
        }

        switch (m_schedulerType)
        {
        case AOI_SCHED_RR: {
            for (uint32_t step = 0; step < N_NODES; ++step)
            {
                uint32_t cand = (m_currentSlot + step) % N_NODES;
                if (reachable[cand]) return static_cast<int>(cand);
            }
            return static_cast<int>(m_currentSlot % N_NODES);
        }

        case AOI_SCHED_FPQ: {
            int best = -1;
            for (uint32_t i = 0; i < N_NODES; ++i)
            {
                if (!reachable[i]) continue;
                if (best == -1 ||
                    ClassPriority(i) > ClassPriority(best) ||
                    (ClassPriority(i) == ClassPriority(best) && m_aoi[i] > m_aoi[best]))
                {
                    best = static_cast<int>(i);
                }
            }
            return (best >= 0) ? best : 0;
        }

        case AOI_SCHED_MAXWEIGHT: {
            int best = -1;
            for (uint32_t i = 0; i < N_NODES; ++i)
            {
                if (!reachable[i]) continue;
                if (best == -1 || (WEIGHTS[i] * m_aoi[i] > WEIGHTS[best] * m_aoi[best]))
                {
                    best = static_cast<int>(i);
                }
            }
            return (best >= 0) ? best : 0;
        }

        case AOI_SCHED_CAG: {
            int best = -1;
            double bestScore = -1e30;
            for (uint32_t i = 0; i < N_NODES; ++i)
            {
                if (!reachable[i]) continue;
                double ps = 1.0 / (1.0 + std::exp(-(m_rssi[i] - R50_DBM) / BETA_LOG));
                double score = WEIGHTS[i] * m_aoi[i] * ps;
                if (best == -1 || score > bestScore)
                {
                    bestScore = score;
                    best = static_cast<int>(i);
                }
            }
            return (best >= 0) ? best : 0;
        }

        case AOI_SCHED_RANDOM: {
            std::vector<int> cands;
            for (uint32_t i = 0; i < N_NODES; ++i)
            {
                if (reachable[i]) cands.push_back(static_cast<int>(i));
            }
            if (cands.empty()) return 0;
            uint32_t idx = static_cast<uint32_t>(std::lround(m_randomPick->GetValue())) % cands.size();
            return cands[idx];
        }

        case AOI_SCHED_DQN: {
            float obs[16];
            BuildObservation(obs);
            return m_dqnPolicy.ActMasked(obs, reachable);
        }
        }
        return 0;
    }

    void HandleDataReply(Ptr<Socket> socket)
    {
        Address from;
        Ptr<Packet> pkt = socket->RecvFrom(from);
        AoITimestampTag tag;
        if (!pkt->PeekPacketTag(tag)) return;

        uint32_t srcId = tag.GetNodeId();
        if (srcId >= N_NODES) return;

        if (!DeliveryOk(srcId))
        {
            m_lossDropped++;
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
        if (!pkt->PeekPacketTag(tag)) return;

        uint32_t srcId = tag.GetNodeId();
        if (srcId < N_NODES)
        {
            m_rssiAge[srcId] = 0.0;
            if (m_liveness[srcId] == NODE_UNREACHABLE)
            {
                m_liveness[srcId] = NODE_OK;
                m_consecutiveMisses[srcId] = 0;
                LogEvent("NODE_RECOVERED", srcId, "Received HEARTBEAT, status restored to OK");
            }
        }
    }

    void WriteCsvRow(int grantedNode,
                     bool shieldFired,
                     bool uplinkReceived,
                     int deliveredNode,
                     double deliveredAgeS)
    {
        uint64_t deliveredAgeUs = uplinkReceived ? static_cast<uint64_t>(deliveredAgeS * 1e6) : 0;
        double rssiAtRx = uplinkReceived ? m_lastRssiAtRx : -999.0;
        int queueStatus = uplinkReceived ? 1 : 0;
        const double energyProxyCost = 1.0;
        if (!uplinkReceived)
        {
            m_emptyGrants++;
        }

        std::string effectivePolicy = m_policyId.empty() ? SchedulerName(m_schedulerType) : m_policyId;

        // Write CSV row in SLOT_LOG_COLUMNS format
        m_csvFile << m_currentSlot << "," << Simulator::Now().GetSeconds() << ","
                  << effectivePolicy << "," << grantedNode << ","
                  << (shieldFired ? 1 : 0) << "," << (uplinkReceived ? 1 : 0) << ","
                  << deliveredNode << "," << deliveredAgeUs << "," << rssiAtRx << ","
                  << queueStatus << "," << energyProxyCost << ",0,0,"
                  << m_aoi[0] << "," << m_aoi[1] << "," << m_aoi[2] << "," << m_aoi[3] << ","
                  << m_rssi[0] << "," << m_rssi[1] << "," << m_rssi[2] << "," << m_rssi[3] << "\n";

        // Stream UDP JSON telemetry if enabled (N2.6)
        if (m_liveFd >= 0)
        {
            std::ostringstream ss;
            ss << std::fixed << std::setprecision(4);
            ss << "{\"slot_id\":" << m_currentSlot
               << ",\"timestamp\":" << Simulator::Now().GetSeconds()
               << ",\"policy_id\":\"" << effectivePolicy << "\""
               << ",\"granted\":" << grantedNode
               << ",\"shield\":" << (shieldFired ? 1 : 0)
               << ",\"delivered\":" << deliveredNode
               << ",\"delivered_age_us\":" << deliveredAgeUs
               << ",\"aoi\":[" << m_aoi[0] << "," << m_aoi[1] << "," << m_aoi[2] << "," << m_aoi[3] << "]"
               << ",\"rssi\":[" << m_rssi[0] << "," << m_rssi[1] << "," << m_rssi[2] << "," << m_rssi[3] << "]"
               << ",\"liveness\":[" << m_liveness[0] << "," << m_liveness[1] << "," << m_liveness[2] << "," << m_liveness[3] << "]}"
               << "\n";
            std::string msg = ss.str();
            ::sendto(m_liveFd, msg.c_str(), msg.size(), 0,
                     reinterpret_cast<const sockaddr*>(&m_liveAddr), sizeof(m_liveAddr));
        }
    }

    std::vector<Ipv4Address> m_staAddrs;
    Time m_slotDuration;
    SchedulerType m_schedulerType;
    std::string m_csvOutputPath;
    std::string m_eventsOutputPath;
    std::string m_policyFile;
    std::string m_policyId;
    uint16_t m_liveUdpPort{0};

    Ptr<Socket> m_grantSocket;
    Ptr<Socket> m_dataSocket;
    Ptr<Socket> m_hbSocket;
    int m_liveFd{-1};
    sockaddr_in m_liveAddr{};
    Ptr<UniformRandomVariable> m_randomPick;

    double m_aoi[N_NODES];
    double m_rssi[N_NODES];
    double m_rssiAge[N_NODES];
    bool m_deliveredThisSlot[N_NODES];
    double m_pendingDeliveredAgeS[N_NODES];
    double m_lastRssiAtRx{-60.0};

    uint32_t m_consecutiveMisses[N_NODES];
    LivenessState m_liveness[N_NODES];
    bool m_queueEstimate[N_NODES];

    DqnPolicy m_dqnPolicy;

    uint32_t m_currentSlot{0};
    std::ofstream m_csvFile;
    std::ofstream m_eventsFile;

    uint32_t m_shieldActivations{0};
    uint32_t m_totalSlots{0};
    uint32_t m_packetsReceived{0};
    uint32_t m_emptyGrants{0};

    int m_pendingGrantedNode{-1};
    bool m_pendingShieldFired{false};

    LossConfig m_loss;
    Ptr<UniformRandomVariable> m_lossRng;
    bool m_geBad[N_NODES];
    uint32_t m_lastProbeSlot[N_NODES]{};
    uint32_t m_lossDropped{0};

    static MasterSchedulerApp* g_instance;
};

MasterSchedulerApp* MasterSchedulerApp::g_instance = nullptr;

// ─────────────────────────────────────────────────────────────────────────
// RSSI Tap
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

// Static ARP: every wifi interface gets permanent entries for all other wifi nodes. ARP is not what the
// experiment studies, and on a weak link a failed resolution makes ns-3 drop every packet to that
// neighbour for DeadTimeout (100 s), which silently decided runs instead of the scheduler.
static void
PopulateStaticArp(const std::vector<Ptr<NetDevice>>& devs)
{
    for (const auto& self : devs)
    {
        Ptr<Ipv4> ipv4 = self->GetNode()->GetObject<Ipv4>();
        int32_t ifIdx = ipv4->GetInterfaceForDevice(self);
        Ptr<ArpCache> cache = ipv4->GetObject<Ipv4L3Protocol>()->GetInterface(ifIdx)->GetArpCache();
        for (const auto& other : devs)
        {
            if (other == self) continue;
            Ptr<Ipv4> oIpv4 = other->GetNode()->GetObject<Ipv4>();
            Ipv4Address oAddr = oIpv4->GetAddress(oIpv4->GetInterfaceForDevice(other), 0).GetLocal();
            ArpCache::Entry* e = cache->Add(oAddr);
            e->SetMacAddress(Mac48Address::ConvertFrom(other->GetAddress()));
            e->MarkPermanent();
        }
    }
}

// Association tracing: logs when each STA associates / de-associates with the AP, so a node that
// is silent because it never joined the BSS can be told apart from a scheduler problem.
static int
NodeIdFromContext(const std::string& ctx)
{
    size_t p = ctx.find("/NodeList/");
    if (p == std::string::npos) return -1;
    return std::atoi(ctx.c_str() + p + 10);
}

static void
OnAssoc(std::string ctx, Mac48Address)
{
    int staId = NodeIdFromContext(ctx) - 1; // node 0 is the AP
    std::cout << "[assoc] t=" << Simulator::Now().GetSeconds() << " STA-" << (staId + 1) << " associated" << std::endl;
    if (staId >= 0 && MasterSchedulerApp::GetInstance())
        MasterSchedulerApp::GetInstance()->LogEvent("STA_ASSOCIATED", staId, "STA associated with AP");
}

static void
OnDeAssoc(std::string ctx, Mac48Address)
{
    int staId = NodeIdFromContext(ctx) - 1;
    std::cout << "[assoc] t=" << Simulator::Now().GetSeconds() << " STA-" << (staId + 1) << " DE-associated" << std::endl;
    if (staId >= 0 && MasterSchedulerApp::GetInstance())
        MasterSchedulerApp::GetInstance()->LogEvent("STA_DEASSOCIATED", staId, "STA lost association");
}

static void
OnApAssociated(std::string, uint16_t aid, Mac48Address addr)
{
    std::cout << "[ap-assoc] t=" << Simulator::Now().GetSeconds() << " AP registered STA aid=" << aid
              << " mac=" << addr << std::endl;
}

static void
OnApDeAssociated(std::string, uint16_t aid, Mac48Address addr)
{
    std::cout << "[ap-assoc] t=" << Simulator::Now().GetSeconds() << " AP REMOVED STA aid=" << aid
              << " mac=" << addr << std::endl;
}

// Optional drop accounting (--traceDrops): counts PHY rx failures and MAC tx drops per node, so a silent
// link can be attributed to a cause (e.g. preamble/SNR failures vs. MAC retry exhaustion).
static std::map<std::string, uint32_t> g_dropCounts;

static void
OnPhyRxDrop(std::string ctx, Ptr<const Packet>, WifiPhyRxfailureReason reason)
{
    g_dropCounts["node" + std::to_string(NodeIdFromContext(ctx)) + " PhyRxDrop reason=" +
                 std::to_string(static_cast<int>(reason))]++;
}

static void
OnMacTxDrop(std::string ctx, Ptr<const Packet>)
{
    g_dropCounts["node" + std::to_string(NodeIdFromContext(ctx)) + " MacTxDrop"]++;
}

int
main(int argc, char* argv[])
{
    std::string schedulerStr = "rr";
    std::string policyFile = "";
    std::string policyId = "";
    double slotDurationS = 0.1;
    double simTimeS = 300.0;
    uint32_t seed = 100;
    bool enableNetAnim = false;
    std::string csvOutput = "results/output.csv";

    // Scenario parameters (N2.2, N2.4, N2.6)
    double txPowerDbm = 20.0;        // matches sim/channel.py (N2.2)
    double pathLossExp = 2.8;         // LogDistance exponent
    double distanceScale = 1.0;       // distance scaling factor
    std::string interferer = "none";  // "none" | "cochannel" | "hidden"
    double intfStartS = 20.0;
    double intfStopS = 45.0;
    double intfRateMbps = 2.0;
    int mobileNode = -1;              // node id to apply waypoint mobility (e.g. 3)
    double mobileSpeed = 1.0;         // m/s
    int failNode = -1;                // node id to inject failure (e.g. 1)
    double failAtS = 70.0;
    double recoverAtS = 100.0;
    std::string scenarioFile = "";
    uint16_t liveUdpPort = 0;         // live telemetry port (N2.6)
    bool lossModel = true;            // delivery-loss model, defaults match config/measured_params.yaml
    MasterSchedulerApp::LossConfig lossCfg;
    bool staticArp = true;
    bool traceDrops = false;
    bool realtime = false;            // realtime simulation clock (N2.6)

    CommandLine cmd(__FILE__);
    cmd.AddValue("scheduler", "rr|fpq|maxweight|cag|random|dqn", schedulerStr);
    cmd.AddValue("policyFile", "Path to exported dqn_seedN.txt file (for dqn scheduler)", policyFile);
    cmd.AddValue("policyId", "Policy ID tag for CSV column (e.g. dqn_seed0)", policyId);
    cmd.AddValue("slotDuration", "Slot duration in seconds", slotDurationS);
    cmd.AddValue("simTime", "Simulation duration in seconds", simTimeS);
    cmd.AddValue("seed", "RNG replication seed (SetRun)", seed);
    cmd.AddValue("enableNetAnim", "Enable NetAnim XML output", enableNetAnim);
    cmd.AddValue("csvOutput", "Path for CSV telemetry output", csvOutput);
    cmd.AddValue("txPower", "AP and STA transmit power in dBm (default 20.0)", txPowerDbm);
    cmd.AddValue("pathLossExp", "Log-distance path loss exponent (default 2.8)", pathLossExp);
    cmd.AddValue("distanceScale", "Scale factor for STA distances (default 1.0)", distanceScale);
    cmd.AddValue("interferer", "Interferer mode: none|cochannel|hidden", interferer);
    cmd.AddValue("intfStart", "Interferer start time (s)", intfStartS);
    cmd.AddValue("intfStop", "Interferer stop time (s)", intfStopS);
    cmd.AddValue("intfRateMbps", "Interferer data rate in Mbps", intfRateMbps);
    cmd.AddValue("mobileNode", "Node ID for waypoint mobility (-1 to disable)", mobileNode);
    cmd.AddValue("mobileSpeed", "Mobility walking speed (m/s)", mobileSpeed);
    cmd.AddValue("failNode", "Node ID for fault injection (-1 to disable)", failNode);
    cmd.AddValue("failAt", "Node fault start time (s)", failAtS);
    cmd.AddValue("recoverAt", "Node fault recovery time (s)", recoverAtS);
    cmd.AddValue("scenarioFile", "Path to scenario JSON file", scenarioFile);
    cmd.AddValue("liveUdpPort", "UDP port for live telemetry streaming (0 to disable)", liveUdpPort);
    cmd.AddValue("lossModel", "Apply the logistic + Gilbert-Elliott delivery-loss model (matches sim/channel.py)", lossModel);
    cmd.AddValue("r50", "Logistic R50 (dBm)", lossCfg.r50);
    cmd.AddValue("slope", "Logistic slope (dB)", lossCfg.slope);
    cmd.AddValue("geGB", "Gilbert-Elliott P(good->bad) per slot", lossCfg.pGoodToBad);
    cmd.AddValue("geBG", "Gilbert-Elliott P(bad->good) per slot", lossCfg.pBadToGood);
    cmd.AddValue("geMult", "Gilbert-Elliott bad-state success multiplier", lossCfg.badMult);
    cmd.AddValue("intfLossNode", "Node hit by extra interferer loss during [intfStart,intfStop) (-1 = none)", lossCfg.intfNode);
    cmd.AddValue("intfLoss", "Extra loss probability on intfLossNode during the interferer window", lossCfg.intfLoss);
    cmd.AddValue("staticArp", "Pre-populate permanent ARP entries (removes ARP-resolution failures on weak links)", staticArp);
    cmd.AddValue("traceDrops", "Print PHY/MAC drop counts per node at the end of the run", traceDrops);
    cmd.AddValue("realtime", "Run in realtime mode (1 sim sec = 1 wall sec)", realtime);
    cmd.Parse(argc, argv);

    // If scenarioFile is demo.json or similar, configure default scenario timeline
    if (!scenarioFile.empty() && scenarioFile.find("demo.json") != std::string::npos)
    {
        simTimeS = 120.0;
        interferer = "cochannel";
        intfStartS = 20.0;
        intfStopS = 45.0;
        mobileNode = 3;
        mobileSpeed = 1.0;
        failNode = 1;
        lossCfg.intfNode = 3;      // co-channel interferer degrades STA-4 (~20% burst loss)
        lossCfg.intfLoss = 0.2;
        failAtS = 70.0;
        recoverAtS = 100.0;
    }

    if (realtime)
    {
        GlobalValue::Bind("SimulatorImplementationType", StringValue("ns3::RealtimeSimulatorImpl"));
    }

    // SetRun seeding (N2.5)
    RngSeedManager::SetSeed(1);
    RngSeedManager::SetRun(seed);

    SchedulerType schedType = ParseSchedulerType(schedulerStr);

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
    std::string eventsPath = resultsDir + "/events.jsonl";

    // ── Nodes ──
    NodeContainer apNode;
    apNode.Create(1);
    NodeContainer staNodes;
    staNodes.Create(N_NODES);
    NodeContainer allNodes(apNode, staNodes);

    // ── Wi-Fi Channel: LogDistance + Nakagami Fading ──
    Ptr<LogDistancePropagationLossModel> logDist = CreateObject<LogDistancePropagationLossModel>();
    logDist->SetAttribute("Exponent", DoubleValue(pathLossExp));
    logDist->SetAttribute("ReferenceDistance", DoubleValue(1.0));
    logDist->SetAttribute("ReferenceLoss", DoubleValue(40.046)); // 1m @ 2.4GHz

    Ptr<NakagamiPropagationLossModel> nakagami = CreateObject<NakagamiPropagationLossModel>();
    nakagami->SetAttribute("m0", DoubleValue(1.5));
    nakagami->SetAttribute("m1", DoubleValue(1.0));
    nakagami->SetAttribute("m2", DoubleValue(0.75));
    logDist->SetNext(nakagami);

    Ptr<YansWifiChannel> channel = CreateObject<YansWifiChannel>();
    channel->SetPropagationLossModel(logDist);
    channel->SetPropagationDelayModel(CreateObject<ConstantSpeedPropagationDelayModel>());

    YansWifiPhyHelper phy;
    phy.SetChannel(channel);
    // Associate at normal power, then drop to the scenario TX power (see ASSOC_END_S below). At low
    // power the association-response ACK can be lost, leaving the STA believing it is associated while
    // the AP never registered it (half-open association): the STA then stays silent for hundreds of s.
    const double assocTxPowerDbm = std::max(txPowerDbm, 16.0206);
    phy.Set("TxPowerStart", DoubleValue(assocTxPowerDbm));
    phy.Set("TxPowerEnd", DoubleValue(assocTxPowerDbm));
    phy.Set("ChannelSettings", StringValue("{1, 20, BAND_2_4GHZ, 0}"));

    // ── Wi-Fi MAC: 802.11n 2.4GHz ──
    WifiHelper wifi;
    wifi.SetStandard(WIFI_STANDARD_80211n);
    wifi.SetRemoteStationManager("ns3::ConstantRateWifiManager",
                                 "DataMode", StringValue("HtMcs0"),
                                 "ControlMode", StringValue("HtMcs0"));

    WifiMacHelper mac;
    Ssid ssid = Ssid("aoi-iot-net");

    // MaxMissedBeacons is effectively disabled: the testbed STAs do not roam, and beacon-loss
    // de-association followed by re-association at low power re-creates half-open associations.
    mac.SetType("ns3::StaWifiMac", "Ssid", SsidValue(ssid), "ActiveProbing", BooleanValue(false),
                "MaxMissedBeacons", UintegerValue(1000000));
    NetDeviceContainer staDevs = wifi.Install(phy, mac, staNodes);

    mac.SetType("ns3::ApWifiMac", "Ssid", SsidValue(ssid));
    NetDeviceContainer apDev = wifi.Install(phy, mac, apNode);

    // ── Mobility ──
    // The mobile node gets a WaypointMobilityModel *instead of* ConstantPosition: aggregating
    // a second MobilityModel onto a node that already has one is silently ignored by ns-3
    // (GetObject returns the first), which made the walk a no-op.
    const int mobileIdx = (mobileNode >= 0 && mobileNode < static_cast<int>(N_NODES)) ? mobileNode : -1;
    MobilityHelper mobility;
    Ptr<ListPositionAllocator> posAlloc = CreateObject<ListPositionAllocator>();
    NodeContainer constNodes;
    posAlloc->Add(Vector(0.0, 0.0, 1.5)); // AP
    constNodes.Add(apNode);
    for (uint32_t i = 0; i < N_NODES; ++i)
    {
        if (static_cast<int>(i) == mobileIdx) continue;
        posAlloc->Add(Vector(BASE_NODE_X[i] * distanceScale, BASE_NODE_Y[i] * distanceScale, 1.0));
        constNodes.Add(staNodes.Get(i));
    }
    mobility.SetPositionAllocator(posAlloc);
    mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mobility.Install(constNodes);

    if (mobileIdx >= 0)
    {
        MobilityHelper wm;
        wm.SetMobilityModel("ns3::WaypointMobilityModel");
        wm.Install(staNodes.Get(mobileIdx));
        Ptr<WaypointMobilityModel> wayMob = staNodes.Get(mobileIdx)->GetObject<WaypointMobilityModel>();
        double origX = BASE_NODE_X[mobileIdx] * distanceScale;
        double origY = BASE_NODE_Y[mobileIdx] * distanceScale;
        double farY = -45.0 * distanceScale;
        double travelTime = std::abs(farY - origY) / std::max(0.1, mobileSpeed);

        wayMob->AddWaypoint(Waypoint(Seconds(0.0), Vector(origX, origY, 1.0)));
        wayMob->AddWaypoint(Waypoint(Seconds(45.0), Vector(origX, origY, 1.0)));
        wayMob->AddWaypoint(Waypoint(Seconds(45.0 + travelTime), Vector(origX, farY, 1.0)));
        wayMob->AddWaypoint(Waypoint(Seconds(80.0), Vector(origX, farY, 1.0)));
        wayMob->AddWaypoint(Waypoint(Seconds(80.0 + travelTime), Vector(origX, origY, 1.0)));
    }

    // ── Interferer Setup (N2.4) ──
    if (interferer != "none")
    {
        NodeContainer intfNodes;
        intfNodes.Create(2);

        MobilityHelper intfMobility;
        Ptr<ListPositionAllocator> intfPos = CreateObject<ListPositionAllocator>();
        if (interferer == "hidden")
        {
            // Hidden terminal: out of carrier-sense range of AP (>80m), near STA-4
            intfPos->Add(Vector(0.0, -35.0, 1.0));
            intfPos->Add(Vector(0.0, -40.0, 1.0));
        }
        else // "cochannel"
        {
            intfPos->Add(Vector(10.0, 0.0, 1.5));
            intfPos->Add(Vector(12.0, 0.0, 1.5));
        }
        intfMobility.SetPositionAllocator(intfPos);
        intfMobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
        intfMobility.Install(intfNodes);

        // Ad-hoc MAC: the interferers must not beacon or accept associations. With the
        // leftover ApWifiMac (same SSID) they became rogue APs, and the STAs associated
        // with them, so grants to STA-1/STA-4 never reached the real AP.
        mac.SetType("ns3::AdhocWifiMac");
        NetDeviceContainer intfDevs = wifi.Install(phy, mac, intfNodes);

        InternetStackHelper internetIntf;
        internetIntf.Install(intfNodes);
        Ipv4AddressHelper ipv4Intf;
        ipv4Intf.SetBase("192.168.2.0", "255.255.255.0");
        Ipv4InterfaceContainer intfIf = ipv4Intf.Assign(intfDevs);

        uint16_t intfPort = 6001;
        OnOffHelper onoff("ns3::UdpSocketFactory", InetSocketAddress(intfIf.GetAddress(1), intfPort));
        onoff.SetAttribute("OnTime", StringValue("ns3::ConstantRandomVariable[Constant=1.0]"));
        onoff.SetAttribute("OffTime", StringValue("ns3::ConstantRandomVariable[Constant=0.0]"));
        onoff.SetAttribute("DataRate", DataRateValue(DataRate(std::to_string(intfRateMbps) + "Mbps")));
        onoff.SetAttribute("PacketSize", UintegerValue(1000));

        ApplicationContainer intfApps = onoff.Install(intfNodes.Get(0));
        intfApps.Start(Seconds(intfStartS));
        intfApps.Stop(Seconds(intfStopS));

        PacketSinkHelper sink("ns3::UdpSocketFactory", InetSocketAddress(Ipv4Address::GetAny(), intfPort));
        ApplicationContainer sinkApps = sink.Install(intfNodes.Get(1));
        sinkApps.Start(Seconds(0.0));
        sinkApps.Stop(Seconds(simTimeS));

        // Schedule events logging for interferer
        Simulator::Schedule(Seconds(intfStartS), [=]() {
            if (MasterSchedulerApp::GetInstance())
                MasterSchedulerApp::GetInstance()->LogEvent("INTERFERER_ON", -1, interferer + " interferer ON");
        });
        Simulator::Schedule(Seconds(intfStopS), [=]() {
            if (MasterSchedulerApp::GetInstance())
                MasterSchedulerApp::GetInstance()->LogEvent("INTERFERER_OFF", -1, interferer + " interferer OFF");
        });
    }

    // ── Internet Stack + Addressing ──
    InternetStackHelper internet;
    internet.Install(allNodes);
    Ipv4AddressHelper ipv4;
    ipv4.SetBase("192.168.1.0", "255.255.255.0");
    Ipv4InterfaceContainer apIf = ipv4.Assign(apDev);
    Ipv4InterfaceContainer staIf = ipv4.Assign(staDevs);
    if (staticArp)
    {
        std::vector<Ptr<NetDevice>> wifiDevs{apDev.Get(0)};
        for (uint32_t i = 0; i < staDevs.GetN(); ++i) wifiDevs.push_back(staDevs.Get(i));
        PopulateStaticArp(wifiDevs);
    }

    // ── Applications ──
    std::vector<Ipv4Address> staAddrs;
    std::vector<Ptr<IoTSensorApp>> sensorApps;
    for (uint32_t i = 0; i < N_NODES; ++i)
    {
        staAddrs.push_back(staIf.GetAddress(i));
        Ptr<IoTSensorApp> sensorApp = CreateObject<IoTSensorApp>(i, apIf.GetAddress(0), 0.1, 2.0);
        staNodes.Get(i)->AddApplication(sensorApp);
        sensorApp->SetStartTime(Seconds(0.5));
        sensorApp->SetStopTime(Seconds(simTimeS));
        sensorApps.push_back(sensorApp);
    }

    Ptr<MasterSchedulerApp> masterApp = CreateObject<MasterSchedulerApp>(
        staAddrs,
        Seconds(slotDurationS),
        schedType,
        csvOutput,
        eventsPath,
        policyFile,
        policyId,
        liveUdpPort);
    Config::Connect("/NodeList/*/DeviceList/*/$ns3::WifiNetDevice/Mac/$ns3::StaWifiMac/Assoc",
                    MakeCallback(&OnAssoc));
    Config::Connect("/NodeList/*/DeviceList/*/$ns3::WifiNetDevice/Mac/$ns3::StaWifiMac/DeAssoc",
                    MakeCallback(&OnDeAssoc));
    if (traceDrops)
    {
        Config::Connect("/NodeList/0/DeviceList/*/$ns3::WifiNetDevice/Mac/$ns3::ApWifiMac/AssociatedSta",
                        MakeCallback(&OnApAssociated));
        Config::Connect("/NodeList/0/DeviceList/*/$ns3::WifiNetDevice/Mac/$ns3::ApWifiMac/DeAssociatedSta",
                        MakeCallback(&OnApDeAssociated));
    }
    if (traceDrops)
    {
        Config::Connect("/NodeList/*/DeviceList/*/$ns3::WifiNetDevice/Phy/PhyRxDrop", MakeCallback(&OnPhyRxDrop));
        Config::Connect("/NodeList/*/DeviceList/*/$ns3::WifiNetDevice/Mac/MacTxDrop", MakeCallback(&OnMacTxDrop));
    }
    if (assocTxPowerDbm != txPowerDbm)
    {
        Simulator::Schedule(Seconds(ASSOC_END_S), [txPowerDbm]() {
            Config::Set("/NodeList/*/DeviceList/*/$ns3::WifiNetDevice/Phy/TxPowerStart", DoubleValue(txPowerDbm));
            Config::Set("/NodeList/*/DeviceList/*/$ns3::WifiNetDevice/Phy/TxPowerEnd", DoubleValue(txPowerDbm));
        });
    }
    lossCfg.enabled = lossModel;
    lossCfg.intfStart = intfStartS;
    lossCfg.intfStop = intfStopS;
    masterApp->ConfigureLoss(lossCfg);
    apNode.Get(0)->AddApplication(masterApp);
    masterApp->SetStartTime(Seconds(1.0));
    masterApp->SetStopTime(Seconds(simTimeS));

    // Fault Injection (N2.4)
    if (failNode >= 0 && failNode < static_cast<int>(N_NODES))
    {
        Simulator::Schedule(Seconds(failAtS), [=, &sensorApps]() {
            sensorApps[failNode]->SetFailed(true);
            if (MasterSchedulerApp::GetInstance())
                MasterSchedulerApp::GetInstance()->LogEvent("INJECT_FAULT", failNode, "Sensor radio muted");
        });
        Simulator::Schedule(Seconds(recoverAtS), [=, &sensorApps]() {
            sensorApps[failNode]->SetFailed(false);
            if (MasterSchedulerApp::GetInstance())
                MasterSchedulerApp::GetInstance()->LogEvent("CLEAR_FAULT", failNode, "Sensor radio unmuted");
        });
    }

    // ── RSSI Monitoring Callback ──
    Config::ConnectWithoutContext(
        "/NodeList/" + std::to_string(apNode.Get(0)->GetId()) +
            "/DeviceList/*/$ns3::WifiNetDevice/Phy/MonitorSnifferRx",
        MakeCallback(&RssiMonitorCallback));

    // ── FlowMonitor ──
    FlowMonitorHelper flowmonHelper;
    Ptr<FlowMonitor> monitor = flowmonHelper.InstallAll();

    // ── NetAnim ──
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

    // ── Execute Simulation ──
    Simulator::Stop(Seconds(simTimeS));
    Simulator::Run();

    monitor->CheckForLostPackets();
    monitor->SerializeToXmlFile(flowmonPath, true, true);

    if (traceDrops)
    {
        for (const auto& kv : g_dropCounts)
            std::cout << "[drops] " << kv.first << " = " << kv.second << std::endl;
    }
    Simulator::Destroy();
    return 0;
}
