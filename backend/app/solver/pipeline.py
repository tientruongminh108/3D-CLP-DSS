from typing import List, Callable, Optional, Tuple
from dataclasses import dataclass
from app.config import get_settings
from app.solver.parsing import parse_and_join, Box, ContainerSpec, PackingListPreview, ShipmentType
from app.solver.sorting import initial_sort, resort_after_blocks
from app.solver.block_generation import build_blocks, Block
from app.solver.ga import genetic_algorithm, Individual
from app.solver.placement import decode_chromosome, place_blocks_greedy
from app.solver.output import build_run_result
from app.solver.geometry import Dimensions
from app.core.models import RunResult, RunStatus


@dataclass
class PipelineResult:
    result: RunResult
    best_individual: Individual
    placed_blocks: List[Block]
    unplaced_blocks: List[Block]
    all_boxes: List[Box]
    unplaced_boxes: List[Box]
    container_spec: ContainerSpec
    is_lcl: bool


def run_pipeline(
    packing_list_df,
    item_master_df,
    container_df,
    options=None,
    progress_callback: Callable[[str, float, dict], None] = None,
) -> PipelineResult:
    settings = get_settings()

    pop_size = options.population_size if options else settings.POPULATION_SIZE
    generations = options.generations if options else settings.GENERATIONS

    if progress_callback:
        progress_callback("parse", 0.05, {"message": "Parsing inputs..."})

    gap = float(options.tolerance_gap_cm) if options and options.tolerance_gap_cm is not None else settings.TOLERANCE_GAP_CM

    boxes, container_spec, preview, shipment_type = parse_and_join(
        packing_list_df, item_master_df, container_df, tolerance_gap=gap
    )

    if progress_callback:
        progress_callback("sort", 0.1, {"message": "Sorting boxes...", "total_boxes": len(boxes)})

    sorted_boxes = initial_sort(boxes, shipment_type.value)

    if progress_callback:
        progress_callback("blocks", 0.2, {"message": "Generating blocks..."})

    blocks, leftover = build_blocks(
        sorted_boxes,
        container_spec.usable_length,
        container_spec.usable_width,
        container_spec.usable_height,
    )

    all_units = blocks + leftover
    all_units = resort_after_blocks(all_units, shipment_type.value)

    container_dims = Dimensions(
        container_spec.usable_length,
        container_spec.usable_width,
        container_spec.usable_height,
    )

    is_lcl = shipment_type == ShipmentType.LCL
    last_customer_sequence = max(u.customer_sequence for u in all_units) if all_units else 0

    if progress_callback:
        progress_callback("ga_start", 0.3, {"message": "Starting Genetic Algorithm...", "units": len(all_units)})

    def ga_progress(gen: int, best: Individual):
        if progress_callback:
            progress_callback(
                "ga_progress",
                0.3 + 0.5 * (gen / generations),
                {
                    "message": f"Generation {gen}/{generations}",
                    "generation": gen,
                    "best_fitness": best.fitness_result.fitness if best.fitness_result else 0,
                    "placed": len(best.placed_data) if best.placed_data else 0,
                    "unplaced": len(best.unplaced) if best.unplaced else 0,
                },
            )

    # GA now includes embedded SA, no separate SA call needed
    best_individual = genetic_algorithm(
        units=all_units,
        container_dims=container_dims,
        max_weight=container_spec.max_weight_kg,
        is_lcl=is_lcl,
        population_size=pop_size,
        generations=generations,
        progress_callback=ga_progress,
    )

    if progress_callback:
        progress_callback("decode", 0.95, {"message": "Building final solution..."})

    # Final decode of best individual to get the plan
    placed_bboxes, placed_data, unplaced, current_weight, placed_postures = decode_chromosome(
        best_individual.chromosome, all_units, container_dims, container_spec.max_weight_kg, is_lcl
    )

    if progress_callback:
        progress_callback("compaction", 0.96, {"message": "Running compaction pass..."})

    from app.solver.compaction import run_compaction_pass
    placed_bboxes, placed_data, placed_postures, unplaced, current_weight, fitness_res = run_compaction_pass(
        placed_bboxes=placed_bboxes,
        placed_data=placed_data,
        placed_postures=placed_postures,
        unplaced=unplaced,
        container_dims=container_dims,
        max_weight=container_spec.max_weight_kg,
        is_lcl=is_lcl,
        current_weight=current_weight,
    )

    best_individual.placed_bboxes = placed_bboxes
    best_individual.placed_data = placed_data
    best_individual.unplaced = unplaced
    best_individual.current_weight = current_weight
    best_individual.placed_postures = placed_postures
    best_individual.fitness_result = fitness_res

    # Separate placed blocks from placed individual boxes
    placed_blocks = []
    placed_individual_boxes = []
    for unit in placed_data:
        if isinstance(unit, Block):
            placed_blocks.append(unit)
        else:
            placed_individual_boxes.append(unit)

    # Unplaced blocks and boxes from final solution
    final_unplaced_blocks = [u for u, _ in unplaced if isinstance(u, Block)]
    final_unplaced_boxes = [u for u, _ in unplaced if not isinstance(u, Block)]

    result = build_run_result(
        individual=best_individual,
        container_dims=container_dims,
        container_spec=container_spec,
        placed_blocks=placed_blocks,
        unplaced_blocks=final_unplaced_blocks,
        all_boxes=boxes,
        unplaced_boxes=final_unplaced_boxes,
        is_lcl=is_lcl,
        placed_bboxes=placed_bboxes,
        placed_data=placed_data,
        placed_individual_boxes=placed_individual_boxes,
        placed_postures=placed_postures,
        status=RunStatus.COMPLETED.value,
        options=options,
    )

    if progress_callback:
        progress_callback("complete", 1.0, {"message": "Done", "run_id": result.run_id})

    return PipelineResult(
        result=result,
        best_individual=best_individual,
        placed_blocks=placed_blocks,
        unplaced_blocks=final_unplaced_blocks,
        all_boxes=boxes,
        unplaced_boxes=final_unplaced_boxes,
        container_spec=container_spec,
        is_lcl=is_lcl,
    )