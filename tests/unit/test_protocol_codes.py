"""錯誤碼清單鎖定：spec §7＋ADR-0007 能力判定碼、ADR-0016 協定層錯誤碼（G1-11）。"""

import pytest

from peditor.core.protocol import ERROR_CODES, PROTOCOL_ERROR_CODES, ProtocolError

SPEC_CODES = {"UNSUPPORTED_ENCODING", "UNSUPPORTED_LAYOUT", "GLYPH_MISSING", "TEXT_OVERFLOW",
              "SHARED_RESOURCE_UNSAFE", "SIGNED_DOCUMENT", "ENCRYPTED_DOCUMENT",
              "REVISION_CONFLICT", "RESOURCE_LIMIT", "VALIDATION_FAILED", "SAVE_FAILED",
              "CANCELLED"}  # fmt: skip
ADR_0007_CODES = {"NO_TEXT_LAYER", "MALFORMED_DOCUMENT", "ACTIVE_CONTENT", "UNSUPPORTED_FEATURE"}
ADR_0016_CODES = {"INVALID_REQUEST", "WORKER_FAILED"}


def test_error_code_sets_match_spec_and_adrs():
    assert ERROR_CODES == SPEC_CODES | ADR_0007_CODES
    assert PROTOCOL_ERROR_CODES == ADR_0016_CODES
    assert not ERROR_CODES & PROTOCOL_ERROR_CODES


def test_unknown_error_code_refused():
    with pytest.raises(ValueError):
        ProtocolError("SOMETHING_ELSE", "x")
