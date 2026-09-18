#!/usr/bin/env python
"""Sweep verification script for FCL and LCL datasets.

Confirms that MAX_BLOCK_FRACTION=0.25 (and lower) achieves strong fill rate
(>75%) compared to the ~28% baseline of 0.60.
"""

import os
import sys
import random
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from app.solver.parsing import parse_and_join
from app.solver.sorting import initial_sort, resort_after_blocks
from app.solver.block_generation import build_blocks
from app.solver.geometry import Dimensions
from app.solver.placement import decode_chromosome
from app.solver.fitness import calculate_fitness
from app.config import get_settings


def test_dataset_sweep(name: str, packing_list_df: pd.DataFrame, item_master_df: pd.DataFrame,
                       container_df: pd.DataFrame, fractions=(0.6, 0.4, 0.25, 0.2)):
    print(f"\n{'='*70}\nSweep Test: {name}\n{'='*70}")
    boxes, container_spec, preview, shipment_type = parse_and_join(packing_list_df, item_master_df, container_df)
    is_lcl = shipment_type.value == 'LCL'
    container_dims = Dimensions(container_spec.usable_length, container_spec.usable_width, container_spec.usable_height)
    cvol = container_spec.usable_length * container_spec.usable_width * container_spec.usable_height
    tot_vol = sum(b.length_cm * b.width_cm * b.height_cm for b in boxes)
    print(f"Total cartons: {len(boxes)}, Shipment: {shipment_type.value}, Max cargo fill: {tot_vol/cvol:.1%}")

    sweep_results = {}
    for frac in fractions:
        os.environ['MAX_BLOCK_FRACTION'] = str(frac)
        get_settings.cache_clear()

        sorted_boxes = initial_sort(boxes, shipment_type.value)
        blocks, leftover = build_blocks(sorted_boxes, container_spec.usable_length,
                                        container_spec.usable_width, container_spec.usable_height)
        all_units = blocks + leftover
        all_units = resort_after_blocks(all_units, shipment_type.value)

        results = []
        for seed in range(5):
            random.seed(seed)
            chromosome = [random.randrange(len(u.permitted_postures)) if u.permitted_postures else 0 for u in all_units]
            placed_bboxes, placed_data, unplaced, current_weight, postures = decode_chromosome(
                list(chromosome), all_units, container_dims, container_spec.max_weight_kg, is_lcl
            )
            fr = calculate_fitness(placed_bboxes, placed_data, unplaced, container_dims, container_spec.max_weight_kg)
            results.append((len(placed_data), len(all_units), fr.placed_volume))

        avg_placed = sum(r[0] for r in results) / len(results)
        avg_vol = sum(r[2] for r in results) / len(results)
        fill_pct = avg_vol / cvol
        sweep_results[frac] = (avg_placed, len(all_units), fill_pct)
        print(f"  frac={frac:.2f} ({'LCL' if is_lcl else 'FCL'}): avg_placed={avg_placed:.1f}/{len(all_units)}, "
              f"avg_vol_fill={fill_pct:.1%}")

    # Check improvement:
    if tot_vol / cvol > 0.50:
        assert sweep_results[0.25][2] > sweep_results[0.6][2] + 0.30, (
            f"Expected >30% fill rate improvement for frac=0.25 over 0.60, got {sweep_results[0.25][2]:.1%} vs {sweep_results[0.6][2]:.1%}"
        )
        print(f"[OK] Significant fill-rate improvement verified for {name}: {sweep_results[0.6][2]:.1%} -> {sweep_results[0.25][2]:.1%}")
    else:
        assert sweep_results[0.25][0] == sweep_results[0.25][1], (
            f"Expected 100% placement for small dataset, got {sweep_results[0.25][0]} / {sweep_results[0.25][1]}"
        )
        print(f"[OK] 100% placement verified for small dataset {name}: {sweep_results[0.25][0]:.0f}/{sweep_results[0.25][1]} units placed")
    return sweep_results


def main():
    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / "data"

    # 1. FCL Dataset
    pl_fcl = pd.read_csv(data_dir / 'packing_list.csv')
    im_fcl = pd.read_csv(data_dir / 'item_master.csv')
    ct_fcl = pd.read_csv(data_dir / 'container_spec.csv')
    test_dataset_sweep("FCL (data/)", pl_fcl, im_fcl, ct_fcl)

    # 2. Multi-Customer LCL Dataset
    pl_lcl = pl_fcl.copy()
    custs = ['CUST-A', 'CUST-B', 'CUST-C']
    pl_lcl['Customer_Code'] = [custs[i % 3] for i in range(len(pl_lcl))]
    test_dataset_sweep("LCL (3-Customer Cargo)", pl_lcl, im_fcl, ct_fcl)

    # 3. Backend LCL sample
    b_data_dir = Path(__file__).parent / "data"
    pl_lcl_small = pd.read_csv(b_data_dir / 'packing_list_samples' / 'lcl_sample.csv')
    im_lcl_small = pd.read_csv(b_data_dir / 'item_master.csv')
    ct_lcl_small = pd.read_csv(b_data_dir / 'container_spec.csv')
    test_dataset_sweep("LCL Small (backend/data/...)", pl_lcl_small, im_lcl_small, ct_lcl_small, fractions=(0.6, 0.25))

    # Reset env
    if 'MAX_BLOCK_FRACTION' in os.environ:
        del os.environ['MAX_BLOCK_FRACTION']
    get_settings.cache_clear()


if __name__ == "__main__":
    main()
