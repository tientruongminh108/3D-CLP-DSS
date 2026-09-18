#!/usr/bin/env python
"""Test script to run the full 3D-CL-DSS pipeline with sample data for both FCL and LCL."""

import sys
import argparse
import pandas as pd
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.solver.pipeline import run_pipeline


def progress_callback(stage: str, progress: float, data: dict):
    if stage == "ga_progress" and 'generation' in data:
        gen = data['generation']
        if gen % 10 == 0 or gen == 1:
            print(f"  [GA] Gen {gen:3d}: best_fitness={data['best_fitness']:.4f}, placed={data['placed']}, unplaced={data['unplaced']}", flush=True)
    elif stage != "ga_progress":
        print(f"[{stage}] {progress*100:.1f}% - {data.get('message', '')}", flush=True)


def run_pipeline_for_dataset(name: str, packing_list_df: pd.DataFrame, item_master_df: pd.DataFrame, container_df: pd.DataFrame):
    print("=" * 70)
    print(f"3D-CL-DSS Full Pipeline Test: {name}")
    print("=" * 70)
    print(f"Packing list: {len(packing_list_df)} rows, Cartons: {packing_list_df['Qty_Cartons'].sum()}")

    result = run_pipeline(
        packing_list_df=packing_list_df,
        item_master_df=item_master_df,
        container_df=container_df,
        progress_callback=progress_callback,
    )

    r = result.result
    c_len = r.container.internal_length_cm
    print("-" * 70)
    print(f"Pipeline Completed for {name}!")
    print(f"Container: {r.container.container_type} (L={c_len:.1f}, W={r.container.internal_width_cm:.1f}, H={r.container.internal_height_cm:.1f})")
    print(f"Status: {r.status}")
    print(f"Volume Utilization: {r.metrics.fill_rate*100:.2f}%")
    print(f"Weight Utilization: {r.metrics.weight_utilization*100:.2f}%")
    print(f"Total Boxes: {r.metrics.total_cartons}")
    print(f"Placed Boxes: {r.metrics.placed_count}")
    print(f"Unplaced Boxes: {r.metrics.unplaced_count}")
    print(f"Placed Weight: {r.metrics.used_weight_kg:.1f} / {r.metrics.max_weight_kg:.1f} kg")
    print(f"COG (x,y,z): ({r.metrics.cog_x:.1f}, {r.metrics.cog_y:.1f}, {r.metrics.cog_z:.1f})")

    # Verify Rear-First Loading (Requirement 5)
    print("\n--- Rear-First Loading Verification ---")
    if r.placed_boxes:
        early_boxes = r.placed_boxes[:min(10, len(r.placed_boxes))]
        late_boxes = r.placed_boxes[-min(10, len(r.placed_boxes)):]
        avg_early_x = sum(b.x for b in early_boxes) / len(early_boxes)
        avg_late_x = sum(b.x for b in late_boxes) / len(late_boxes)
        print(f"Average X of first {len(early_boxes)} placed boxes: {avg_early_x:.1f} cm (near rear wall L={c_len:.1f}cm)")
        print(f"Average X of last {len(late_boxes)} placed boxes:  {avg_late_x:.1f} cm (near door x=0)")
        for b in early_boxes[:5]:
            print(f"  Early box {b.box_id} ({b.customer_code or 'FCL'}): x={b.x:.1f}, y={b.y:.1f}, z={b.z:.1f}, dims=({b.length_cm}x{b.width_cm}x{b.height_cm})")

        # For LCL: Check customer sequence vs X coordinate
        cust_codes = list(dict.fromkeys(b.customer_code for b in r.placed_boxes if b.customer_code))
        if len(cust_codes) > 1:
            print("\nCustomer depth distribution (LCL LIFO check):")
            for c in cust_codes:
                c_boxes = [b for b in r.placed_boxes if b.customer_code == c]
                avg_x = sum(b.x for b in c_boxes) / len(c_boxes)
                max_x = max(b.x for b in c_boxes)
                min_x = min(b.x for b in c_boxes)
                print(f"  Customer {c}: count={len(c_boxes)}, avg_x={avg_x:.1f}, min_x={min_x:.1f}, max_x={max_x:.1f}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Run 3D-CL-DSS pipeline")
    parser.add_argument("--mode", choices=["fcl", "lcl", "both", "lcl_small"], default="both", help="Shipment mode to test")
    parser.add_argument("--generations", type=int, default=100, help="Number of GA generations (default: 100)")
    parser.add_argument("--pop-size", type=int, default=60, help="Population size (default: 60)")
    args = parser.parse_args()

    from app.core.models import RunOptions
    options = RunOptions(generations=args.generations, population_size=args.pop_size)

    data_dir = Path(__file__).parent.parent / "data"
    b_data_dir = Path(__file__).parent / "data"

    item_master_df = pd.read_csv(data_dir / "item_master.csv")
    container_df = pd.read_csv(data_dir / "container_spec.csv")

    def run_with_options(name, pl, im=item_master_df, ct=container_df):
        result = run_pipeline(
            packing_list_df=pl,
            item_master_df=im,
            container_df=ct,
            options=options,
            progress_callback=progress_callback,
        )
        r = result.result
        c_len = r.container.internal_length_cm
        print("-" * 70)
        print(f"Pipeline Completed for {name}!")
        print(f"Container: {r.container.container_type} (L={c_len:.1f}, W={r.container.internal_width_cm:.1f}, H={r.container.internal_height_cm:.1f})")
        print(f"Status: {r.status}")
        print(f"Volume Utilization: {r.metrics.fill_rate*100:.2f}%")
        print(f"Weight Utilization: {r.metrics.weight_utilization*100:.2f}%")
        print(f"Total Boxes: {r.metrics.total_cartons}")
        print(f"Placed Boxes: {r.metrics.placed_count}")
        print(f"Unplaced Boxes: {r.metrics.unplaced_count}")
        print(f"Placed Weight: {r.metrics.used_weight_kg:.1f} / {r.metrics.max_weight_kg:.1f} kg")
        print(f"COG (x,y,z): ({r.metrics.cog_x:.1f}, {r.metrics.cog_y:.1f}, {r.metrics.cog_z:.1f})")

        print("\n--- Rear-First Loading Verification ---")
        if r.placed_boxes:
            early_boxes = r.placed_boxes[:min(10, len(r.placed_boxes))]
            late_boxes = r.placed_boxes[-min(10, len(r.placed_boxes)):]
            avg_early_x = sum(b.x for b in early_boxes) / len(early_boxes)
            avg_late_x = sum(b.x for b in late_boxes) / len(late_boxes)
            print(f"Average X of first {len(early_boxes)} placed boxes: {avg_early_x:.1f} cm (near rear wall L={c_len:.1f}cm)")
            print(f"Average X of last {len(late_boxes)} placed boxes:  {avg_late_x:.1f} cm (near door x=0)")
            for b in early_boxes[:5]:
                print(f"  Early box {b.box_id} ({b.customer_code or 'FCL'}): x={b.x:.1f}, y={b.y:.1f}, z={b.z:.1f}, dims=({b.length_cm}x{b.width_cm}x{b.height_cm})")

            cust_codes = list(dict.fromkeys(b.customer_code for b in r.placed_boxes if b.customer_code))
            if len(cust_codes) > 1:
                print("\nCustomer depth distribution (LCL LIFO check):")
                for c in cust_codes:
                    c_boxes = [b for b in r.placed_boxes if b.customer_code == c]
                    avg_x = sum(b.x for b in c_boxes) / len(c_boxes)
                    max_x = max(b.x for b in c_boxes)
                    min_x = min(b.x for b in c_boxes)
                    print(f"  Customer {c}: count={len(c_boxes)}, avg_x={avg_x:.1f}, min_x={min_x:.1f}, max_x={max_x:.1f}")
        return result

    if args.mode in ["fcl", "both"]:
        packing_list_df = pd.read_csv(data_dir / "packing_list.csv")
        run_with_options("FCL Sample (data/)", packing_list_df)

    if args.mode in ["lcl", "both"]:
        pl_fcl = pd.read_csv(data_dir / "packing_list.csv")
        pl_lcl = pl_fcl.copy()
        custs = ['CUST-A', 'CUST-B', 'CUST-C']
        pl_lcl['Customer_Code'] = [custs[i % 3] for i in range(len(pl_lcl))]
        run_with_options("LCL 3-Customer (derived from data/)", pl_lcl)

    if args.mode == "lcl_small":
        pl_lcl_small = pd.read_csv(b_data_dir / "packing_list_samples" / "lcl_sample.csv")
        im_lcl_small = pd.read_csv(b_data_dir / "item_master.csv")
        ct_lcl_small = pd.read_csv(b_data_dir / "container_spec.csv")
        run_with_options("LCL Small", pl_lcl_small, im=im_lcl_small, ct=ct_lcl_small)


if __name__ == "__main__":
    main()