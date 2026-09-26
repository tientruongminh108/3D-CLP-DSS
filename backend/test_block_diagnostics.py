#!/usr/bin/env python
"""Diagnostic: block dimensions vs MAX_BLOCK_FRACTION, posture rejection reasons, unplaced reasons."""

import sys, pandas as pd
from pathlib import Path
from collections import Counter
sys.path.insert(0, str(Path(__file__).parent))

from app.solver.pipeline import run_pipeline
from app.solver.block_generation import Block, build_blocks
from app.solver.parsing import parse_and_join
from app.solver.sorting import initial_sort, resort_after_blocks
from app.solver.placement import place_blocks_greedy, check_all_constraints, PlacementCandidate
from app.solver.geometry import Dimensions, Position, BoundingBox, Posture
from app.config import get_settings

def progress_cb(stage, p, d):
    if stage=='ga_progress': print(f'  Gen {d["generation"]}: fit={d["best_fitness"]:.1f}, placed={d["placed"]}, unplaced={d["unplaced"]}')

def test_block_at_origin(block, container_dims, max_weight, is_lcl):
    """Test each permitted posture at origin (0,0,0) - returns dict with rejection reasons."""
    settings = get_settings()
    results = []
    for posture in block.permitted_postures:
        dims = Dimensions(block.length_cm, block.width_cm, block.height_cm).apply_posture(posture)
        inflated = Dimensions(block.inflated_length, block.inflated_width, block.inflated_height).apply_posture(posture)
        pos = Position(0,0,0)
        bbox = BoundingBox.from_position_and_dims(pos, inflated)
        valid, reason = check_all_constraints(
            PlacementCandidate(position=pos, posture=posture, dims=inflated, actual_dims=dims,
                               box=block.boxes[0] if block.boxes else None),
            [], [], container_dims, 0, max_weight, is_lcl
        )
        bounds_ok = (inflated.length <= container_dims.length and
                     inflated.width <= container_dims.width and
                     inflated.height <= container_dims.height)
        results.append({
            'posture': posture.name,
            'dims': (dims.length, dims.width, dims.height),
            'inflated': (inflated.length, inflated.width, inflated.height),
            'bounds_ok': bounds_ok,
            'constraints_ok': valid,
            'reason': reason if not valid else 'OK'
        })
    return results

data_dir = Path('..')/'data'
pl = pd.read_csv(data_dir/'packing_list.csv')
im = pd.read_csv(data_dir/'item_master.csv')
ct = pd.read_csv(data_dir/'container_spec.csv')

print('Customer Codes:', pl['Customer_Code'].value_counts().to_dict())

# Parse & sort
boxes, container_spec, preview, shipment_type = parse_and_join(pl, im, ct)
sorted_boxes = initial_sort(boxes, shipment_type.value)

# Build blocks
blocks, leftover = build_blocks(sorted_boxes, container_spec.usable_length,
                                container_spec.usable_width, container_spec.usable_height)
all_units = blocks + leftover
all_units = resort_after_blocks(all_units, shipment_type.value)

container_dims = Dimensions(container_spec.usable_length, container_spec.usable_width, container_spec.usable_height)
is_lcl = shipment_type == shipment_type.LCL
last_cust = max(u.customer_sequence for u in all_units) if all_units else 0
settings = get_settings()
max_frac_x = settings.MAX_BLOCK_FRACTION_X
max_frac_y = settings.MAX_BLOCK_FRACTION_Y
max_frac_z = settings.MAX_BLOCK_FRACTION_Z

print(f'\nContainer usable: {container_dims.length:.1f} x {container_dims.width:.1f} x {container_dims.height:.1f}')
print(f'MAX_BLOCK_FRACTION: X={max_frac_x}, Y={max_frac_y}, Z={max_frac_z}')
print(f'Blocks: {len(blocks)}, Leftover: {len(leftover)}')

# 1. Block dimensions vs limits
print('\n' + '='*70)
print('1. BLOCK DIMENSIONS vs MAX_BLOCK_FRACTION LIMITS')
print('='*70)
for b in blocks:
    lim_L = container_dims.length * max_frac_x
    lim_W = container_dims.width * max_frac_y
    lim_H = container_dims.height * max_frac_z
    print(f'\n{b.block_id}: {len(b.contents)} cartons')
    print(f'  Native:     {b.length_cm:.1f} x {b.width_cm:.1f} x {b.height_cm:.1f}')
    print(f'  Inflated:   {b.inflated_length:.1f} x {b.inflated_width:.1f} x {b.inflated_height:.1f}')
    print(f'  Limits:     {lim_L:.1f} x {lim_W:.1f} x {lim_H:.1f}')
    print(f'  Over L: {b.inflated_length > lim_L}, Over W: {b.inflated_width > lim_W}, Over H: {b.inflated_height > lim_H}')
    print(f'  Fits container: L={b.inflated_length<=container_dims.length}, W={b.inflated_width<=container_dims.width}, H={b.inflated_height<=container_dims.height}')
    print(f'  Postures: {[p.name for p in b.permitted_postures]}')
    for c in b.contents:
        print(f'    {c.box_id}: {c.item_id} ({c.length_cm}x{c.width_cm}x{c.height_cm}) postures={c.permitted_postures}')

# 2. Posture rejection at origin
print('\n' + '='*70)
print('2. POSTURE REJECTION AT ORIGIN (0,0,0)')
print('='*70)
unplaceable_blocks = []
for b in blocks:
    print(f'\n{b.block_id}:')
    posture_results = test_block_at_origin(b, container_dims, container_spec.max_weight_kg, is_lcl)
    all_rej = True
    for pr in posture_results:
        status = '✓' if pr['bounds_ok'] and pr['constraints_ok'] else '✗'
        why = []
        if not pr['bounds_ok']: why.append('BOUNDS')
        if not pr['constraints_ok']: why.append(f'CONSTRAINT({pr["reason"]})')
        print(f'  {status} {pr["posture"]}: inflated={pr["inflated"][0]:.0f}x{pr["inflated"][1]:.0f}x{pr["inflated"][2]:.0f} {" ".join(why) if why else ""}')
        if pr['bounds_ok'] and pr['constraints_ok']: all_rej = False
    if all_rej: unplaceable_blocks.append(b.block_id)

print(f'\nBlocks with NO valid posture at origin: {unplaceable_blocks}')

# 3. Full pipeline
print('\n' + '='*70)
print('3. FULL PIPELINE RESULTS')
print('='*70)
result = run_pipeline(pl, im, ct, progress_callback=progress_cb)

print(f'\nUnplaced boxes (individual): {len(result.unplaced_boxes)}')
print(f'Unplaced blocks: {len(result.unplaced_blocks)}')

# 4. Unplaced reasons
print('\n' + '='*70)
print('4. UNPLACED REASONS (from result.unplaced_cartons)')
print('='*70)
reasons = Counter()
for uc in result.result.unplaced_cartons:
    reasons[str(uc.reason)] += 1
print(f'Reason breakdown: {dict(reasons)}')

# 5. Unplaced by item + block membership
print('\n' + '='*70)
print('5. UNPLACED BY ITEM + BLOCK MEMBERSHIP')
print('='*70)
item_unplaced = Counter()
block_unplaced = Counter()
for b in result.unplaced_boxes:
    item_unplaced[b.item_id] += 1
for block in result.unplaced_blocks:
    for c in block.contents:
        block_unplaced[c.item_id] += 1

all_up = Counter()
all_up.update(item_unplaced)
all_up.update(block_unplaced)

for item_id, count in sorted(all_up.items(), key=lambda x: -x[1])[:20]:
    sample = next((b for b in result.all_boxes if b.item_id == item_id), None)
    in_block = block_unplaced.get(item_id, 0)
    individual = item_unplaced.get(item_id, 0)
    if sample:
        vol = sample.length_cm * sample.width_cm * sample.height_cm
        print(f'  {item_id}: total_unplaced={count} (in_blocks={in_block}, individual={individual})')
        print(f'    vol={vol/1e6:.2f}M cm³, dims={sample.length_cm}x{sample.width_cm}x{sample.height_cm}, weight={sample.weight_kg}kg, postures={sample.permitted_postures}')