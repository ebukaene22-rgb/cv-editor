import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from research.stats import annualized_sharpe, cluster_bootstrap_mean


class TestClusterBootstrap(unittest.TestCase):
    def test_point_estimate_is_grand_mean(self):
        data = {"a": [0.01, 0.03], "b": [0.02], "c": [-0.02, 0.06]}
        res = cluster_bootstrap_mean(data, n_boot=500, seed=1)
        self.assertAlmostEqual(res.point, 0.02)
        self.assertEqual(res.n_clusters, 3)
        self.assertEqual(res.n_obs, 5)

    def test_deterministic_given_seed(self):
        data = {i: [0.001 * (i % 7 - 3), 0.002] for i in range(30)}
        a = cluster_bootstrap_mean(data, n_boot=1000, seed=42)
        b = cluster_bootstrap_mean(data, n_boot=1000, seed=42)
        self.assertEqual((a.ci_low, a.ci_high), (b.ci_low, b.ci_high))

    def test_ci_contains_point_for_reasonable_data(self):
        data = {i: [0.01 + 0.001 * ((i * 7) % 5 - 2)] for i in range(50)}
        res = cluster_bootstrap_mean(data, n_boot=2000, seed=0)
        self.assertLessEqual(res.ci_low, res.point)
        self.assertGreaterEqual(res.ci_high, res.point)
        self.assertTrue(res.excludes_zero())

    def test_clustering_widens_ci_versus_fake_independence(self):
        # 10 clusters of 10 identical observations each: the effective sample
        # is 10, not 100. Treating each observation as its own cluster must
        # produce a tighter interval than honest clustering.
        values = [0.05, -0.03, 0.02, 0.04, -0.01, 0.03, -0.02, 0.06, 0.00, 0.01]
        clustered = {i: [v] * 10 for i, v in enumerate(values)}
        fake_iid = {(i, j): [v] for i, v in enumerate(values) for j in range(10)}
        wide = cluster_bootstrap_mean(clustered, n_boot=3000, seed=7)
        narrow = cluster_bootstrap_mean(fake_iid, n_boot=3000, seed=7)
        self.assertGreater(
            wide.ci_high - wide.ci_low, narrow.ci_high - narrow.ci_low
        )

    def test_empty_input_rejected(self):
        with self.assertRaises(ValueError):
            cluster_bootstrap_mean({})
        with self.assertRaises(ValueError):
            cluster_bootstrap_mean({"a": []})


class TestSharpe(unittest.TestCase):
    def test_known_value(self):
        # mean 0.01, sd 0.01 -> daily SR 1.0 -> annualized sqrt(252)
        rets = [0.00, 0.02] * 50
        sr = annualized_sharpe(rets)
        self.assertAlmostEqual(sr, (0.01 / self._sd(rets)) * 252**0.5)

    @staticmethod
    def _sd(rets):
        m = sum(rets) / len(rets)
        var = sum((r - m) ** 2 for r in rets) / (len(rets) - 1)
        return var**0.5

    def test_requires_two_observations(self):
        with self.assertRaises(ValueError):
            annualized_sharpe([0.01])

    def test_zero_vol_rejected(self):
        with self.assertRaises(ValueError):
            annualized_sharpe([0.01, 0.01, 0.01])


if __name__ == "__main__":
    unittest.main()
