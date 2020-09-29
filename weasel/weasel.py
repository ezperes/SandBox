""" Genetic algorithm to accomplish the weasel test
"""
import string
import random
import json
from pprint import pprint

import numpy as np
import pandas as pd


class Goal:
    value = "esta frase eh do caralho"
    charset = string.ascii_lowercase+" "
    size = len(value)


class PopSettings:
    pop_init_size = 50          # Population initial size
    charset = Goal.charset      # The searchspace
    avg_size = Goal.size        # Avg size of individuals
    std_dev_ratio = 0.0
    std_dev = round(std_dev_ratio*avg_size)


class GeneticSettings:
    population_grow_rate = .1         # How much pop grows throughout generations
    offspring_method_params = {
        'elite_rate': 0.6,       # Ratio from pop considered best fit for random choice
        'x_elite_supremacy': 0.35,             # Ratio to randomly choose parent's gene to heritage
        'mutation_prob': 0.05,
        'tournment_t-uple': 4,
        'tournment_rate': 0.6,
        'random_rate': 0.7,
    }
    max_iter = 1000
    precision_goal = 0


def random_string(n=PopSettings.avg_size, charset=PopSettings.charset):
    """ Generates a n-length string with random characters,
        for the given character set
    """
    return ''.join(random.choice(charset) for _ in range(n))


def save_json(target_object, filename: str):
    """ Saves target_object in file using json format
    """
    with open(filename, 'w') as newfile:
        json.dump(target_object, newfile)


def load_pop():
    """ Returns 1st_pop.json content """
    with open('/Users/eduardo/Dev/Sandbox/1st_pop.json', 'r') as fp:
        return json.load(fp)


def spawn_population(n=PopSettings.pop_init_size, avg_size=PopSettings.avg_size, deviation=PopSettings.std_dev,
                     charset=PopSettings.charset) -> list:
    """ Spawn a population of random individuals
        :n: number of individuals
        :size: string average size
        :deviation: max absolute deviation in string size
        :returns: a population of random string, as a list
    """
    return [random_string(avg_size+random.randint(-deviation, deviation+1), charset) for _ in range(n)]


def fitness(x, goal=Goal.value):
    """ Returns a score for string match
        0 means full match
    """

    maxpoints = len(goal)
    x_size = len(x)

    if maxpoints == x_size:
        # Goal and tested obj lenghts DO match

        score = maxpoints
        x_size = len(x)

        for i, letter in enumerate(x.lower()):
            tested_one = goal[i].lower()
            if letter == tested_one:
                # print("%d-th character match! %s == %s" % (i, letter, tested_one))
                score -= 1
    else:
        # Lengths don't match -> let's penalize
        score = maxpoints*10 + abs(maxpoints-x_size)*1000

    # print("Individual: %s    ->   Score: %d" % (x, score))
    return score


def x_over(a, b, elite: pd.Series):
    g, h = list(a), list(b)

    # 1. Picks shortest lenght and the longest one
    len_g = len(g)
    len_h = len(h)
    short_len = min(len_g, len_h)
    longest = g if len_g > len_h else h

    # 2. Calculates brooding size
    g_elite = 1 if a in elite.values else 0
    h_elite = 1 if b in elite.values else 0
    brooding_n = 1 + g_elite + h_elite

    # 3. Generates brooding
    brood = list()

    for _ in range(brooding_n):

        # 3.1. Calculates offspring length
        out_len = round(random.triangular(len_g, len_h))
        # 3.2. Generates offspring
        offspring = list()
        bias = GeneticSettings.offspring_method_params['x_elite_supremacy']
        for i in range(out_len):
            if i < short_len:
                offspring.append(g[i] if random.random() < bias else h[i])
            else:
                offspring.append(longest[i])

        brood.append(''.join(offspring))

    return brood



# def eval_pop(pop: pd.Series, goal):
#     """ Evaluates the score of each individual within a population
#             :pop:       The population as a Series
#             :goal:      The goal string
#     """
#     return {individual: f(individual) for individual in pop}


# def sort_pop(pop: pd.DataFrame) -> dict:
#     """ Sorts a given population DataFrame in place """
#     return dict(sorted(pop.items(), key=operator.itemgetter(1)))


def pick_random_parents(pop: pd.DataFrame,
                        random_rate: float = GeneticSettings.offspring_method_params['random_rate'],
                        elite_rate: float = GeneticSettings.offspring_method_params['elite_rate']
                        ):
    pass


def pick_elite(pop:pd.DataFrame,
               elite_rate: float = GeneticSettings.offspring_method_params['elite_rate']
               ) -> pd.DataFrame:
    """ Returns the elite indivuals of a population
            :pop:DataFrame: The population with Fitness column
            :elite_rate:float: Percentage of pop which are considered elite
            :return: the elite group as Dataframe
    """
    # 1. Set the elite amount
    elite_amount = round(pop.shape[0]*elite_rate)

    # 2. Return the elite group
    return pop.nsmallest(elite_amount, 'Fitness')


def pick_non_elite(pop: pd.DataFrame, elite: pd.DataFrame) -> pd.DataFrame:
    """ Returns the non elite indivuals of a population
            :pop:DataFrame: The population
            :elite:DataFrame: The elite
            :return: the non-elite group as Dataframe
    """
    return pop[pop.Individual.isin(elite.Individual) == False]


def x_elite_breeder(pop: pd.DataFrame) -> pd.DataFrame:

    # Get elite individuals
    elite = pick_elite(pop)
    elite.reset_index(drop=True, inplace=True)

    # For each elite individual, get the couple counterpart (the other parent)
    other = pop.sample(n=elite.shape[0])
    other.reset_index(drop=True, inplace=True)
    other.rename(columns={'Individual': 'Other'}, inplace=True)

    # Join copules
    couples = pd.concat([elite['Individual'], other['Other']], axis=1)

    # Breeds
    breed = couples.apply(lambda x: x_over(x.Individual, x.Other, elite), axis=1)
    breed = pd.DataFrame(breed.sum(), columns=['Individual'])

    # Creates a column with fitness values in breed
    breed['Fitness'] = breed.Individual.apply(fitness)

    return breed


def mutate_dna(indv):
    ind = list(indv)
    bias = GeneticSettings.offspring_method_params['mutation_prob']
    for i, letter in enumerate(ind):
        ind[i] = letter if random.random() >= bias else random.choice(PopSettings.charset)
    ind = ''.join(ind)
    return ind


def mutate_pop(pop):
    return pop.Individual.apply(mutate_dna)


def print_pop_stats(pop: pd.DataFrame, generation: int = None):
    """ Print population statistics """
    print("="*60)
    if generation:
        print("Generation nr: %04d" % generation)
    print("Stats:")
    print("Pop size: ", pop.shape[0])
    print("Average: ", pop.Fitness.mean())
    print("Max: ", pop.Fitness.max())
    print("Min: ", pop.Fitness.min())
    print("Mode: ", pop.Fitness.mode())
    print("Std Dev: ", pop.Fitness.std())
    pprint(pop.sort_values('Fitness').head(5))


# Loads test population
# pop = load_pop()

# Generates random population
pop = spawn_population()

# Creates a dataframe with population from json file
dfpop = pd.DataFrame(pop, columns=['Individual'])

# Creates a column with fitness values
dfpop['Fitness'] = dfpop.Individual.apply(fitness)

print("Original population redy to spawn 1st brood:")
print_pop_stats(dfpop)

i = 0
while i < GeneticSettings.max_iter and dfpop.Fitness.min() > GeneticSettings.precision_goal:

    # Breeds the elite's offspring
    x_breed = x_elite_breeder(dfpop)

    # Appends breed into existing population in a copyed dataset
    newpop = dfpop.append(x_breed, ignore_index=True)

    # Mutation phenomena over the new dataset
    mutant = mutate_pop(newpop)
    newpop['Individual'] = mutant
    # newpop.reset_index(drop=True, inplace=True)

    # Calculates the next population's size
    newpop_amount = round(dfpop.shape[0]*(1.0+GeneticSettings.population_grow_rate))

    # Calculates everyone's Fitness, and stores in a new DS column
    newpop['Fitness'] = newpop.Individual.apply(fitness)

    # Kills the unfitted
    newpop = newpop.nsmallest(newpop_amount, 'Fitness').reset_index(drop=True)

    # Updates main population dataset
    dfpop = newpop

    # Exhibits population stats
    print_pop_stats(dfpop, i)

    # Increments population count
    i += 1

    # Checks and exhibits wether goal is achieved or not
    if dfpop.Fitness.min() > GeneticSettings.precision_goal:
        print("Goal not achieved yet. Let's try %0002d generation" % i)
    else:
        print("Goal achieved!")

if i >= GeneticSettings.max_iter:
    print("Max nr of iteration (%d) reached." % i)
