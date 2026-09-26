"""Regression and performance tests for decode_chromosome and incremental extreme points."""
import time
import random
from pathlib import Path
import pandas as pd
import pytest

from app.solver.parsing import parse_and_join
from app.solver.sorting import initial_sort, resort_after_blocks
from app.solver.block_generation import build_blocks
from app.solver.geometry import Dimensions
from app.solver.placement import decode_chromosome


@pytest.fixture(scope="module")
def fcl_dataset():
    data_dir = Path(__file__).parent.parent.parent / "data"
    pl = pd.read_csv(data_dir / "packing_list.csv")
    im = pd.read_csv(data_dir / "item_master.csv")
    ct = pd.read_csv(data_dir / "container_spec.csv")
    boxes, container_spec, preview, shipment_type = parse_and_join(pl, im, ct)
    sorted_boxes = initial_sort(boxes, shipment_type.value)
    blocks, leftover = build_blocks(
        sorted_boxes,
        container_spec.usable_length,
        container_spec.usable_width,
        container_spec.usable_height,
    )
    all_units = resort_after_blocks(blocks + leftover, shipment_type.value)
    container_dims = Dimensions(
        container_spec.usable_length,
        container_spec.usable_width,
        container_spec.usable_height,
    )
    return all_units, container_dims, container_spec.max_weight_kg


def test_decode_chromosome_exact_placement(fcl_dataset):
    """Assert that decode_chromosome produces a valid placement for seed 1."""
    all_units, container_dims, max_weight = fcl_dataset
    random.seed(1)
    chromosome = [
        random.randrange(len(u.permitted_postures)) if u.permitted_postures else 0
        for u in all_units
    ]

    placed_bboxes, placed_data, unplaced, current_weight, placed_postures = decode_chromosome(
        list(chromosome), all_units, container_dims, max_weight, is_lcl=False
    )

    # At least 27 units must be placed (without stacking group restrictions, 29 units are placed)
    assert len(placed_bboxes) >= 27
    assert len(placed_data) == len(placed_bboxes)
    # Total weight of placed cargo (with weight-based stacking and no stacking groups: 5319.8 kg)
    independent_weight = sum(u.weight_kg for u in placed_data)
    assert independent_weight == pytest.approx(5319.8, abs=0.1)
    assert current_weight == pytest.approx(5319.8, abs=0.1)

    # All placed boxes must be within container bounds
    last_box = placed_bboxes[-1]
    assert last_box.max_x <= container_dims.length + 1e-6
    assert last_box.max_y <= container_dims.width + 1e-6
    assert last_box.max_z <= container_dims.height + 1e-6


def test_regression_placement_floors(fcl_dataset):
    """Regression test asserting BOTH a minimum carton count floor AND fill rate floor.

    Calibrated on the FCL fixture dataset (152 cartons) for seed 1.
    Protects against changes that inflate one metric (e.g. carton count via weight-sort)
    while quietly degrading the other (fill rate / volume utilization).
    """
    all_units, container_dims, max_weight = fcl_dataset
    random.seed(1)
    chromosome = [
        random.randrange(len(u.permitted_postures)) if u.permitted_postures else 0
        for u in all_units
    ]

    placed_bboxes, placed_data, unplaced, current_weight, placed_postures = decode_chromosome(
        list(chromosome), all_units, container_dims, max_weight, is_lcl=False
    )

    placed_carton_count = sum(len(getattr(u, 'boxes', [u])) for u in placed_data)
    c_vol = container_dims.length * container_dims.width * container_dims.height
    placed_carton_volume = sum(
        c.length_cm * c.width_cm * c.height_cm
        for u in placed_data
        for c in getattr(u, 'boxes', [u])
    )
    fill_rate = placed_carton_volume / c_vol

    # Floor for cartons placed: achieved is 98/152
    assert placed_carton_count >= 95, (
        f"Placed carton count ({placed_carton_count}) fell below the floor of 95"
    )

    # Floor for fill rate: achieved is 50.4%
    assert fill_rate >= 0.48, (
        f"Fill rate ({fill_rate:.1%}) fell below the floor of 48.0%"
    )


def test_decode_chromosome_execution_time(fcl_dataset):
    """Assert that decode_chromosome executes in well under 0.25s even on cold test runners."""
    all_units, container_dims, max_weight = fcl_dataset
    random.seed(1)
    chromosome = [
        random.randrange(len(u.permitted_postures)) if u.permitted_postures else 0
        for u in all_units
    ]

    # Warm up call
    decode_chromosome(list(chromosome), all_units, container_dims, max_weight, is_lcl=False)

    t0 = time.perf_counter()
    decode_chromosome(list(chromosome), all_units, container_dims, max_weight, is_lcl=False)
    elapsed = time.perf_counter() - t0

    # Ensure single decode takes well under 1.0s (baseline was 16.8s; typically ~0.09s on fast HW)
    assert elapsed < 1.0, f"decode_chromosome took {elapsed:.3f}s (expected < 1.0s, baseline was 16.8s)"
