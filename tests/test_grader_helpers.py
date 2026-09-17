import pytest

from android_bench.grader import delivery_class, extract_json_object
from android_bench.models import DeliveryClass


@pytest.mark.parametrize(
    ("local_app", "interaction", "expected"),
    [
        (False, False, DeliveryClass.REMOTE_ZERO_CLICK),
        (False, True, DeliveryClass.REMOTE_ONE_CLICK),
        (True, False, DeliveryClass.LOCAL_APP_ZERO_CLICK),
        (True, True, DeliveryClass.LOCAL_APP_ONE_CLICK),
    ],
)
def test_delivery_class(
    local_app: bool, interaction: bool, expected: DeliveryClass
) -> None:
    assert delivery_class(local_app, interaction) is expected


def test_extract_json_object_accepts_incidental_text() -> None:
    assert extract_json_object('prefix ```json\n{"cheating": false}\n```') == {
        "cheating": False
    }


def test_extract_json_object_rejects_missing_object() -> None:
    with pytest.raises(ValueError):
        extract_json_object("[]")
