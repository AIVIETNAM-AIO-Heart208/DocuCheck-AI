"""Queue/review invariants without GPU, network or optional web dependencies."""

from concurrent.futures import ThreadPoolExecutor
import threading
import uuid

import pytest

from docucheck.web.settings import Settings
from docucheck.web.storage import Capacity, Conflict, Store
from docucheck.web.uploads import normalize_upload


def create(store, settings, owner="owner", token=None):
    key = str(uuid.uuid4())
    store.directory(key).mkdir()
    return store.create(owner, token or uuid.uuid4().hex, key, {"width":20,"height":30}, settings)[0]


def test_queue_admission_is_atomic(tmp_path):
    store = Store(tmp_path)
    settings = Settings(storage=tmp_path, queue_size=1, per_session=1)
    gate = threading.Barrier(2)
    def submit():
        gate.wait()
        try:
            create(store, settings)
            return True
        except Capacity:
            return False
    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(submit) for _ in range(2)]
        assert sum(f.result() for f in futures) == 1


def test_duplicate_token_owner_and_restart(tmp_path):
    store = Store(tmp_path)
    settings = Settings(storage=tmp_path)
    job = create(store,settings,token="same")
    duplicate, created = store.create("owner","same",str(uuid.uuid4()),{},settings)
    assert not created and duplicate["id"] == job["id"]
    with pytest.raises(KeyError):
        store.get(job["id"],"different-owner")
    store.claim()
    store.interrupted()
    assert store.get(job["id"])["error"]["code"] == "interrupted"


def test_review_preserves_ai_and_invalidates_changed_confirmation(tmp_path):
    store=Store(tmp_path)
    job=create(store,Settings(storage=tmp_path))
    ai={"seller_name":"STORE","seller_address":None,"transaction_datetime":"2020-01-01","total_amount":0}
    store.update(job["id"],state="succeeded",result=ai)
    updated=store.review(job["id"],"owner",ai,0,True)
    assert updated["review"]["confirmed"]
    with pytest.raises(Conflict):
        store.review(job["id"],"owner",ai,0,False)
    changed=store.review(job["id"],"owner",{**ai,"seller_name":"EDIT"},1,True)
    assert not changed["review"]["confirmed"]
    assert changed["result"] == ai


def test_cancel_pending_and_path_guard(tmp_path):
    store=Store(tmp_path)
    job=create(store,Settings(storage=tmp_path))
    store.cancel(job["id"],"owner")
    assert store.claim() is None
    with pytest.raises(ValueError):
        store.directory("../outside")


def test_normalize_exif_dimensions_and_pixel_limit(tmp_path):
    from PIL import Image
    path=tmp_path / "upload.bin"
    image=Image.new("RGB",(20,30))
    exif=image.getexif()
    exif[274]=6
    image.save(path,format="JPEG",exif=exif)
    normalized=normalize_upload(path,1000)
    assert (normalized["width"],normalized["height"]) == (30,20)
    assert normalized["exif_orientation"] == 6
    with pytest.raises(ValueError):
        normalize_upload(path,100)
    path.write_text("not an image")
    with pytest.raises(ValueError):
        normalize_upload(path,1000)


def test_settings_resident_requires_explicit_validation():
    with pytest.raises(ValueError,match="RESIDENT_VALIDATED"):
        Settings(gpu_policy="resident")
    assert Settings().gpu_policy == "exclusive"


def test_public_errors_are_actionable_without_exposing_tracebacks():
    from docucheck.web.coordinator import failure_details
    assert failure_details(RuntimeError("full_cuda_offload_not_verified"))["code"]=="full_cuda_offload_not_verified"
    assert failure_details(TimeoutError("private path"))["code"]=="timeout"
    assert "private path" not in failure_details(RuntimeError("private path"))["message"]
