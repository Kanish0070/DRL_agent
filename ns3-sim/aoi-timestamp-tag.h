#ifndef AOI_TIMESTAMP_TAG_H
#define AOI_TIMESTAMP_TAG_H

#include "ns3/tag.h"
#include "ns3/tag-buffer.h"
#include "ns3/type-id.h"

#include <iostream>

namespace ns3
{

/**
 * Packet tag carrying the generation-time timestamp and originating node id
 * for a sensor DATA/HEARTBEAT packet, so the gateway can compute
 * generation-time Age of Information on reception (matches
 * common/contracts/aoi.py's authoritative AoI definition, D0.1).
 *
 * Header-only: kept small enough that inline definitions avoid a
 * separate translation unit in the ns-3 scratch build.
 */
class AoITimestampTag : public Tag
{
  public:
    static TypeId GetTypeId()
    {
        static TypeId tid = TypeId("ns3::AoITimestampTag")
                                 .SetParent<Tag>()
                                 .SetGroupName("AoiScheduler")
                                 .AddConstructor<AoITimestampTag>();
        return tid;
    }

    TypeId GetInstanceTypeId() const override
    {
        return GetTypeId();
    }

    uint32_t GetSerializedSize() const override
    {
        return sizeof(uint64_t) + sizeof(uint32_t);
    }

    void Serialize(TagBuffer i) const override
    {
        i.WriteU64(m_genTimeUs);
        i.WriteU32(m_nodeId);
    }

    void Deserialize(TagBuffer i) override
    {
        m_genTimeUs = i.ReadU64();
        m_nodeId = i.ReadU32();
    }

    void Print(std::ostream& os) const override
    {
        os << "AoITag[node=" << m_nodeId << " gen=" << m_genTimeUs << "us]";
    }

    void SetData(uint32_t nodeId, uint64_t genTimeUs)
    {
        m_nodeId = nodeId;
        m_genTimeUs = genTimeUs;
    }

    uint64_t GetGenTimeUs() const
    {
        return m_genTimeUs;
    }

    uint32_t GetNodeId() const
    {
        return m_nodeId;
    }

  private:
    uint64_t m_genTimeUs{0};
    uint32_t m_nodeId{0};
};

} // namespace ns3

#endif // AOI_TIMESTAMP_TAG_H
