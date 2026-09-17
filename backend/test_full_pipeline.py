#!/usr/bin/env python
"""Test script to run the full 3D-CL-DSS pipeline with sample data."""

import sys
import pandas as pd
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.solver.pipeline import run_pipeline


def progress_callback(stage: str, progress: float, data: dict):
    print(f"[{stage}] {progress*100:.1f}% - {data.get('message', '')}")
    if 'generation' in data:
        print(f"  Gen {data['generation']}: fitness={data['best_fitness']:.2f}, placed={data['placed']}, unplaced={data['unplaced']}")


def main():
    print("=" * 60)
    print("3D-CL-DSS Full Pipeline Test")
    print("=" * 60)
    
    # Load sample data
    data_dir = Path(__file__).parent.parent / "data"
    
    print("\nLoading data files...")
    packing_list_df = pd.read_csv(data_dir / "packing_list.csv")
    item_master_df = pd.read_csv(data_dir / "item_master.csv")
    container_df = pd.read_csv(data_dir / "container_spec.csv")
    
    print(f"  Packing list: {len(packing_list_df)} rows")
    print(f"  Item master: {len(item_master_df)} items")
    print(f"  Container spec: {len(container_df)} containers")
    
    print("\nRunning pipeline...")
    print("-" * 60)
    
    # Run the pipeline
    result = run_pipeline(
        packing_list_df=packing_list_df,
        item_master_df=item_master_df,
        container_df=container_df,
        progress_callback=progress_callback,
    )
    
    print("-" * 60)
    print("\nPipeline completed!")
    print("=" * 60)
    print("RESULTS:")
    print("=" * 60)
    
    r = result.result
    print(f"Run ID: {r.run_id}")
    print(f"Status: {r.status}")
    print(f"Container: {r.container.container_type}")
    print(f"Volume Utilization: {r.metrics.fill_rate*100:.2f}%")
    print(f"Weight Utilization: {r.metrics.weight_utilization*100:.2f}%")
    print(f"Total Boxes: {r.metrics.total_cartons}")
    print(f"Placed Boxes: {r.metrics.placed_count}")
    print(f"Unplaced Boxes: {r.metrics.unplaced_count}")
    print(f"Total Weight: {r.metrics.max_weight_kg:.2f} kg")
    print(f"Placed Weight: {r.metrics.used_weight_kg:.2f} kg")
    print(f"COG (x,y,z): ({r.metrics.cog_x:.2f}, {r.metrics.cog_y:.2f}, {r.metrics.cog_z:.2f})")
    print(f"COG Deviation XY: {r.metrics.cog_deviation_xy:.4f}")
    print(f"COG Deviation Z: {r.metrics.cog_deviation_z:.4f}")
    print(f"Fitness Score: {r.metrics.fill_rate:.4f}")
    
    print("\nPlaced Items:")
    for item in r.placed_boxes:
        print(f"  {item.box_id}: pos=({item.x:.1f}, {item.y:.1f}, {item.z:.1f}), "
              f"dims=({item.length_cm:.1f}x{item.width_cm:.1f}x{item.height_cm:.1f}), "
              f"weight={item.weight_kg:.1f}, posture={item.posture}")
    
    print(f"\nUnplaced Items ({len(r.unplaced_cartons)}):")
    for item in r.unplaced_cartons[:10]:
        print(f"  {item.box_id}: {item.reason}")
    if len(r.unplaced_cartons) > 10:
        print(f"  ... and {len(r.unplaced_cartons) - 10} more")
    
    print("\n" + "=" * 60)
    print("Best Individual Details:")
    print("=" * 60)
    best = result.best_individual
    print(f"Chromosome length: {len(best.chromosome)}")
    if best.fitness_result:
        print(f"Fitness: {best.fitness_result.fitness:.4f}")
        print(f"Placed Volume: {best.fitness_result.placed_volume:.2f}")
        print(f"Unplaced Count: {best.fitness_result.unplaced_count}")
        print(f"COG Deviation XY: {best.fitness_result.cog_deviation_xy:.4f}")
        print(f"COG Deviation Z: {best.fitness_result.cog_deviation_z:.4f}")
    
    return result


if __name__ == "__main__":
    main()