import time, resource, concurrent.futures as cf
from argon2 import PasswordHasher

profiles = [("19MiB t2", 19456, 2), ("32MiB t2", 32768, 2), ("64MiB t3", 65536, 3)]


def one(ph):
    a = time.perf_counter(); h = ph.hash("correct horse battery"); hm = time.perf_counter() - a
    a = time.perf_counter(); ph.verify(h, "correct horse battery"); return hm, time.perf_counter() - a


for name, m, t in profiles:
    ph = PasswordHasher(time_cost=t, memory_cost=m, parallelism=1)
    h, v = one(ph)
    t0 = time.perf_counter()
    with cf.ThreadPoolExecutor(3) as ex:
        list(ex.map(lambda _: one(ph), range(3)))
    wall = time.perf_counter() - t0
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    print(f"{name}: hash={h*1000:.0f}ms verify={v*1000:.0f}ms | 3 parallel wall={wall*1000:.0f}ms | peakRSS={peak:.0f}MB", flush=True)
