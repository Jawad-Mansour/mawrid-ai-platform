"""
Feature:  RAG Pipeline — Parent/Child Chunking
Layer:    Tests / Unit
Module:   tests.unit.test_chunker
Purpose:  Unit tests for the deterministic parent/child chunker that feeds the
          product_chunks table. Verifies window sizes, overlap, parent linkage,
          and edge cases (empty text, short text).
Depends:  app.rag.chunker
HITL:     None.
"""

from __future__ import annotations

from app.rag.chunker import build_chunks


def _words(n: int) -> str:
    return " ".join(f"w{i}" for i in range(n))


class TestBuildChunks:
    def test_empty_text_yields_no_chunks(self) -> None:
        assert build_chunks("") == []
        assert build_chunks("   \n\t ") == []

    def test_short_text_one_parent_one_child(self) -> None:
        specs = build_chunks("Samsung 65 inch TV")
        parents = [s for s in specs if s.chunk_type == "parent"]
        children = [s for s in specs if s.chunk_type == "child"]
        assert len(parents) == 1
        assert len(children) == 1
        assert parents[0].chunk_text == "Samsung 65 inch TV"
        # The only child links to the only parent.
        assert children[0].parent_index == 0

    def test_parents_are_non_overlapping_and_cover_all_words(self) -> None:
        specs = build_chunks(_words(2500), parent_tokens=1000, child_tokens=200, child_overlap=20)
        parents = [s for s in specs if s.chunk_type == "parent"]
        # 2500 words / 1000 → 3 parents (1000, 1000, 500).
        assert len(parents) == 3
        rejoined = " ".join(p.chunk_text for p in parents)
        assert rejoined == _words(2500)  # non-overlapping, full coverage

    def test_children_overlap_and_link_to_a_valid_parent(self) -> None:
        specs = build_chunks(_words(1000), parent_tokens=400, child_tokens=100, child_overlap=20)
        parents = [s for s in specs if s.chunk_type == "parent"]
        children = [s for s in specs if s.chunk_type == "child"]
        assert len(parents) == 3  # 400, 400, 200
        # Overlap means more children than a clean division would give.
        assert len(children) > len(parents)
        for child in children:
            assert child.parent_index is not None
            assert 0 <= child.parent_index < len(parents)

    def test_child_indices_are_sequential(self) -> None:
        specs = build_chunks(_words(500), parent_tokens=200, child_tokens=100, child_overlap=10)
        children = [s for s in specs if s.chunk_type == "child"]
        assert [c.chunk_index for c in children] == list(range(len(children)))
