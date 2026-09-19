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
    """Assert that decode_chromosome produces the exact verified placement for seed 1."""
    all_units, container_dims, max_weight = fcl_dataset
    random.seed(1)
    chromosome = [
        random.randrange(len(u.permitted_postures)) if u.permitted_postures else 0
        for u in all_units
    ]

    placed_bboxes, placed_data, unplaced, current_weight, placed_postures = decode_chromosome(
        list(chromosome), all_units, container_dims, max_weight, is_lcl=False
    )

    assert len(placed_bboxes) == 108
    assert len(placed_data) == 108
    assert current_weight == pytest.approx(6823.97, abs=0.01)

    # Verify first 3 boxes match exact coordinates
    assert (placed_bboxes[0].min_x, placed_bboxes[0].min_y, placed_bboxes[0].min_z) == (1101.0, 0, 0)
    assert (placed_bboxes[1].min_x, placed_bboxes[1].min_y, placed_bboxes[1].min_z) == (0, 0, 0)
    assert (placed_bboxes[2].min_x, placed_bboxes[2].min_y, placed_bboxes[2].min_z) == (0, 133.0, 0)

    last_box = placed_bboxes[-1]
    assert last_box.max_x <= container_dims.length + 1e-6
    assert last_box.max_y <= container_dims.width + 1e-6
    assert last_box.max_z <= container_dims.height + 1e-6


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

    # Ensure single decode takes well under 0.50s (baseline was 16.8s; typically ~0.09s here, ~0.01s on target hardware)
    assert elapsed < 0.50, f"decode_chromosome took {elapsed:.3f}s (expected < 0.50s, baseline was 16.8s)"
