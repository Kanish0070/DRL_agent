def update_aoi_for_slot(current_aoi: float, packet_arrived: bool, delivered_age: float, t_slot: float) -> float:
    """
    Authoritative update rule for Generation-Time Age of Information (AoI).
    (Implements D0.1).
    
    Args:
        current_aoi: The AoI at the start of the slot.
        packet_arrived: True if a valid uplink from this node arrived during the slot.
        delivered_age: The age of the newly delivered packet at the end of the slot.
        t_slot: The slot duration in seconds.
        
    Returns:
        The new AoI value.
    """
    if packet_arrived:
        # Reset to the age of the delivered packet (resolves F2.2)
        return delivered_age
    
    # Otherwise, AoI increases by the elapsed slot duration
    return current_aoi + t_slot

def compute_delivered_age(t_now_pi: float, t_rx_pi: float, age_at_tx_us: int, d_up_hat: float) -> float:
    """
    Computes the generation-time age of a packet without clock synchronisation.
    (Implements D2.1).
    
    Args:
        t_now_pi: Absolute monotonic time on the Pi at evaluation (seconds).
        t_rx_pi: Absolute monotonic time on the Pi when packet was received (seconds).
        age_at_tx_us: The duration the packet spent on the node before TX (microseconds).
        d_up_hat: Estimated one-way uplink delay in seconds.
        
    Returns:
        The true age of the information in seconds.
    """
    time_since_rx = t_now_pi - t_rx_pi
    generation_age = (age_at_tx_us * 1e-6) + d_up_hat
    return time_since_rx + generation_age
