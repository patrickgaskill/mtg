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

    def test_skips_digital_cards(self):
        # Scryfall uses Magic Online catalog IDs as collector numbers for
        # digital sets like prm, which aren't real collector numbers.
        aggregator = MaxCollectorNumberBySetAggregator()
        aggregator.process_card(
            make_card(set="prm", set_type="promo", collector_number="65961", digital=True)
        )
        assert aggregator.get_sorted_data() == []

    def test_skips_non_traditional_sets(self):
        # Memorabilia prints like Vintage Championship use event years as
        # collector numbers.
        aggregator = MaxCollectorNumberBySetAggregator()
        aggregator.process_card(
            make_card(set="ovnt", set_type="memorabilia", collector_number="2018")
        )
        assert aggregator.get_sorted_data() == []
