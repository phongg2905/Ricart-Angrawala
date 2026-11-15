import asyncio

import pytest

from tests.cluster import Cluster


@pytest.mark.stress
@pytest.mark.integration
async def test_twelve_rounds_five_real_nodes(tmp_path):
    async with Cluster(tmp_path, 5) as c:
        for round_number in range(1, 13):
            await asyncio.gather(*(c.command(i, "REQUEST_CS", duration=0.05) for i in c.ports))
            await c.until(lambda ss: len(ss) == 5 and all(s["completed"] == round_number for s in ss))
        c.assert_safety(60)
        states = await c.statuses()
        assert sum(s["sent"]["REQUEST"] for s in states) == 240
        assert sum(s["sent"]["REPLY"] for s in states) == 240
