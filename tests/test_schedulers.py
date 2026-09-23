import numpy as np
from schedulers.round_robin import RoundRobinScheduler
from schedulers.fixed_priority import FixedPriorityScheduler
from schedulers.random_scheduler import RandomScheduler
from schedulers.max_weight import MaxWeightScheduler
from schedulers.channel_aware_greedy import ChannelAwareGreedyScheduler
from schedulers.oracle import OracleScheduler

def test_round_robin():
    scheduler = RoundRobinScheduler()
    aoi = np.zeros(4)
    rssi = np.zeros(4)
    queue = np.zeros(4)
    weights = np.zeros(4)
    
    assert scheduler.select(aoi, rssi, queue, weights) == 0
    assert scheduler.select(aoi, rssi, queue, weights) == 1
    assert scheduler.select(aoi, rssi, queue, weights) == 2
    assert scheduler.select(aoi, rssi, queue, weights) == 3
    assert scheduler.select(aoi, rssi, queue, weights) == 0

def test_fixed_priority():
    scheduler = FixedPriorityScheduler(["routine", "urgent", "important", "urgent"])
    # Priorities: 0, 2, 1, 2
    aoi = np.array([10.0, 5.0, 20.0, 4.0])
    # Node 1 and 3 are urgent. Node 1 has AoI 5.0, Node 3 has AoI 4.0. Node 1 should be selected.
    assert scheduler.select(aoi, np.zeros(4), np.zeros(4), np.zeros(4)) == 1
    
    # Tie-break test
    aoi[3] = 6.0
    assert scheduler.select(aoi, np.zeros(4), np.zeros(4), np.zeros(4)) == 3

def test_random_scheduler():
    s1 = RandomScheduler(seed=42)
    s2 = RandomScheduler(seed=42)
    
    aoi = np.zeros(4)
    for _ in range(10):
        assert s1.select(aoi, aoi, aoi, aoi) == s2.select(aoi, aoi, aoi, aoi)

def test_max_weight():
    scheduler = MaxWeightScheduler()
    aoi = np.array([1.0, 2.0, 3.0, 4.0])
    weights = np.array([10.0, 6.0, 3.0, 1.0])
    # w * aoi = [10.0, 12.0, 9.0, 4.0]
    # Node 1 should win
    assert scheduler.select(aoi, np.zeros(4), np.zeros(4), weights) == 1

def test_channel_aware_greedy():
    # p_s(rssi) uses logistic curve. Let's mock a measured_params.
    measured_params = {
        "timing": {"slot_duration_s": 0.01, "late_arrival_probability": 0.0},
        "channel": {
            "path_loss_exponent": 2.8,
            "reference_distance_m": 1.0,
            "reference_loss_db": 40.046,
            "shadowing_sigma_db": 4.0,
            "shadowing_correlation_rho": 0.9,
            "logistic_r50_dbm": -82.0,
            "logistic_slope_db": 4.0,
            "ge_prob_good_to_bad": 0.02,
            "ge_prob_bad_to_good": 0.30,
            "ge_bad_state_success_multiplier": 0.3
        }
    }
    scheduler = ChannelAwareGreedyScheduler(measured_params)
    aoi = np.array([10.0, 10.0, 10.0, 10.0])
    weights = np.array([1.0, 1.0, 1.0, 1.0])
    # rssi: -60, -70, -80, -90
    rssi = np.array([-60.0, -70.0, -80.0, -90.0])
    # The higher the RSSI, the higher the p_s. Since weights and AoI are equal, 
    # the node with the highest RSSI (-60) should win.
    assert scheduler.select(aoi, rssi, np.zeros(4), weights) == 0
    
    # Now let's change weights and AoI so node 2 wins despite lower RSSI
    weights[2] = 100.0
    assert scheduler.select(aoi, rssi, np.zeros(4), weights) == 2

def test_oracle():
    scheduler = OracleScheduler()
    aoi = np.array([10.0, 10.0, 10.0, 10.0])
    weights = np.array([1.0, 1.0, 1.0, 1.0])
    true_success_probs = np.array([0.9, 0.8, 0.1, 0.5])
    
    # Case 1: no node has data buffered (queue all 0).
    # Fallback to argmax(weights * aoi), which are all 10.0. Tie-break usually picks 0.
    queue = np.zeros(4)
    assert scheduler.select_with_oracle(aoi, queue, weights, true_success_probs) == 0
    
    # Case 2: Node 1 and 2 have data buffered.
    queue[1] = 1
    queue[2] = 1
    # Node 1 p_s=0.8, Node 2 p_s=0.1
    assert scheduler.select_with_oracle(aoi, queue, weights, true_success_probs) == 1
