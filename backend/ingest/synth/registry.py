"""The hidden ground-truth person registry.

The KSP schema has no person entity — that is the entire premise of the project.
This registry is the answer key: a population of real people, each of whom may
surface across many FIRs under corrupted names. The entity-resolution pipeline
never sees this; it has to *reconstruct* it, and P8 scores the reconstruction
against what is recorded here.

It owns three structures the network/overlap features depend on:
  - **gangs**: sets of people who tend to be arrested together, producing the
    co-offending edges collective resolution (P7) and community detection (P12)
    need to find.
  - **repeat offenders**: solo people who recur across cases as accused.
  - **duals**: people who appear as a *victim* in one FIR and an *accused* in
    another — the victim-offender overlap (P7a), invisible in the raw schema.

Everyone else is a singleton, created on demand. Draws are weighted so most
people appear once and a long tail recurs, matching real offender frequency.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .names import NameParts, canonical_name


@dataclass
class TruePerson:
    pid: int
    gender_id: int
    birth_year: int
    home_district_id: int
    parts: NameParts
    kind: str  # 'singleton' | 'repeat' | 'gang' | 'dual'
    gang_id: int | None = None
    appearances: list[dict] = field(default_factory=list)

    def record(self, role: str, source_row_id: int, case_master_id: int, age_year: int) -> None:
        self.appearances.append(
            {
                "role": role,
                "source_row_id": source_row_id,
                "case_master_id": case_master_id,
                "age_year": age_year,
            }
        )


@dataclass
class RegistryConfig:
    n_cases: int
    gang_frac: float = 0.006  # gangs per case
    gang_size_range: tuple[int, int] = (2, 5)
    repeat_frac: float = 0.05  # solo repeat offenders per case
    dual_frac: float = 0.015  # victim-offender overlap people per case
    recurring_accused_prob: float = 0.45
    gang_group_prob: float = 0.55  # of multi-accused cases drawn from one gang
    seed_year: int = 2018


class PersonRegistry:
    def __init__(self, rng, cfg: RegistryConfig, districts):
        self.rng = rng
        self.cfg = cfg
        self.districts = districts
        self._next_pid = 1
        self.people: dict[int, TruePerson] = {}
        self.gangs: dict[int, list[int]] = {}
        self.repeat_pool: list[int] = []
        self.dual_pool: list[int] = []  # duals still owing a victim appearance
        self._build_recurring()

    # --- population construction --------------------------------------------

    def _fresh(self, kind: str, gang_id: int | None = None) -> TruePerson:
        gender_id = 1 if self.rng.random() < 0.82 else 2  # accused skew male
        birth_year = self.cfg.seed_year - self.rng.randint(18, 60)
        d = self.rng.choice(self.districts)
        p = TruePerson(
            pid=self._next_pid,
            gender_id=gender_id,
            birth_year=birth_year,
            home_district_id=d.district_id,
            parts=canonical_name(gender_id, self.rng),
            kind=kind,
            gang_id=gang_id,
        )
        self.people[p.pid] = p
        self._next_pid += 1
        return p

    def _build_recurring(self) -> None:
        n = self.cfg.n_cases
        n_gangs = max(1, int(n * self.cfg.gang_frac))
        for g in range(1, n_gangs + 1):
            size = self.rng.randint(*self.cfg.gang_size_range)
            members = [self._fresh("gang", gang_id=g).pid for _ in range(size)]
            self.gangs[g] = members
            self.repeat_pool.extend(members)

        for _ in range(max(1, int(n * self.cfg.repeat_frac))):
            self.repeat_pool.append(self._fresh("repeat").pid)

        for _ in range(max(1, int(n * self.cfg.dual_frac))):
            pid = self._fresh("dual").pid
            self.repeat_pool.append(pid)  # duals also offend
            self.dual_pool.append(pid)

    # --- draws ---------------------------------------------------------------

    def draw_accused_group(self, k: int) -> list[TruePerson]:
        """Return k people to fill a case's accused slots. Multi-accused cases are
        often drawn from a single gang so co-arrest edges accumulate."""
        if k >= 2 and self.gangs and self.rng.random() < self.cfg.gang_group_prob:
            gang_id = self.rng.choice(list(self.gangs))
            members = self.gangs[gang_id][:]
            self.rng.shuffle(members)
            chosen = [self.people[pid] for pid in members[:k]]
            while len(chosen) < k:  # top up if gang smaller than k
                chosen.append(self._draw_one_accused())
            return chosen
        return [self._draw_one_accused() for _ in range(k)]

    def _draw_one_accused(self) -> TruePerson:
        if self.repeat_pool and self.rng.random() < self.cfg.recurring_accused_prob:
            return self.people[self.rng.choice(self.repeat_pool)]
        return self._fresh("singleton")

    def draw_victim(self) -> TruePerson:
        """Victims are mostly one-off, but a dual person occasionally takes their
        victim appearance here so the overlap exists to be found later."""
        if self.dual_pool and self.rng.random() < 0.5:
            pid = self.dual_pool.pop()
            return self.people[pid]
        return self._fresh("singleton")

    def draw_complainant(self) -> TruePerson:
        return self._fresh("singleton")

    # --- ground truth --------------------------------------------------------

    def distinct_people_with_appearances(self) -> list[TruePerson]:
        return [p for p in self.people.values() if p.appearances]

    def ground_truth(self) -> dict:
        appearing = self.distinct_people_with_appearances()
        multi = [p for p in appearing if len(p.appearances) > 1]
        return {
            "n_distinct_people": len(appearing),
            "n_recurring_people": len(multi),
            "n_total_appearances": sum(len(p.appearances) for p in appearing),
            "n_gangs": len(
                [g for g, m in self.gangs.items() if any(self.people[pid].appearances for pid in m)]
            ),
            "people": [
                {
                    "true_person_id": p.pid,
                    "kind": p.kind,
                    "gang_id": p.gang_id,
                    "canonical_given": p.parts.given,
                    "canonical_patronymic": p.parts.patronymic,
                    "gender_id": p.gender_id,
                    "birth_year": p.birth_year,
                    "appearances": p.appearances,
                }
                for p in appearing
            ],
        }
