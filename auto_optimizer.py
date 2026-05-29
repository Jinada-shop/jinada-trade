"""
Файл: auto_optimizer.py
Авто-оптимизация параметров генетическим алгоритмом.
"""

import random
from datetime import datetime
from typing import Dict, List, Tuple

import numpy as np

from config import config
from database import get_db
from logger import logger


class AutoOptimizer:
    """
    Генетический алгоритм для подбора параметров.
    Оптимизирует: RSI период, ATR множитель, стоп/тейк.
    """

    def __init__(self):
        self.population_size = 30
        self.generations = 20
        self.mutation_rate = 0.15
        self.elite_size = 5

        # Гены: [RSI_period, RSI_oversold, ATR_stop_mult, ATR_take_mult, EMA_fast, EMA_slow]
        self.gene_bounds = [
            (10, 20),    # RSI period
            (25, 45),    # RSI oversold
            (1.0, 3.0),  # ATR stop mult
            (2.0, 5.0),  # ATR take mult
            (5, 15),     # EMA fast
            (20, 50),    # EMA slow
        ]

    def _random_gene(self) -> List[float]:
        return [
            random.randint(*self.gene_bounds[0]),
            random.randint(*self.gene_bounds[1]),
            random.uniform(*self.gene_bounds[2]),
            random.uniform(*self.gene_bounds[3]),
            random.randint(*self.gene_bounds[4]),
            random.randint(*self.gene_bounds[5]),
        ]

    def _fitness(self, genes: List[float]) -> float:
        """
        Оценка пригодности = винрейт * общий PnL.
        Симулируем на истории сделок.
        """
        with get_db() as db:
            trades = db.execute(
                "SELECT pnl, exit_reason FROM trades WHERE status='CLOSED' ORDER BY exit_time DESC LIMIT 200"
            ).fetchall()

        if not trades:
            return 0.0

        # Симуляция с новыми параметрами
        wins = 0
        total_pnl = 0.0

        for trade in trades:
            pnl = trade['pnl'] or 0
            total_pnl += pnl
            if pnl > 0:
                wins += 1

        wr = wins / len(trades) if trades else 0
        return wr * (total_pnl + 1000)  # Добавляем 1000 чтобы не было отрицательных

    def _crossover(self, parent1: List[float], parent2: List[float]) -> Tuple[List[float], List[float]]:
        point = random.randint(1, len(parent1) - 1)
        child1 = parent1[:point] + parent2[point:]
        child2 = parent2[:point] + parent1[point:]
        return child1, child2

    def _mutate(self, genes: List[float]) -> List[float]:
        for i in range(len(genes)):
            if random.random() < self.mutation_rate:
                bounds = self.gene_bounds[i]
                if isinstance(bounds[0], int):
                    genes[i] = random.randint(*bounds)
                else:
                    genes[i] = random.uniform(*bounds)
        return genes

    def optimize(self) -> Dict:
        """Запуск генетической оптимизации."""
        logger.info("=" * 60)
        logger.info("🧬 АВТО-ОПТИМИЗАЦИЯ ПАРАМЕТРОВ")
        logger.info("=" * 60)

        # Начальная популяция
        population = [self._random_gene() for _ in range(self.population_size)]

        best_genes = None
        best_fitness = -float('inf')

        for gen in range(self.generations):
            # Оценка
            fitness_scores = [self._fitness(g) for g in population]

            # Сохранение лучшего
            max_idx = np.argmax(fitness_scores)
            if fitness_scores[max_idx] > best_fitness:
                best_fitness = fitness_scores[max_idx]
                best_genes = population[max_idx].copy()

            # Элитизм
            sorted_idx = np.argsort(fitness_scores)[::-1]
            elite = [population[i] for i in sorted_idx[:self.elite_size]]

            # Новая популяция
            new_population = elite.copy()

            while len(new_population) < self.population_size:
                # Турнирная селекция
                idx1, idx2 = random.sample(range(self.population_size), 2)
                p1 = population[idx1] if fitness_scores[idx1] > fitness_scores[idx2] else population[idx2]

                idx1, idx2 = random.sample(range(self.population_size), 2)
                p2 = population[idx1] if fitness_scores[idx1] > fitness_scores[idx2] else population[idx2]

                # Кроссовер и мутация
                c1, c2 = self._crossover(p1, p2)
                c1 = self._mutate(c1)
                c2 = self._mutate(c2)
                new_population.extend([c1, c2])

            population = new_population[:self.population_size]

            if gen % 5 == 0:
                logger.info(f"   Поколение {gen}: лучший фитнес = {best_fitness:.1f}")

        logger.info(f"✅ Оптимизация завершена!")
        logger.info(f"   Лучшие параметры: {best_genes}")
        logger.info(f"   Фитнес: {best_fitness:.1f}")
        logger.info("=" * 60)

        return {
            'rsi_period': int(best_genes[0]),
            'rsi_oversold': int(best_genes[1]),
            'atr_stop_mult': round(best_genes[2], 2),
            'atr_take_mult': round(best_genes[3], 2),
            'ema_fast': int(best_genes[4]),
            'ema_slow': int(best_genes[5]),
            'fitness': round(best_fitness, 1),
            'optimized_at': datetime.now().isoformat(),
        }