import random
import copy
from typing import List, Tuple, Callable, Optional
from dataclasses import dataclass
from app.config import get_settings
from app.solver.parsing import Box
from app.solver.block_generation import Block
from app.solver.geometry import Dimensions, Posture
from app.solver.placement import decode_chromosome
from app.solver.fitness import calculate_fitness, FitnessResult
from app.solver.sa import simulated_annealing, run_simulated_annealing


@dataclass
class Individual:
    chromosome: List[int]
    fitness_result: Optional[FitnessResult] = None
    placed_bboxes: List = None
    placed_data: List = None
    unplaced: List = None
    current_weight: float = 0.0
    placed_postures: Optional[List[Posture]] = None


def create_individual(units: List[Box]) -> Individual:
    chromosome = []
    for unit in units:
        if unit.permitted_postures:
            idx = random.randrange(len(unit.permitted_postures))
        else:
            idx = 0
        chromosome.append(idx)
    return Individual(chromosome=chromosome)


def evaluate_individual(
    individual: Individual,
    units: List[Box],
    container_dims: Dimensions,
    max_weight: float,
    is_lcl: bool,
) -> Individual:
    placed_bboxes, placed_data, unplaced, current_weight, placed_postures = decode_chromosome(
        individual.chromosome, units, container_dims, max_weight, is_lcl
    )
    fitness_result = calculate_fitness(
        placed_bboxes, placed_data, unplaced, container_dims, max_weight
    )
    individual.fitness_result = fitness_result
    individual.placed_bboxes = placed_bboxes
    individual.placed_data = placed_data
    individual.unplaced = unplaced
    individual.current_weight = current_weight
    individual.placed_postures = placed_postures
    return individual


def rank_based_selection(population: List[Individual], count: int) -> List[Individual]:
    """Rank-based roulette selection: worst gets weight 1, best gets weight n."""
    ranked = sorted(population, key=lambda x: x.fitness_result.fitness if x.fitness_result else -float('inf'))
    n = len(ranked)
    weights = list(range(1, n + 1))
    total_weight = sum(weights)
    
    selected = []
    for _ in range(count):
        r = random.uniform(0, total_weight)
        cumulative = 0
        for i, ind in enumerate(ranked):
            cumulative += weights[i]
            if cumulative >= r:
                selected.append(copy.deepcopy(ind))
                break
    return selected


def crossover(parent1: Individual, parent2: Individual, crossover_probability: float) -> Tuple[Individual, Individual]:
    """Multi-point crossover with 2 random points."""
    if random.random() >= crossover_probability:
        return copy.deepcopy(parent1), copy.deepcopy(parent2)

    if len(parent1.chromosome) != len(parent2.chromosome) or len(parent1.chromosome) <= 1:
        return copy.deepcopy(parent1), copy.deepcopy(parent2)

    length = len(parent1.chromosome)
    if length == 2:
        point_a, point_b = 1, 2
    else:
        point_a, point_b = sorted(random.sample(range(1, length), 2))

    child1_chrom = (
        parent1.chromosome[:point_a] +
        parent2.chromosome[point_a:point_b] +
        parent1.chromosome[point_b:]
    )
    child2_chrom = (
        parent2.chromosome[:point_a] +
        parent1.chromosome[point_a:point_b] +
        parent2.chromosome[point_b:]
    )

    child1 = Individual(chromosome=child1_chrom)
    child2 = Individual(chromosome=child2_chrom)

    return child1, child2


def mutate(individual: Individual, units: List[Box], mutation_rate: float) -> Individual:
    """Random mutation with dynamic rate."""
    mutated = copy.deepcopy(individual)

    for i in range(len(mutated.chromosome)):
        if random.random() < mutation_rate:
            if i < len(units) and units[i].permitted_postures:
                mutated.chromosome[i] = random.randrange(len(units[i].permitted_postures))

    return mutated


def genetic_algorithm(
    units: List[Box],
    container_dims: Dimensions,
    max_weight: float,
    is_lcl: bool,
    population_size: int = None,
    generations: int = None,
    elite_fraction: float = None,
    crossover_probability: float = None,
    mutation_rate_base: float = None,
    mutation_rate_max: float = None,
    mutation_rate_min: float = None,
    sa_interval: int = None,
    min_improvement: float = None,
    early_stop_patience: int = None,
    progress_callback: Callable[[int, Individual], None] = None,
) -> Individual:
    settings = get_settings()

    pop_size = population_size or settings.POPULATION_SIZE
    num_gens = generations or settings.GENERATIONS
    elite_frac = elite_fraction or settings.ELITE_FRACTION
    cross_prob = crossover_probability or settings.CROSSOVER_PROBABILITY
    mut_base = mutation_rate_base or settings.MUTATION_RATE_BASE
    mut_max = mutation_rate_max or settings.MUTATION_RATE_MAX
    mut_min = mutation_rate_min or settings.MUTATION_RATE_MIN
    sa_int = sa_interval or settings.SA_INTERVAL_GENERATIONS
    min_imp = min_improvement or settings.MIN_IMPROVEMENT
    patience = early_stop_patience or settings.EARLY_STOP_PATIENCE
    # BUG-16 fix: hoist settings out of the per-generation loop
    # (lru_cache means it's cheap, but saving the lookup inside hot loops adds up)
    _min_imp = min_imp

    population = [create_individual(units) for _ in range(pop_size)]

    for ind in population:
        evaluate_individual(ind, units, container_dims, max_weight, is_lcl)

    population.sort(key=lambda x: x.fitness_result.fitness if x.fitness_result else -float('inf'), reverse=True)

    best_individual = copy.deepcopy(population[0])
    best_fitness = best_individual.fitness_result.fitness if best_individual.fitness_result else -float('inf')
    stagnant_generations = 0
    mutation_rate = mut_base

    for gen in range(1, num_gens + 1):
        fitnesses = [ind.fitness_result.fitness if ind.fitness_result else -float('inf') for ind in population]
        gen_best_idx = fitnesses.index(max(fitnesses))

        # Check for meaningful improvement
        if fitnesses[gen_best_idx] > best_fitness + min_imp:
            best_individual = copy.deepcopy(population[gen_best_idx])
            best_fitness = fitnesses[gen_best_idx]
            stagnant_generations = 0
            mutation_rate = max(mut_min, mutation_rate * 0.9)
        else:
            stagnant_generations += 1
            mutation_rate = min(mut_max, mutation_rate * 1.1)
            # Keep sub-threshold improvements but don't reset patience
            if fitnesses[gen_best_idx] > best_fitness:
                best_individual = copy.deepcopy(population[gen_best_idx])
                best_fitness = fitnesses[gen_best_idx]

        # Simulated Annealing as local operator
        if gen % sa_int == 0:
            # BUG-09 fix: pass the real max_weight instead of volume*0.001
            sa_individual, sa_fitness = run_simulated_annealing(
                container_dims, units, best_individual, best_fitness, is_lcl,
                max_weight=max_weight,
            )
            if sa_fitness > best_fitness + min_imp:
                best_individual = sa_individual
                best_fitness = sa_fitness
                stagnant_generations = 0
            elif sa_fitness > best_fitness:
                best_individual = sa_individual
                best_fitness = sa_fitness

        # Early stopping: if all units are placed and stagnant for 3 generations, or if stagnant for patience
        all_placed = bool(best_individual.placed_data and len(best_individual.placed_data) == len(units))
        if (all_placed and stagnant_generations >= 3) or stagnant_generations >= patience:
            break

        # Selection and reproduction
        elite_count = max(1, int(pop_size * elite_frac))
        elites = population[:elite_count]
        selected = rank_based_selection(population, pop_size - elite_count)

        next_generation = [copy.deepcopy(e) for e in elites]

        while len(next_generation) < pop_size:
            parent1 = random.choice(selected)
            parent2 = random.choice(selected)
            child1, child2 = crossover(parent1, parent2, cross_prob)

            child1 = mutate(child1, units, mutation_rate)
            child2 = mutate(child2, units, mutation_rate)

            evaluate_individual(child1, units, container_dims, max_weight, is_lcl)
            evaluate_individual(child2, units, container_dims, max_weight, is_lcl)

            next_generation.append(child1)
            if len(next_generation) < pop_size:
                next_generation.append(child2)

        population = next_generation[:pop_size]
        population.sort(key=lambda x: x.fitness_result.fitness if x.fitness_result else -float('inf'), reverse=True)

        if progress_callback:
            progress_callback(gen, best_individual)

    return best_individual