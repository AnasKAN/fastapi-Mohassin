import os
import multiprocessing
print("Number of CPUs/threads available:", os.cpu_count() or multiprocessing.cpu_count())