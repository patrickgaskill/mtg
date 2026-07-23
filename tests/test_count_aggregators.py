"""Tests for the counting aggregators."""

from aggregators.count_aggregators import MaxCollectorNumberBySetAggregator


def make_card(**overrides):
    base = {
        "name": "Test Card",
        "set": "tst",
        "set_type": "expansion",
        "layout": "normal",
        "border_color": "black",
        "collector_number": "42",
    }
    base.update(overrides)
    return base


class TestMaxCollectorNumberBySetAggregator:
    def test_tracks_max_number_per_set(self):
        aggregator = MaxCollectorNumberBySetAggregator()
        aggregator.process_card(make_card(collector_number="42"))
        aggregator.process_card(make_card(collector_number="7"))
        aggregator.process_card(make_card(collector_number="300", set="oth"))
        assert aggregator.get_sorted_data() == [
            {"set": "oth", "maxNumber": 300},
            {"set": "tst", "maxNumber": 42},
        ]

    def test_ignores_non_numeric_collector_numbers(self):
        aggregator = MaxCollectorNumberBySetAggregator()
        aggregator.process_card(make_card(collector_number="123a"))
        assert aggregator.get_sorted_data() == []

    def test_skips_sets_with_invented_collector_numbers(self):
        # Scryfall invents collector numbers for some sets — e.g. Magic Online
        # catalog IDs for prm, event years for Vintage Championship prints.
        aggregator = MaxCollectorNumberBySetAggregator()
        aggregator.process_card(make_card(set="prm", collector_number="65961"))
        aggregator.process_card(make_card(set="ovnt", collector_number="2018"))
        assert aggregator.get_sorted_data() == []

    def test_counts_silver_border_and_funny_sets(self):
        # Un-set cards have real printed collector numbers.
        aggregator = MaxCollectorNumberBySetAggregator()
        aggregator.process_card(
            make_card(set="ust", set_type="funny", border_color="silver", collector_number="216")
        )
        assert aggregator.get_sorted_data() == [{"set": "ust", "maxNumber": 216}]
