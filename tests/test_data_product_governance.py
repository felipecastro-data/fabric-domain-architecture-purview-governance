from fabric_mesh_tools.data_product_governance import diff_product

PRODUCT = {
    "label_id": "label-confidential",
    "tags": {"Data Product": "tag-dp", "Source Aligned": "tag-sa"},
    "endorsement": "Certified",
}


def scanned(label="label-confidential", endorsement="Certified"):
    return {"sensitivityLabel": {"labelId": label}, "endorsementDetails": {"endorsement": endorsement}}


def test_match():
    d = diff_product(PRODUCT, scanned(), {"tag-dp", "tag-sa"})
    assert d.label_ok and d.tags_ok and d.endorsement_ok


def test_label_tags_and_endorsement_drift():
    d = diff_product(PRODUCT, scanned(label="label-public", endorsement="Promoted"), {"tag-dp", "tag-old"})
    assert not d.label_ok
    assert d.tags_add == {"tag-sa"} and d.tags_remove == {"tag-old"}
    assert not d.endorsement_ok and d.endorsement == "Promoted"


def test_unscanned_item_has_no_label_and_no_endorsement():
    d = diff_product(PRODUCT, {}, set())
    assert not d.label_ok
    assert d.endorsement == "None" and not d.endorsement_ok


def test_null_endorsement_is_not_checked():
    d = diff_product({**PRODUCT, "endorsement": None}, scanned(endorsement="None"), {"tag-dp", "tag-sa"})
    assert d.endorsement_ok
