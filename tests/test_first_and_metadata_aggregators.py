"""Tests for the first-card and illustration aggregators."""

from aggregators.first_card_aggregators import FirstCardByPowerToughnessAggregator
from aggregators.metadata_aggregators import (
    CountCardIllustrationsBySetAggregator,
    MostPrintingsSameArtAggregator,
    MostUniqueIllustrationsAggregator,
)


def dfc_printing(set_code, front_art, back_art):
    return {
        "name": "Delver of Secrets // Insectile Aberration",
        "set": set_code,
        "layout": "transform",
        "set_type": "expansion",
        "border_color": "black",
        "released_at": "2011-09-30",
        "collector_number": "51",
        "card_faces": [
            {"name": "Delver of Secrets", "illustration_id": front_art},
            {"name": "Insectile Aberration", "illustration_id": back_art},
        ],
    }


class TestIllustrationsOnDoubleFacedCards:
    def test_count_by_set_uses_face_art(self):
        aggregator = CountCardIllustrationsBySetAggregator()
        aggregator.process_card(dfc_printing("isd", "a", "b"))
        (row,) = aggregator.get_sorted_data()
        assert row["count"] == 1

    def test_same_art_reprints_are_detected(self):
        aggregator = MostPrintingsSameArtAggregator()
        aggregator.process_card(dfc_printing("isd", "a", "b"))
        aggregator.process_card(dfc_printing("mm3", "a", "b"))
        (row,) = aggregator.get_sorted_data()
        assert row["printings"] == 2

    def test_new_art_counts_as_unique(self):
        aggregator = MostUniqueIllustrationsAggregator()
        aggregator.process_card(dfc_printing("isd", "a", "b"))
        aggregator.process_card(dfc_printing("mh2", "c", "d"))
        (row,) = aggregator.get_sorted_data()
        assert row["illustrations"] == 2


class TestFirstCardByPowerToughness:
    def test_reads_power_toughness_from_faces(self, sample_dfc_card):
        sample_dfc_card.update(set_type="expansion", border_color="black")
        aggregator = FirstCardByPowerToughnessAggregator()
        aggregator.process_card(sample_dfc_card)
        rows = aggregator.get_sorted_data()
        assert {(row["power"], row["toughness"]) for row in rows} == {("1", "1"), ("3", "2")}

    def test_skips_tokens(self, sample_creature):
        aggregator = FirstCardByPowerToughnessAggregator()
        aggregator.process_card({**sample_creature, "layout": "token"})
        assert aggregator.get_sorted_data() == []

    def test_counts_single_faced_creatures(self, sample_creature):
        aggregator = FirstCardByPowerToughnessAggregator()
        aggregator.process_card(sample_creature)
        (row,) = aggregator.get_sorted_data()
        assert (row["power"], row["toughness"], row["name"]) == ("2", "2", "Grizzly Bears")
