"""``/gap`` (tickets 34, 35): the Elite gap against the top 10k (``/gap 100k``: the top 100k),
on demand only.

Reads what the post-deadline job stored: the Elite cohort's XI and captain shares at the last
deadline (``store/elite.py``), the Member's Squad at that deadline and average points over the
last 4 finished Gameweeks as the weight. The Gap itself is ticket 33's pure ``advice/gap.py``,
with the sample's margin of error. Rendered in the shape of ``eliteMessage`` in the Gap
prototype. Figures of another Gameweek are never shown in place of the last deadline's.
"""

from fplbot.advice.gap import GapLine, Shares, gap
from fplbot.clock import Clock
from fplbot.delivery import texts
from fplbot.delivery.gap_lines import backing, name, percent, signed, xi_line
from fplbot.store.elite import EliteStore
from fplbot.store.footballer_stats import FootballerStatsStore
from fplbot.store.members import MemberRecord
from fplbot.store.reference import ReferenceStore
from fplbot.store.seasons import season_of
from fplbot.store.squads import SquadStore

TOP_10K = "10k"
TOP_100K = "100k"
_VIEW_WORDS = {TOP_10K, TOP_100K, "captain"}


class EliteGaps:
    def __init__(
        self,
        *,
        clock: Clock,
        reference: ReferenceStore,
        squads: SquadStore,
        elite: EliteStore,
        stats: FootballerStatsStore,
    ) -> None:
        self._clock = clock
        self._reference = reference
        self._squads = squads
        self._elite = elite
        self._stats = stats

    async def reply(self, member: MemberRecord, argument: str) -> str:
        words = argument.lower().split()
        view = set(words)
        if not view <= _VIEW_WORDS or len(view) < len(words) or {TOP_10K, TOP_100K} <= view:
            return texts.GAP_USAGE
        captain_only = "captain" in view
        cohort = TOP_100K if TOP_100K in view else TOP_10K
        now = self._clock.now()
        season = season_of(now)
        deadlines = await self._reference.deadlines(now)
        if deadlines.last is None:
            return texts.NO_DEADLINE_YET
        current = deadlines.last.id
        # This Gameweek's figures, else (its sample did not finish, or fell short of half its
        # target) the previous Gameweek's, labelled as such. Never a mix of the two.
        figures = await self._elite.figures(season, current, cohort)
        if figures is None:
            figures = await self._elite.figures(season, current - 1, cohort)
        if figures is None:
            return texts.gap_not_ready(cohort, current)
        squad = await self._squads.latest_squad(member.number, season, deadlines.last.id)
        if squad is None:
            return texts.gap_no_squad(deadlines.last.id)
        weights = await self._stats.average_points(season)
        if not weights:
            return texts.RIVALS_NO_STATS
        reference = {
            footballer: Shares(xi=shares.xi, captain=shares.captain)
            for footballer, shares in figures.footballers.items()
        }
        result = gap(
            backing(squad),
            reference,
            weights,
            margin_of_error=figures.margin_of_error,
            captain_only=captain_only,
        )
        ids = {line.footballer_id for line in (*result.you_back, *result.they_back)}
        names = await self._reference.footballer_names(season, ids)
        render = _captain_line if captain_only else xi_line
        upcoming = deadlines.next
        lines = [
            texts.gap_header(cohort, captain_only),
            texts.gap_sample(
                figures.gameweek,
                figures.sample_size,
                figures.margin_of_error,
                partial=figures.partial,
                read_late=figures.read_late,
            )
            if figures.gameweek == current
            else texts.gap_previous_figures(figures.gameweek, current),
            texts.rivals_squad_as_of(squad.gameweek, upcoming.id if upcoming else None),
            "",
            texts.gap_edge_explained(cohort),
        ]
        for title, side in (
            (texts.RIVALS_YOU_BACK, result.you_back),
            (texts.RIVALS_THEY_BACK, result.they_back),
        ):
            if side:
                lines += ["", title, *(render(line, names) for line in side)]
        if result.empty:
            lines += ["", texts.GAP_TEMPLATE]
        return "\n".join(lines)


def _captain_line(line: GapLine, names: dict[int, str]) -> str:
    return texts.gap_captain_line(
        name(names, line.footballer_id),
        line.you_captain,
        percent(line.reference.captain),
        signed(line.edge),
    )
