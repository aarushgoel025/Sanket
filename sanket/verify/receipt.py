"""Verification receipt assembler and task acceptance gate.

Collects verification outcomes across solver agreement, render fidelity,
visibility checks, blind model testing, and consistency checks into an auditable Receipt.
"""

from typing import Literal

from sanket.schema import Answer, Receipt, Scene, Task


def build_receipt(
    task: Task,
    scene: Scene,
    solver_answer: Answer | str,
    independent_answer: Answer | str,
    fidelity: tuple[bool, str] | bool,
    visibility: tuple[bool, float] | bool,
    evidence_visible_ratio: float | None = None,
    blind_correct_rate: float | None = None,
    blind_rejected: bool = False,
    pair_verified: bool | None = None,
    human_audit: Literal["pass", "fail", "unaudited"] = "unaudited",
    notes: str = "",
) -> Receipt:
    """Build an audit Receipt recording the outcome of all verification layers.

    Agreement rule:
    `agree = (solver_answer == independent_answer == task.gold)`

    Args:
        task: Benchmark task instance.
        scene: Scene specification.
        solver_answer: Ground-truth answer from venue graph solver.
        independent_answer: Answer from independent verifier.
        fidelity: Fidelity outcome (bool or (bool, reason) tuple).
        visibility: Visibility outcome (bool or (bool, visible_ratio) tuple).
        evidence_visible_ratio: Optional explicit visible ratio.
        blind_correct_rate: Fraction of correct guesses from text-only blind model.
        blind_rejected: Whether task was rejected by the blind-guessing audit.
        pair_verified: Whether minimal-pair differential check passed.
        human_audit: Manual inspection label.
        notes: Verification or diagnostic notes.

    Returns:
        Populated Receipt model.
    """
    if isinstance(fidelity, tuple):
        fidelity_ok_val, fidelity_note = fidelity
    else:
        fidelity_ok_val, fidelity_note = fidelity, ""

    if isinstance(visibility, tuple):
        visibility_ok_val, vis_ratio = visibility
    else:
        visibility_ok_val = visibility
        vis_ratio = evidence_visible_ratio if evidence_visible_ratio is not None else 1.0

    # Core ground-truth agreement contract
    agree = solver_answer == independent_answer == task.gold

    combined_notes = notes
    if fidelity_note and not combined_notes:
        combined_notes = fidelity_note
    elif fidelity_note and combined_notes:
        combined_notes = f"{combined_notes}; {fidelity_note}"

    return Receipt(
        solver_answer=solver_answer,  # type: ignore[arg-type]
        independent_answer=independent_answer,  # type: ignore[arg-type]
        agree=agree,
        fidelity_ok=fidelity_ok_val,
        visibility_ok=visibility_ok_val,
        evidence_visible_ratio=vis_ratio,
        blind_correct_rate=blind_correct_rate,
        blind_rejected=blind_rejected,
        pair_verified=pair_verified,
        human_audit=human_audit,
        notes=combined_notes,
    )


def is_task_kept(receipt: Receipt) -> bool:
    """Determine whether a task passes all required acceptance criteria.

    A task is kept if and only if:
    - solver_answer == independent_answer == task.gold (agree is True)
    - fidelity_ok is True
    - visibility_ok is True
    - blind_rejected is False
    """
    return bool(
        receipt.agree
        and receipt.fidelity_ok
        and receipt.visibility_ok
        and not receipt.blind_rejected
    )


__all__ = ["build_receipt", "is_task_kept"]
